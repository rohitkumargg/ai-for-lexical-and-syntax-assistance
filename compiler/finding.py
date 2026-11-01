# compiler/finding.py
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class FindingCategory(str, Enum):
    LEXICAL = "LEXICAL"
    SYNTAX = "SYNTAX"
    SEMANTIC = "SEMANTIC"
    SECURITY = "SECURITY"
    SYSTEM = "SYSTEM"


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    WARNING = "WARNING"
    LOW = "LOW"
    INFO = "INFO"


class FindingStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    POSSIBLE = "POSSIBLE"
    SUPPRESSED_CASCADING = "SUPPRESSED_CASCADING"
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class SourceLocation:
    line: int
    col: int
    file_path: Optional[str] = None
    end_line: Optional[int] = None
    end_col: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line": self.line,
            "col": self.col,
            "end_line": self.end_line,
            "end_col": self.end_col,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SourceLocation:
        return cls(
            line=int(data.get("line", 1)),
            col=int(data.get("col", 0)),
            file_path=data.get("file_path"),
            end_line=data.get("end_line"),
            end_col=data.get("end_col"),
        )


@dataclass
class CorrectionSuggestion:
    description: str
    replacement_text: Optional[str] = None
    confidence: float = 1.0
    is_deterministic: bool = True
    start_line: Optional[int] = None
    start_col: Optional[int] = None
    end_line: Optional[int] = None
    end_col: Optional[int] = None
    rule_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CorrectionSuggestion:
        return cls(**data)


def compute_stable_finding_id(
    category: str,
    line: int,
    col: int,
    message: str,
    file_path: Optional[str] = None,
) -> str:
    """Generate a deterministic, reproducible hash identity for a finding."""
    norm_msg = " ".join((message or "").strip().lower().split())
    raw = f"{category}:{file_path or ''}:{line}:{col}:{norm_msg}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"FND-{category[:3].upper()}-{line}:{col}-{digest}"


@dataclass
class Finding:
    id: str
    category: FindingCategory
    location: SourceLocation
    evidence: str
    explanation: str
    severity: FindingSeverity = FindingSeverity.WARNING
    confidence: float = 1.0
    status: FindingStatus = FindingStatus.CONFIRMED
    suggested_corrections: List[CorrectionSuggestion] = field(default_factory=list)
    is_root_cause: bool = False
    cascades_from_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        category: FindingCategory,
        line: int,
        col: int,
        explanation: str,
        evidence: str = "",
        severity: FindingSeverity = FindingSeverity.WARNING,
        confidence: float = 1.0,
        status: FindingStatus = FindingStatus.CONFIRMED,
        file_path: Optional[str] = None,
        suggested_corrections: Optional[List[CorrectionSuggestion]] = None,
        is_root_cause: bool = False,
        cascades_from_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        custom_id: Optional[str] = None,
    ) -> Finding:
        finding_id = custom_id or compute_stable_finding_id(
            category=category.value,
            line=line,
            col=col,
            message=explanation,
            file_path=file_path,
        )
        return cls(
            id=finding_id,
            category=category,
            location=SourceLocation(line=line, col=col, file_path=file_path),
            evidence=evidence,
            explanation=explanation,
            severity=severity,
            confidence=max(0.0, min(1.0, float(confidence))),
            status=status,
            suggested_corrections=suggested_corrections or [],
            is_root_cause=is_root_cause,
            cascades_from_id=cascades_from_id,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.metadata.get("rule_id", ""),
            "category": self.category.value,
            "location": self.location.to_dict(),
            "line": self.location.line,
            "column": self.location.col,
            "evidence": self.evidence,
            "explanation": self.explanation,
            "severity": self.severity.value,
            "confidence": round(self.confidence, 3),
            "status": self.status.value,
            "suggested_corrections": [c.to_dict() for c in self.suggested_corrections],
            "is_root_cause": self.is_root_cause,
            "cascades_from_id": self.cascades_from_id,
            "metadata": dict(self.metadata),
        }
