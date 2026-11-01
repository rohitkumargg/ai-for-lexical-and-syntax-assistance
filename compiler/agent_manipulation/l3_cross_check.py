# compiler/agent_manipulation/l3_cross_check.py
"""Layer 3: Behavioural cross-check verifying candidate patches and model decisions against deterministic invariants."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from compiler.call_extractor import extract_call_sites
from compiler.security_checker import DANGEROUS_FUNCTIONS, UNSAFE_FUNCTIONS


@dataclass
class L3CrossCheckVerdict:
    is_valid: bool
    rejection_reason: Optional[str]
    contradiction_type: Optional[str]
    introduced_dangerous_calls: List[str] = field(default_factory=list)
    touched_protected_files: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "rejection_reason": self.rejection_reason,
            "contradiction_type": self.contradiction_type,
            "introduced_dangerous_calls": self.introduced_dangerous_calls,
            "touched_protected_files": self.touched_protected_files,
            "details": self.details,
        }


class L3BehaviouralCrossChecker:
    """
    Cross-checks candidate patches and model outputs against deterministic analyzers:
    1. Rejects if model/patch claims 'clean' or 'safe' when deterministic findings exist.
    2. Rejects if candidate adds dangerous or unsafe function calls (gets, strcpy, system, etc.).
    3. Rejects if candidate attempts to modify or reference protected repository files.
    """

    PROTECTED_FILES = {
        "app.py",
        "conftest.py",
        "requirements.txt",
        "pyproject.toml",
        ".env",
        "compiler",
        "tests",
        "gui",
    }

    DANGEROUS_CALL_NAMES = {
        "gets", "system", "popen", "exec", "execl", "execle", "execlp", "execv", "execvp", "execvpe",
        "fork", "strcpy", "strcat", "sprintf", "vsprintf",
    }

    @classmethod
    def cross_check_candidate(
        cls,
        original_code: str,
        candidate_code: str,
        filename: str = "main.c",
        language: str = "c",
        deterministic_findings: Optional[List[Any]] = None,
        claimed_clean: bool = False,
    ) -> L3CrossCheckVerdict:
        """Runs the behavioural cross-check against deterministic findings and dangerous calls."""
        if not candidate_code:
            return L3CrossCheckVerdict(
                is_valid=False,
                rejection_reason="Candidate code is empty.",
                contradiction_type="EMPTY_CANDIDATE",
            )

        # 1. Contradiction check: Claiming CLEAN while real actionable findings exist
        has_actionable_findings = False
        if deterministic_findings:
            has_actionable_findings = any(
                getattr(f, "category", "") not in ("INFO", "ADVISORY")
                for f in deterministic_findings
            )
        if claimed_clean and has_actionable_findings:
            return L3CrossCheckVerdict(
                is_valid=False,
                rejection_reason="Model claimed clean status, but deterministic analyzers confirmed active findings.",
                contradiction_type="CONTRADICTION_CLEAN_STATUS",
                details={"finding_count": len(deterministic_findings or [])},
            )

        # 2. Introduced dangerous calls check
        orig_calls = {c.fn_name for c in extract_call_sites(original_code)} if language == "c" else set()
        cand_calls = {c.fn_name for c in extract_call_sites(candidate_code)} if language == "c" else set()
        
        # In Python, check via regex
        if language == "python":
            orig_calls = set(re.findall(r"\b(eval|exec|os\.system|subprocess\.[a-zA-Z0-9_]+)\b", original_code))
            cand_calls = set(re.findall(r"\b(eval|exec|os\.system|subprocess\.[a-zA-Z0-9_]+)\b", candidate_code))

        new_dangerous = (cand_calls - orig_calls) & cls.DANGEROUS_CALL_NAMES
        if new_dangerous:
            return L3CrossCheckVerdict(
                is_valid=False,
                rejection_reason=f"Candidate patch introduced prohibited dangerous function call(s): {', '.join(sorted(new_dangerous))}.",
                contradiction_type="INTRODUCED_DANGEROUS_CALLS",
                introduced_dangerous_calls=list(sorted(new_dangerous)),
            )

        # 3. Protected files check: ensures candidate does not target core platform paths
        touched_protected = []
        for pf in cls.PROTECTED_FILES:
            if re.search(rf"\b{re.escape(pf)}\b", candidate_code):
                # Verify it wasn't already in original code
                if not re.search(rf"\b{re.escape(pf)}\b", original_code):
                    touched_protected.append(pf)

        if touched_protected:
            return L3CrossCheckVerdict(
                is_valid=False,
                rejection_reason=f"Candidate patch references protected internal system files: {', '.join(touched_protected)}.",
                contradiction_type="PROTECTED_FILE_TOUCHED",
                touched_protected_files=touched_protected,
            )

        return L3CrossCheckVerdict(
            is_valid=True,
            rejection_reason=None,
            contradiction_type=None,
        )
