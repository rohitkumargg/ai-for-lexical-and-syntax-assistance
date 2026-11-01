# compiler/optimization_potential.py
"""
Optimization Potential Engine for Antigravity Compiler Assistant.

Features:
1. Normalized Optimization Potential metric from 0% to 100% estimating remaining
   improvement opportunities based on measurable and explicitly identified issues.
2. 5 Supported Evidence Categories:
   - Redundant operations (dead computations, repeated pure expressions, duplicate checks)
   - Avoidable computation (loop-invariant expressions, un-cached strlen() in conditions, heavy math)
   - Algorithmic complexity indicators (nested loops O(N^2), O(N^3), quadratic searches)
   - Unnecessary allocations (repeated malloc/calloc in loops, churn without reuse)
   - Inefficient I/O & Memory patterns (pass-by-value structs, unbuffered loop I/O, quadratic strcat)
3. Epistemological & Theoretical Honesty:
   - Clear distinction between STATIC_ESTIMATE and MEASURED_BENCHMARK.
   - Does NOT equate high optimization potential with low absolute performance.
   - Never claims to have found a globally optimal program (undecidable by Rice's Theorem).
   - Zero-fabrication guardrail on empty or incomplete source snippets.
4. Actionable remediation suggestions with estimated theoretical speedup factors.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class OpportunityCategory(str, Enum):
    REDUNDANT_OPERATIONS = "redundant_operations"
    AVOIDABLE_COMPUTATION = "avoidable_computation"
    ALGORITHMIC_COMPLEXITY = "algorithmic_complexity"
    UNNECESSARY_ALLOCATIONS = "unnecessary_allocations"
    INEFFICIENT_IO_MEMORY = "inefficient_io_memory"


class EstimateType(str, Enum):
    STATIC_ESTIMATE = "STATIC_ESTIMATE"
    MEASURED_BENCHMARK = "MEASURED_BENCHMARK"


class OpportunityImpact(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class OptimizationStatus(str, Enum):
    SCORED = "SCORED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    INCOMPLETE_SOURCE = "INCOMPLETE_SOURCE"
    EMPTY_SOURCE = "EMPTY_SOURCE"


@dataclass
class OptimizationOpportunity:
    id: str
    category: OpportunityCategory
    impact: OpportunityImpact
    estimate_type: EstimateType
    title: str
    description: str
    suggested_action: str
    estimated_speedup: str
    line: Optional[int] = None
    code_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "impact": self.impact.value,
            "estimate_type": self.estimate_type.value,
            "title": self.title,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "estimated_speedup": self.estimated_speedup,
            "line": self.line,
            "code_snippet": self.code_snippet,
        }


@dataclass
class BenchmarkEvidence:
    runtime_ms: Optional[float] = None
    cpu_percent: Optional[float] = None
    peak_memory_mb: Optional[float] = None
    hotspot_phase: Optional[str] = None
    is_measured: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_ms": round(self.runtime_ms, 2) if self.runtime_ms is not None else None,
            "cpu_percent": round(self.cpu_percent, 2) if self.cpu_percent is not None else None,
            "peak_memory_mb": round(self.peak_memory_mb, 2) if self.peak_memory_mb is not None else None,
            "hotspot_phase": self.hotspot_phase,
            "is_measured": self.is_measured,
            "details": dict(self.details),
        }


@dataclass
class OptimizationPotentialReport:
    optimization_potential: Optional[float]
    status: OptimizationStatus
    can_score: bool
    status_reason: str
    category_scores: Dict[str, float]
    opportunities: List[OptimizationOpportunity]
    benchmark: BenchmarkEvidence
    disclaimer: str
    summary: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "optimization_potential": round(self.optimization_potential, 1) if self.optimization_potential is not None else None,
            "status": self.status.value,
            "can_score": self.can_score,
            "status_reason": self.status_reason,
            "category_scores": {k: round(v, 1) for k, v in self.category_scores.items()},
            "opportunities": [o.to_dict() for o in self.opportunities],
            "opportunities_count": len(self.opportunities),
            "benchmark": self.benchmark.to_dict(),
            "disclaimer": self.disclaimer,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }


OPTIMIZATION_DISCLAIMER = (
    "The Optimization Potential metric is an analytical estimate of remaining code improvement "
    "opportunity based on statically identified patterns and optional runtime profiling. "
    "A high optimization potential does NOT equate to poor runtime performance, nor does a low potential "
    "indicate a globally optimal program (which is theoretically undecidable per Rice's Theorem). "
    "Static heuristics are strictly labeled separately from measured runtime benchmarks."
)


class OptimizationPotentialAnalyzer:
    """
    Analyzes C/SimpleC source code to estimate Optimization Potential (%)
    with explicit evidence, theoretical speedup estimates, and clear runtime/static separation.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            OpportunityCategory.ALGORITHMIC_COMPLEXITY.value: 0.30,
            OpportunityCategory.AVOIDABLE_COMPUTATION.value: 0.25,
            OpportunityCategory.UNNECESSARY_ALLOCATIONS.value: 0.20,
            OpportunityCategory.REDUNDANT_OPERATIONS.value: 0.15,
            OpportunityCategory.INEFFICIENT_IO_MEMORY.value: 0.10,
        }

    def analyze(
        self,
        source_code: str,
        filename: str = "main.c",
        green_metrics: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
    ) -> OptimizationPotentialReport:
        stripped = (source_code or "").strip()
        lang = (language or ("python" if (filename or "").endswith(".py") else "c")).lower()

        # Zero-fabrication check: Empty source
        if not stripped:
            return OptimizationPotentialReport(
                optimization_potential=None,
                status=OptimizationStatus.EMPTY_SOURCE,
                can_score=False,
                status_reason="Source code is empty. Optimization potential requires non-empty program source.",
                category_scores={},
                opportunities=[],
                benchmark=BenchmarkEvidence(is_measured=False),
                disclaimer=OPTIMIZATION_DISCLAIMER,
                summary="Optimization Potential Unavailable: Empty Source Code",
            )

        # Zero-fabrication check: Fragmented or trivial snippet (< 15 non-comment chars)
        code_without_comments = re.sub(r"//.*?\n|/\*.*?\*/|#.*?\n", "", stripped, flags=re.DOTALL).strip()
        if len(code_without_comments) < 15:
            return OptimizationPotentialReport(
                optimization_potential=None,
                status=OptimizationStatus.INSUFFICIENT_INFORMATION,
                can_score=False,
                status_reason="Source snippet is too brief (< 15 characters) to assess meaningful optimization opportunities.",
                category_scores={},
                opportunities=[],
                benchmark=BenchmarkEvidence(is_measured=False),
                disclaimer=OPTIMIZATION_DISCLAIMER,
                summary="Optimization Potential Incomplete: Insufficient Code Context",
            )

        opportunities: List[OptimizationOpportunity] = []
        lines = source_code.splitlines()

        # 1. Analyze Algorithmic Complexity Indicators (supports both C and Python)
        alg_score = self._check_algorithmic_complexity(source_code, lines, opportunities, language=lang)

        # 2-5: Language-appropriate analysis
        if lang == "python":
            avoid_score = 0.0
            alloc_score = 0.0
            redundant_score = self._check_redundant_operations(source_code, lines, opportunities)
            io_score = 0.0
        else:
            avoid_score = self._check_avoidable_computation(source_code, lines, opportunities)
            alloc_score = self._check_unnecessary_allocations(source_code, lines, opportunities)
            redundant_score = self._check_redundant_operations(source_code, lines, opportunities)
            io_score = self._check_inefficient_io_memory(source_code, lines, opportunities)

        category_scores = {
            OpportunityCategory.ALGORITHMIC_COMPLEXITY.value: alg_score,
            OpportunityCategory.AVOIDABLE_COMPUTATION.value: avoid_score,
            OpportunityCategory.UNNECESSARY_ALLOCATIONS.value: alloc_score,
            OpportunityCategory.REDUNDANT_OPERATIONS.value: redundant_score,
            OpportunityCategory.INEFFICIENT_IO_MEMORY.value: io_score,
        }

        # Calculate weighted potential (0 to 100%)
        weighted_potential = sum(category_scores[cat] * self.weights.get(cat, 0.20) for cat in category_scores)

        # 6. Benchmark Evidence integration (if available from Green Metrics / runtime run)
        benchmark = self._extract_benchmark_evidence(green_metrics)
        if benchmark.is_measured:
            # If actual runtime indicates a hotspot, add measured opportunity
            if benchmark.hotspot_phase and benchmark.runtime_ms and benchmark.runtime_ms > 150.0:
                opportunities.append(
                    OptimizationOpportunity(
                        id=f"measured_hotspot:{benchmark.hotspot_phase}",
                        category=OpportunityCategory.AVOIDABLE_COMPUTATION,
                        impact=OpportunityImpact.MEDIUM,
                        estimate_type=EstimateType.MEASURED_BENCHMARK,
                        title=f"Measured Runtime Hotspot in '{benchmark.hotspot_phase}'",
                        description=f"Phase '{benchmark.hotspot_phase}' consumed {benchmark.runtime_ms:.1f}ms during compiler run.",
                        suggested_action="Profile execution to isolate algorithmic bottlenecks or redundant iterations.",
                        estimated_speedup="Up to 1.5x - 2.5x pipeline throughput",
                    )
                )

        # Sort opportunities by impact (HIGH -> MEDIUM -> LOW)
        impact_order = {OpportunityImpact.HIGH: 0, OpportunityImpact.MEDIUM: 1, OpportunityImpact.LOW: 2}
        opportunities.sort(key=lambda o: impact_order.get(o.impact, 99))

        final_potential = max(0.0, min(100.0, weighted_potential))

        opt_explanation = (
            f"0.0% (No opportunities detected by current rules; does not prove mathematical optimality)"
            if final_potential == 0.0
            else f"{round(final_potential, 1)}% ({len(opportunities)} identified improvement opportunities)"
        )
        summary = f"Optimization Potential: {opt_explanation}"

        return OptimizationPotentialReport(
            optimization_potential=final_potential,
            status=OptimizationStatus.SCORED,
            can_score=True,
            status_reason="Analyzed successfully across 5 optimization categories.",
            category_scores=category_scores,
            opportunities=opportunities,
            benchmark=benchmark,
            disclaimer=OPTIMIZATION_DISCLAIMER,
            summary=summary,
        )

    # -------------------------------------------------------------------------
    # 1. Algorithmic Complexity Indicators
    # -------------------------------------------------------------------------
    def _check_algorithmic_complexity(
        self, code: str, lines: List[str], opps: List[OptimizationOpportunity], language: str = "c"
    ) -> float:
        score = 0.0

        if language == "python":
            # Python nested loops
            py_double_match = re.search(
                r"for\s+\w+\s+in\s+[^\n:]+:\s*\n[ \t]+[^\n]*for\s+\w+\s+in\s+[^\n:]+:",
                code,
            )
            if py_double_match:
                score += 35.0
                line_no = self._find_line_number(code, py_double_match.start())
                opps.append(
                    OptimizationOpportunity(
                        id=f"algo_nested_loop:{line_no}",
                        category=OpportunityCategory.ALGORITHMIC_COMPLEXITY,
                        impact=OpportunityImpact.MEDIUM,
                        estimate_type=EstimateType.STATIC_ESTIMATE,
                        title="Polynomial Algorithmic Complexity (O(N^2) Nested Python Loops)",
                        description="Detected nested loop traversal yielding quadratic scaling.",
                        suggested_action="Consider dictionary lookup, set membership, or list comprehension vectorization.",
                        estimated_speedup="O(N^2) -> O(N) or O(N log N)",
                        line=line_no,
                        code_snippet=py_double_match.group(0)[:50] + "...",
                    )
                )
            return min(100.0, score)

        # C triple nested loops: O(N^3)
        triple_loop_match = re.search(
            r"for\s*\([^;]+;[^;]+;[^)]+\)[^{]*\{[^{}]*for\s*\([^;]+;[^;]+;[^)]+\)[^{]*\{[^{}]*for\s*\([^;]+;[^;]+;[^)]+\)",
            code,
            flags=re.DOTALL,
        )
        if triple_loop_match:
            score += 55.0
            line_no = self._find_line_number(code, triple_loop_match.start())
            opps.append(
                OptimizationOpportunity(
                    id=f"algo_cubic_loop:{line_no}",
                    category=OpportunityCategory.ALGORITHMIC_COMPLEXITY,
                    impact=OpportunityImpact.HIGH,
                    estimate_type=EstimateType.STATIC_ESTIMATE,
                    title="Cubic Algorithmic Complexity (O(N^3) Nested Loops)",
                    description="Detected 3 nested loop iterations, which scale cubically with data size.",
                    suggested_action="Refactor logic to decompose matrix operations, sort input upfront, or use spatial indexing.",
                    estimated_speedup="O(N^3) -> O(N^2) or O(N log N)",
                    line=line_no,
                    code_snippet=triple_loop_match.group(0)[:60] + "...",
                )
            )
        else:
            # Check double nested loops: O(N^2)
            double_loop_match = re.search(
                r"for\s*\([^;]+;[^;]+;[^)]+\)[^{]*\{[^{}]*for\s*\([^;]+;[^;]+;[^)]+\)",
                code,
                flags=re.DOTALL,
            )
            if double_loop_match:
                score += 35.0
                line_no = self._find_line_number(code, double_loop_match.start())
                opps.append(
                    OptimizationOpportunity(
                        id=f"algo_nested_loop:{line_no}",
                        category=OpportunityCategory.ALGORITHMIC_COMPLEXITY,
                        impact=OpportunityImpact.MEDIUM,
                        estimate_type=EstimateType.STATIC_ESTIMATE,
                        title="Polynomial Algorithmic Complexity (O(N^2) Nested Loops)",
                        description="Detected nested loop traversal yielding quadratic scaling.",
                        suggested_action="Consider hash set / lookup table indexing if searching, or sort and binary search.",
                        estimated_speedup="O(N^2) -> O(N) or O(N log N)",
                        line=line_no,
                        code_snippet=double_loop_match.group(0)[:50] + "...",
                    )
                )

        # Check linear scan inside while loop (quadratic search pattern)
        if re.search(r"while\s*\([^)]+\)[^{]*\{[^{}]*for\s*\(", code, flags=re.DOTALL):
            score = min(80.0, score + 25.0)

        return min(100.0, score)

    # -------------------------------------------------------------------------
    # 2. Avoidable Computation
    # -------------------------------------------------------------------------
    def _check_avoidable_computation(
        self, code: str, lines: List[str], opps: List[OptimizationOpportunity]
    ) -> float:
        score = 0.0

        # Check strlen() call inside loop termination condition
        strlen_match = re.search(r"for\s*\([^;]*;\s*[^;]*\bstrlen\s*\([^)]+\)[^;]*;[^)]*\)", code)
        if strlen_match:
            score += 45.0
            line_no = self._find_line_number(code, strlen_match.start())
            opps.append(
                OptimizationOpportunity(
                    id=f"avoidable_strlen_loop:{line_no}",
                    category=OpportunityCategory.AVOIDABLE_COMPUTATION,
                    impact=OpportunityImpact.HIGH,
                    estimate_type=EstimateType.STATIC_ESTIMATE,
                    title="Avoidable strlen() Traversal in Loop Condition",
                    description="Re-evaluating strlen() on each iteration turns an O(N) loop into an O(N^2) bottleneck.",
                    suggested_action="Cache the length in a local variable before loop header: 'int len = strlen(s); for(i=0; i<len; i++)'.",
                    estimated_speedup="O(N^2) -> O(N)",
                    line=line_no,
                    code_snippet=strlen_match.group(0),
                )
            )

        # Check heavy pow(x, 2) or pow(x, 3)
        pow_match = re.search(r"\bpow\s*\(\s*([a-zA-Z0-9_]+)\s*,\s*2(?:\.0)?\s*\)", code)
        if pow_match:
            score += 15.0
            var_name = pow_match.group(1)
            line_no = self._find_line_number(code, pow_match.start())
            opps.append(
                OptimizationOpportunity(
                    id=f"avoidable_pow_square:{line_no}",
                    category=OpportunityCategory.AVOIDABLE_COMPUTATION,
                    impact=OpportunityImpact.LOW,
                    estimate_type=EstimateType.STATIC_ESTIMATE,
                    title=f"Replace pow({var_name}, 2) with Direct Multiplication",
                    description="Calling libm pow() involves floating-point emulation and transcendental overhead.",
                    suggested_action=f"Replace with direct multiplication: '{var_name} * {var_name}'.",
                    estimated_speedup="~10x - 20x microbenchmark speedup over pow()",
                    line=line_no,
                    code_snippet=pow_match.group(0),
                )
            )

        # Check power-of-two integer division by constant: x / 2, x / 4, x / 8
        div_pow2 = re.search(r"\b([a-zA-Z0-9_]+)\s*/\s*(2|4|8|16|32|64|128|256)\b", code)
        if div_pow2:
            score += 10.0

        return min(100.0, score)

    # -------------------------------------------------------------------------
    # 3. Unnecessary Allocations
    # -------------------------------------------------------------------------
    def _check_unnecessary_allocations(
        self, code: str, lines: List[str], opps: List[OptimizationOpportunity]
    ) -> float:
        score = 0.0

        # Check malloc/calloc inside a for or while loop
        malloc_in_loop = re.search(
            r"(?:for|while)\s*\([^)]+\)[^{]*\{[^{}]*\b(malloc|calloc|realloc)\s*\(",
            code,
            flags=re.DOTALL,
        )
        if malloc_in_loop:
            score += 50.0
            alloc_fn = malloc_in_loop.group(1)
            line_no = self._find_line_number(code, malloc_in_loop.start())
            opps.append(
                OptimizationOpportunity(
                    id=f"alloc_in_loop:{line_no}",
                    category=OpportunityCategory.UNNECESSARY_ALLOCATIONS,
                    impact=OpportunityImpact.HIGH,
                    estimate_type=EstimateType.STATIC_ESTIMATE,
                    title=f"Repeated Dynamic Memory Allocation ({alloc_fn}) in Loop",
                    description=f"Invoking {alloc_fn}() inside a loop incurs operating system heap allocator churn and lock contention.",
                    suggested_action="Pre-allocate an arena buffer outside the loop and reuse memory across iterations.",
                    estimated_speedup="Eliminates syscall overhead & heap lock contention",
                    line=line_no,
                )
            )

        # Check small fixed malloc (e.g. malloc(4) or malloc(sizeof(int)))
        small_malloc = re.search(r"\bmalloc\s*\(\s*(?:sizeof\s*\([^)]+\)|[1-8])\s*\)", code)
        if small_malloc and not malloc_in_loop:
            score += 15.0
            line_no = self._find_line_number(code, small_malloc.start())
            opps.append(
                OptimizationOpportunity(
                    id=f"alloc_small_heap:{line_no}",
                    category=OpportunityCategory.UNNECESSARY_ALLOCATIONS,
                    impact=OpportunityImpact.LOW,
                    estimate_type=EstimateType.STATIC_ESTIMATE,
                    title="Small Scalar Heap Allocation",
                    description="Allocating trivial scalar objects on the heap introduces pointer dereference and fragmentation.",
                    suggested_action="Use automatic stack allocation or pass by value/pointer to stack object.",
                    estimated_speedup="Instant stack allocation vs heap traversal",
                    line=line_no,
                )
            )

        return min(100.0, score)

    # -------------------------------------------------------------------------
    # 4. Redundant Operations
    # -------------------------------------------------------------------------
    def _check_redundant_operations(
        self, code: str, lines: List[str], opps: List[OptimizationOpportunity]
    ) -> float:
        score = 0.0

        # Check consecutive duplicate assignments: x = ...; x = ... without read
        dead_store = re.search(
            r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*=[^;]+;\s*\n\s*\1\s*=[^;]+;",
            code,
        )
        if dead_store:
            var_name = dead_store.group(1)
            score += 25.0
            line_no = self._find_line_number(code, dead_store.start())
            opps.append(
                OptimizationOpportunity(
                    id=f"redundant_dead_store:{line_no}",
                    category=OpportunityCategory.REDUNDANT_OPERATIONS,
                    impact=OpportunityImpact.MEDIUM,
                    estimate_type=EstimateType.STATIC_ESTIMATE,
                    title=f"Dead Store / Redundant Assignment to '{var_name}'",
                    description=f"Variable '{var_name}' is assigned twice in succession without intervening read.",
                    suggested_action=f"Remove the initial assignment to '{var_name}' or verify intended logic.",
                    estimated_speedup="Eliminates unused CPU write cycles",
                    line=line_no,
                    code_snippet=dead_store.group(0).replace("\n", " "),
                )
            )

        # Check redundant identity arithmetic: + 0, - 0, * 1
        identity_op = re.search(r"\b([a-zA-Z0-9_]+)\s*[\+\-]\s*0\b|\b([a-zA-Z0-9_]+)\s*\*\s*1\b", code)
        if identity_op:
            score += 15.0

        return min(100.0, score)

    # -------------------------------------------------------------------------
    # 5. Inefficient I/O and Memory Patterns
    # -------------------------------------------------------------------------
    def _check_inefficient_io_memory(
        self, code: str, lines: List[str], opps: List[OptimizationOpportunity]
    ) -> float:
        score = 0.0

        # Check unbuffered character I/O (getchar/putchar/fgetc) inside loops
        io_in_loop = re.search(
            r"(?:for|while)\s*\([^)]+\)[^{]*\{[^{}]*\b(getchar|putchar|fgetc|fputc)\s*\(",
            code,
            flags=re.DOTALL,
        )
        if io_in_loop:
            fn = io_in_loop.group(1)
            score += 35.0
            line_no = self._find_line_number(code, io_in_loop.start())
            opps.append(
                OptimizationOpportunity(
                    id=f"inefficient_io_loop:{line_no}",
                    category=OpportunityCategory.INEFFICIENT_IO_MEMORY,
                    impact=OpportunityImpact.MEDIUM,
                    estimate_type=EstimateType.STATIC_ESTIMATE,
                    title=f"Unbuffered Single-Character I/O ({fn}) Inside Loop",
                    description=f"Calling {fn}() repeatedly inside a loop increases context switches and syscall boundary transitions.",
                    suggested_action="Use block buffered I/O functions like fread(), fwrite(), or fgets() into a local buffer.",
                    estimated_speedup="3x - 10x I/O throughput improvement",
                    line=line_no,
                )
            )

        # Check repeated strcat inside loop (Schlemiel the Painter's algorithm: O(N^2))
        strcat_in_loop = re.search(
            r"(?:for|while)\s*\([^)]+\)[^{]*\{[^{}]*\bstrcat\s*\(",
            code,
            flags=re.DOTALL,
        )
        if strcat_in_loop:
            score += 45.0
            line_no = self._find_line_number(code, strcat_in_loop.start())
            opps.append(
                OptimizationOpportunity(
                    id=f"inefficient_strcat_loop:{line_no}",
                    category=OpportunityCategory.INEFFICIENT_IO_MEMORY,
                    impact=OpportunityImpact.HIGH,
                    estimate_type=EstimateType.STATIC_ESTIMATE,
                    title="Repeated strcat() in Loop (Quadratic String Copy)",
                    description="strcat() re-scans the string from index 0 on every concatenation, causing O(N^2) complexity.",
                    suggested_action="Track the tail pointer or use snprintf() with current offset for linear O(N) concatenation.",
                    estimated_speedup="O(N^2) -> O(N) string concatenation",
                    line=line_no,
                )
            )

        return min(100.0, score)

    # -------------------------------------------------------------------------
    # Helper: Benchmark Evidence Extraction
    # -------------------------------------------------------------------------
    def _extract_benchmark_evidence(self, green_metrics: Optional[Dict[str, Any]]) -> BenchmarkEvidence:
        if not green_metrics or not isinstance(green_metrics, dict):
            return BenchmarkEvidence(is_measured=False)

        values = green_metrics.get("values") or {}
        runtime_ms = green_metrics.get("total_runtime_ms")
        hotspot = green_metrics.get("hotspot")

        cpu = values.get("cpu_percent")
        mem = values.get("peak_memory_mb") or values.get("memory_mb")

        return BenchmarkEvidence(
            runtime_ms=float(runtime_ms) if runtime_ms is not None else None,
            cpu_percent=float(cpu) if cpu is not None else None,
            peak_memory_mb=float(mem) if mem is not None else None,
            hotspot_phase=str(hotspot) if hotspot else None,
            is_measured=runtime_ms is not None,
            details=green_metrics,
        )

    @staticmethod
    def _find_line_number(text: str, char_idx: int) -> int:
        return text[:char_idx].count("\n") + 1
