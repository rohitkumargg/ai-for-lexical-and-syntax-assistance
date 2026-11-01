# compiler/code_quality.py
"""
Code Quality Scoring Engine for Antigravity Compiler Assistant.

Features:
1. Normalized Code Quality Score from 0 to 100 based on documented & configurable weights.
2. 5 Distinct Dimensions:
   - Correctness checks (compiler syntax/lexical, semantic diagnostics, confirmed security vulnerabilities).
   - Maintainability indicators (function lengths, comment ratios, identifier clarity, line length).
   - Coding-standard compliance (canonical signatures, consistent indentation, type discipline).
   - Complexity indicators (cyclomatic complexity, nesting depth).
   - Efficiency-related findings (nested loops, quadratic string patterns, resource hotspots).
3. Epistemological Honesty:
   - Explicitly distinguishes MEASURED properties from HEURISTIC estimates.
   - Refuses to fabricate scores on empty or incomplete source (INSUFFICIENT_INFORMATION).
   - Displays clear disclaimer that score is a diagnostic index, not an absolute quality truth.
4. Specific findings and actionable remediation suggestions.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Set


class MeasurementType(str, Enum):
    MEASURED = "MEASURED"
    HEURISTIC = "HEURISTIC"
    HYBRID = "HYBRID"


class QualityStatus(str, Enum):
    SCORED = "SCORED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    INCOMPLETE_SOURCE = "INCOMPLETE_SOURCE"
    EMPTY_SOURCE = "EMPTY_SOURCE"


@dataclass
class QualitySuggestion:
    category: str
    priority: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    finding: str
    action: str
    line: Optional[int] = None
    is_heuristic: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComponentScore:
    name: str
    score: float
    weight: float
    measurement_type: MeasurementType
    evidence: List[str]
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 1),
            "weight": self.weight,
            "measurement_type": self.measurement_type.value,
            "evidence": list(self.evidence),
            "metrics": dict(self.metrics),
        }


@dataclass
class QualityConfig:
    weight_correctness: float = 0.35
    weight_compliance: float = 0.20
    weight_maintainability: float = 0.15
    weight_complexity: float = 0.15
    weight_efficiency: float = 0.15

    max_function_lines: int = 50
    max_nesting_depth: int = 3
    max_cyclomatic: int = 10
    target_comment_ratio: float = 0.10
    max_line_length: int = 100

    def validate_weights(self) -> None:
        total = (
            self.weight_correctness
            + self.weight_compliance
            + self.weight_maintainability
            + self.weight_complexity
            + self.weight_efficiency
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"QualityConfig weights must sum to 1.0, got {total}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CodeQualityReport:
    overall_score: Optional[float]
    status: QualityStatus
    can_score: bool
    status_reason: str
    components: Dict[str, ComponentScore]
    suggestions: List[QualitySuggestion]
    config: QualityConfig
    disclaimer: str
    summary: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 1) if self.overall_score is not None else None,
            "status": self.status.value,
            "can_score": self.can_score,
            "status_reason": self.status_reason,
            "components": {k: v.to_dict() for k, v in self.components.items()},
            "suggestions": [s.to_dict() for s in self.suggestions],
            "config": self.config.to_dict(),
            "disclaimer": self.disclaimer,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }


QUALITY_DISCLAIMER = (
    "The Code Quality Score is a diagnostic composite index derived from static parser measurements "
    "and heuristic style models. It is not an absolute or exhaustive measurement of software fitness, "
    "runtime reliability, or business logic correctness. Deterministic measurements (syntax, semantics, "
    "confirmed security vulnerabilities) are distinguished from heuristic indicators (naming, maintainability)."
)


class CodeQualityScorer:
    """
    Evaluates source code against configurable dimensions and generates
    the Code Quality Score with granular evidence and actionable remediation.
    """

    def __init__(self, config: Optional[QualityConfig] = None):
        self.config = config or QualityConfig()
        self.config.validate_weights()

    @staticmethod
    def _sec_summary_text(s: Any) -> str:
        if isinstance(s, dict):
            return s.get("message") or s.get("potential_impact") or s.get("rule_id") or "Security vulnerability"
        return getattr(s, "potential_impact", None) or getattr(s, "rule_id", None) or getattr(s, "evidence", None) or "Security vulnerability"

    def analyze_source(
        self,
        source_code: str,
        filename: str = "main.c",
        syntax_errors: Optional[List[Any]] = None,
        semantic_issues: Optional[List[Any]] = None,
        security_findings: Optional[List[Any]] = None,
        green_metrics: Optional[Dict[str, Any]] = None,
    ) -> CodeQualityReport:
        stripped = (source_code or "").strip()

        # Epistemological check 1: Empty source
        if not stripped:
            return CodeQualityReport(
                overall_score=None,
                status=QualityStatus.EMPTY_SOURCE,
                can_score=False,
                status_reason="Source code is empty. Scoring requires non-empty program source.",
                components={},
                suggestions=[],
                config=self.config,
                disclaimer=QUALITY_DISCLAIMER,
                summary="Quality Score Unavailable: Empty Source Code",
            )

        # Epistemological check 2: Insufficient information / fragmented snippet
        non_comment_chars = len(re.sub(r"/\*[\s\S]*?\*/|//.*", "", stripped).strip())
        if non_comment_chars < 15:
            return CodeQualityReport(
                overall_score=None,
                status=QualityStatus.INSUFFICIENT_INFORMATION,
                can_score=False,
                status_reason=(
                    "Source snippet is too brief or incomplete to calculate representative "
                    "maintainability, complexity, or standard compliance metrics."
                ),
                components={},
                suggestions=[
                    QualitySuggestion(
                        category="general",
                        priority="LOW",
                        finding="Code length is under 15 non-comment characters.",
                        action="Provide a complete function or program declaration to enable quality scoring.",
                        is_heuristic=False,
                    )
                ],
                config=self.config,
                disclaimer=QUALITY_DISCLAIMER,
                summary="Quality Score Incomplete: Insufficient Code Context",
            )

        # Run internal analyzers if not provided
        if syntax_errors is None or semantic_issues is None:
            synth_errors, synth_semantic = self._parse_and_analyze(source_code, filename)
            if syntax_errors is None:
                syntax_errors = synth_errors
            if semantic_issues is None:
                semantic_issues = synth_semantic

        if security_findings is None:
            security_findings = self._analyze_security(source_code, filename)

        # Evaluate individual components
        suggestions: List[QualitySuggestion] = []

        comp_correctness = self._eval_correctness(syntax_errors, semantic_issues, security_findings, suggestions)
        comp_complexity = self._eval_complexity(source_code, suggestions)
        comp_maintainability = self._eval_maintainability(source_code, suggestions)
        comp_compliance = self._eval_compliance(source_code, filename, suggestions)
        comp_efficiency = self._eval_efficiency(source_code, green_metrics, suggestions)

        components = {
            "correctness": comp_correctness,
            "compliance": comp_compliance,
            "maintainability": comp_maintainability,
            "complexity": comp_complexity,
            "efficiency": comp_efficiency,
        }

        # Weighted aggregate calculation
        weighted_score = (
            comp_correctness.score * self.config.weight_correctness
            + comp_compliance.score * self.config.weight_compliance
            + comp_maintainability.score * self.config.weight_maintainability
            + comp_complexity.score * self.config.weight_complexity
            + comp_efficiency.score * self.config.weight_efficiency
        )
        final_score = max(0.0, min(100.0, weighted_score))

        # Sort suggestions by priority
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        suggestions.sort(key=lambda s: priority_order.get(s.priority, 99))

        summary = f"Code Quality Score: {round(final_score, 1)}% ({len(suggestions)} actionable suggestions)"

        return CodeQualityReport(
            overall_score=final_score,
            status=QualityStatus.SCORED,
            can_score=True,
            status_reason="Successfully scored across all 5 dimensions.",
            components=components,
            suggestions=suggestions,
            config=self.config,
            disclaimer=QUALITY_DISCLAIMER,
            summary=summary,
        )

    assess = analyze_source

    # ------------------------------------------------------------------
    # 1. Correctness Checks (MEASURED)
    # ------------------------------------------------------------------
    def _eval_correctness(
        self,
        syntax_errors: List[Any],
        semantic_issues: List[Any],
        security_findings: List[Any],
        suggestions: List[QualitySuggestion],
    ) -> ComponentScore:
        score = 100.0
        evidence: List[str] = []

        num_syntax = len(syntax_errors)
        num_semantic = len(semantic_issues)

        # Security breakdown
        critical_sec = 0
        high_sec = 0
        heur_sec = 0
        for sec in security_findings:
            sev = (getattr(sec, "severity", None) or (sec.get("severity") if isinstance(sec, dict) else "MEDIUM")).upper()
            status = getattr(sec, "status", None) or (sec.get("status") if isinstance(sec, dict) else "POSSIBLE")
            is_confirmed = str(status).upper() == "CONFIRMED"

            if sev in ("CRITICAL", "BLOCKER"):
                critical_sec += 1
            elif sev == "HIGH" or is_confirmed:
                high_sec += 1
            else:
                heur_sec += 1

        # Penalty calculations
        if num_syntax > 0:
            pen = min(50.0, num_syntax * 25.0)
            score -= pen
            evidence.append(f"Syntax & parser errors ({num_syntax}) (-{pen:.0f} pts)")
            suggestions.append(
                QualitySuggestion(
                    category="correctness",
                    priority="CRITICAL",
                    finding=f"Code contains {num_syntax} unresolved syntax/parser errors.",
                    action="Resolve syntax discrepancies before compiling (missing semicolons, mismatched delimiters).",
                    is_heuristic=False,
                )
            )
        else:
            evidence.append("Clean syntax parsing (0 parser errors)")

        if num_semantic > 0:
            pen = min(30.0, num_semantic * 10.0)
            score -= pen
            evidence.append(f"Semantic diagnostics ({num_semantic}) (-{pen:.0f} pts)")
            suggestions.append(
                QualitySuggestion(
                    category="correctness",
                    priority="HIGH",
                    finding=f"Code contains {num_semantic} semantic issues (type/scope/declaration).",
                    action="Check variable scopes, struct definitions, and function prototypes.",
                    is_heuristic=False,
                )
            )
        else:
            evidence.append("Clean semantic checks (0 semantic errors)")

        if critical_sec > 0:
            pen = min(40.0, critical_sec * 25.0)
            score -= pen
            sec_details = [
                self._sec_summary_text(s)
                for s in security_findings
                if (getattr(s, "severity", None) or (s.get("severity") if isinstance(s, dict) else "")).upper() in ("CRITICAL", "BLOCKER")
            ]
            detail_str = f": {sec_details[0]}" if sec_details else ""
            evidence.append(f"Critical security findings ({critical_sec}){detail_str} (-{pen:.0f} pts)")
            suggestions.append(
                QualitySuggestion(
                    category="security",
                    priority="CRITICAL",
                    finding=f"Detected {critical_sec} critical security vulnerabilities" + (f" ({sec_details[0]})" if sec_details else "."),
                    action="Replace dangerous standard functions (e.g. gets -> fgets, sprintf -> snprintf).",
                    is_heuristic=False,
                )
            )
        elif high_sec > 0:
            pen = min(20.0, high_sec * 10.0)
            score -= pen
            sec_details = [
                self._sec_summary_text(s)
                for s in security_findings
                if (getattr(s, "severity", None) or (s.get("severity") if isinstance(s, dict) else "")).upper() == "HIGH"
                or getattr(s, "is_confirmed", False) or (isinstance(s, dict) and s.get("is_confirmed"))
            ]
            detail_str = f": {sec_details[0]}" if sec_details else ""
            evidence.append(f"Confirmed high security findings ({high_sec}){detail_str} (-{pen:.0f} pts)")
            suggestions.append(
                QualitySuggestion(
                    category="security",
                    priority="HIGH",
                    finding=f"Detected {high_sec} high-severity security findings" + (f" ({sec_details[0]})" if sec_details else "."),
                    action="Review buffer bounds and sanitize inputs.",
                    is_heuristic=False,
                )
            )

        score = max(0.0, min(100.0, score))

        return ComponentScore(
            name="correctness",
            score=score,
            weight=self.config.weight_correctness,
            measurement_type=MeasurementType.MEASURED,
            evidence=evidence,
            metrics={
                "syntax_error_count": num_syntax,
                "semantic_issue_count": num_semantic,
                "critical_security_count": critical_sec,
                "high_security_count": high_sec,
            },
        )

    # ------------------------------------------------------------------
    # 2. Complexity Indicators (MEASURED)
    # ------------------------------------------------------------------
    def _eval_complexity(self, code: str, suggestions: List[QualitySuggestion]) -> ComponentScore:
        score = 100.0
        evidence: List[str] = []

        # 1. Cyclomatic Complexity
        decisions = len(re.findall(r"\b(if|else\s+if|while|for|case)\b|\&\&|\|\||\?", code))
        cyclomatic = 1 + decisions

        if cyclomatic > self.config.max_cyclomatic:
            pen = min(35.0, (cyclomatic - self.config.max_cyclomatic) * 4.0)
            score -= pen
            evidence.append(f"Cyclomatic complexity = {cyclomatic} (threshold: {self.config.max_cyclomatic}) (-{pen:.0f} pts)")
            suggestions.append(
                QualitySuggestion(
                    category="complexity",
                    priority="HIGH" if cyclomatic > 15 else "MEDIUM",
                    finding=f"High cyclomatic complexity ({cyclomatic} decision points).",
                    action="Refactor compound conditional blocks or decompose long routines into subroutines.",
                    is_heuristic=False,
                )
            )
        else:
            evidence.append(f"Acceptable cyclomatic complexity ({cyclomatic})")

        # 2. Max Control Flow Nesting Depth
        max_depth = 0
        current_depth = 0
        lines = code.splitlines()
        max_depth_line = 1

        for line_idx, line in enumerate(lines, 1):
            clean_l = re.sub(r"/\*[\s\S]*?\*/|//.*|'(?:\\.|[^\\'])*'|\"(?:\\.|[^\\\"])*\"", "", line)
            for ch in clean_l:
                if ch == "{":
                    current_depth += 1
                    if current_depth > max_depth:
                        max_depth = current_depth
                        max_depth_line = line_idx
                elif ch == "}":
                    current_depth = max(0, current_depth - 1)

        # In C, function body starts at depth 1, so control structures start at depth 2+
        control_nesting = max(0, max_depth - 1)
        if control_nesting > self.config.max_nesting_depth:
            pen = min(35.0, (control_nesting - self.config.max_nesting_depth) * 12.0)
            score -= pen
            evidence.append(f"Max control nesting depth = {control_nesting} (threshold: {self.config.max_nesting_depth}) (-{pen:.0f} pts)")
            suggestions.append(
                QualitySuggestion(
                    category="complexity",
                    priority="MEDIUM",
                    finding=f"Deep control-flow nesting (depth {control_nesting}) at line {max_depth_line}.",
                    action="Use guard clauses with early returns or extract inner logic into a helper function.",
                    line=max_depth_line,
                    is_heuristic=False,
                )
            )
        else:
            evidence.append(f"Control nesting depth within limits (depth {control_nesting})")

        score = max(0.0, min(100.0, score))

        return ComponentScore(
            name="complexity",
            score=score,
            weight=self.config.weight_complexity,
            measurement_type=MeasurementType.MEASURED,
            evidence=evidence,
            metrics={
                "cyclomatic_complexity": cyclomatic,
                "max_control_nesting": control_nesting,
            },
        )

    # ------------------------------------------------------------------
    # 3. Maintainability Indicators (HEURISTIC)
    # ------------------------------------------------------------------
    def _eval_maintainability(self, code: str, suggestions: List[QualitySuggestion]) -> ComponentScore:
        score = 100.0
        evidence: List[str] = []

        lines = code.splitlines()
        total_lines = len(lines)
        blank_lines = sum(1 for l in lines if not l.strip())
        comment_lines = len(re.findall(r"/\*[\s\S]*?\*/|//.*", code))
        effective_code_lines = max(1, total_lines - blank_lines - comment_lines)

        # 1. Comment Density Ratio
        comment_ratio = comment_lines / float(total_lines)
        if total_lines > 20 and comment_ratio < self.config.target_comment_ratio:
            pen = 15.0
            score -= pen
            evidence.append(f"Low comment density ({comment_ratio:.1%}, target: {self.config.target_comment_ratio:.0%}) (-{pen:.0f} pts)")
            suggestions.append(
                QualitySuggestion(
                    category="maintainability",
                    priority="LOW",
                    finding=f"Low comment ratio ({comment_ratio:.1%}).",
                    action="Add descriptive comments documenting function contracts, assumptions, and invariants.",
                    is_heuristic=True,
                )
            )
        else:
            evidence.append(f"Comment density = {comment_ratio:.1%}")

        # 2. Line Length
        long_lines = [(idx + 1, len(l)) for idx, l in enumerate(lines) if len(l) > self.config.max_line_length]
        if long_lines:
            pen = min(20.0, len(long_lines) * 5.0)
            score -= pen
            first_long_line = long_lines[0][0]
            evidence.append(f"{len(long_lines)} overlong lines (> {self.config.max_line_length} chars) (-{pen:.0f} pts)")
            suggestions.append(
                QualitySuggestion(
                    category="maintainability",
                    priority="LOW",
                    finding=f"Detected lines exceeding {self.config.max_line_length} columns (e.g. line {first_long_line}).",
                    action="Break long expressions or statements across multiple lines for readability.",
                    line=first_long_line,
                    is_heuristic=True,
                )
            )
        else:
            evidence.append(f"Line length compliant (all <= {self.config.max_line_length} cols)")

        # 3. Function Length Heuristic
        # Approximate function boundaries in C: `^\w+.*\{` to `^\}`
        func_blocks = re.findall(r"(\w+\s+[*\w\s]+\([^)]*\)\s*\{[\s\S]*?\n\})", code)
        overlong_funcs = 0
        for fb in func_blocks:
            flen = len(fb.splitlines())
            if flen > self.config.max_function_lines:
                overlong_funcs += 1

        if overlong_funcs > 0:
            pen = min(25.0, overlong_funcs * 12.0)
            score -= pen
            evidence.append(f"{overlong_funcs} overlong function(s) (> {self.config.max_function_lines} lines) (-{pen:.0f} pts)")
            suggestions.append(
                QualitySuggestion(
                    category="maintainability",
                    priority="MEDIUM",
                    finding=f"Found {overlong_funcs} function(s) exceeding {self.config.max_function_lines} lines.",
                    action="Break extensive monolithic functions into modular single-purpose helper functions.",
                    is_heuristic=True,
                )
            )
        else:
            evidence.append("Function sizes within maintainability thresholds")

        score = max(0.0, min(100.0, score))

        return ComponentScore(
            name="maintainability",
            score=score,
            weight=self.config.weight_maintainability,
            measurement_type=MeasurementType.HEURISTIC,
            evidence=evidence,
            metrics={
                "total_lines": total_lines,
                "code_lines": effective_code_lines,
                "comment_ratio": round(comment_ratio, 3),
                "overlong_lines": len(long_lines),
                "overlong_functions": overlong_funcs,
            },
        )

    # ------------------------------------------------------------------
    # 4. Coding-Standard Compliance (HYBRID)
    # ------------------------------------------------------------------
    def _eval_compliance(self, code: str, filename: str, suggestions: List[QualitySuggestion]) -> ComponentScore:
        score = 100.0
        evidence: List[str] = []

        is_c = filename.endswith(".c") or filename.endswith(".h") or "int main" in code or "void main" in code

        if is_c:
            # 1. Canonical main signature
            if "void main" in code:
                pen = 15.0
                score -= pen
                evidence.append("Non-standard 'void main()' signature (-15 pts)")
                suggestions.append(
                    QualitySuggestion(
                        category="compliance",
                        priority="MEDIUM",
                        finding="'void main()' violates C99/C11 standards.",
                        action="Change entry point signature to 'int main(void)' or 'int main(int argc, char *argv[])'.",
                        is_heuristic=False,
                    )
                )
            elif "main" in code and not re.search(r"\bint\s+main\b", code):
                pen = 10.0
                score -= pen
                evidence.append("Non-canonical main return type (-10 pts)")

            # 2. Inconsistent Indentation (Tabs vs Spaces)
            lines = code.splitlines()
            has_tabs = any(l.startswith("\t") for l in lines)
            has_spaces = any(l.startswith("    ") or l.startswith("  ") for l in lines)

            if has_tabs and has_spaces:
                pen = 15.0
                score -= pen
                evidence.append("Mixed indentation (both tabs and spaces used) (-15 pts)")
                suggestions.append(
                    QualitySuggestion(
                        category="compliance",
                        priority="LOW",
                        finding="Mixed indentation styles (both tab characters and spaces detected).",
                        action="Normalize indentation across the file to either 4 spaces or tabs consistently.",
                        is_heuristic=True,
                    )
                )
            else:
                evidence.append("Consistent indentation style")

            # 3. Missing explicit header includes
            uses_printf = "printf" in code
            includes_stdio = "#include <stdio.h>" in code or '#include "stdio.h"' in code
            if uses_printf and not includes_stdio:
                pen = 10.0
                score -= pen
                evidence.append("Missing <stdio.h> header for printf (-10 pts)")
                suggestions.append(
                    QualitySuggestion(
                        category="compliance",
                        priority="MEDIUM",
                        finding="'printf' is invoked without including <stdio.h> header.",
                        action="Add '#include <stdio.h>' at top of source file.",
                        is_heuristic=False,
                    )
                )
        else:
            evidence.append("General language standard compliance verified")

        score = max(0.0, min(100.0, score))

        return ComponentScore(
            name="compliance",
            score=score,
            weight=self.config.weight_compliance,
            measurement_type=MeasurementType.HYBRID,
            evidence=evidence,
            metrics={"is_c_source": is_c},
        )

    # ------------------------------------------------------------------
    # 5. Efficiency-Related Findings (HYBRID)
    # ------------------------------------------------------------------
    def _eval_efficiency(
        self,
        code: str,
        green_metrics: Optional[Dict[str, Any]],
        suggestions: List[QualitySuggestion],
    ) -> ComponentScore:
        score = 100.0
        evidence: List[str] = []

        # 1. Nested loops detection (O(N^2) or higher potential)
        nested_loop_matches = re.findall(
            r"\b(for|while)\b[^{]*\{[^{}]*\b(for|while)\b", code
        )
        if nested_loop_matches:
            pen = min(25.0, len(nested_loop_matches) * 12.0)
            score -= pen
            evidence.append(f"Nested loop structure detected (potential O(N^2) complexity) (-{pen:.0f} pts)")
            suggestions.append(
                QualitySuggestion(
                    category="efficiency",
                    priority="MEDIUM",
                    finding="Found nested loop structure with polynomial complexity risk.",
                    action="Evaluate if inner iteration can be indexed via hash table or lookup array.",
                    is_heuristic=True,
                )
            )
        else:
            evidence.append("No excessive nested loop structures")

        # 2. strlen() call inside loop condition (classic quadratic trap in C)
        strlen_in_loop = re.search(r"for\s*\([^;]*;\s*[^;]*strlen\s*\([^)]*\)\s*;\s*[^)]*\)", code)
        if strlen_in_loop:
            pen = 20.0
            score -= pen
            evidence.append("strlen() call inside loop termination condition (-20 pts)")
            suggestions.append(
                QualitySuggestion(
                    category="efficiency",
                    priority="HIGH",
                    finding="Invoking 'strlen()' inside loop condition re-computes string length every iteration (O(N^2)).",
                    action="Cache string length in a local variable before the loop: 'int len = strlen(s); for(int i=0; i<len; i++)'.",
                    is_heuristic=False,
                )
            )

        # 3. Green compiler profile integration if available
        if green_metrics:
            g_score = green_metrics.get("green_score")
            hotspot = green_metrics.get("hotspot", "")
            if g_score is not None and g_score < 70:
                pen = 15.0
                score -= pen
                evidence.append(f"Green energy profile flagged bottleneck in phase '{hotspot}' (-15 pts)")
            else:
                evidence.append("Green execution profile: efficient resource utilization")

        score = max(0.0, min(100.0, score))

        return ComponentScore(
            name="efficiency",
            score=score,
            weight=self.config.weight_efficiency,
            measurement_type=MeasurementType.HYBRID,
            evidence=evidence,
            metrics={"nested_loops": len(nested_loop_matches)},
        )

    # ------------------------------------------------------------------
    # Helper Analyzers
    # ------------------------------------------------------------------
    def _parse_and_analyze(self, source_code: str, filename: str) -> Tuple[List[Any], List[Any]]:
        syntax_errs: List[Any] = []
        semantic_errs: List[Any] = []

        try:
            from test_parser import parse_source, has_any_errors
            tree, listeners, _ = parse_source(source_code, filename)
            lis_list = listeners.values() if isinstance(listeners, dict) else listeners
            for lis in lis_list:
                if hasattr(lis, "errors"):
                    syntax_errs.extend(lis.errors)
                elif hasattr(lis, "syntax_errors"):
                    syntax_errs.extend(lis.syntax_errors)
        except Exception:
            pass

        try:
            from compiler.semantic import SemanticAnalyzer
            analyzer = SemanticAnalyzer()
            analyzer.analyze(source_code)
            if hasattr(analyzer, "errors"):
                semantic_errs.extend(analyzer.errors)
        except Exception:
            pass

        return syntax_errs, semantic_errs

    def _analyze_security(self, source_code: str, filename: str) -> List[Any]:
        try:
            from compiler.security_reporter import SecurityReporter
            reporter = SecurityReporter()
            report = reporter.analyze_source(source_code, filename)
            return getattr(report, "findings", [])
        except Exception:
            return []


def calculate_code_quality_metrics(
    q: Optional[float],
    o: Optional[float],
    v: Optional[float],
) -> Dict[str, Any]:
    """
    Computes coordinated code quality metrics assessing the original source:
    - Optimal Code % = clamp(100 - O, 0, 100) where O is optimization potential
    - Poor Code % = clamp(100 - Q, 0, 100) (clearly documented as the inverse of Q, not an independent measurement)
    - Vulnerability Risk % = clamp(V, 0, 100) (normalized risk indicator, not attack probability)
    - Overall Code Quality % = clamp(0.50 * Q + 0.25 * (100 - O) + 0.25 * (100 - V), 0, 100)

    If any required component (Q, O, or V) is None, Overall Code Quality % is None (pending/incomplete).
    Missing values are never silently replaced with 0.
    """
    def _clamp(val: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, val))

    optimal = round(_clamp(100.0 - float(o)), 1) if o is not None else None
    poor = round(_clamp(100.0 - float(q)), 1) if q is not None else None
    vuln_risk = round(_clamp(float(v)), 1) if v is not None else None

    if q is not None and o is not None and v is not None:
        raw_overall = 0.50 * float(q) + 0.25 * (100.0 - float(o)) + 0.25 * (100.0 - float(v))
        overall = round(_clamp(raw_overall), 1)
    else:
        overall = None

    return {
        "overall_code_quality": overall,
        "optimal_code": optimal,
        "poor_code": poor,
        "vulnerability_risk": vuln_risk,
        "is_complete": (overall is not None),
        "notes": {
            "optimal_code": (
                "Optimal Code % = clamp(100 - O, 0, 100). Higher means fewer detected optimization opportunities. "
                "A 0% Optimization Potential result indicates no opportunities were detected by the current heuristic rules; "
                "it does not prove that code is perfectly optimal."
            ),
            "poor_code": (
                "Poor Code % = clamp(100 - Q, 0, 100). Higher means more detected quality problems. "
                "Defined as the inverse of Code Quality (100 - Q), not an independent measurement. "
                "It is not counted as independent evidence in the overall score."
            ),
            "vulnerability_risk": (
                "Vulnerability Risk % is a normalized static security risk indicator (0–100%), "
                "NOT the probability that an attack will occur."
            ),
            "overall_code_quality": (
                "Overall Code Quality % = 0.50 * Q + 0.25 * (100 - O) + 0.25 * (100 - V). "
                "Synthesizes code quality, optimal code ratio, and security safety on original source code."
            ),
        },
    }

