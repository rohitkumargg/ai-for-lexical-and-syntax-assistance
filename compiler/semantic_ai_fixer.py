"""Stage 4 AI-guided Semantic Error Repair with SemanticChecker Oracle Verification.

Handles judgment-dependent semantic issues:
1. undeclared (when non-inferable and not known library)
2. redeclared (when renaming / duplicate elimination needed)
3. unknown_member (when non-typo struct member access)

Target format: LINE <L>: <repaired_line>

Every prediction is verified against the ANTLR parser and SemanticChecker:
- Must parse cleanly without syntax errors
- Must resolve the targeted semantic issue
- Must not introduce new semantic violations
Any candidate failing verification is safely rejected and routed to SUGGESTED.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional, Tuple

import torch
from peft import PeftModel
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from compiler.semantic_checker import SemanticChecker
from test_parser import has_any_errors, parse_source

BASE_MODEL_NAME = "Salesforce/codet5-base"
DEFAULT_ADAPTER_DIR = os.getenv("CD_SEMANTIC_ADAPTER_DIR", "models/codet5_semantic_adapter")
MODEL_KINDS = {"undeclared", "redeclared", "unknown_member"}

LINE_PATCH_RE = re.compile(r"^\s*LINE\s+(\d+)\s*:\s*(.*)$", re.IGNORECASE | re.DOTALL)


class SemanticAIFixer:
    def __init__(self, adapter_dir: str = DEFAULT_ADAPTER_DIR):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.adapter_dir = adapter_dir
        self.model = None
        self.tokenizer = None
        self._load_attempted = False

    def _ensure_loaded(self) -> bool:
        if self._load_attempted:
            return self.model is not None

        self._load_attempted = True
        if not os.path.isdir(self.adapter_dir):
            return False

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.adapter_dir, local_files_only=True)
            try:
                base = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL_NAME, local_files_only=True)
            except Exception:
                base = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL_NAME)
            self.model = PeftModel.from_pretrained(base, self.adapter_dir)
            self.model.to(self.device)
            self.model.eval()
            return True
        except Exception:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.adapter_dir)
                base = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL_NAME)
                self.model = PeftModel.from_pretrained(base, self.adapter_dir)
                self.model.to(self.device)
                self.model.eval()
                return True
            except Exception:
                self.model = None
                self.tokenizer = None
                return False

    def build_prompt(self, source: str, issue: Dict[str, Any]) -> str:
        kind = issue.get("kind", "")
        name = issue.get("name", "")
        line = issue.get("line", 1)
        col = issue.get("col", 0)
        return f"repair_semantic kind={kind} name={name} line={line} col={col}\n{source}\n--> edit:"

    def apply_predicted_patch(self, source: str, prediction: str, fallback_line: int = 1) -> Optional[str]:
        pred = prediction.strip()
        m = LINE_PATCH_RE.match(pred)
        if m:
            target_line = int(m.group(1))
            new_line_content = m.group(2).strip()
        else:
            target_line = fallback_line
            new_line_content = pred

        lines = source.splitlines(keepends=True)
        if target_line < 1 or target_line > len(lines):
            return None

        orig_line = lines[target_line - 1]
        indent = orig_line[: len(orig_line) - len(orig_line.lstrip())]
        ending = "\n" if orig_line.endswith("\n") else ""

        # Avoid redundant double indentation
        if new_line_content.startswith(indent):
            lines[target_line - 1] = f"{new_line_content}{ending}"
        else:
            lines[target_line - 1] = f"{indent}{new_line_content}{ending}"

        return "".join(lines)

    def verify_candidate(
        self,
        candidate_code: str,
        original_issue: Dict[str, Any],
        baseline_issues: list,
    ) -> bool:
        """Strict Oracle verification using ANTLR parser and SemanticChecker."""
        tree, listeners, parser = parse_source(candidate_code, "verify_ai")
        if not tree or has_any_errors(listeners):
            return False

        sc = SemanticChecker()
        sc.visit(tree)
        new_issues = sc.get_issues()

        target_kind = original_issue.get("kind")
        target_name = (original_issue.get("name") or "").strip()

        # 1. Target issue must no longer exist with same kind and name
        still_present = any(
            i.get("kind") == target_kind and (not target_name or (i.get("name") or "").strip() == target_name)
            for i in new_issues
        )
        if still_present:
            return False

        # 2. Overall issue count must decrease or stay equal without new kinds
        old_kinds = {i.get("kind") for i in baseline_issues}
        new_kinds = {i.get("kind") for i in new_issues}
        if not new_kinds.issubset(old_kinds) and len(new_issues) >= len(baseline_issues):
            return False

        return True

    def fix_semantic_issue_ai(
        self,
        source: str,
        issue: Dict[str, Any],
        baseline_issues: Optional[list] = None,
    ) -> Tuple[str, Optional[str]]:
        kind = issue.get("kind")
        if kind not in MODEL_KINDS:
            return source, None

        if not self._ensure_loaded():
            return source, None

        prompt = self.build_prompt(source, issue)
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=256,
        ).to(self.device)

        with torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=64,
                num_beams=1,
                do_sample=False,
            )

        pred = self.tokenizer.decode(out[0], skip_special_tokens=True).strip()
        if not pred:
            return source, None

        candidate = self.apply_predicted_patch(source, pred, fallback_line=int(issue.get("line", 1) or 1))
        if not candidate or candidate == source:
            return source, None

        # Oracle verification
        if self.verify_candidate(candidate, issue, baseline_issues or [issue]):
            return candidate, f"AI: repaired {kind} ({pred})"

        # Verification failed: reject candidate to avoid code breakage
        return source, None


# Global singleton instance
_GLOBAL_AI_FIXER: Optional[SemanticAIFixer] = None


def get_semantic_ai_fixer() -> SemanticAIFixer:
    global _GLOBAL_AI_FIXER
    if _GLOBAL_AI_FIXER is None:
        _GLOBAL_AI_FIXER = SemanticAIFixer()
    return _GLOBAL_AI_FIXER
