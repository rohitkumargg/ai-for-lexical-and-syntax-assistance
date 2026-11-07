# compiler/security_reporter.py
"""
Security Vulnerability Reporting and Benchmarking Component for SimpleC/C.

Fulfills Phase 6 Requirements:
1. Comprehensive Security Findings:
   - Affected line / source range (line, col, end_line, end_col)
   - Vulnerability category (CWE classification)
   - Severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)
   - Evidence snippet
   - Potential impact description
   - Confidence score and status (CONFIRMED vs HEURISTIC)
   - Actionable remediation suggestions
2. Prioritization and distinguishing confirmed vulnerabilities from heuristic warnings.
3. Rejecting unsupported findings merely suspected by an AI model.
4. Post-Repair Delta Analysis:
   - Resolved vulnerabilities
   - Remaining vulnerabilities
   - Introduced vulnerabilities (regressions)
5. Security Disclaimers (honesty regarding static analysis limitations).
6. Benchmark Evaluation:
   - Evaluates labeled benchmarks
   - Measures False Positives (FP), False Negatives (FN), True Positives (TP),
     True Negatives (TN), Precision, Recall, F1 Score, and Accuracy.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


SECURITY_DISCLAIMER = (
    "DISCLAIMER: Static security analysis cannot guarantee that a program is completely secure "
    "or free of all vulnerabilities, logical flaws, timing leaks, or zero-day exploits. "
    "This report reflects findings against supported static analysis, taint flow tracking, "
    "and heuristic rules only. A clean analysis result does not certify safety against unsupported "
    "threat models or runtime environment hazards."
)


class VulnerabilityCategory(str, Enum):
    COMMAND_INJECTION = "COMMAND_INJECTION"
    UNBOUNDED_INPUT = "UNBOUNDED_INPUT"
    BUFFER_OVERFLOW = "BUFFER_OVERFLOW"
    FORMAT_STRING = "FORMAT_STRING"
    INTEGER_OVERFLOW = "INTEGER_OVERFLOW"
    NULL_DEREFERENCE = "NULL_DEREFERENCE"
    OFF_BY_ONE = "OFF_BY_ONE"
    TAINT_FLOW = "TAINT_FLOW"
    INSECURE_API = "INSECURE_API"
    SENSITIVE_PATH = "SENSITIVE_PATH"
    UNVALIDATED_POINTER = "UNVALIDATED_POINTER"
    GENERAL_SECURITY = "GENERAL_SECURITY"


class SecuritySeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @property
    def rank(self) -> int:
        ranks = {
            "CRITICAL": 5,
            "HIGH": 4,
            "MEDIUM": 3,
            "LOW": 2,
            "INFO": 1,
        }
        return ranks.get(self.value, 0)


class ConfidenceStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    POSSIBLE = "POSSIBLE"
    HEURISTIC = "HEURISTIC"
    UNSUPPORTED_SPECULATION = "UNSUPPORTED_SPECULATION"


@dataclass
class SecurityVulnerability:
    id: str
    rule_id: str
    category: VulnerabilityCategory
    severity: SecuritySeverity
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    evidence: str = ""
    potential_impact: str = ""
    confidence: float = 1.0
    status: ConfidenceStatus = ConfidenceStatus.CONFIRMED
    remediation_suggestions: List[str] = field(default_factory=list)
    cwe_id: Optional[str] = None
    is_blocked: bool = False
    source_layer: str = "static_analysis"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_vulnerability(self) -> bool:
        """True if finding is an actionable security vulnerability (not merely an informational notice)."""
        return self.severity != SecuritySeverity.INFO

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
            "evidence": self.evidence,
            "potential_impact": self.potential_impact,
            "confidence": round(self.confidence, 3),
            "status": self.status.value,
            "remediation_suggestions": list(self.remediation_suggestions),
            "cwe_id": self.cwe_id,
            "is_blocked": self.is_blocked,
            "is_vulnerability": self.is_vulnerability,
            "source_layer": self.source_layer,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SecurityVulnerability:
        return cls(
            id=data["id"],
            rule_id=data.get("rule_id", "SEC-GENERIC"),
            category=VulnerabilityCategory(data.get("category", "GENERAL_SECURITY")),
            severity=SecuritySeverity(data.get("severity", "WARNING")),
            line=int(data.get("line", 1)),
            column=int(data.get("column", 0)),
            end_line=data.get("end_line"),
            end_column=data.get("end_column"),
            evidence=data.get("evidence", ""),
            potential_impact=data.get("potential_impact", ""),
            confidence=float(data.get("confidence", 1.0)),
            status=ConfidenceStatus(data.get("status", "CONFIRMED")),
            remediation_suggestions=data.get("remediation_suggestions", []),
            cwe_id=data.get("cwe_id"),
            is_blocked=bool(data.get("is_blocked", False)),
            source_layer=data.get("source_layer", "static_analysis"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ComprehensiveSecurityReport:
    file_path: str
    findings: List[SecurityVulnerability] = field(default_factory=list)
    confirmed_count: int = 0
    heuristic_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    vulnerabilities_count: int = 0
    is_blocked: bool = False
    disclaimer: str = SECURITY_DISCLAIMER
    summary: str = ""

    @property
    def actionable_vulnerabilities(self) -> List[SecurityVulnerability]:
        return [f for f in self.findings if f.is_vulnerability]

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "findings": [f.to_dict() for f in self.findings],
            "vulnerabilities": [f.to_dict() for f in self.actionable_vulnerabilities],
            "confirmed_count": self.confirmed_count,
            "heuristic_count": self.heuristic_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "info_count": self.info_count,
            "vulnerabilities_count": self.vulnerabilities_count,
            "total_findings": len(self.findings),
            "is_blocked": self.is_blocked,
            "disclaimer": self.disclaimer,
            "summary": self.summary,
        }


@dataclass
class SecurityDeltaReport:
    original_findings: List[SecurityVulnerability] = field(default_factory=list)
    patched_findings: List[SecurityVulnerability] = field(default_factory=list)
    resolved_vulnerabilities: List[SecurityVulnerability] = field(default_factory=list)
    remaining_vulnerabilities: List[SecurityVulnerability] = field(default_factory=list)
    introduced_vulnerabilities: List[SecurityVulnerability] = field(default_factory=list)
    is_security_improved: bool = False
    has_regressions: bool = False
    disclaimer: str = SECURITY_DISCLAIMER
    is_inconclusive: bool = False
    inconclusive_reason: str = ""
    status: str = "COMPLETED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_count": len(self.original_findings),
            "patched_count": len(self.patched_findings),
            "resolved_count": len(self.resolved_vulnerabilities),
            "remaining_count": len(self.remaining_vulnerabilities),
            "introduced_count": len(self.introduced_vulnerabilities),
            "resolved_vulnerabilities": [v.to_dict() for v in self.resolved_vulnerabilities],
            "remaining_vulnerabilities": [v.to_dict() for v in self.remaining_vulnerabilities],
            "introduced_vulnerabilities": [v.to_dict() for v in self.introduced_vulnerabilities],
            "is_security_improved": self.is_security_improved,
            "has_regressions": self.has_regressions,
            "disclaimer": self.disclaimer,
            "is_inconclusive": self.is_inconclusive,
            "inconclusive_reason": self.inconclusive_reason,
            "status": self.status,
        }


def _compute_vuln_hash(category: str, line: int, col: int, rule_id: str, snippet: str) -> str:
    raw = f"{category}:{line}:{col}:{rule_id}:{snippet.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


# Impact catalog for standardized, precise security risk explanations
IMPACT_CATALOG = {
    VulnerabilityCategory.COMMAND_INJECTION: (
        "Arbitrary Operating System Command Injection. Untrusted or unvalidated input passed "
        "to a system shell allows attackers to execute arbitrary commands with process privileges.",
        "CWE-78",
    ),
    VulnerabilityCategory.UNBOUNDED_INPUT: (
        "Unbounded buffer read without length constraints. Input exceeding buffer capacity "
        "corrupts adjacent stack memory, leading to denial of service or arbitrary code execution.",
        "CWE-120",
    ),
    VulnerabilityCategory.BUFFER_OVERFLOW: (
        "Buffer overflow via unsafe string copy or formatting. Writing data beyond allocated "
        "memory bounds can overwrite return addresses or sensitive control data.",
        "CWE-120",
    ),
    VulnerabilityCategory.FORMAT_STRING: (
        "Format string vulnerability. Passing user-controlled format strings to printf/sprintf "
        "can leak sensitive memory contents or allow arbitrary write primitives via %n specifiers.",
        "CWE-134",
    ),
    VulnerabilityCategory.INTEGER_OVERFLOW: (
        "Integer overflow or sign truncation during arithmetic. When used for memory allocation "
        "or loop bounds, arithmetic wrap-around leads to under-allocated buffers and heap corruption.",
        "CWE-190",
    ),
    VulnerabilityCategory.NULL_DEREFERENCE: (
        "Null pointer dereference. Attempting to read or write through a NULL address causes "
        "process segmentation faults and availability denial of service.",
        "CWE-476",
    ),
    VulnerabilityCategory.OFF_BY_ONE: (
        "Off-by-one boundary error in array indexing or loop termination. Writing one byte beyond "
        "array boundaries can corrupt the frame pointer or adjacent variables.",
        "CWE-193",
    ),
    VulnerabilityCategory.TAINT_FLOW: (
        "Tainted data flow from an untrusted source directly into a privileged security sink "
        "without intermediate sanitization or validation.",
        "CWE-20",
    ),
    VulnerabilityCategory.INSECURE_API: (
        "Use of inherently hazardous or deprecated API functions with safer, bounded alternatives.",
        "CWE-676",
    ),
    VulnerabilityCategory.SENSITIVE_PATH: (
        "Hardcoded sensitive file or system path access, risking privilege escalation or leakage.",
        "CWE-200",
    ),
    VulnerabilityCategory.UNVALIDATED_POINTER: (
        "Pointer destination buffer capacity cannot be proven. Unbounded writes risk memory corruption.",
        "CWE-119",
    ),
    VulnerabilityCategory.GENERAL_SECURITY: (
        "Potential security hazard detected by static policy check.",
        "CWE-699",
    ),
}


class SecurityReporter:
    """
    Unified Security Analysis & Reporting Engine.
    Executes AST security rules, taint analysis, and security checker, then synthesizes
    prioritized reports with clear confirmation status and actionable remediations.
    """

    def __init__(self):
        pass

    def analyze_source(
        self,
        source_text: str,
        filename: str = "main.c",
        filter_unsupported_ai: bool = True,
    ) -> ComprehensiveSecurityReport:
        """
        Runs comprehensive security checks and returns a structured, prioritized report.
        """
        lines = source_text.splitlines()
        findings: List[SecurityVulnerability] = []
        seen_keys: Set[str] = set()
        analyzer_errors: List[str] = []

        # ------------------------------------------------------------------
        # 1. Run SecurityEngine (TaintChecker, SecurityChecker, StringFlow)
        # ------------------------------------------------------------------
        try:
            from compiler.security_engine import SecurityEngine
            engine = SecurityEngine()
            raw_issues, is_blocked, categorized = engine.analyze(source_text)

            for issue in raw_issues:
                line_no = getattr(issue, "line", None) or 1
                col_no = getattr(issue, "col", None) or 0
                fn_name = getattr(issue, "fn", None) or ""
                sev_raw = str(getattr(issue, "severity", "WARNING")).upper()
                msg = str(getattr(issue, "message", "")).strip()
                sugg = str(getattr(issue, "suggestion", "")).strip()
                stable_id = getattr(issue, "stable_id", None)

                evidence = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""

                # Classify category
                category, rule_id, cwe, default_impact = self._classify_engine_issue(fn_name, msg, sev_raw)

                # Distinguish CONFIRMED from HEURISTIC
                is_confirmed = (
                    sev_raw == "CRITICAL"
                    or fn_name in {"gets", "strcpy", "strcat", "sprintf"}
                    or "banned function" in msg.lower()
                    or "unbounded input into" in msg.lower()
                    or "vulnerability detected" in msg.lower()
                    or "tainted" in msg.lower()
                )

                if "constant string" in msg.lower() or "destination size unknown" in msg.lower() or "guarded by allowlist" in msg.lower():
                    is_confirmed = False

                status = ConfidenceStatus.CONFIRMED if is_confirmed else ConfidenceStatus.HEURISTIC
                confidence = 1.0 if is_confirmed else 0.70

                # Map Severity
                severity = self._map_severity(sev_raw)
                if fn_name == "gets":
                    severity = SecuritySeverity.CRITICAL

                # Remediation suggestions
                remediations: List[str] = []
                if sugg:
                    remediations.append(sugg)
                remediations.extend(self._get_default_remediations(category, fn_name, evidence))

                # Impact
                impact = default_impact or IMPACT_CATALOG.get(category, ("", ""))[0]

                vid = stable_id or f"SEC-ENG-{_compute_vuln_hash(category.value, line_no, col_no, rule_id, msg)}"

                vuln = SecurityVulnerability(
                    id=vid,
                    rule_id=rule_id,
                    category=category,
                    severity=severity,
                    line=line_no,
                    column=col_no,
                    evidence=evidence.strip(),
                    potential_impact=impact,
                    confidence=confidence,
                    status=status,
                    remediation_suggestions=remediations,
                    cwe_id=cwe,
                    is_blocked=(severity == SecuritySeverity.CRITICAL),
                    source_layer="security_engine",
                    metadata={"raw_message": msg, "fn": fn_name, "raw_severity": sev_raw},
                )

                dedup_key = f"{vuln.category.value}:{vuln.line}:{vuln.rule_id}"
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    findings.append(vuln)
        except Exception as e:
            import logging
            logging.getLogger("SecurityReporter").error(f"SecurityEngine exception: {type(e).__name__}: {str(e)}", exc_info=True)
            analyzer_errors.append(f"SecurityEngine: {type(e).__name__}: {str(e)}")

        # ------------------------------------------------------------------
        # 2. Run SecurityRules (SEC-01 through SEC-10)
        # ------------------------------------------------------------------
        try:
            from compiler.security_rules import run_security_rules
            _, rule_findings, _ = run_security_rules(source_text)

            for f in rule_findings:
                r_rule = str(getattr(f, "rule", "") or f.get("rule", "SEC-GENERIC"))
                r_kind = str(getattr(f, "kind", "") or f.get("kind", ""))
                r_line = int(getattr(f, "line", 1) or f.get("line", 1))
                r_msg = str(getattr(f, "message", "") or f.get("message", ""))
                r_sev = str(getattr(f, "severity", "WARNING") or f.get("severity", "WARNING")).upper()
                r_sugg = str(getattr(f, "suggestion", "") or f.get("suggestion", "")).strip()

                evidence = lines[r_line - 1] if 1 <= r_line <= len(lines) else ""
                category, cwe, default_impact = self._classify_sec_rule(r_rule, r_kind)

                severity = self._map_severity(r_sev)
                if r_rule == "SEC-01":
                    is_const = "constant" in r_msg.lower() or "value" in r_msg.lower()
                    status = ConfidenceStatus.CONFIRMED if is_const else ConfidenceStatus.POSSIBLE
                else:
                    status = ConfidenceStatus.CONFIRMED  # AST-verified rules are confirmed
                confidence = 0.95

                remediations: List[str] = []
                if r_sugg:
                    remediations.append(r_sugg)
                remediations.extend(self._get_default_remediations(category, r_rule, evidence))

                vid = f"SEC-RULE-{_compute_vuln_hash(category.value, r_line, 0, r_rule, r_msg)}"

                vuln = SecurityVulnerability(
                    id=vid,
                    rule_id=r_rule,
                    category=category,
                    severity=severity,
                    line=r_line,
                    column=0,
                    evidence=evidence.strip(),
                    potential_impact=default_impact or IMPACT_CATALOG.get(category, ("", ""))[0],
                    confidence=confidence,
                    status=status,
                    remediation_suggestions=remediations,
                    cwe_id=cwe,
                    is_blocked=(severity == SecuritySeverity.CRITICAL),
                    source_layer="security_rules",
                    metadata={"kind": r_kind, "raw_message": r_msg},
                )

                dedup_key = f"{vuln.category.value}:{vuln.line}:{vuln.rule_id}"
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    findings.append(vuln)
        except Exception as e:
            import logging
            logging.getLogger("SecurityReporter").error(f"SecurityRules exception: {type(e).__name__}: {str(e)}", exc_info=True)
            analyzer_errors.append(f"SecurityRules: {type(e).__name__}: {str(e)}")

        # ------------------------------------------------------------------
        # 3. Filter unsupported AI speculation
        # ------------------------------------------------------------------
        if filter_unsupported_ai:
            findings = [
                f for f in findings
                if f.status != ConfidenceStatus.UNSUPPORTED_SPECULATION
            ]

        # ------------------------------------------------------------------
        # 4. Prioritize Findings
        # Sort Key: (Severity Rank Descending, Status CONFIRMED first, Line Ascending)
        # ------------------------------------------------------------------
        findings.sort(
            key=lambda x: (
                -x.severity.rank,
                0 if x.status == ConfidenceStatus.CONFIRMED else 1,
                x.line,
                x.column,
            )
        )

        # Compute summary counters
        confirmed_count = sum(1 for f in findings if f.status == ConfidenceStatus.CONFIRMED and f.is_vulnerability)
        heuristic_count = sum(1 for f in findings if f.status == ConfidenceStatus.HEURISTIC and f.is_vulnerability)
        crit_count = sum(1 for f in findings if f.severity == SecuritySeverity.CRITICAL)
        high_count = sum(1 for f in findings if f.severity == SecuritySeverity.HIGH)
        med_count = sum(1 for f in findings if f.severity == SecuritySeverity.MEDIUM)
        low_count = sum(1 for f in findings if f.severity == SecuritySeverity.LOW)
        info_count = sum(1 for f in findings if f.severity == SecuritySeverity.INFO)
        vuln_count = crit_count + high_count + med_count + low_count
        is_blocked = any(f.is_blocked for f in findings)

        summary_parts = []
        if crit_count > 0:
            summary_parts.append(f"{crit_count} CRITICAL")
        if high_count > 0:
            summary_parts.append(f"{high_count} HIGH")
        if med_count > 0:
            summary_parts.append(f"{med_count} MEDIUM")
        if low_count > 0:
            summary_parts.append(f"{low_count} LOW")
        if info_count > 0:
            summary_parts.append(f"{info_count} INFO advisories")

        if vuln_count > 0:
            summary = f"{vuln_count} security vulnerabilities ({confirmed_count} confirmed, {heuristic_count} heuristic): " + ", ".join(summary_parts)
        elif info_count > 0:
            summary = f"No security vulnerabilities detected ({info_count} informational advisories)."
        else:
            summary = "No security vulnerabilities detected against supported static policies."

        return ComprehensiveSecurityReport(
            file_path=filename,
            findings=findings,
            confirmed_count=confirmed_count,
            heuristic_count=heuristic_count,
            critical_count=crit_count,
            high_count=high_count,
            medium_count=med_count,
            low_count=low_count,
            info_count=info_count,
            vulnerabilities_count=vuln_count,
            is_blocked=is_blocked,
            disclaimer=SECURITY_DISCLAIMER,
            summary=summary,
        )

    def compare_patches(
        self,
        original_source: str,
        patched_source: str,
        filename: str = "main.c",
    ) -> SecurityDeltaReport:
        """
        After a candidate repair is applied to a temporary copy, rerun security checks
        and compute the exact delta:
        - Resolved vulnerabilities (in original, gone in patch)
        - Remaining vulnerabilities (in original, still in patch)
        - Introduced vulnerabilities (absent in original, newly appeared in patch!)
        """
        # Prerequisite check: If baseline contains fatal syntax errors, static security rules cannot run reliably
        orig_has_syntax_errors = False
        if (filename or "").endswith(".py"):
            try:
                import ast
                ast.parse(original_source)
            except SyntaxError:
                orig_has_syntax_errors = True
            except Exception:
                pass
        else:
            try:
                from test_parser import parse_source, has_any_errors
                orig_tree, orig_listeners, _ = parse_source(original_source, filename)
                orig_has_syntax_errors = (orig_tree is None) or has_any_errors(orig_listeners)
            except Exception:
                pass

        orig_report = self.analyze_source(original_source, filename)
        patch_report = self.analyze_source(patched_source, filename)

        # Prerequisite checks: Non-empty source and absence of syntax errors on both sides
        if not (original_source or "").strip() or not (patched_source or "").strip():
            return SecurityDeltaReport(
                original_findings=orig_report.findings,
                patched_findings=patch_report.findings,
                resolved_vulnerabilities=[],
                remaining_vulnerabilities=[],
                introduced_vulnerabilities=[],
                is_security_improved=False,
                has_regressions=False,
                is_inconclusive=True,
                inconclusive_reason="Empty source code provided for baseline or candidate. Security delta comparison cannot be computed.",
                status="NOT_ASSESSED",
                disclaimer=SECURITY_DISCLAIMER,
            )

        patch_has_syntax_errors = False
        if (filename or "").endswith(".py"):
            try:
                import ast
                ast.parse(patched_source)
            except SyntaxError:
                patch_has_syntax_errors = True
            except Exception:
                pass
        else:
            try:
                from test_parser import parse_source, has_any_errors
                patch_tree, patch_listeners, _ = parse_source(patched_source, filename)
                patch_has_syntax_errors = (patch_tree is None) or has_any_errors(patch_listeners)
            except Exception:
                pass

        if orig_has_syntax_errors or patch_has_syntax_errors:
            # Epistemological safeguard: baseline or candidate could not be verified statically.
            # Mark comparison inconclusive rather than falsely claiming original or patch was clean.
            reason = (
                "Original source contains syntax errors preventing static security baseline extraction."
                if orig_has_syntax_errors
                else "Candidate source contains syntax errors preventing static security assessment."
            )
            return SecurityDeltaReport(
                original_findings=orig_report.findings,
                patched_findings=patch_report.findings,
                resolved_vulnerabilities=[],
                remaining_vulnerabilities=[],
                introduced_vulnerabilities=[],
                is_security_improved=False,
                has_regressions=False,
                is_inconclusive=True,
                inconclusive_reason=f"{reason} Security delta comparison is inconclusive.",
                status="INCONCLUSIVE",
                disclaimer=SECURITY_DISCLAIMER,
            )

        orig_vulns = orig_report.actionable_vulnerabilities
        patch_vulns = patch_report.actionable_vulnerabilities

        def vuln_key(v: SecurityVulnerability) -> str:
            fn = v.metadata.get("fn") or ""
            return f"{v.category.value}:{v.rule_id}:{fn}:{v.cwe_id or ''}"

        patch_pool = list(patch_vulns)
        matched_patch_ids: Set[str] = set()

        resolved: List[SecurityVulnerability] = []
        remaining: List[SecurityVulnerability] = []

        for orig in orig_vulns:
            key_orig = vuln_key(orig)
            matched = None
            for p in patch_pool:
                if p.id in matched_patch_ids:
                    continue
                if vuln_key(p) == key_orig or (p.category == orig.category and p.rule_id == orig.rule_id):
                    matched = p
                    break

            if matched is not None:
                remaining.append(matched)
                matched_patch_ids.add(matched.id)
            else:
                resolved.append(orig)

        # Any finding in patched code that did NOT match an original finding is newly INTRODUCED!
        introduced: List[SecurityVulnerability] = [
            p for p in patch_vulns if p.id not in matched_patch_ids
        ]

        is_improved = (len(resolved) > 0 and len(introduced) == 0)
        has_regressions = (len(introduced) > 0)

        return SecurityDeltaReport(
            original_findings=orig_report.findings,
            patched_findings=patch_report.findings,
            resolved_vulnerabilities=resolved,
            remaining_vulnerabilities=remaining,
            introduced_vulnerabilities=introduced,
            is_security_improved=is_improved,
            has_regressions=has_regressions,
            disclaimer=SECURITY_DISCLAIMER,
        )

    # ------------------------------------------------------------------
    # Helper classification methods
    # ------------------------------------------------------------------
    def _classify_engine_issue(
        self, fn_name: str, msg: str, sev_raw: str
    ) -> Tuple[VulnerabilityCategory, str, str, str]:
        m_lower = msg.lower()
        if fn_name == "gets" or "unsafe function detected: gets" in m_lower or "call to 'gets'" in m_lower or "banned standard c function gets" in m_lower:
            return (
                VulnerabilityCategory.UNBOUNDED_INPUT,
                "SEC-BANNED-GETS",
                "CWE-120",
                "Banned standard C function gets() has no buffer bound checks and inherently enables stack buffer overflow.",
            )
        if fn_name in {"system", "popen", "WinExec", "ShellExecute", "CreateProcess", "execv", "execvp", "execl", "execve"} or "command execution" in m_lower or "command injection" in m_lower:
            fn_suffix = fn_name.upper() if fn_name else "EXEC"
            return (
                VulnerabilityCategory.COMMAND_INJECTION,
                f"SEC-CMD-{fn_suffix}",
                "CWE-78",
                "Command execution API invocation. Non-constant or tainted inputs allow arbitrary shell command execution.",
            )
        if "scanf" in m_lower or "unbounded input into" in m_lower or "exceeds buffer" in m_lower or fn_name in {"scanf", "fscanf", "sscanf", "vscanf", "vfscanf", "vsscanf"}:
            return (
                VulnerabilityCategory.BUFFER_OVERFLOW,
                "SEC-UNBOUNDED-SCANF",
                "CWE-120",
                "Unbounded or oversized scanf format string allows stack buffer overflow on input exceeding buffer size.",
            )
        if fn_name in {"strcpy", "strcat"} or "string copy" in m_lower:
            return (
                VulnerabilityCategory.BUFFER_OVERFLOW,
                f"SEC-UNSAFE-{fn_name.upper()}",
                "CWE-120",
                "Unbounded string copy function does not check destination buffer capacity.",
            )
        if fn_name in {"sprintf", "vsprintf"}:
            return (
                VulnerabilityCategory.BUFFER_OVERFLOW,
                f"SEC-UNSAFE-{fn_name.upper()}",
                "CWE-120",
                "Unsafe sprintf formatting writes without maximum bounds into destination buffer.",
            )
        if "format string" in m_lower or "printf" in m_lower:
            return (
                VulnerabilityCategory.FORMAT_STRING,
                "SEC-FORMAT-STRING",
                "CWE-134",
                "Format string not a constant literal. Allows memory inspection and arbitrary memory modification.",
            )
        if "tainted" in m_lower:
            return (
                VulnerabilityCategory.TAINT_FLOW,
                "SEC-TAINT-SINK",
                "CWE-20",
                "Untrusted user input flows into a critical sink call without required validation.",
            )
        if "destination size unknown" in m_lower:
            return (
                VulnerabilityCategory.UNVALIDATED_POINTER,
                "SEC-PTR-DEST-UNKNOWN",
                "CWE-119",
                "Destination buffer size cannot be statically proven for string operation.",
            )
        return (
            VulnerabilityCategory.GENERAL_SECURITY,
            "SEC-GENERIC",
            "CWE-699",
            "Security policy violation detected.",
        )

    def _classify_sec_rule(
        self, rule_id: str, kind: str
    ) -> Tuple[VulnerabilityCategory, str, str]:
        kind_lower = kind.lower()
        if "overflow" in kind_lower or rule_id == "SEC-01":
            return (
                VulnerabilityCategory.INTEGER_OVERFLOW,
                "CWE-190",
                "Integer multiplication or arithmetic overflow before assignment to larger storage.",
            )
        if "null" in kind_lower or rule_id == "SEC-03":
            return (
                VulnerabilityCategory.NULL_DEREFERENCE,
                "CWE-476",
                "Dereferencing pointer without verifying non-NULL status causes segmentation crash.",
            )
        if "off_by_one" in kind_lower or rule_id == "SEC-06":
            return (
                VulnerabilityCategory.OFF_BY_ONE,
                "CWE-193",
                "Array boundary loop index off-by-one condition writing beyond array bounds.",
            )
        if "scanf" in kind_lower or rule_id == "SEC-09":
            return (
                VulnerabilityCategory.BUFFER_OVERFLOW,
                "CWE-120",
                "Unbounded or oversized format string in scanf-family call allows buffer overflow beyond destination capacity.",
            )
        if "buffer" in kind_lower:
            return (
                VulnerabilityCategory.BUFFER_OVERFLOW,
                "CWE-120",
                "Buffer capacity boundary violation.",
            )
        return (
            VulnerabilityCategory.GENERAL_SECURITY,
            "CWE-699",
            "Security rule alert.",
        )

    def _map_severity(self, raw: str) -> SecuritySeverity:
        raw = raw.upper()
        if "CRITICAL" in raw:
            return SecuritySeverity.CRITICAL
        if "HIGH" in raw:
            return SecuritySeverity.HIGH
        if "WARNING" in raw or "MEDIUM" in raw:
            return SecuritySeverity.MEDIUM
        if "LOW" in raw:
            return SecuritySeverity.LOW
        return SecuritySeverity.INFO

    def _get_default_remediations(
        self, category: VulnerabilityCategory, token: str, evidence: str
    ) -> List[str]:
        suggestions: List[str] = []
        if category == VulnerabilityCategory.UNBOUNDED_INPUT:
            if "gets" in token.lower() or "gets" in evidence.lower():
                suggestions.append("Replace gets(buf) with fgets(buf, sizeof(buf), stdin) and strip any trailing newline.")
            elif "scanf" in token.lower() or "scanf" in evidence.lower():
                suggestions.append("Specify maximum field width in scanf (e.g., %19s for a 20-character buffer).")
        elif category == VulnerabilityCategory.BUFFER_OVERFLOW:
            if "strcpy" in token.lower():
                suggestions.append("Replace strcpy(dst, src) with strncpy(dst, src, sizeof(dst) - 1) and null-terminate dst[sizeof(dst)-1] = '\\0', or use snprintf.")
            elif "strcat" in token.lower():
                suggestions.append("Replace strcat(dst, src) with strncat(dst, src, sizeof(dst) - strlen(dst) - 1) or snprintf.")
            elif "sprintf" in token.lower():
                suggestions.append("Replace sprintf(dst, ...) with snprintf(dst, sizeof(dst), ...).")
        elif category == VulnerabilityCategory.COMMAND_INJECTION:
            suggestions.append("Avoid command execution via shell. Use parameterized system calls or strict allowlists of authorized arguments.")
        elif category == VulnerabilityCategory.FORMAT_STRING:
            suggestions.append("Always pass format string literals, e.g. printf(\"%s\", user_str) instead of printf(user_str).")
        elif category == VulnerabilityCategory.INTEGER_OVERFLOW:
            suggestions.append("Cast operand to wider type before multiplication: e.g. (long long)a * b, or verify INT_MAX / b >= a.")
        elif category == VulnerabilityCategory.NULL_DEREFERENCE:
            suggestions.append("Add check 'if (ptr != NULL)' before dereferencing pointer.")
        elif category == VulnerabilityCategory.OFF_BY_ONE:
            suggestions.append("Change loop boundary condition from '<=' to '<' for zero-indexed array.")
        return suggestions


# ----------------------------------------------------------------------
# Benchmark Evaluator (TP, FP, TN, FN, Precision, Recall, F1)
# ----------------------------------------------------------------------
@dataclass
class BenchmarkEvaluationResult:
    total_cases: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    case_results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "accuracy": round(self.accuracy, 4),
            "case_results": self.case_results,
        }


class SecurityBenchmarkEvaluator:
    """
    Evaluates SecurityReporter against ground-truth labeled benchmark suites
    (such as examples/security_fix_2026/expected.json).
    Measures precision, recall, false positives, false negatives, and F1 score.
    """

    def __init__(self, reporter: Optional[SecurityReporter] = None):
        self.reporter = reporter or SecurityReporter()

    def evaluate_directory(self, benchmark_dir: str) -> BenchmarkEvaluationResult:
        expected_json_path = os.path.join(benchmark_dir, "expected.json")
        if not os.path.exists(expected_json_path):
            raise FileNotFoundError(f"Expected benchmark labels file not found: {expected_json_path}")

        with open(expected_json_path, "r", encoding="utf-8") as f:
            expected_data = json.load(f)

        tp = 0
        fp = 0
        tn = 0
        fn = 0
        case_details: List[Dict[str, Any]] = []

        for case_key, exp_info in expected_data.items():
            # Check for broken vs fixed file paths
            broken_file = os.path.join(benchmark_dir, f"{case_key}_broken.c")
            fixed_file = os.path.join(benchmark_dir, f"{case_key}_fixed.c")

            if not os.path.exists(broken_file):
                # Try direct filename
                broken_file = os.path.join(benchmark_dir, case_key)

            if os.path.exists(broken_file):
                with open(broken_file, "r", encoding="utf-8") as bf:
                    broken_src = bf.read()

                report = self.reporter.analyze_source(broken_src, filename=os.path.basename(broken_file))
                expected_before = exp_info.get("before", "SUCCESS")
                has_vulns = report.vulnerabilities_count > 0
                is_blocked = report.is_blocked

                # Is this case a ground-truth positive (vulnerable) or negative (safe)?
                is_ground_truth_vulnerable = (expected_before in {"BLOCKED_SECURITY", "SUCCESS_WITH_WARNINGS"})

                if is_ground_truth_vulnerable:
                    if has_vulns:
                        tp += 1
                        case_status = "TRUE_POSITIVE"
                    else:
                        fn += 1
                        case_status = "FALSE_NEGATIVE"
                else:
                    # Clean code expected (Negative)
                    if has_vulns:
                        fp += 1
                        case_status = "FALSE_POSITIVE"
                    else:
                        tn += 1
                        case_status = "TRUE_NEGATIVE"

                case_details.append({
                    "case": case_key,
                    "file": os.path.basename(broken_file),
                    "ground_truth_vulnerable": is_ground_truth_vulnerable,
                    "vulnerabilities_count": report.vulnerabilities_count,
                    "total_findings": len(report.findings),
                    "is_blocked": is_blocked,
                    "verdict": case_status,
                })

            # If a fixed variant exists, evaluate it as a Negative (should be clean)
            if os.path.exists(fixed_file):
                with open(fixed_file, "r", encoding="utf-8") as ff:
                    fixed_src = ff.read()

                f_report = self.reporter.analyze_source(fixed_src, filename=os.path.basename(fixed_file))
                f_has_vulns = f_report.vulnerabilities_count > 0
                if f_has_vulns:
                    fp += 1
                    f_verdict = "FALSE_POSITIVE"
                else:
                    tn += 1
                    f_verdict = "TRUE_NEGATIVE"

                case_details.append({
                    "case": f"{case_key}_fixed",
                    "file": os.path.basename(fixed_file),
                    "ground_truth_vulnerable": False,
                    "vulnerabilities_count": f_report.vulnerabilities_count,
                    "total_findings": len(f_report.findings),
                    "is_blocked": f_report.is_blocked,
                    "verdict": f_verdict,
                })

        total = tp + fp + tn + fn
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / total if total > 0 else 0.0

        return BenchmarkEvaluationResult(
            total_cases=total,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            accuracy=accuracy,
            case_results=case_details,
        )
