# compiler/orchestrator.py
from __future__ import annotations

import time
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from compiler.finding import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    CorrectionSuggestion,
)
from compiler.agents import (
    BaseCompilerAgent,
    LexicalAgent,
    SyntaxAgent,
    SemanticAgent,
    SecurityAgent,
    PythonSyntaxAgent,
    PythonSemanticAgent,
    PythonSecurityAgent,
)
from compiler.languages import detect_language


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AttemptedRepair:
    finding_id: str
    rule_id: Optional[str]
    description: str
    applied_at: str
    validation_passed: bool
    errors_before: int
    errors_after: int
    patch_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DecisionState(str, Enum):
    GENERATED = "GENERATED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    VALIDATION_INCOMPLETE = "VALIDATION_INCOMPLETE"
    AWAITING_USER_DECISION = "AWAITING_USER_DECISION"
    USER_APPROVED = "USER_APPROVED"
    USER_REJECTED = "USER_REJECTED"
    APPLIED = "APPLIED"
    REVERTED = "REVERTED"
    UNRESOLVED = "UNRESOLVED"
    CANDIDATE_GENERATED = "CANDIDATE_GENERATED"
    VALIDATION_IN_PROGRESS = "VALIDATION_IN_PROGRESS"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class UserDecision:
    finding_id: str
    decision: str  # e.g. "PENDING" | "AWAITING_USER_DECISION" | "USER_APPROVED" | "USER_REJECTED"
    decided_at: str
    validation_status: str = "VALIDATION_PASSED"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrchestratorResult:
    original_source: str
    working_source: str
    findings: List[Finding]
    root_cause_findings: List[Finding]
    cascading_findings: List[Finding]
    confirmed_security_findings: List[Finding]
    possible_security_findings: List[Finding]
    attempted_repairs: List[AttemptedRepair]
    user_decisions: List[UserDecision]
    unresolved_findings: List[Finding]
    agent_telemetry: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_source": self.original_source,
            "working_source": self.working_source,
            "findings": [f.to_dict() for f in self.findings],
            "root_cause_findings": [f.to_dict() for f in self.root_cause_findings],
            "cascading_findings": [f.to_dict() for f in self.cascading_findings],
            "confirmed_security_findings": [f.to_dict() for f in self.confirmed_security_findings],
            "possible_security_findings": [f.to_dict() for f in self.possible_security_findings],
            "attempted_repairs": [r.to_dict() for r in self.attempted_repairs],
            "user_decisions": [d.to_dict() for d in self.user_decisions],
            "unresolved_findings": [f.to_dict() for f in self.unresolved_findings],
            "agent_telemetry": dict(self.agent_telemetry),
        }


class AgentOrchestrator:
    """
    Central coordinator managing specialized compiler agents, finding consolidation,
    root-cause identification, cascading-error suppression, and validation state.
    """

    def __init__(self, agents: Optional[List[BaseCompilerAgent]] = None):
        self.agents: List[BaseCompilerAgent] = agents or [
            LexicalAgent(),
            SyntaxAgent(),
            SemanticAgent(),
            SecurityAgent(),
        ]
        self.attempted_repairs: List[AttemptedRepair] = []
        self.user_decisions: Dict[str, UserDecision] = {}

    def run_analysis(
        self,
        source_text: str,
        filename: str = "main.c",
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
    ) -> OrchestratorResult:
        """
        Execute multi-agent analysis, isolate analyzer crashes, consolidate findings,
        identify root causes, and suppress cascading errors.
        """
        original_source = source_text
        working_source = source_text
        raw_findings: List[Finding] = []
        telemetry: Dict[str, Any] = {"phase_durations_ms": {}, "agent_status": {}}

        lang_id = detect_language(filename, language or (context.get("language") if context else None))
        if lang_id == "python":
            active_agents = [
                PythonSyntaxAgent(),
                PythonSemanticAgent(),
                PythonSecurityAgent(),
            ]
        else:
            active_agents = self.agents

        # 1. Early Malicious Code Precheck
        t0_pre = time.perf_counter()
        precheck_rep = None
        try:
            from compiler.malicious_precheck import MaliciousCodePrecheck
            precheck_rep = MaliciousCodePrecheck.analyze(working_source, filename=filename, language=lang_id)
            telemetry["agent_status"]["MaliciousCodePrecheck"] = "SUCCESS"
            telemetry["precheck_report"] = precheck_rep.to_dict()
            sev_map = {
                "LOW": FindingSeverity.LOW,
                "MEDIUM": FindingSeverity.WARNING,
                "HIGH": FindingSeverity.HIGH,
                "CRITICAL": FindingSeverity.CRITICAL,
            }
            for pf in precheck_rep.findings:
                raw_findings.append(
                    Finding.create(
                        category=FindingCategory.SECURITY,
                        line=pf.line,
                        col=pf.column,
                        explanation=pf.explanation,
                        severity=sev_map.get(pf.severity, FindingSeverity.HIGH),
                        confidence=pf.confidence,
                        status=FindingStatus.CONFIRMED if pf.is_malicious_intent else FindingStatus.POSSIBLE,
                        file_path=filename,
                        evidence=pf.evidence or pf.snippet,
                        metadata={
                            "precheck": True,
                            "rule_id": pf.rule_id,
                            "risk_level": pf.risk_level.value,
                            "blocks_execution": pf.blocks_execution,
                            "recommended_mitigation": pf.recommended_mitigation,
                            "snippet": pf.snippet,
                            "is_malicious_intent": pf.is_malicious_intent,
                        },
                    )
                )
        except Exception as e:
            telemetry["agent_status"]["MaliciousCodePrecheck"] = f"FAILED: {str(e)}"
        finally:
            telemetry["phase_durations_ms"]["MaliciousCodePrecheck"] = round((time.perf_counter() - t0_pre) * 1000.0, 2)

        # 2. Run agents sequentially with crash isolation
        for agent in active_agents:
            t0 = time.perf_counter()
            try:
                findings = agent.analyze(working_source, filename=filename, context=context)
                raw_findings.extend(findings)
                telemetry["agent_status"][agent.name] = "SUCCESS"
            except Exception as e:
                # Catch analyzer crash gracefully, create a diagnostic finding, and proceed
                telemetry["agent_status"][agent.name] = f"FAILED: {str(e)}"
                raw_findings.append(
                    Finding.create(
                        category=FindingCategory.SYSTEM,
                        line=1,
                        col=0,
                        explanation=f"Analyzer '{agent.name}' encountered an error: {str(e)}",
                        severity=FindingSeverity.WARNING,
                        confidence=0.5,
                        status=FindingStatus.POSSIBLE,
                        file_path=filename,
                        metadata={"agent": agent.name, "exception": str(e)},
                    )
                )
            finally:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                telemetry["phase_durations_ms"][agent.name] = round(elapsed_ms, 2)

        # 3. Identify Root Causes and Suppress Cascading Errors
        consolidated = self._suppress_and_prioritize(raw_findings)

        # 4. Categorize Security findings into Confirmed vs Possible
        confirmed_sec = [
            f for f in consolidated
            if f.category == FindingCategory.SECURITY and f.status == FindingStatus.CONFIRMED
        ]
        possible_sec = [
            f for f in consolidated
            if f.category == FindingCategory.SECURITY and f.status == FindingStatus.POSSIBLE
        ]

        # 5. Partition Root vs Cascading
        root_causes = [f for f in consolidated if f.is_root_cause]
        cascading = [f for f in consolidated if f.status == FindingStatus.SUPPRESSED_CASCADING]

        # 6. Determine unresolved findings
        unresolved = [
            f for f in consolidated
            if f.status not in (FindingStatus.RESOLVED, FindingStatus.SUPPRESSED_CASCADING)
        ]

        return OrchestratorResult(
            original_source=original_source,
            working_source=working_source,
            findings=consolidated,
            root_cause_findings=root_causes,
            cascading_findings=cascading,
            confirmed_security_findings=confirmed_sec,
            possible_security_findings=possible_sec,
            attempted_repairs=list(self.attempted_repairs),
            user_decisions=list(self.user_decisions.values()),
            unresolved_findings=unresolved,
            agent_telemetry=telemetry,
        )

    def _suppress_and_prioritize(self, findings: List[Finding]) -> List[Finding]:
        """
        Identify root-cause syntax/semantic errors and mark misleading follow-on
        parser noise or downstream variable references as cascading.
        """
        if not findings:
            return []

        # Sort findings primarily by source line & col
        sorted_findings = sorted(
            findings,
            key=lambda f: (f.location.line, f.location.col)
        )

        syntax_findings = [f for f in sorted_findings if f.category == FindingCategory.SYNTAX]
        has_syntax_errors = len(syntax_findings) > 0

        # Syntax cascading suppression:
        # The earliest syntax error is considered the primary root cause. Subsequent syntax
        # errors on adjacent or subsequent lines are frequently parser cascade artifacts.
        primary_syntax_root: Optional[Finding] = None
        if syntax_findings:
            primary_syntax_root = syntax_findings[0]
            primary_syntax_root.is_root_cause = True
            current_root = primary_syntax_root

            for sf in syntax_findings[1:]:
                # If on same or immediately adjacent line (+-1 line), it's a parser cascade artifact
                if abs(sf.location.line - current_root.location.line) <= 1:
                    sf.status = FindingStatus.SUPPRESSED_CASCADING
                    sf.cascades_from_id = current_root.id
                else:
                    sf.is_root_cause = True
                    current_root = sf

        # Semantic cascading suppression:
        # If there are syntax errors, semantic checks on the broken AST are largely cascades.
        # Furthermore, an undeclared variable suppresses downstream type errors on the same name.
        undeclared_names = set()
        for f in sorted_findings:
            if f.category == FindingCategory.SEMANTIC:
                kind = f.metadata.get("kind")
                name = f.metadata.get("name")
                if kind == "undeclared" and name:
                    undeclared_names.add(name)
                    f.is_root_cause = True
                elif has_syntax_errors:
                    # Suppress semantic noise if source doesn't parse
                    f.status = FindingStatus.SUPPRESSED_CASCADING
                    if primary_syntax_root:
                        f.cascades_from_id = primary_syntax_root.id
                elif name in undeclared_names:
                    # Downstream use of already-flagged undeclared variable
                    f.status = FindingStatus.SUPPRESSED_CASCADING
                    f.cascades_from_id = f"UNDECL-{name}"

        # Deduplication: merge duplicate findings on same line/category, preserving precheck enriched finding
        deduped_map = {}
        for f in sorted_findings:
            key_kw = ""
            for kw in ("gets", "strcpy", "strcat", "sprintf", "system", "popen", "scanf", "exec", "memcpy"):
                if kw in f.explanation.lower() or kw in str(f.evidence).lower():
                    key_kw = kw
                    break
            dedup_key = (f.location.line, f.category.value, key_kw or f.explanation[:30])
            if dedup_key in deduped_map:
                existing = deduped_map[dedup_key]
                if f.status == FindingStatus.CONFIRMED and existing.status != FindingStatus.CONFIRMED:
                    existing.status = FindingStatus.CONFIRMED
                    existing.confidence = max(existing.confidence, f.confidence)
                    existing.severity = f.severity
                if f.metadata.get("precheck"):
                    existing.metadata.update(f.metadata)
                continue
            deduped_map[dedup_key] = f
        sorted_findings = list(deduped_map.values())

        # Prioritization ordering:
        # 1. Lexical errors
        # 2. Root cause Syntax errors
        # 3. Confirmed Security vulnerabilities (CRITICAL / HIGH)
        # 4. Root cause Semantic errors
        # 5. Remaining non-cascading errors
        # 6. Possible Security warnings
        # 7. Cascading / Info
        def priority_score(f: Finding) -> int:
            if f.status == FindingStatus.SUPPRESSED_CASCADING:
                return 100
            if f.category == FindingCategory.LEXICAL:
                return 10
            if f.category == FindingCategory.SYNTAX and f.is_root_cause:
                return 20
            if f.category == FindingCategory.SECURITY and f.status == FindingStatus.CONFIRMED:
                return 30
            if f.category == FindingCategory.SEMANTIC and f.is_root_cause:
                return 40
            if f.status == FindingStatus.CONFIRMED:
                return 50
            if f.status == FindingStatus.POSSIBLE:
                return 60
            return 80

        sorted_findings.sort(key=priority_score)
        return sorted_findings

    def record_user_decision(
        self,
        finding_id: str,
        decision: str,
        notes: Optional[str] = None,
    ) -> UserDecision:
        """Track explicit user approval / rejection of proposed corrections."""
        rec = UserDecision(
            finding_id=finding_id,
            decision=decision.upper(),
            decided_at=_utc_now_iso(),
            notes=notes,
        )
        self.user_decisions[finding_id] = rec
        return rec

    def record_attempted_repair(
        self,
        finding_id: str,
        rule_id: Optional[str],
        description: str,
        validation_passed: bool,
        errors_before: int,
        errors_after: int,
        patch_snippet: Optional[str] = None,
    ) -> AttemptedRepair:
        """Track repair attempts and validation verification results."""
        attempt = AttemptedRepair(
            finding_id=finding_id,
            rule_id=rule_id,
            description=description,
            applied_at=_utc_now_iso(),
            validation_passed=validation_passed,
            errors_before=errors_before,
            errors_after=errors_after,
            patch_snippet=patch_snippet,
        )
        self.attempted_repairs.append(attempt)
        return attempt
