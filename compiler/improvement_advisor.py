# compiler/improvement_advisor.py
"""
Post-Repair Improvement Advisor for Antigravity Compiler Assistant.

Features:
1. Performs comprehensive second analysis on repaired/clean source code:
   - Lexical & Syntax status
   - Semantic checks
   - Security findings (via SecurityReporter & SecurityRiskScorer)
   - Code Quality Score (via CodeQualityScorer)
   - Optimization Potential (via OptimizationPotentialAnalyzer)
   - Green Metrics
2. Generates actionable, evidence-backed improvement candidates with reviewable diffs:
   - Categorized by strategy:
     * Conservative minimal
     * Maintainability
     * Performance optimization
     * Security hardening
   - Accompanied by:
     * Stable ID
     * Precise location & evidence
     * Assumptions & behavior trade-offs
     * Expected effect vs measured score comparison
     * Independent patch validation results
     * Strict user decision tracking (PENDING / AWAITING_USER_DECISION)
3. No external AI cloud inference; operates 100% locally.
4. Rice's Theorem honesty: Does not claim guaranteed global optimality.
"""
from __future__ import annotations

import difflib
import hashlib
import re
import time
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from compiler.orchestrator import DecisionState
from compiler.code_quality import CodeQualityScorer, CodeQualityReport
from compiler.optimization_potential import (
    OptimizationPotentialAnalyzer,
    OptimizationPotentialReport,
    OpportunityCategory,
)
from compiler.security_reporter import SecurityReporter, ComprehensiveSecurityReport
from compiler.security_risk import SecurityRiskScorer, SecurityRiskReport
from compiler.patch_validator import PatchValidator, PatchValidationReport


class ImprovementStrategy(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    MAINTAINABILITY = "MAINTAINABILITY"
    PERFORMANCE = "PERFORMANCE"
    SECURITY_HARDENING = "SECURITY_HARDENING"


@dataclass
class ImprovementCandidate:
    id: str
    strategy: ImprovementStrategy
    category: str
    priority: str  # "HIGH", "MEDIUM", "LOW"
    title: str
    explanation: str
    line: int
    col: int
    evidence: str
    original_code: str
    original_source_hash: str
    proposed_code: str
    proposed_source_hash: str
    filename: str
    unified_diff: str
    expected_effect: str
    assumptions: List[str]
    trade_offs: str
    relevant_metric: str
    predicted_metric_delta: str
    confidence: float
    validation_passed: bool
    validation_state: str  # "VALIDATED", "VALIDATION_FAILED", "VALIDATION_INCOMPLETE"
    is_eligible_for_application: bool
    validation_report: Dict[str, Any]
    user_decision_state: str  # "AWAITING_USER_DECISION", "USER_APPROVED", "USER_REJECTED", "APPLIED", "VALIDATION_FAILED"
    before_scores: Dict[str, Any] = field(default_factory=dict)
    after_scores: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    applied_at: Optional[float] = None
    run_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "strategy": self.strategy.value,
            "category": self.category,
            "priority": self.priority,
            "title": self.title,
            "explanation": self.explanation,
            "line": self.line,
            "col": self.col,
            "evidence": self.evidence,
            "original_code": self.original_code,
            "original_source_hash": self.original_source_hash,
            "proposed_code": self.proposed_code,
            "proposed_source_hash": self.proposed_source_hash,
            "filename": self.filename,
            "unified_diff": self.unified_diff,
            "expected_effect": self.expected_effect,
            "assumptions": list(self.assumptions),
            "trade_offs": self.trade_offs,
            "relevant_metric": self.relevant_metric,
            "predicted_metric_delta": self.predicted_metric_delta,
            "confidence": round(self.confidence, 2),
            "validation_passed": self.validation_passed,
            "validation_state": self.validation_state,
            "is_eligible_for_application": self.is_eligible_for_application,
            "validation_report": self.validation_report,
            "user_decision_state": self.user_decision_state,
            "before_scores": self.before_scores,
            "after_scores": self.after_scores,
            "timestamp": self.timestamp,
            "applied_at": self.applied_at,
        }


@dataclass
class ImprovementAdvisorReport:
    source_snapshot_hash: str
    filename: str
    quality_score: Optional[float]
    optimization_potential: Optional[float]
    security_risk_score: Optional[float]
    total_candidates: int
    candidates: List[ImprovementCandidate]
    unfixable_advisories: List[Dict[str, Any]]
    disclaimer: str
    summary: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_snapshot_hash": self.source_snapshot_hash,
            "filename": self.filename,
            "quality_score": round(self.quality_score, 1) if self.quality_score is not None else None,
            "optimization_potential": round(self.optimization_potential, 1) if self.optimization_potential is not None else None,
            "security_risk_score": round(self.security_risk_score, 1) if self.security_risk_score is not None else None,
            "total_candidates": self.total_candidates,
            "candidates": [c.to_dict() for c in self.candidates],
            "unfixable_advisories": self.unfixable_advisories,
            "disclaimer": self.disclaimer,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }


IMPROVEMENT_DISCLAIMER = (
    "The Post-Repair Improvement Advisor generates static, evidence-backed recommendations "
    "for programs that already compile or have completed syntax repair. Proposed code modifications "
    "represent possible local optimizations or hardenings with explicit assumptions and trade-offs; "
    "they do NOT guarantee global optimality or defect-free behavior. Original code remains unaltered "
    "until explicitly approved and applied by the user."
)


class ImprovementAdvisor:
    """
    Coordinates post-repair re-analysis, extracts safe improvement patterns,
    validates candidate transformations independently, and scores before/after deltas.
    """

    def __init__(self):
        self.quality_scorer = CodeQualityScorer()
        self.opt_analyzer = OptimizationPotentialAnalyzer()
        self.sec_reporter = SecurityReporter()
        self.sec_scorer = SecurityRiskScorer()
        self.patch_validator = PatchValidator()

    def analyze_and_advise(
        self,
        source_code: str,
        filename: str = "main.c",
        green_report: Optional[Dict[str, Any]] = None,
    ) -> ImprovementAdvisorReport:
        import hashlib
        snapshot_hash = hashlib.sha256((source_code or "").encode("utf-8")).hexdigest()[:12]

        if not source_code or len(source_code.strip()) <= 0:
            return ImprovementAdvisorReport(
                source_snapshot_hash=snapshot_hash,
                filename=filename,
                quality_score=None,
                optimization_potential=None,
                security_risk_score=None,
                total_candidates=0,
                candidates=[],
                unfixable_advisories=[],
                disclaimer=IMPROVEMENT_DISCLAIMER,
                summary="Improvement Advisor unavailable on empty or fragmented source snippet.",
            )

        # 1. Run baseline analyses on the current code snapshot
        q_rep = self.quality_scorer.assess(source_code, filename=filename)
        opt_rep = self.opt_analyzer.analyze(source_code, filename=filename, green_metrics=green_report)
        sec_findings_rep = self.sec_reporter.analyze_source(source_code, filename=filename)
        sec_risk_rep = self.sec_scorer.assess(sec_findings_rep.findings, source_code=source_code, filename=filename)

        base_scores = {
            "quality_score": q_rep.overall_score,
            "optimization_potential": opt_rep.optimization_potential,
            "security_risk_score": sec_risk_rep.risk_score,
        }

        candidates: List[ImprovementCandidate] = []
        unfixable: List[Dict[str, Any]] = []

        # 2. Strategy A: Performance / Optimization Candidates
        self._generate_performance_candidates(source_code, filename, opt_rep, base_scores, candidates, unfixable)

        # 3. Strategy B: Security Hardening Candidates
        self._generate_security_candidates(source_code, filename, sec_findings_rep, base_scores, candidates, unfixable)

        # 4. Strategy C: Maintainability Candidates
        self._generate_maintainability_candidates(source_code, filename, q_rep, base_scores, candidates, unfixable)

        # 5. Strategy D: Conservative Minimal Candidates
        self._generate_conservative_candidates(source_code, filename, base_scores, candidates)

        summary = (
            f"Improvement Advisor identified {len(candidates)} actionable candidate change(s) "
            f"across {len(unfixable)} recommendation(s). Quality: {round(q_rep.overall_score or 0, 1)}%, "
            f"Optimization Potential: {round(opt_rep.optimization_potential or 0, 1)}%, "
            f"Security Risk: {round(sec_risk_rep.risk_score or 0, 1)}%."
        )

        for c in candidates:
            candidate_registry.register(c)

        return ImprovementAdvisorReport(
            source_snapshot_hash=snapshot_hash,
            filename=filename,
            quality_score=q_rep.overall_score,
            optimization_potential=opt_rep.optimization_potential,
            security_risk_score=sec_risk_rep.risk_score,
            total_candidates=len(candidates),
            candidates=candidates,
            unfixable_advisories=unfixable,
            disclaimer=IMPROVEMENT_DISCLAIMER,
            summary=summary,
        )

    # -------------------------------------------------------------------------
    # Candidate Generators
    # -------------------------------------------------------------------------
    def _generate_performance_candidates(
        self,
        source: str,
        filename: str,
        opt_rep: OptimizationPotentialReport,
        base_scores: Dict[str, Any],
        candidates: List[ImprovementCandidate],
        unfixable: List[Dict[str, Any]],
    ) -> None:
        lines = source.splitlines()

        # Check for loop-invariant strlen() in loop condition: for (...; i < strlen(s); ...)
        strlen_pattern = re.compile(r"for\s*\(\s*(int\s+)?([a-zA-Z0-9_]+)\s*=\s*0\s*;\s*\2\s*<\s*strlen\s*\(([^)]+)\)\s*;\s*([^\)]+)\)")
        for idx, line in enumerate(lines, start=1):
            match = strlen_pattern.search(line)
            if match:
                loop_var = match.group(2)
                target_str = match.group(3).strip()
                iter_step = match.group(4).strip()

                indent = re.match(r"^\s*", line).group(0)
                brace_suffix = " {" if "{" in line else ""
                len_var = f"{target_str}_len"
                hoisted_decl = f"{indent}int {len_var} = strlen({target_str});\n"
                new_loop = f"{indent}for (int {loop_var} = 0; {loop_var} < {len_var}; {iter_step}){brace_suffix}"

                patched_lines = list(lines)
                patched_lines[idx - 1] = hoisted_decl + new_loop
                proposed_code = "\n".join(patched_lines)

                diff = self._create_diff(source, proposed_code, filename)
                val_report = self.patch_validator.validate_patch(source, proposed_code, filename=filename)

                # Predict & re-score
                after_scores = self._recompute_candidate_scores(proposed_code, filename)

                cand = self._build_candidate(
                    strategy=ImprovementStrategy.PERFORMANCE,
                    category="Avoidable Computation",
                    priority="HIGH",
                    title="Hoist Loop-Invariant strlen() Call Out of Loop Header",
                    explanation=(
                        f"Repeatedly evaluating strlen({target_str}) inside the for-loop condition re-traverses "
                        f"the null-terminated string on every iteration, degrading performance from O(N) to O(N²)."
                    ),
                    line=idx,
                    col=line.find("strlen"),
                    evidence=line.strip(),
                    source=source,
                    proposed_code=proposed_code,
                    filename=filename,
                    diff=diff,
                    expected_effect="Eliminates repeated strlen traversal; reduces iteration complexity to linear O(N).",
                    assumptions=[
                        f"String '{target_str}' is not modified within the loop body.",
                        "strlen() is side-effect free.",
                    ],
                    trade_offs="Adds a single local variable; negligible memory overhead.",
                    relevant_metric="Optimization Potential",
                    predicted_metric_delta="-25% Avoidable Computation opportunity",
                    confidence=0.92,
                    val_report=val_report,
                    base_scores=base_scores,
                    after_scores=after_scores,
                )
                candidates.append(cand)

        # Check for unbuffered single-byte getchar/putchar in loops
        io_pattern = re.compile(r"while\s*\(\s*1\s*\).*?getchar\(\)", re.DOTALL)
        if io_pattern.search(source):
            unfixable.append({
                "category": "Inefficient I/O",
                "priority": "MEDIUM",
                "title": "Unbuffered Character I/O Pattern Detected",
                "recommendation": "Consider reading blocks with fread() or fgets() rather than single-byte getchar() loops.",
                "requires_manual_refactoring": True,
            })

    def _generate_security_candidates(
        self,
        source: str,
        filename: str,
        sec_findings_rep: ComprehensiveSecurityReport,
        base_scores: Dict[str, Any],
        candidates: List[ImprovementCandidate],
        unfixable: List[Dict[str, Any]],
    ) -> None:
        lines = source.splitlines()

        # Check for unbounded strcpy(dst, src)
        strcpy_pattern = re.compile(r"\bstrcpy\s*\(\s*([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*\)")
        for idx, line in enumerate(lines, start=1):
            match = strcpy_pattern.search(line)
            if match:
                dst = match.group(1)
                src = match.group(2)
                indent = re.match(r"^\s*", line).group(0)

                # Safe bounded replacement
                replacement = (
                    f"{indent}strncpy({dst}, {src}, sizeof({dst}) - 1);\n"
                    f"{indent}{dst}[sizeof({dst}) - 1] = 0;"
                )
                patched_lines = list(lines)
                patched_lines[idx - 1] = replacement
                proposed_code = "\n".join(patched_lines)

                diff = self._create_diff(source, proposed_code, filename)
                val_report = self.patch_validator.validate_patch(source, proposed_code, filename=filename)
                after_scores = self._recompute_candidate_scores(proposed_code, filename)

                cand = self._build_candidate(
                    strategy=ImprovementStrategy.SECURITY_HARDENING,
                    category="Memory Safety",
                    priority="HIGH",
                    title="Replace Unbounded strcpy() with Bounded strncpy() and Sentinel Null",
                    explanation=(
                        f"Function strcpy({dst}, {src}) does not check target buffer capacity. If {src} exceeds "
                        f"{dst}'s bounds, memory is corrupted, causing stack frame corruption or arbitrary code execution."
                    ),
                    line=idx,
                    col=line.find("strcpy"),
                    evidence=line.strip(),
                    source=source,
                    proposed_code=proposed_code,
                    filename=filename,
                    diff=diff,
                    expected_effect="Prevents buffer overflow by strictly clamping copy length to target capacity minus 1.",
                    assumptions=[
                        f"Target buffer '{dst}' has a static array sizeof() capacity.",
                        "Source string is standard null-terminated C string.",
                    ],
                    trade_offs="Truncates source string if length exceeds buffer capacity instead of overflowing buffer.",
                    relevant_metric="Security Risk Score",
                    predicted_metric_delta="-23% Security Risk (Neutralizes BUFFER_OVERFLOW risk)",
                    confidence=0.95,
                    val_report=val_report,
                    base_scores=base_scores,
                    after_scores=after_scores,
                )
                candidates.append(cand)

        # Check for sprintf(dst, ...)
        sprintf_pattern = re.compile(r"\bsprintf\s*\(\s*([a-zA-Z0-9_]+)\s*,\s*([^,]+)(,.*)?\)")
        for idx, line in enumerate(lines, start=1):
            match = sprintf_pattern.search(line)
            if match:
                dst = match.group(1)
                fmt = match.group(2).strip()
                args = match.group(3) or ""
                indent = re.match(r"^\s*", line).group(0)

                replacement = f"{indent}snprintf({dst}, sizeof({dst}), {fmt}{args});"
                patched_lines = list(lines)
                patched_lines[idx - 1] = replacement
                proposed_code = "\n".join(patched_lines)

                diff = self._create_diff(source, proposed_code, filename)
                val_report = self.patch_validator.validate_patch(source, proposed_code, filename=filename)
                after_scores = self._recompute_candidate_scores(proposed_code, filename)

                cand = self._build_candidate(
                    strategy=ImprovementStrategy.SECURITY_HARDENING,
                    category="Format Security",
                    priority="HIGH",
                    title="Replace Unbounded sprintf() with Safe snprintf()",
                    explanation=f"sprintf({dst}, ...) does not enforce buffer boundaries. snprintf guarantees bounded write.",
                    line=idx,
                    col=line.find("sprintf"),
                    evidence=line.strip(),
                    source=source,
                    proposed_code=proposed_code,
                    filename=filename,
                    diff=diff,
                    expected_effect="Enforces hard bound on formatted output length.",
                    assumptions=[f"'{dst}' capacity is measurable by sizeof()."],
                    trade_offs="Formatted string may be truncated if length exceeds buffer limit.",
                    relevant_metric="Security Risk Score",
                    predicted_metric_delta="-15% Security Risk",
                    confidence=0.90,
                    val_report=val_report,
                    base_scores=base_scores,
                    after_scores=after_scores,
                )
                candidates.append(cand)

    def _generate_maintainability_candidates(
        self,
        source: str,
        filename: str,
        q_rep: CodeQualityReport,
        base_scores: Dict[str, Any],
        candidates: List[ImprovementCandidate],
        unfixable: List[Dict[str, Any]],
    ) -> None:
        lines = source.splitlines()

        # Non-canonical main signature: void main() -> int main() with return 0;
        void_main_pattern = re.compile(r"^\s*void\s+main\s*\(\s*\)")
        for idx, line in enumerate(lines, start=1):
            if void_main_pattern.search(line):
                indent = re.match(r"^\s*", line).group(0)
                new_line = re.sub(r"\bvoid\s+main\s*\(\s*\)", "int main()", line)
                patched_lines = list(lines)
                patched_lines[idx - 1] = new_line

                # Add return 0 before closing brace of main if absent
                if not any("return 0;" in l for l in patched_lines):
                    for r_idx in range(len(patched_lines) - 1, -1, -1):
                        if "}" in patched_lines[r_idx]:
                            patched_lines.insert(r_idx, f"{indent}    return 0;")
                            break

                proposed_code = "\n".join(patched_lines)
                diff = self._create_diff(source, proposed_code, filename)
                val_report = self.patch_validator.validate_patch(source, proposed_code, filename=filename)
                after_scores = self._recompute_candidate_scores(proposed_code, filename)

                cand = self._build_candidate(
                    strategy=ImprovementStrategy.MAINTAINABILITY,
                    category="Coding Standards",
                    priority="MEDIUM",
                    title="Adopt Canonical ISO C Main Signature (int main() with return 0)",
                    explanation="void main() is non-standard in ISO C99/C11. Returning int with 0 signifies successful OS exit status.",
                    line=idx,
                    col=0,
                    evidence=line.strip(),
                    source=source,
                    proposed_code=proposed_code,
                    filename=filename,
                    diff=diff,
                    expected_effect="Conforms to standard C entry-point semantics and improves portability.",
                    assumptions=["Program runs in standard hosted C environment."],
                    trade_offs="None; strictly increases standards compliance.",
                    relevant_metric="Code Quality Score",
                    predicted_metric_delta="+8% Coding Standards Compliance",
                    confidence=0.98,
                    val_report=val_report,
                    base_scores=base_scores,
                    after_scores=after_scores,
                )
                candidates.append(cand)

    def _generate_conservative_candidates(
        self,
        source: str,
        filename: str,
        base_scores: Dict[str, Any],
        candidates: List[ImprovementCandidate],
    ) -> None:
        lines = source.splitlines()

        # Check for uninitialized pointer declarations: int *p; -> int *p = NULL;
        uninit_ptr = re.compile(r"^\s*(int|char|float|double|void)\s*\*\s*([a-zA-Z0-9_]+)\s*;")
        for idx, line in enumerate(lines, start=1):
            match = uninit_ptr.match(line)
            if match and "NULL" not in line:
                var_type = match.group(1)
                var_name = match.group(2)
                indent = re.match(r"^\s*", line).group(0)

                new_line = f"{indent}{var_type} *{var_name} = NULL;"
                patched_lines = list(lines)
                patched_lines[idx - 1] = new_line
                proposed_code = "\n".join(patched_lines)

                diff = self._create_diff(source, proposed_code, filename)
                val_report = self.patch_validator.validate_patch(source, proposed_code, filename=filename)
                after_scores = self._recompute_candidate_scores(proposed_code, filename)

                cand = self._build_candidate(
                    strategy=ImprovementStrategy.CONSERVATIVE,
                    category="Defensive Initialization",
                    priority="LOW",
                    title=f"Conservatively Initialize Pointer '{var_name}' to NULL",
                    explanation="Wild pointers pointing to arbitrary stack remnants can lead to silent corruption if dereferenced.",
                    line=idx,
                    col=0,
                    evidence=line.strip(),
                    source=source,
                    proposed_code=proposed_code,
                    filename=filename,
                    diff=diff,
                    expected_effect="Ensures predictable NULL state for pointer before allocation.",
                    assumptions=[f"'{var_name}' is initialized or checked before dereference."],
                    trade_offs="Minor initialization instruction; prevents wild pointer hazards.",
                    relevant_metric="Code Quality Score",
                    predicted_metric_delta="+3% Correctness & Hygiene",
                    confidence=0.96,
                    val_report=val_report,
                    base_scores=base_scores,
                    after_scores=after_scores,
                )
                candidates.append(cand)

    # -------------------------------------------------------------------------
    # Helper utilities
    # -------------------------------------------------------------------------
    def _create_diff(self, original: str, proposed: str, filename: str) -> str:
        orig_lines = original.splitlines(keepends=True)
        prop_lines = proposed.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            prop_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
        return "".join(diff)

    def _recompute_candidate_scores(self, candidate_code: str, filename: str) -> Dict[str, Any]:
        """Calculates actual post-patch metrics independently for the isolated candidate source."""
        try:
            q = self.quality_scorer.assess(candidate_code, filename=filename)
            opt = self.opt_analyzer.analyze(candidate_code, filename=filename)
            sec_findings = self.sec_reporter.analyze_source(candidate_code, filename=filename)
            sec = self.sec_scorer.assess(sec_findings.findings, source_code=candidate_code, filename=filename)
            return {
                "quality_score": q.overall_score,
                "optimization_potential": opt.optimization_potential,
                "security_risk_score": sec.risk_score,
            }
        except Exception:
            return {}

    def _build_candidate(
        self,
        strategy: ImprovementStrategy,
        category: str,
        priority: str,
        title: str,
        explanation: str,
        line: int,
        col: int,
        evidence: str,
        source: str,
        proposed_code: str,
        filename: str,
        diff: str,
        expected_effect: str,
        assumptions: List[str],
        trade_offs: str,
        relevant_metric: str,
        predicted_metric_delta: str,
        confidence: float,
        val_report: PatchValidationReport,
        base_scores: Dict[str, Any],
        after_scores: Dict[str, Any],
    ) -> ImprovementCandidate:
        orig_hash = hashlib.sha256((source or "").encode("utf-8")).hexdigest()[:12]
        prop_hash = hashlib.sha256((proposed_code or "").encode("utf-8")).hexdigest()[:12]
        strat_tag = strategy.value.lower()[:4]
        cand_id = f"cand-{strat_tag}-{orig_hash[:6]}-{line:03d}-{prop_hash[:6]}"

        val_is_valid = bool(val_report.is_valid)
        if val_is_valid:
            validation_state = DecisionState.VALIDATED.value
            is_eligible = True
            decision_state = DecisionState.AWAITING_USER_DECISION.value
        else:
            validation_state = DecisionState.VALIDATION_FAILED.value
            is_eligible = False
            decision_state = DecisionState.VALIDATION_FAILED.value

        return ImprovementCandidate(
            id=cand_id,
            strategy=strategy,
            category=category,
            priority=priority,
            title=title,
            explanation=explanation,
            line=line,
            col=col,
            evidence=evidence,
            original_code=source,
            original_source_hash=orig_hash,
            proposed_code=proposed_code,
            proposed_source_hash=prop_hash,
            filename=filename,
            unified_diff=diff,
            expected_effect=expected_effect,
            assumptions=assumptions,
            trade_offs=trade_offs,
            relevant_metric=relevant_metric,
            predicted_metric_delta=predicted_metric_delta,
            confidence=confidence,
            validation_passed=val_is_valid,
            validation_state=validation_state,
            is_eligible_for_application=is_eligible,
            validation_report=val_report.to_dict(),
            user_decision_state=decision_state,
            before_scores=base_scores,
            after_scores=after_scores,
        )


class CandidateRegistry:
    """
    Registry for improvement candidates that guarantees:
    1. Uniqueness of candidate IDs.
    2. Verification of baseline source hash before applying patch to prevent stale application.
    3. Strict eligibility policy: only candidates passing required validation can be applied.
    4. Lifecycle state transitions: AWAITING_USER_DECISION -> USER_APPROVED / APPLIED / USER_REJECTED.
    5. Reversion/rollback of applied status if UI application fails, avoiding permanent candidate consumption.
    """
    def __init__(self):
        self._candidates: Dict[str, ImprovementCandidate] = {}
        self._lock = threading.Lock()

    def register(self, candidate: ImprovementCandidate) -> None:
        with self._lock:
            self._candidates[candidate.id] = candidate

    def update(self, candidate: ImprovementCandidate) -> bool:
        """Replace a registered proposal after whole-job validation finalizes its code."""
        with self._lock:
            if candidate.id not in self._candidates:
                return False
            self._candidates[candidate.id] = candidate
            return True

    def get(self, candidate_id: str) -> Optional[ImprovementCandidate]:
        with self._lock:
            return self._candidates.get(candidate_id)

    def verify_and_apply(
        self,
        candidate_id: str,
        current_source: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[ImprovementCandidate]]:
        with self._lock:
            cand = self._candidates.get(candidate_id)
            if not cand:
                return False, f"Candidate '{candidate_id}' not found", None

            # 1. State check: already applied or rejected
            if cand.user_decision_state == DecisionState.APPLIED.value:
                return False, f"Candidate '{cand.id}' has already been applied", cand
            if cand.user_decision_state == DecisionState.USER_REJECTED.value:
                return False, f"Candidate '{cand.id}' was previously rejected by user", cand

            # 2. Validation eligibility check
            if not cand.is_eligible_for_application:
                return False, f"Candidate '{cand.id}' is ineligible for application: validation state is {cand.validation_state}", cand

            # 3. Non-empty proposed code check
            if not cand.proposed_code or not cand.proposed_code.strip():
                return False, f"Candidate '{cand.id}' has empty proposed code", cand

            # 4. Stale baseline check: verify current editor source hash
            if current_source is None:
                return False, "Current editor source code is required to verify freshness before application.", cand

            def _norm_code(text: Optional[str]) -> str:
                return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()

            curr_norm = _norm_code(current_source)
            curr_full = hashlib.sha256(current_source.encode("utf-8")).hexdigest()
            curr_norm_hash = hashlib.sha256(curr_norm.encode("utf-8")).hexdigest()

            orig = cand.original_source_hash or ""
            is_matching = (
                curr_full == orig
                or curr_full[:12] == orig[:12]
                or curr_norm_hash == orig
                or curr_norm_hash[:12] == orig[:12]
                or curr_norm == _norm_code(cand.original_code)
            )
            if not is_matching:
                return False, f"Stale candidate: source modified since proposal (baseline hash {orig[:12]} != current hash {curr_norm_hash[:12]}). Please re-run analysis.", cand

            # 5. Transition to APPLIED state
            cand.user_decision_state = DecisionState.APPLIED.value
            cand.applied_at = time.time()
            return True, f"Candidate '{cand.title}' successfully applied to editor.", cand

    def rollback_apply(self, candidate_id: str, reason: str = "") -> Tuple[bool, str, Optional[ImprovementCandidate]]:
        """
        Safely roll back an APPLIED candidate back to AWAITING_USER_DECISION
        if the UI editor insertion failed or was cancelled.
        """
        with self._lock:
            cand = self._candidates.get(candidate_id)
            if not cand:
                return False, f"Candidate '{candidate_id}' not found", None
            if cand.user_decision_state != DecisionState.APPLIED.value:
                return False, f"Candidate '{cand.id}' is not in APPLIED state (current: {cand.user_decision_state})", cand

            cand.user_decision_state = DecisionState.AWAITING_USER_DECISION.value
            cand.applied_at = None
            msg = f"Candidate '{cand.id}' rolled back to AWAITING_USER_DECISION: {reason}" if reason else f"Candidate '{cand.id}' rolled back to AWAITING_USER_DECISION."
            return True, msg, cand

    def reject(self, candidate_id: str) -> Tuple[bool, str, Optional[ImprovementCandidate]]:
        with self._lock:
            cand = self._candidates.get(candidate_id)
            if not cand:
                return False, f"Candidate '{candidate_id}' not found", None

            cand.user_decision_state = DecisionState.USER_REJECTED.value
            return True, f"Candidate '{cand.title}' rejected by user.", cand

    def clear(self) -> None:
        with self._lock:
            self._candidates.clear()


candidate_registry = CandidateRegistry()
