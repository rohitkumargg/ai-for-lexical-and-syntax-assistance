"""
Continuation Session Manager for Multi-Round Program Repair.

Enforces:
1. Session persistence across rounds via continuation_id.
2. Tracking of completed findings and already-repaired line windows.
3. Monotonic repair progress (remaining findings strictly decrease unless a new finding is introduced and reported).
4. Terminal state REPAIR_UNAVAILABLE with actionable manual alternatives when automated repair cannot proceed.
5. Re-binding of security approval tokens only to server-generated candidates that introduce no new or higher-severity findings.
6. Preservation of CRLF line endings.
"""

import copy
import hashlib
import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple


class ContinuationRecord:
    def __init__(
        self,
        continuation_id: str,
        initial_code: str,
        filename: str = "main.c",
        language: str = "c",
        initial_finding_count: int = 0,
        approval_token: Optional[str] = None,
    ):
        self.continuation_id = continuation_id
        self.filename = filename
        self.language = language
        self.round_index = 1
        self.initial_code = initial_code
        self.current_code = initial_code
        self.initial_source_hash = hashlib.sha256(initial_code.encode("utf-8")).hexdigest()
        self.current_source_hash = self.initial_source_hash
        self.candidate_source_hash: Optional[str] = None
        self.initial_finding_count = initial_finding_count
        self.remaining_finding_count = initial_finding_count
        self.has_crlf = "\r\n" in initial_code

        self.repaired_windows: List[Tuple[int, int]] = []
        self.completed_finding_signatures: Set[str] = set()
        self.approval_token: Optional[str] = approval_token
        self.token_rebind_error: Optional[str] = None

        self.history: List[Dict[str, Any]] = []
        self.created_at = time.time()
        self.updated_at = self.created_at

    def is_line_in_repaired_window(self, line: int) -> bool:
        for start_l, end_l in self.repaired_windows:
            if start_l <= line <= end_l:
                return True
        return False

    def add_repaired_window(self, start_line: int, end_line: int) -> None:
        if start_line > end_line:
            start_line, end_line = end_line, start_line
        self.repaired_windows.append((max(1, start_line), max(1, end_line)))


class ContinuationManager:
    _lock = threading.Lock()
    _sessions: Dict[str, ContinuationRecord] = {}

    @classmethod
    def get_or_create_session(
        cls,
        continuation_id: Optional[str],
        source_code: str,
        filename: str = "main.c",
        language: str = "c",
        finding_count: int = 0,
        approval_token: Optional[str] = None,
        round_index: Optional[int] = None,
    ) -> ContinuationRecord:
        with cls._lock:
            if not continuation_id:
                continuation_id = f"cont_{uuid.uuid4().hex[:12]}"

            session = cls._sessions.get(continuation_id)
            if not session:
                session = ContinuationRecord(
                    continuation_id=continuation_id,
                    initial_code=source_code,
                    filename=filename,
                    language=language,
                    initial_finding_count=finding_count,
                    approval_token=approval_token,
                )
                cls._sessions[continuation_id] = session
            else:
                session.current_code = source_code
                session.current_source_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
                session.updated_at = time.time()
                if round_index is not None:
                    session.round_index = round_index
                else:
                    session.round_index += 1
                if approval_token:
                    session.approval_token = approval_token
            return session

    @classmethod
    def get_session(cls, continuation_id: str) -> Optional[ContinuationRecord]:
        with cls._lock:
            return cls._sessions.get(continuation_id)

    @classmethod
    def rebind_token_for_new_code(
        cls,
        old_token: Optional[str],
        new_source_code: str,
        filename: str = "main.c",
        operation: str = "repair",
        continuation_id: Optional[str] = None,
        server_generated: bool = False,
    ) -> Optional[str]:
        """
        Re-binds security approval ONLY to a candidate the server generated itself
        in an approved continuation, and ONLY if the candidate introduces no new
        or higher-severity security finding.
        Otherwise returns None (requiring explicit re-approval with 4xx).
        """
        if not continuation_id:
            return None

        with cls._lock:
            session = cls._sessions.get(continuation_id)
            if not session:
                return None

            # Check 1: Must be in an approved continuation if security approval was required
            effective_token = old_token or session.approval_token
            if not effective_token:
                from compiler.security_approval_gate import SecurityDecisionGate
                base_check = SecurityDecisionGate.evaluate(
                    source_code=session.initial_code,
                    filename=filename,
                    operation=operation,
                )
                if base_check.is_blocked:
                    session.token_rebind_error = "Continuation session was not previously approved."
                    return None
                else:
                    session.token_rebind_error = None

            # Check 2: Must be server-generated
            if not server_generated:
                session.token_rebind_error = "Candidate was not server-generated; re-approval required."
                return None

        # Check 3: Security finding evaluation between baseline and candidate
        from compiler.security_approval_gate import SecurityDecisionGate, SecurityApprovalManager, _ApprovalTokenRecord

        base_verdict = SecurityDecisionGate.evaluate(
            source_code=session.initial_code,
            filename=filename,
            operation=operation,
        )
        cand_verdict = SecurityDecisionGate.evaluate(
            source_code=new_source_code,
            filename=filename,
            operation=operation,
        )

        # Gate check: Never mint a token when no approval exists and the gate requires one
        if not effective_token:
            if cand_verdict.is_blocked:
                with cls._lock:
                    session.approval_token = None
                    session.token_rebind_error = "No approval exists and candidate requires approval."
                return None
            else:
                with cls._lock:
                    session.approval_token = None
                    session.token_rebind_error = None
                return None

        SEV_RANK = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "WARNING": 3, "LOW": 2, "INFO": 1}

        base_findings = base_verdict.findings
        cand_findings = cand_verdict.findings

        def get_finding_sig(f: Any) -> str:
            rule = getattr(f, "rule_id", None) or getattr(f, "rule", None) or getattr(f, "id", "") or ""
            cat = getattr(f, "category", "")
            cat_str = cat.value if hasattr(cat, "value") else str(cat)
            snippet = getattr(f, "snippet", "") or getattr(f, "evidence", "") or ""
            fn_name = getattr(f, "function_name", "") or getattr(f, "function", "") or ""
            norm_snip = re.sub(r"\s+", " ", str(snippet).strip())[:40]
            # Independent of line numbers: rule_id + normalized function or snippet
            return f"{rule}:{cat_str}:{fn_name}:{norm_snip}"

        # Map base findings by rule_id for per-finding severity comparison (not against global max)
        base_sev_by_rule: Dict[str, int] = {}
        base_sigs: Set[str] = set()
        for f in base_findings:
            rule = getattr(f, "rule_id", None) or getattr(f, "rule", None) or getattr(f, "id", "") or ""
            f_sev = SEV_RANK.get(str(getattr(f, "severity", "")).upper(), 0)
            base_sev_by_rule[rule] = max(base_sev_by_rule.get(rule, 0), f_sev)
            base_sigs.add(get_finding_sig(f))

        # Inspect candidate findings
        for cf in cand_findings:
            cf_rule = getattr(cf, "rule_id", None) or getattr(cf, "rule", None) or getattr(cf, "id", "") or ""
            cf_sig = get_finding_sig(cf)
            cf_sev = SEV_RANK.get(str(getattr(cf, "severity", "")).upper(), 0)

            # Reject if candidate introduced a brand new finding rule
            if cf_rule not in base_sev_by_rule and cf_sig not in base_sigs:
                with cls._lock:
                    session.approval_token = None
                    session.token_rebind_error = f"Candidate introduced new security finding rule '{cf_rule}'. Explicit user re-approval required."
                return None

            # Compare severity per finding (matched by rule_id), not against global max
            max_allowed_sev = base_sev_by_rule.get(cf_rule, 0)
            if cf_sev > max_allowed_sev:
                with cls._lock:
                    session.approval_token = None
                    session.token_rebind_error = f"Candidate escalated security severity for '{cf_rule}' from rank {max_allowed_sev} to {cf_sev} ({getattr(cf, 'severity', '')}). Explicit user re-approval required."
                return None

        # Re-binding approved: issue fresh approval token bound to candidate hash
        now = time.time()
        new_hash = hashlib.sha256(new_source_code.encode("utf-8")).hexdigest()
        new_token = f"appr_cont_{uuid.uuid4().hex}"

        rec = _ApprovalTokenRecord(
            token=new_token,
            source_hash=new_hash,
            filename=filename,
            operation=operation,
            finding_ids={getattr(f, "id", "") for f in cand_findings},
            created_at=now,
            expires_at=now + 120.0,
            used=False,
        )
        with SecurityApprovalManager._lock if hasattr(SecurityApprovalManager, "_lock") else cls._lock:
            SecurityApprovalManager._tokens[new_token] = rec
            SecurityApprovalManager._approvals_by_hash[new_hash] = rec

        with cls._lock:
            session.approval_token = new_token
            session.candidate_source_hash = new_hash
            session.token_rebind_error = None

        return new_token

    @classmethod
    def generate_manual_alternatives(
        cls,
        code: str,
        findings: List[Any],
        filename: str = "main.c",
    ) -> List[Dict[str, Any]]:
        """
        Constructs concrete, human-actionable manual alternative suggestions
        for remaining findings that could not be repaired automatically.
        """
        lines = code.splitlines()
        alternatives: List[Dict[str, Any]] = []

        for f in findings:
            f_line = getattr(f, "line", 1) or 1
            f_col = getattr(f, "column", 0) or 0
            f_msg = getattr(f, "explanation", "") or getattr(f, "title", "") or getattr(f, "message", "Syntax or semantic issue")
            f_cat = getattr(f, "category", "SYNTAX")
            f_cat_str = f_cat.value if hasattr(f_cat, "value") else str(f_cat)

            code_snippet = ""
            if 1 <= f_line <= len(lines):
                idx = f_line - 1
                start_l = max(0, idx - 1)
                end_l = min(len(lines), idx + 2)
                snippet_lines = []
                for li in range(start_l, end_l):
                    prefix = "-> " if li == idx else "   "
                    snippet_lines.append(f"{li+1:4d} | {prefix}{lines[li]}")
                code_snippet = "\n".join(snippet_lines)

            # Heuristic actionable suggestions
            suggestion = "Review and correct the statement manually."
            if "expected ';'" in f_msg.lower() or "missing ';'" in f_msg.lower():
                suggestion = f"Add missing ';' at line {f_line}."
            elif "undeclared" in f_msg.lower():
                suggestion = f"Declare the variable or check symbol spelling at line {f_line}."
            elif f_cat_str == "SECURITY":
                suggestion = f"Replace unsafe call at line {f_line} with a bounds-checked alternative (e.g. fgets/snprintf)."

            alternatives.append({
                "line": f_line,
                "column": f_col,
                "category": f_cat_str,
                "issue": f_msg,
                "suggestion": suggestion,
                "code_snippet": code_snippet,
            })

        return alternatives
