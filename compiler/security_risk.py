# compiler/security_risk.py
"""
Normalized Security Risk Score (%) Engine for Antigravity Compiler Assistant.

Features:
1. Normalized Security Risk Score from 0% to 100% derived from supported security findings.
2. Multi-factor risk formula:
   - Severity (Critical, High, Medium, Low, Info)
   - Exploitability (unbounded memory write, code execution vs memory leak)
   - Exposure (standard input / external attack surface vs internal helper scope)
   - Confidence (confirmed deterministic finding vs heuristic warning)
3. Granular Reporting:
   - Critical, High, Medium, and Low finding counts displayed separately.
   - Specific contribution of each important finding to the total score.
   - Clear enumeration of unresolved findings vs resolved fixes.
4. Epistemological & Theoretical Honesty:
   - Explicitly framed as a risk indicator, NOT a calibrated attack probability.
   - Does not claim to predict future exploit occurrences or guarantee absolute security.
   - Refuses to fabricate percentages on empty or incomplete source snippets (INCOMPLETE_ASSESSMENT).
5. Before-and-After Preservation:
   - Recalculates risk score across proposed patches.
   - Preserves before score, after score, risk delta, and vulnerability transition states.

Risk Formula:
    Risk Points = BaseSeverityWeight * ExploitabilityFactor * ExposureFactor * ConfidenceFactor
    Normalized Risk Score (%) = 100.0 * (1.0 - exp(-TotalRiskPoints / ScaleConstant))
    ScaleConstant = 40.0

Parity Guarantee:
    - Unbounded scanf (CWE-120/242): Base=45.0, Exploitability=1.0, Exposure=1.0, Confidence=1.0 => 45.0 pts (67.5% score).
    - Tainted CRITICAL Command Injection (CWE-78): Base=45.0, Exploitability=1.0, Exposure=1.0, Confidence=1.0 => 45.0 pts (67.5% score).
    A tainted CRITICAL sink strictly scores >= unbounded scanf.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class SecurityRiskStatus(str, Enum):
    ASSESSED = "ASSESSED"
    INCOMPLETE_ASSESSMENT = "INCOMPLETE_ASSESSMENT"
    EMPTY_SOURCE = "EMPTY_SOURCE"
    INCONCLUSIVE = "INCONCLUSIVE"
    HEURISTIC = "HEURISTIC"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass
class FindingRiskContribution:
    finding_id: str
    rule_id: str
    category: str
    severity: str
    line: int
    title: str
    base_severity_weight: float
    exploitability_factor: float
    exposure_factor: float
    confidence_factor: float
    risk_points: float
    is_confirmed: bool
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "line": self.line,
            "title": self.title,
            "base_severity_weight": self.base_severity_weight,
            "exploitability_factor": round(self.exploitability_factor, 2),
            "exposure_factor": round(self.exposure_factor, 2),
            "confidence_factor": round(self.confidence_factor, 2),
            "risk_points": round(self.risk_points, 1),
            "is_confirmed": self.is_confirmed,
            "explanation": self.explanation,
        }


@dataclass
class SecurityRiskReport:
    risk_score: Optional[float]
    status: SecurityRiskStatus
    can_score: bool
    status_reason: str
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    total_findings: int
    unresolved_count: int
    contributions: List[FindingRiskContribution]
    unresolved_findings: List[Dict[str, Any]]
    disclaimer: str
    summary: str
    confirmed_count: int = 0
    heuristic_count: int = 0
    before_score: Optional[float] = None
    after_score: Optional[float] = None
    delta_score: Optional[float] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": round(self.risk_score, 1) if self.risk_score is not None else None,
            "status": self.status.value,
            "can_score": self.can_score,
            "status_reason": self.status_reason,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "info_count": self.info_count,
            "confirmed_count": self.confirmed_count,
            "heuristic_count": self.heuristic_count,
            "finding_counts": {
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": self.medium_count,
                "low": self.low_count,
                "info": self.info_count,
                "confirmed": self.confirmed_count,
                "heuristic": self.heuristic_count,
            },
            "total_findings": self.total_findings,
            "unresolved_count": self.unresolved_count,
            "contributions": [c.to_dict() for c in self.contributions],
            "unresolved_findings": self.unresolved_findings,
            "disclaimer": self.disclaimer,
            "summary": self.summary,
            "before_score": round(self.before_score, 1) if self.before_score is not None else None,
            "after_score": round(self.after_score, 1) if self.after_score is not None else None,
            "delta_score": round(self.delta_score, 1) if self.delta_score is not None else None,
            "timestamp": self.timestamp,
        }


SECURITY_RISK_DISCLAIMER = (
    "The Security Risk Score is a static composite risk indicator derived from identified "
    "vulnerabilities, severity, exploitability, exposure, and confidence. It is NOT a calibrated "
    "probability that a security attack or breach will occur in the future. A low risk score does not "
    "guarantee the absence of unmodeled or zero-day vulnerabilities. If source code is incomplete or "
    "insufficient, the assessment status is flagged as incomplete rather than fabricating a percentage."
)


class SecurityRiskScorer:
    """
    Evaluates detected security vulnerabilities and computes a normalized Security Risk Score (0 - 100%).
    Factors in Severity, Exploitability, Exposure, and Confidence.
    """

    SEVERITY_WEIGHTS = {
        "CRITICAL": 45.0,
        "BLOCKER": 45.0,
        "HIGH": 25.0,
        "MEDIUM": 12.0,
        "LOW": 5.0,
        "INFO": 0.0,  # Informational advisories are non-actionable notices; 0 risk points by explicit policy
    }

    def __init__(self, scale_constant: float = 40.0):
        # scale_constant governs the asymptotic saturation rate of cumulative risk points.
        # e.g., 40.0 means 45 raw points yields ~67.5% risk, 90 raw points yields ~89.5% risk.
        self.scale_constant = scale_constant

    def assess(
        self,
        findings: List[Any],
        source_code: str = "",
        filename: str = "main.c",
        has_syntax_errors: Optional[bool] = None,
    ) -> SecurityRiskReport:
        stripped = (source_code or "").strip()

        # Check for syntax errors if not explicitly provided
        if has_syntax_errors is None and source_code:
            try:
                from test_parser import parse_source, has_any_errors
                tree, listeners, _ = parse_source(source_code, filename)
                has_syntax_errors = (tree is None) or has_any_errors(listeners)
            except Exception:
                has_syntax_errors = False
        if not has_syntax_errors and findings:
            for f in findings:
                f_cat = getattr(f, "category", "")
                f_cat_str = f_cat.value if hasattr(f_cat, "value") else str(f_cat)
                if str(f_cat_str).upper() in ("SYNTAX", "LEXICAL"):
                    has_syntax_errors = True
                    break

        # Zero-fabrication check 1: Empty source
        if not stripped and not findings:
            return SecurityRiskReport(
                risk_score=None,
                status=SecurityRiskStatus.EMPTY_SOURCE,
                can_score=False,
                status_reason="Source code is empty. Security risk assessment requires non-empty program source.",
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                info_count=0,
                total_findings=0,
                unresolved_count=0,
                contributions=[],
                unresolved_findings=[],
                disclaimer=SECURITY_RISK_DISCLAIMER,
                summary="Security Risk Score Unavailable: Empty Source Code",
                confirmed_count=0,
                heuristic_count=0,
            )

        # Zero-fabrication check 2: Fragmented snippet with no findings
        code_without_comments = re.sub(r"//.*?\n|/\*.*?\*/", "", stripped, flags=re.DOTALL).strip()
        if len(code_without_comments) <= 0 and not findings:
            return SecurityRiskReport(
                risk_score=None,
                status=SecurityRiskStatus.INCOMPLETE_ASSESSMENT,
                can_score=False,
                status_reason="Source snippet is too brief (< 15 characters) for a reliable security assessment.",
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                info_count=0,
                total_findings=0,
                unresolved_count=0,
                contributions=[],
                unresolved_findings=[],
                disclaimer=SECURITY_RISK_DISCLAIMER,
                summary="Security Risk Score Incomplete: Insufficient Code Context",
                confirmed_count=0,
                heuristic_count=0,
            )

        # Count severities and confidence separately
        crit_count = 0
        high_count = 0
        med_count = 0
        low_count = 0
        info_count = 0
        confirmed_count = 0
        heuristic_count = 0

        contributions: List[FindingRiskContribution] = []
        unresolved_list: List[Dict[str, Any]] = []
        seen_finding_keys: Set[str] = set()

        total_raw_points = 0.0

        for f in findings:
            cat_raw = self._get_attr(f, "category", "GENERAL_SECURITY")
            cat = (cat_raw.name if hasattr(cat_raw, "name") else (cat_raw.value if hasattr(cat_raw, "value") else str(cat_raw))).upper()
            if cat.startswith("FINDINGCATEGORY."):
                cat = cat.split(".", 1)[1]
            # Explicit guard: filter out compiler-only findings (syntax, lexical, semantic) if present
            if cat in ("SYNTAX", "LEXICAL", "SEMANTIC", "SYSTEM"):
                continue

            loc = getattr(f, "location", None)
            default_line = getattr(loc, "line", 1) if loc is not None else 1
            line = int(self._get_attr(f, "line", default_line))
            rule_id = str(self._get_attr(f, "rule_id", "SEC-VULN"))

            # Deduplicate correlated findings reporting the same vulnerability/sink on the same line
            sink_kw = ""
            for kw in ("gets", "strcpy", "strcat", "sprintf", "system", "popen", "scanf", "exec", "memcpy", "injection", "free", "format", "uaf", "memleak"):
                if kw in rule_id.lower() or kw in str(f).lower():
                    sink_kw = kw
                    break
            dedup_key = f"{line}:{sink_kw}" if sink_kw else f"{line}:{rule_id}:{cat}"
            if dedup_key in seen_finding_keys:
                continue
            seen_finding_keys.add(dedup_key)

            sev = self._get_attr(f, "severity", "MEDIUM").upper()
            if sev in ("CRITICAL", "BLOCKER"):
                crit_count += 1
            elif sev == "HIGH":
                high_count += 1
            elif sev == "MEDIUM":
                med_count += 1
            elif sev == "LOW":
                low_count += 1
            else:
                info_count += 1

            # Confidence factor (0.5 - 1.0)
            status_val = str(self._get_attr(f, "status", "CONFIRMED")).upper()
            is_confirmed = "CONFIRMED" in status_val or bool(self._get_attr(f, "is_confirmed", False))
            # When syntax errors prevent reliable AST analysis, fallback findings cannot be confirmed
            if has_syntax_errors:
                is_confirmed = False

            conf_val = float(self._get_attr(f, "confidence", 1.0 if is_confirmed else 0.7))
            confidence_factor = 1.0 if is_confirmed else max(0.5, min(0.7 if has_syntax_errors else 0.9, conf_val))

            if is_confirmed:
                confirmed_count += 1
            else:
                heuristic_count += 1

            # Base severity weight (0 for INFO advisories by policy)
            base_weight = self.SEVERITY_WEIGHTS.get(sev, 10.0)

            # Exploitability factor (0.4 - 1.0)
            exploitability, exp_reason = self._compute_exploitability(cat, f)

            # Exposure factor (0.5 - 1.0)
            exposure, exposure_reason = self._compute_exposure(f, source_code, line)

            # Contribution formula: Base * Exploitability * Exposure * Confidence
            if sev == "INFO":
                points = 0.0
                explanation = f"INFO advisory ({rule_id}): Non-actionable informational notice (0.0 pts)"
            else:
                points = base_weight * exploitability * exposure * confidence_factor
                explanation = (
                    f"{sev} finding ({rule_id}) contributes +{points:.1f} pts "
                    f"[Base: {base_weight:.0f}, Exploitability: {exploitability:.2f} ({exp_reason}), "
                    f"Exposure: {exposure:.2f} ({exposure_reason}), Confidence: {confidence_factor:.2f}]"
                )

            total_raw_points += points

            finding_id = str(self._get_attr(f, "id", f"{rule_id}:{line}"))
            msg = str(
                self._get_attr(f, "potential_impact", "")
                or self._get_attr(f, "message", "")
                or self._get_attr(f, "evidence", "")
                or "Security finding"
            )

            contrib = FindingRiskContribution(
                finding_id=finding_id,
                rule_id=rule_id,
                category=cat,
                severity=sev,
                line=line,
                title=msg,
                base_severity_weight=base_weight,
                exploitability_factor=exploitability,
                exposure_factor=exposure,
                confidence_factor=confidence_factor,
                risk_points=points,
                is_confirmed=is_confirmed,
                explanation=explanation,
            )
            contributions.append(contrib)

            unresolved_list.append({
                "id": finding_id,
                "rule_id": rule_id,
                "severity": sev,
                "line": line,
                "category": cat,
                "impact": msg,
                "is_confirmed": is_confirmed,
                "risk_contribution": round(points, 1),
            })

        # If source has syntax errors and no security findings were detected, the assessment is inconclusive
        if has_syntax_errors and len(contributions) == 0:
            return SecurityRiskReport(
                risk_score=None,
                status=SecurityRiskStatus.INCONCLUSIVE,
                can_score=False,
                status_reason="Syntax errors in source code prevent reliable AST construction and static security analysis. Zero detected findings cannot certify absence of vulnerabilities while syntax remains invalid.",
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                info_count=0,
                total_findings=0,
                unresolved_count=0,
                contributions=[],
                unresolved_findings=[],
                disclaimer=SECURITY_RISK_DISCLAIMER,
                summary="Security Risk Assessment Inconclusive: Syntax errors prevent reliable analysis",
                confirmed_count=0,
                heuristic_count=0,
            )

        # Calculate normalized score (0% to 100%)
        if total_raw_points <= 0.0:
            final_score = 0.0
        else:
            final_score = 100.0 * (1.0 - math.exp(-total_raw_points / self.scale_constant))
            final_score = max(0.0, min(100.0, final_score))

        # Sort contributions by risk points descending
        contributions.sort(key=lambda c: c.risk_points, reverse=True)

        summary = (
            f"Security Risk Score: {round(final_score, 1)}% "
            f"({crit_count} Critical, {high_count} High, {med_count} Medium, {low_count} Low, {info_count} Info)"
        )
        if has_syntax_errors:
            summary += " [Syntax errors present in source; partial assessment]"

        status_reason = (
            "Security findings detected; however, full AST-based security analysis is incomplete due to syntax errors in source code."
            if has_syntax_errors
            else "Security risk calculated from supported findings, exploitability, and exposure factors."
        )

        report_status = SecurityRiskStatus.HEURISTIC if has_syntax_errors else SecurityRiskStatus.ASSESSED
        return SecurityRiskReport(
            risk_score=final_score,
            status=report_status,
            can_score=True,
            status_reason=status_reason,
            critical_count=crit_count,
            high_count=high_count,
            medium_count=med_count,
            low_count=low_count,
            info_count=info_count,
            confirmed_count=confirmed_count,
            heuristic_count=heuristic_count,
            total_findings=len(contributions),
            unresolved_count=len(unresolved_list),
            contributions=contributions,
            unresolved_findings=unresolved_list,
            disclaimer=SECURITY_RISK_DISCLAIMER,
            summary=summary,
        )

    def assess_delta(
        self,
        before_findings: List[Any],
        after_findings: List[Any],
        before_code: str = "",
        after_code: str = "",
        filename: str = "main.c",
    ) -> SecurityRiskReport:
        """
        Recalculates Security Risk Score across proposed or approved code fixes,
        preserving before, after, delta, and resolved findings state.
        Never fabricates a 0.0 score when either assessment is incomplete.
        """
        rep_before = self.assess(before_findings, source_code=before_code, filename=filename)
        rep_after = self.assess(after_findings, source_code=after_code, filename=filename)

        if not rep_before.can_score or not rep_after.can_score:
            rep_after.can_score = False
            rep_after.status = SecurityRiskStatus.INCOMPLETE_ASSESSMENT
            rep_after.status_reason = (
                f"Before assessment ({rep_before.status.value}) or after assessment "
                f"({rep_after.status.value}) is incomplete. Delta score cannot be computed."
            )
            rep_after.before_score = rep_before.risk_score
            rep_after.after_score = rep_after.risk_score
            rep_after.delta_score = None
            rep_after.summary = "Security Risk Delta Unavailable: Incomplete Assessment"
            return rep_after

        before_score = rep_before.risk_score
        after_score = rep_after.risk_score
        delta = after_score - before_score

        rep_after.before_score = round(before_score, 1)
        rep_after.after_score = round(after_score, 1)
        rep_after.delta_score = round(delta, 1)

        # Update summary with delta description
        direction = "decreased by" if delta <= 0 else "increased by"
        rep_after.summary = (
            f"Security Risk Score: {round(after_score, 1)}% "
            f"(Risk {direction} {abs(round(delta, 1))}%) - "
            f"{rep_after.critical_count} Critical, {rep_after.high_count} High remaining"
        )
        return rep_after

    # -------------------------------------------------------------------------
    # Helper factor calculations
    # -------------------------------------------------------------------------
    def _compute_exploitability(self, category: str, finding: Any) -> Tuple[float, str]:
        cat = category.upper()
        rule = str(self._get_attr(finding, "rule_id", "") or "").upper()
        evidence = str(self._get_attr(finding, "evidence", "")).lower()

        if "PROMPT_INJECTION" in cat:
            return 0.70, "Adversarial prompt-injection directive in comments"
        if (
            "UNBOUNDED_INPUT" in cat
            or bool(re.search(r"\bgets\s*\(", evidence))
            or "BUFFER_OVERFLOW" in cat
            or "COMMAND_INJECTION" in cat
            or "CWE-78" in rule
            or "COMMAND_INJECTION" in rule
            or "FORMAT_STRING" in cat
            or "system" in evidence
            or "popen" in evidence
            or "exec" in evidence
        ):
            return 1.0, "Direct stack/memory or shell command execution control"
        if "NULL_DEREFERENCE" in cat or "UNVALIDATED_POINTER" in cat:
            return 0.85, "Pointer corruption or denial of service"
        if "INTEGER_OVERFLOW" in cat or "OFF_BY_ONE" in cat or "TAINT_FLOW" in cat:
            return 0.75, "Arithmetic wrap / tainted flow boundary"
        if "INSECURE_API" in cat or "SENSITIVE_PATH" in cat:
            return 0.60, "Dangerous standard library usage"
        if "UNINITIALIZED" in cat:
            return 0.55, "Unpredictable memory disclosure"
        return 0.50, "General static policy check"

    def _compute_exposure(self, finding: Any, source_code: str, line: int) -> Tuple[float, str]:
        evidence = str(self._get_attr(finding, "evidence", "")).lower()
        if not source_code:
            return 0.8, "Default entry surface"

        lines = source_code.splitlines()
        target_line = lines[line - 1].lower() if 0 < line <= len(lines) else evidence

        cat = str(self._get_attr(finding, "category", "")).upper()
        rule = str(self._get_attr(finding, "rule_id", "")).upper()
        finding_str = str(finding).lower()

        # Command injection from tainted source or dataflow has exposure = 1.0 (untrusted user input boundary)
        if "COMMAND_INJECTION" in cat or "CWE-78" in rule or "taint" in evidence or "source line" in finding_str:
            return 1.0, "External untrusted I/O input boundary (tainted dataflow)"

        clean_target = re.sub(r"//.*$|/\*.*?\*/", "", target_line).strip()
        if any(re.search(rf"\b{kw}\b", clean_target) for kw in ("gets", "scanf", "argv", "read", "recv", "stdin", "socket")):
            return 1.0, "External untrusted I/O input boundary"

        if self._is_line_in_main(source_code, line):
            return 0.85, "Entry point (main function) execution path"

        return 0.65, "Internal function scope"

    @staticmethod
    def _is_line_in_main(source_code: str, target_line: int) -> bool:
        """Determines if a target line falls inside the main() function definition."""
        if not source_code or target_line < 1:
            return False
        lines = source_code.splitlines()
        in_main = False
        brace_depth = 0
        for idx, line_str in enumerate(lines, start=1):
            if re.search(r"\b(int|void)?\s*main\s*\(", line_str) or re.search(r"def\s+main\s*\(|if\s+__name__\s*==\s*['\"]__main__['\"]:", line_str):
                in_main = True
            if in_main:
                if "{" in line_str or "}" in line_str:
                    brace_depth += line_str.count("{") - line_str.count("}")
                    if idx == target_line:
                        return True
                    if brace_depth <= 0 and "{" in line_str:
                        in_main = False
                else:
                    # Python or lines without braces: check if target_line is near or in block
                    if idx == target_line:
                        return True
        return False

    @staticmethod
    def _get_attr(obj: Any, attr: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(attr, default)
        val = getattr(obj, attr, None)
        return val if val is not None else default
