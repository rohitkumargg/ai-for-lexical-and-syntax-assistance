# compiler/agent_manipulation/enforcement.py
"""Enforcement mechanics for agent manipulation: masking, patch region validation, and immutable outputs."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class MaskedRegion:
    line_start: int
    line_end: int
    col_start: int
    col_end: int
    original_text: str
    channel_type: str


class ManipulationEnforcer:
    """
    Enforces runtime safety invariants for files containing flagged reviewer instructions:
    1. Masks flagged comments and string bodies with inert placeholders before passing to AI.
    2. Rejects any patch candidate that modifies, injects into, or touches masked regions.
    3. Guarantees that AI model output cannot alter deterministic findings, scores, or approvals.
    """

    INERT_COMMENT_PLACEHOLDER = "/* [REDACTED_REVIEWER_INSTRUCTION] */"
    INERT_STRING_PLACEHOLDER = '"[REDACTED_REVIEWER_STRING]"'
    INERT_PY_COMMENT_PLACEHOLDER = "# [REDACTED_REVIEWER_INSTRUCTION]"

    @classmethod
    def mask_source_for_ai(
        cls,
        source_code: str,
        flagged_channels: List[Any],
        language: str = "c"
    ) -> Tuple[str, List[MaskedRegion]]:
        """
        Masks flagged comment and string bodies with inert placeholders so AI models never receive
        the adversarial text.
        """
        if not source_code or not flagged_channels:
            return source_code, []

        lines = source_code.splitlines(keepends=True)
        masked_regions: List[MaskedRegion] = []
        is_python = (language.lower() == "python")

        # Sort flagged channels in reverse order by line_start to avoid coordinate shifting
        sorted_channels = sorted(
            flagged_channels,
            key=lambda c: (getattr(c, "line_start", 1), getattr(c, "col_start", 0)),
            reverse=True
        )

        modified_code = source_code

        for ch in sorted_channels:
            raw = getattr(ch, "raw_text", "")
            ch_type = str(getattr(ch, "channel_type", ""))
            l_start = getattr(ch, "line_start", 1)
            l_end = getattr(ch, "line_end", 1)

            if not raw:
                continue

            # Determine placeholder
            if "STRING" in ch_type:
                placeholder = cls.INERT_STRING_PLACEHOLDER
                target_str = f'"{raw}"' if f'"{raw}"' in modified_code else (f"'{raw}'" if f"'{raw}'" in modified_code else raw)
            elif is_python:
                placeholder = cls.INERT_PY_COMMENT_PLACEHOLDER
                target_str = f"#{raw}" if f"#{raw}" in modified_code else (f"# {raw}" if f"# {raw}" in modified_code else raw)
            else:
                placeholder = cls.INERT_COMMENT_PLACEHOLDER
                target_str = f"//{raw}" if f"//{raw}" in modified_code else (f"// {raw}" if f"// {raw}" in modified_code else raw)

            if target_str in modified_code:
                modified_code = modified_code.replace(target_str, placeholder, 1)
                masked_regions.append(MaskedRegion(
                    line_start=l_start,
                    line_end=l_end,
                    col_start=getattr(ch, "col_start", 0),
                    col_end=getattr(ch, "col_end", len(raw)),
                    original_text=raw,
                    channel_type=ch_type,
                ))

        return modified_code, masked_regions

    @classmethod
    def validate_patch_does_not_touch_masked_regions(
        cls,
        original_code: str,
        candidate_code: str,
        masked_regions: List[MaskedRegion],
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates that a candidate patch does NOT touch, resurrect, or modify masked regions.
        Returns: (is_valid, rejection_reason)
        """
        if not masked_regions:
            return True, None

        orig_lines = original_code.splitlines()
        cand_lines = candidate_code.splitlines()

        # Check line-level diffs
        matcher = difflib.SequenceMatcher(None, orig_lines, cand_lines)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ("replace", "insert", "delete"):
                # Diff affected original lines i1..i2 (0-indexed) -> lines i1+1..i2 (1-indexed)
                for mr in masked_regions:
                    # Check overlap with [mr.line_start, mr.line_end]
                    if not (i2 < mr.line_start - 1 or i1 > mr.line_end - 1):
                        # The patch modified or attempted to rewrite the masked region
                        # Check if it tried to resurrect the original adversarial text
                        if any(mr.original_text.lower() in cand_l.lower() for cand_l in cand_lines[j1:j2]):
                            return False, (
                                f"Candidate patch attempted to resurrect or modify masked reviewer instruction "
                                f"at lines {mr.line_start}-{mr.line_end}: '{mr.original_text[:60]}'."
                            )

        return True, None

    @classmethod
    def sanitize_model_output_against_overrides(
        cls,
        model_output_decision: Dict[str, Any],
        authoritative_findings: List[Any],
        authoritative_scores: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Enforces that model output cannot arbitrarily change findings, scores, or approvals.
        The findings and scores remain strictly determined by deterministic analyzers.
        """
        sanitized = dict(model_output_decision)
        # Authoritative findings cannot be overwritten by the model
        sanitized["findings"] = [f.to_dict() if hasattr(f, "to_dict") else f for f in authoritative_findings]
        sanitized["scores"] = dict(authoritative_scores)
        # Approval gate status cannot be forced by model text
        sanitized["approval_granted"] = False
        return sanitized

    def mask_for_ai(
        self,
        source_code: str,
        flagged_spans: List[Tuple[int, int]],
        language: str = "c"
    ) -> str:
        """Helper for char-span based masking."""
        res = source_code
        for start, end in sorted(flagged_spans, key=lambda x: x[0], reverse=True):
            placeholder = self.INERT_COMMENT_PLACEHOLDER if language.lower() != "python" else self.INERT_PY_COMMENT_PLACEHOLDER
            res = res[:start] + placeholder + res[end:]
        return res

    def validate_patch(
        self,
        original_code: str,
        candidate_code: str,
        flagged_spans: List[Tuple[int, int]]
    ) -> Tuple[bool, Optional[str]]:
        """Helper for char-span based patch validation."""
        for start, end in flagged_spans:
            target = original_code[start:end]
            if target and target in original_code and target not in candidate_code:
                return False, f"Candidate patch attempted to modify masked reviewer instruction: '{target[:60]}'."
        return True, None
