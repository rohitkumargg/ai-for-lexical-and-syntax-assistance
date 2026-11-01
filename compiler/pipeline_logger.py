# compiler/pipeline_logger.py
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class PipelineEvent:
    event_id: str
    run_id: str
    stage_id: str
    stage_name: str
    status: str                         # PENDING, RUNNING, PASSED, FAILED, SKIPPED, UNAVAILABLE
    timestamp_iso: str
    timestamp_display: str              # HH:MM:SS.mmm
    duration_ms: float = 0.0
    description: str = ""
    findings_count: int = 0
    findings_summary: List[str] = field(default_factory=list)
    failure_reason: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "stage_id": self.stage_id,
            "stage_name": self.stage_name,
            "status": self.status,
            "timestamp_iso": self.timestamp_iso,
            "timestamp_display": self.timestamp_display,
            "duration_ms": round(self.duration_ms, 2),
            "description": self.description,
            "findings_count": self.findings_count,
            "findings_summary": list(self.findings_summary),
            "failure_reason": self.failure_reason,
            "diagnostics": dict(self.diagnostics),
        }


def _now_timestamps() -> tuple[str, str]:
    now = datetime.now()
    iso = now.isoformat()
    disp = now.strftime("%H:%M:%S.") + f"{int(now.microsecond / 1000):03d}"
    return iso, disp


STAGE_EXECUTION_ORDER: Dict[str, int] = {
    "security_gate": 0,
    "security_gate_approval": 0,
    "pre_execution_security_gate": 0,
    "malicious_precheck_stage": 0,
    "source_received": 1,
    "lexical_analysis": 2,
    "syntax_analysis": 3,
    "semantic_analysis": 4,
    "security_analysis": 5,
    "finding_consolidation": 6,
    "security_remediation_planning": 6,
    "deterministic_rules": 7,
    "codet5_model": 8,
    "qwen_ollama": 9,
    "candidate_generation": 10,
    "patch_validation": 11,
    "user_approval_apply": 12,
    "reanalysis_post_patch": 13,
    "quality_optimization_metrics": 14,
    "security_risk_scoring": 15,
    "green_metrics": 16,
}


class PipelineRunLogger:
    """
    Genuine structured pipeline run event logger.
    Associates all events with an immutable run_id, measures exact wall-clock durations,
    and produces honest diagnostics for each stage of the compiler & repair pipeline.
    """

    def __init__(self, run_id: Optional[str] = None):
        self.run_id: str = run_id or f"run_{uuid.uuid4().hex[:12]}"
        self.events: List[PipelineEvent] = []
        self._stage_starts: Dict[str, float] = {}
        self._created_at_iso, self._created_at_disp = _now_timestamps()

    @property
    def ordered_events(self) -> List[PipelineEvent]:
        """Returns events sorted in canonical 16-stage pipeline execution order."""
        return sorted(self.events, key=lambda ev: STAGE_EXECUTION_ORDER.get(ev.stage_id, 99))

    def record_stage(
        self,
        stage_id: str,
        stage_name: str,
        status: StageStatus | str,
        description: str,
        duration_ms: float = 0.0,
        findings_count: int = 0,
        findings_summary: Optional[List[str]] = None,
        failure_reason: Optional[str] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> PipelineEvent:
        """Record a completed, skipped, or failed stage event with genuine duration and diagnostics."""
        iso, disp = _now_timestamps()
        st_val = status.value if isinstance(status, StageStatus) else str(status).upper()
        
        # Update in-place if stage already exists (e.g. user approval PENDING -> PASSED)
        for ev in self.events:
            if ev.stage_id == stage_id:
                ev.stage_name = stage_name
                ev.status = st_val
                ev.timestamp_iso = iso
                ev.timestamp_display = disp
                ev.duration_ms = round(duration_ms, 2)
                ev.description = description
                ev.findings_count = findings_count
                ev.findings_summary = findings_summary or []
                ev.failure_reason = failure_reason
                ev.diagnostics = diagnostics or {}
                return ev

        event = PipelineEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            run_id=self.run_id,
            stage_id=stage_id,
            stage_name=stage_name,
            status=st_val,
            timestamp_iso=iso,
            timestamp_display=disp,
            duration_ms=round(duration_ms, 2),
            description=description,
            findings_count=findings_count,
            findings_summary=findings_summary or [],
            failure_reason=failure_reason,
            diagnostics=diagnostics or {},
        )
        self.events.append(event)
        return event

    def start_stage_timer(self, stage_id: str) -> None:
        self._stage_starts[stage_id] = time.perf_counter()

    def stop_stage_timer(self, stage_id: str) -> float:
        start_t = self._stage_starts.pop(stage_id, None)
        if start_t is None:
            return 0.0
        return (time.perf_counter() - start_t) * 1000.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at_iso": self._created_at_iso,
            "created_at_display": self._created_at_disp,
            "total_events": len(self.events),
            "events": [e.to_dict() for e in self.ordered_events],
        }


# Global registry of active/recent pipeline runs for query and post-application logging
_PIPELINE_RUNS_CACHE: Dict[str, PipelineRunLogger] = {}


def register_pipeline_run(logger: PipelineRunLogger) -> None:
    global _PIPELINE_RUNS_CACHE
    _PIPELINE_RUNS_CACHE[logger.run_id] = logger
    # Evict oldest if cache exceeds 100 runs
    if len(_PIPELINE_RUNS_CACHE) > 100:
        oldest_key = next(iter(_PIPELINE_RUNS_CACHE))
        _PIPELINE_RUNS_CACHE.pop(oldest_key, None)


def get_pipeline_run(run_id: str) -> Optional[PipelineRunLogger]:
    return _PIPELINE_RUNS_CACHE.get(run_id)
