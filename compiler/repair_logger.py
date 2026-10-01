# compiler/repair_logger.py
from __future__ import annotations

import json
import os
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
    Very lightweight JSONL logger.
    Each run produces a sequence of events for the same case_id.

    Output: logs/repair_log.jsonl
    """

    def __init__(self, log_path: str = "logs/repair_log.jsonl"):
        self.log_path = log_path
        self.case_id: Optional[str] = None
        self._enabled = True

        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def enable(self, enabled: bool) -> None:
        self._enabled = enabled

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
        print(p_info)
        if p_warn:
            print(p_warn)
        case_meta = dict(meta or {})
        case_meta["parser_check"] = p_info
        if p_warn:
            case_meta["parser_warning"] = p_warn
        payload = {
            "case_id": case_id,
            "filename": filename,
            "original_source": original_source,
            "meta": case_meta,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="case_start", data=payload))

    def log_lex_step(self, step: str, source_after: str) -> None:
        if not self.case_id:
            return
        payload = {
            "case_id": self.case_id,
            "kind": "LEX",
            "step": step,
            "source_after": source_after,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="repair_step", data=payload))

    def log_rule_step(self, step: str, source_after: str) -> None:
        if not self.case_id:
            return
        payload = {
            "case_id": self.case_id,
            "kind": "RULE",
            "step": step,
            "source_after": source_after,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="repair_step", data=payload))

    def log_sem_step(self, step: str, source_after: str) -> None:
        if not self.case_id:
            return
        payload = {
            "case_id": self.case_id,
            "kind": "SEM",
            "step": step,
            "source_after": source_after,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="repair_step", data=payload))

    def log_ai_step(self, cmd: str, source_after: str) -> None:
        if not self.case_id:
            return
        payload = {
            "case_id": self.case_id,
            "kind": "AI",
            "cmd": cmd,
            "source_after": source_after,
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
            "status": status,  # SUCCESS / UNFIXABLE / SEM_ISSUES / STOPPED
            "final_source": final_source,
            "applied_steps": applied_steps,
            "note": note,
        }
        self._write(RepairLogEvent(ts_utc=_utc_now_iso(), event="case_end", data=payload))
        self.case_id = None