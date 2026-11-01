# compiler/repair_logger.py
from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RepairLogEvent:
    ts_utc: str
    event: str
    data: Dict[str, Any]


class RepairLogger:
    """
    Structured JSONL logger for analysis stages, model selection, repair attempts,
    validation results, and resource metrics.

    Security/Privacy Policy:
    Source code is sanitized by default (SHA-256 fingerprint, line count, byte length)
    to avoid unnecessarily storing sensitive/proprietary code in persistent log files.

    Output: logs/repair_log.jsonl
    """

    def __init__(self, log_path: str = "logs/repair_log.jsonl", store_sensitive_source: bool = False):
        self.log_path = log_path
        self.case_id: Optional[str] = None
        self._enabled = True
        self.store_sensitive_source = store_sensitive_source

        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def enable(self, enabled: bool) -> None:
        self._enabled = enabled

    def _sanitize_source(self, code: Optional[str]) -> Dict[str, Any]:
        """Redact source code to a cryptographic fingerprint and structural metrics."""
        if code is None:
            return {"source_hash": None, "lines": 0, "bytes": 0}
        
        info = {
            "source_hash": hashlib.sha256(code.encode("utf-8")).hexdigest()[:16],
            "lines": len(code.splitlines()),
            "bytes": len(code.encode("utf-8")),
        }
        if self.store_sensitive_source:
            info["source_raw"] = code
        return info

    def _write(self, event: RepairLogEvent) -> None:
        if not self._enabled:
            return
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    def start_case(
        self,
        case_id: str,
        filename: str,
        original_source: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.case_id = case_id
        from compiler.week5_repair_helpers import check_parser_status
        is_fresh, p_info, p_warn = check_parser_status()
        case_meta = dict(meta or {})
        case_meta["parser_check"] = p_info
        if p_warn:
            case_meta["parser_warning"] = p_warn

        payload = {
            "case_id": case_id,
            "filename": filename,
            "source_metrics": self._sanitize_source(original_source),
            "meta": case_meta,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="case_start", data=payload))

    def log_analysis_stage(
        self,
        stage: str,
        findings_count: int,
        duration_ms: float = 0.0,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Structured log for compiler analysis stages (lexical, syntax, semantic, security)."""
        payload = {
            "case_id": self.case_id,
            "stage": stage,
            "findings_count": findings_count,
            "duration_ms": round(duration_ms, 2),
            "meta": meta or {},
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="analysis_stage", data=payload))

    def log_model_selection(
        self,
        tier: str,
        model_name: str,
        reason: str,
        is_available: bool,
    ) -> None:
        """Structured log for escalation ladder decision."""
        payload = {
            "case_id": self.case_id,
            "tier": tier,
            "model_name": model_name,
            "selection_reason": reason,
            "is_available": is_available,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="model_selection", data=payload))

    def log_repair_attempt(
        self,
        tier: str,
        candidate_id: str,
        description: str,
        validation_passed: bool,
        errors_before: int = 0,
        errors_after: int = 0,
        duration_ms: float = 0.0,
    ) -> None:
        """Structured log for a candidate patch generation attempt."""
        payload = {
            "case_id": self.case_id,
            "tier": tier,
            "candidate_id": candidate_id,
            "description": description,
            "validation_passed": validation_passed,
            "errors_before": errors_before,
            "errors_after": errors_after,
            "duration_ms": round(duration_ms, 2),
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="repair_attempt", data=payload))

    def log_validation_result(
        self,
        candidate_id: str,
        passed: bool,
        stage_results: Optional[Dict[str, Any]] = None,
        feedback: Optional[str] = None,
    ) -> None:
        """Structured log for independent patch validation."""
        payload = {
            "case_id": self.case_id,
            "candidate_id": candidate_id,
            "passed": passed,
            "stage_results": stage_results or {},
            "feedback": feedback,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="validation_result", data=payload))

    def log_model_error(
        self,
        model_name: str,
        error_type: str,
        message: str,
        fallback_action: str = "FALLBACK_TO_DETERMINISTIC",
    ) -> None:
        """Structured log for model timeouts, missing weights, or memory exhaustion."""
        payload = {
            "case_id": self.case_id,
            "model_name": model_name,
            "error_type": error_type,
            "message": message,
            "fallback_action": fallback_action,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="model_error", data=payload))

    def log_metrics(self, metrics: Dict[str, Any]) -> None:
        """Structured log for computational and green resource measurements."""
        payload = {
            "case_id": self.case_id,
            "metrics": metrics,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="metrics", data=payload))

    def log_lex_step(self, step: str, source_after: str) -> None:
        if not self.case_id:
            return
        payload = {
            "case_id": self.case_id,
            "kind": "LEX",
            "step": step,
            "source_metrics": self._sanitize_source(source_after),
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="repair_step", data=payload))

    def log_rule_step(self, step: str, source_after: str) -> None:
        if not self.case_id:
            return
        payload = {
            "case_id": self.case_id,
            "kind": "RULE",
            "step": step,
            "source_metrics": self._sanitize_source(source_after),
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="repair_step", data=payload))

    def log_sem_step(self, step: str, source_after: str) -> None:
        if not self.case_id:
            return
        payload = {
            "case_id": self.case_id,
            "kind": "SEM",
            "step": step,
            "source_metrics": self._sanitize_source(source_after),
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="repair_step", data=payload))

    def log_ai_step(self, cmd: str, source_after: str) -> None:
        if not self.case_id:
            return
        payload = {
            "case_id": self.case_id,
            "kind": "AI",
            "cmd": cmd,
            "source_metrics": self._sanitize_source(source_after),
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="repair_step", data=payload))

    def log_parse_errors(self, stage: str, errors: List[str]) -> None:
        if not self.case_id:
            return
        payload = {
            "case_id": self.case_id,
            "stage": stage,
            "errors": errors,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="parse_errors", data=payload))

    def log_semantic_issues(self, issues: List[Dict[str, Any]]) -> None:
        if not self.case_id:
            return
        payload = {
            "case_id": self.case_id,
            "issues": issues,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="semantic_issues", data=payload))

    def end_case(
        self,
        status: str,
        final_source: str,
        applied_steps: List[str],
        note: str = "",
    ) -> None:
        if not self.case_id:
            return
        payload = {
            "case_id": self.case_id,
            "status": status,
            "final_source_metrics": self._sanitize_source(final_source),
            "applied_steps": applied_steps,
            "note": note,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="case_end", data=payload))
        self.case_id = None