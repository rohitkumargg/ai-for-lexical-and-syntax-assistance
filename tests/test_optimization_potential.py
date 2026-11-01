"""
Unit and Integration Tests for Optimization Potential (%) Engine and API.

Validates:
1. Optimization Potential metric (0% to 100%) based on measurable and explicitly identified issues.
2. 5 Evidence Categories:
   - Redundant operations (dead stores, duplicate assignments)
   - Avoidable computation (strlen() in loop conditions, pow() square)
   - Algorithmic complexity indicators (O(N^2), O(N^3) nested loops)
   - Unnecessary allocations (repeated malloc inside loops)
   - Inefficient I/O & Memory patterns (unbuffered single-char I/O, strcat in loops)
3. Epistemological and theoretical honesty:
   - Clear distinction between STATIC_ESTIMATE and MEASURED_BENCHMARK.
   - Disclaimer noting that high potential != poor performance, and no global optimality claim.
   - Zero-fabrication on empty or incomplete source snippets.
4. Actionable remediation suggestions with theoretical speedup estimates.
5. Flask REST endpoints (/api/optimization/potential, /api/optimization/config).
6. Integration into /api/repair payload.
"""
import pytest
from compiler.optimization_potential import (
    OptimizationPotentialAnalyzer,
    OptimizationPotentialReport,
    OptimizationStatus,
    OpportunityCategory,
    EstimateType,
    OpportunityImpact,
    OPTIMIZATION_DISCLAIMER,
)
from app import app


def test_zero_fabrication_on_empty_source():
    """Refuse to fabricate optimization potential when source code is empty."""
    analyzer = OptimizationPotentialAnalyzer()
    report = analyzer.analyze("")

    assert report.can_score is False
    assert report.optimization_potential is None
    assert report.status == OptimizationStatus.EMPTY_SOURCE
    assert "empty" in report.status_reason.lower()
    assert report.disclaimer == OPTIMIZATION_DISCLAIMER


def test_zero_fabrication_on_insufficient_fragment():
    """Refuse to fabricate optimization potential on trivial fragments (< 15 characters)."""
    analyzer = OptimizationPotentialAnalyzer()
    report = analyzer.analyze("int x;")

    assert report.can_score is False
    assert report.optimization_potential is None
    assert report.status == OptimizationStatus.INSUFFICIENT_INFORMATION
    assert "brief" in report.status_reason.lower() or "incomplete" in report.status_reason.lower()


def test_clean_code_low_optimization_potential():
    """Clean, linear code without detected anti-patterns has minimal optimization potential."""
    code = """
    #include <stdio.h>

    int add(int a, int b) {
        return a + b;
    }

    int main() {
        int res = add(5, 10);
        printf("%d\\n", res);
        return 0;
    }
    """
    analyzer = OptimizationPotentialAnalyzer()
    report = analyzer.analyze(code)

    assert report.can_score is True
    assert report.optimization_potential is not None
    assert report.optimization_potential <= 15.0
    assert len(report.opportunities) == 0


def test_algorithmic_complexity_nested_loops():
    """Detect polynomial O(N^2) and cubic O(N^3) nested loop structures."""
    cubic_code = """
    #include <stdio.h>

    void matrix_multiply(int n) {
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                for (int k = 0; k < n; k++) {
                    printf("%d", i * j * k);
                }
            }
        }
    }
    """
    analyzer = OptimizationPotentialAnalyzer()
    report = analyzer.analyze(cubic_code)

    assert report.can_score is True
    assert report.optimization_potential is not None
    assert report.optimization_potential >= 15.0
    assert report.category_scores[OpportunityCategory.ALGORITHMIC_COMPLEXITY.value] >= 50.0

    cubic_opps = [o for o in report.opportunities if o.category == OpportunityCategory.ALGORITHMIC_COMPLEXITY]
    assert len(cubic_opps) > 0
    assert cubic_opps[0].impact == OpportunityImpact.HIGH
    assert "cubic" in cubic_opps[0].title.lower()
    assert "O(N^3)" in cubic_opps[0].estimated_speedup


def test_avoidable_computation_strlen_and_pow():
    """Detect strlen() called inside loop condition and pow(x, 2) replaceable by multiplication."""
    code = """
    #include <stdio.h>
    #include <string.h>
    #include <math.h>

    void process(char *s, double x) {
        for (int i = 0; i < strlen(s); i++) {
            putchar(s[i]);
        }
        double sq = pow(x, 2);
        printf("%f", sq);
    }
    """
    analyzer = OptimizationPotentialAnalyzer()
    report = analyzer.analyze(code)

    assert report.can_score is True
    avoid_opps = [o for o in report.opportunities if o.category == OpportunityCategory.AVOIDABLE_COMPUTATION]
    assert len(avoid_opps) >= 2

    strlen_opp = next(o for o in avoid_opps if "strlen" in o.title.lower())
    assert strlen_opp.impact == OpportunityImpact.HIGH
    assert "cache" in strlen_opp.suggested_action.lower()

    pow_opp = next(o for o in avoid_opps if "pow" in o.title.lower())
    assert "multiplication" in pow_opp.title.lower()


def test_unnecessary_allocations_in_loop():
    """Detect repeated malloc() calls inside loop bodies."""
    code = """
    #include <stdio.h>
    #include <stdlib.h>

    void churn(int n) {
        for (int i = 0; i < n; i++) {
            char *buf = (char *)malloc(128);
            buf[0] = 'a';
            free(buf);
        }
    }
    """
    analyzer = OptimizationPotentialAnalyzer()
    report = analyzer.analyze(code)

    assert report.can_score is True
    alloc_opps = [o for o in report.opportunities if o.category == OpportunityCategory.UNNECESSARY_ALLOCATIONS]
    assert len(alloc_opps) > 0
    assert alloc_opps[0].impact == OpportunityImpact.HIGH
    assert "loop" in alloc_opps[0].title.lower()
    assert "pre-allocate" in alloc_opps[0].suggested_action.lower() or "arena" in alloc_opps[0].suggested_action.lower()


def test_redundant_operations_dead_store():
    """Detect consecutive dead store assignments to the same variable."""
    code = """
    #include <stdio.h>

    int compute() {
        int x = 10;
        x = 20;
        return x;
    }
    """
    analyzer = OptimizationPotentialAnalyzer()
    report = analyzer.analyze(code)

    assert report.can_score is True
    red_opps = [o for o in report.opportunities if o.category == OpportunityCategory.REDUNDANT_OPERATIONS]
    assert len(red_opps) > 0
    assert "dead store" in red_opps[0].title.lower()


def test_inefficient_io_unbuffered_loop():
    """Detect unbuffered single-character I/O calls inside loop."""
    code = """
    #include <stdio.h>

    void read_data(int n) {
        for (int i = 0; i < n; i++) {
            int ch = getchar();
            putchar(ch);
        }
    }
    """
    analyzer = OptimizationPotentialAnalyzer()
    report = analyzer.analyze(code)

    assert report.can_score is True
    io_opps = [o for o in report.opportunities if o.category == OpportunityCategory.INEFFICIENT_IO_MEMORY]
    assert len(io_opps) > 0
    assert "unbuffered" in io_opps[0].title.lower()


def test_static_vs_measured_benchmark_separation():
    """Verify clear labeling between STATIC_ESTIMATE and MEASURED_BENCHMARK."""
    code = """
    #include <stdio.h>
    int run() {
        for(int i=0; i<10; i++) {
            for(int j=0; j<10; j++) {
                printf("%d", i+j);
            }
        }
        return 0;
    }
    """
    analyzer = OptimizationPotentialAnalyzer()

    # Pure static analysis (no green metrics)
    report_static = analyzer.analyze(code)
    assert report_static.benchmark.is_measured is False
    assert all(o.estimate_type == EstimateType.STATIC_ESTIMATE for o in report_static.opportunities)

    # Measured benchmark analysis with runtime profile
    green_metrics = {
        "total_runtime_ms": 320.5,
        "hotspot": "syntax_repair",
        "values": {"cpu_percent": 45.0, "peak_memory_mb": 18.2},
    }
    report_measured = analyzer.analyze(code, green_metrics=green_metrics)
    assert report_measured.benchmark.is_measured is True
    assert report_measured.benchmark.runtime_ms == 320.5
    assert report_measured.benchmark.hotspot_phase == "syntax_repair"

    # Should include a measured benchmark opportunity
    measured_opps = [o for o in report_measured.opportunities if o.estimate_type == EstimateType.MEASURED_BENCHMARK]
    assert len(measured_opps) > 0
    assert "syntax_repair" in measured_opps[0].title


def test_epistemological_disclaimer_content():
    """Verify disclaimer explicitly states that high potential != poor performance and no global optimality."""
    analyzer = OptimizationPotentialAnalyzer()
    report = analyzer.analyze("int main() { return 0; }")
    assert report.disclaimer == OPTIMIZATION_DISCLAIMER
    assert "Rice's Theorem" in report.disclaimer
    assert "NOT equate to poor runtime performance" in report.disclaimer


def test_api_optimization_config_endpoint():
    """Verify GET /api/optimization/config returns documented categories and disclaimer."""
    client = app.test_client()
    resp = client.get("/api/optimization/config")
    assert resp.status_code == 200

    data = resp.get_json()
    assert "categories" in data
    assert "estimate_types" in data
    assert "disclaimer" in data
    assert len(data["categories"]) == 5
    cat_names = [c["category"] for c in data["categories"]]
    assert "algorithmic_complexity" in cat_names
    assert "avoidable_computation" in cat_names
    assert "unnecessary_allocations" in cat_names
    assert "redundant_operations" in cat_names
    assert "inefficient_io_memory" in cat_names


def test_api_optimization_potential_endpoint():
    """Verify POST /api/optimization/potential calculates report over REST."""
    client = app.test_client()
    code = """
    #include <stdio.h>
    #include <string.h>

    int main() {
        char s[] = "test";
        for (int i = 0; i < strlen(s); i++) {
            printf("%c", s[i]);
        }
        return 0;
    }
    """
    resp = client.post(
        "/api/optimization/potential",
        json={"code": code, "filename": "test.c"},
    )
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["can_score"] is True
    assert data["status"] == "SCORED"
    assert data["optimization_potential"] > 0.0
    assert "opportunities" in data
    assert len(data["opportunities"]) > 0
    assert "benchmark" in data
    assert "category_scores" in data


def test_api_repair_includes_optimization_report():
    """Verify /api/repair response payload includes optimization_report."""
    client = app.test_client()
    code = """
    int main() {
        int a = 10;
        return 0;
    }
    """
    resp = client.post(
        "/api/repair",
        json={"code": code, "filename": "main.c", "mode": "deterministic"},
    )
    assert resp.status_code == 200
    data = resp.get_json()

    assert "optimization_report" in data
    opt_rep = data["optimization_report"]
    assert opt_rep is not None
    assert opt_rep["can_score"] is True
    assert opt_rep["optimization_potential"] is not None
