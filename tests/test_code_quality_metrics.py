"""
Unit and Integration Tests for Clarified Code-Quality Metrics.

Verifies:
1. Formula calculations and 0-100 bounds:
   - Optimal Code % = clamp(100 - O, 0, 100)
   - Poor Code % = clamp(100 - Q, 0, 100) (inverse of Q)
   - Vulnerability Risk % = clamp(V, 0, 100) (normalized risk indicator)
   - Overall Code Quality % = clamp(0.50 * Q + 0.25 * (100 - O) + 0.25 * (100 - V), 0, 100)
2. Missing/incomplete metrics handling (None propagation, no silent zero replacement).
3. Vulnerability-risk label and score mapping (explicitly verified as risk indicator, not probability).
4. Baseline metrics calculated strictly on original source code before repair.
5. Language routing isolation (Python not evaluated as C; C-specific memory checks skipped for Python).
6. No stale metric values when resetting or analyzing a second, different program.
7. End-to-end API response consistency through Flask endpoints.
"""
import pytest
from compiler.code_quality import calculate_code_quality_metrics, CodeQualityScorer
from compiler.optimization_potential import OptimizationPotentialAnalyzer
from compiler.security_risk import SecurityRiskScorer, SECURITY_RISK_DISCLAIMER
from compiler.repair_planner import RepairPlanner
from app import app


# -----------------------------------------------------------------------------
# 1. Formula Calculations and Bounds Clamping
# -----------------------------------------------------------------------------
def test_formula_exact_calculations():
    """Verify exact formula calculation with known representative scores."""
    # Q = 80, O = 20, V = 10
    # Optimal = 100 - 20 = 80.0
    # Poor = 100 - 80 = 20.0
    # Vuln = 10.0
    # Overall = 0.50*80 + 0.25*(100-20) + 0.25*(100-10) = 40 + 20 + 22.5 = 82.5
    res = calculate_code_quality_metrics(q=80.0, o=20.0, v=10.0)
    assert res["overall_code_quality"] == 82.5
    assert res["optimal_code"] == 80.0
    assert res["poor_code"] == 20.0
    assert res["vulnerability_risk"] == 10.0
    assert res["is_complete"] is True


def test_formula_perfect_scores():
    """Verify perfect 100% scores across clean code."""
    # Q = 100, O = 0, V = 0
    # Overall = 0.50*100 + 0.25*100 + 0.25*100 = 100.0
    res = calculate_code_quality_metrics(q=100.0, o=0.0, v=0.0)
    assert res["overall_code_quality"] == 100.0
    assert res["optimal_code"] == 100.0
    assert res["poor_code"] == 0.0
    assert res["vulnerability_risk"] == 0.0


def test_formula_worst_scores():
    """Verify worst-case 0% scores."""
    # Q = 0, O = 100, V = 100
    # Overall = 0.50*0 + 0.25*0 + 0.25*0 = 0.0
    res = calculate_code_quality_metrics(q=0.0, o=100.0, v=100.0)
    assert res["overall_code_quality"] == 0.0
    assert res["optimal_code"] == 0.0
    assert res["poor_code"] == 100.0
    assert res["vulnerability_risk"] == 100.0


def test_bounds_clamping_limits():
    """Verify values beyond 0-100 are strictly clamped."""
    # Out of bounds inputs
    res_high = calculate_code_quality_metrics(q=120.0, o=-15.0, v=-20.0)
    assert res_high["overall_code_quality"] == 100.0
    assert res_high["optimal_code"] == 100.0
    assert res_high["poor_code"] == 0.0
    assert res_high["vulnerability_risk"] == 0.0

    res_low = calculate_code_quality_metrics(q=-50.0, o=150.0, v=200.0)
    assert res_low["overall_code_quality"] == 0.0
    assert res_low["optimal_code"] == 0.0
    assert res_low["poor_code"] == 100.0
    assert res_low["vulnerability_risk"] == 100.0


# -----------------------------------------------------------------------------
# 2. Missing and Incomplete Metrics Handling
# -----------------------------------------------------------------------------
def test_missing_metrics_explicit_none():
    """Missing or incomplete component inputs must never be silently converted to 0."""
    # Missing Q
    res_no_q = calculate_code_quality_metrics(q=None, o=20.0, v=10.0)
    assert res_no_q["overall_code_quality"] is None
    assert res_no_q["poor_code"] is None
    assert res_no_q["optimal_code"] == 80.0
    assert res_no_q["vulnerability_risk"] == 10.0
    assert res_no_q["is_complete"] is False

    # Missing O
    res_no_o = calculate_code_quality_metrics(q=80.0, o=None, v=10.0)
    assert res_no_o["overall_code_quality"] is None
    assert res_no_o["optimal_code"] is None
    assert res_no_o["poor_code"] == 20.0
    assert res_no_o["vulnerability_risk"] == 10.0
    assert res_no_o["is_complete"] is False

    # Missing V
    res_no_v = calculate_code_quality_metrics(q=80.0, o=20.0, v=None)
    assert res_no_v["overall_code_quality"] is None
    assert res_no_v["vulnerability_risk"] is None
    assert res_no_v["optimal_code"] == 80.0
    assert res_no_v["poor_code"] == 20.0
    assert res_no_v["is_complete"] is False

    # All missing
    res_empty = calculate_code_quality_metrics(q=None, o=None, v=None)
    assert res_empty["overall_code_quality"] is None
    assert res_empty["optimal_code"] is None
    assert res_empty["poor_code"] is None
    assert res_empty["vulnerability_risk"] is None
    assert res_empty["is_complete"] is False


# -----------------------------------------------------------------------------
# 3. Vulnerability Risk Label & Epistemological Disclaimer
# -----------------------------------------------------------------------------
def test_vulnerability_risk_not_exploit_probability():
    """Verify that Vulnerability Risk % is explicitly documented as a risk indicator, not probability."""
    res = calculate_code_quality_metrics(q=75.0, o=15.0, v=30.0)
    notes = res["notes"]
    assert "NOT the probability" in notes["vulnerability_risk"] or "not an attack probability" in notes["vulnerability_risk"]

    # Also verify disclaimer in security_risk module
    assert "probability" in SECURITY_RISK_DISCLAIMER.lower()
    assert "not a calibrated probability" in SECURITY_RISK_DISCLAIMER.lower()


def test_poor_code_documented_as_inverse():
    """Verify Poor Code % documentation explicitly notes inverse relationship, avoiding double-counting."""
    res = calculate_code_quality_metrics(q=75.0, o=15.0, v=30.0)
    notes = res["notes"]
    assert "inverse of Code Quality" in notes["poor_code"]
    assert "not an independent measurement" in notes["poor_code"]


# -----------------------------------------------------------------------------
# 4. Baseline Metrics Assessed Strictly on Original Code
# -----------------------------------------------------------------------------
def test_baseline_assessed_before_repairs():
    """Ensure baseline_scores evaluates original code prior to repair or candidate generation."""
    code_with_bugs = """
    #include <stdio.h>
    int main() {
        char buf[16];
        gets(buf);
        return 0;
    }
    """
    planner = RepairPlanner()
    findings, baseline = planner.analyze_program(code_with_bugs, filename="main.c", language="c")

    # Original code has gets() -> Vulnerability Risk must reflect gets() on original code
    assert baseline["vulnerability_risk"] is not None
    assert baseline["vulnerability_risk"] > 50.0
    assert baseline["overall_code_quality"] is not None
    # Original code has gets(), so overall code quality must reflect the original risk
    assert baseline["overall_code_quality"] < 90.0

    # Execute plan_and_repair
    plan = planner.plan_and_repair(code_with_bugs, filename="main.c", language="c")
    # baseline_scores and original_assessment must retain original assessment
    assert plan["baseline_scores"]["vulnerability_risk"] == baseline["vulnerability_risk"]
    assert plan["original_assessment"]["overall_code_quality"] == baseline["overall_code_quality"]


# -----------------------------------------------------------------------------
# 5. Language Routing: Python and C Isolation
# -----------------------------------------------------------------------------
def test_python_language_routing_isolation():
    """Verify Python programs are routed to Python analyzers and not treated as C."""
    py_code = """
def compute_squares(n):
    result = []
    for i in range(n):
        for j in range(n):
            result.append(i * j)
    return result

if __name__ == '__main__':
    print(compute_squares(10))
    """
    planner = RepairPlanner()
    findings, baseline = planner.analyze_program(py_code, filename="main.py", language="python")

    # Python nested loop should be detected by Python complexity analyzer
    assert baseline["optimization_potential"] is not None
    # Optimal Code % should be 100 - O
    expected_optimal = round(100.0 - baseline["optimization_potential"], 1)
    assert baseline["optimal_code"] == expected_optimal
    # Clean Python code has 0 vulnerability risk
    assert baseline["vulnerability_risk"] == 0.0
    # Overall Code Quality should be calculated
    assert baseline["overall_code_quality"] is not None


def test_syntax_errors_do_not_fabricate_vulnerability_risk():
    """Verify that pure syntax errors in C are not misclassified as security vulnerabilities."""
    syntax_broken_c = """
    #include <stdio.h>
    int main() {
        int x = ;
        return 0;
    }
    """
    planner = RepairPlanner()
    findings, baseline = planner.analyze_program(syntax_broken_c, filename="main.c", language="c")

    # Pure syntax error must NOT produce fabricated 0% vulnerability risk or false security clearance
    assert baseline["vulnerability_risk"] is None
    assert baseline["security_status"] == "INCONCLUSIVE"


# -----------------------------------------------------------------------------
# 6. No Stale Metrics on Subsequent Different Program
# -----------------------------------------------------------------------------
def test_sequential_runs_different_metrics():
    """Verify that analyzing two distinct programs produces distinct, independent scores without stale retention."""
    clean_code = """
    #include <stdio.h>
    int main() {
        printf("Hello World\\n");
        return 0;
    }
    """
    vuln_code = """
    #include <stdio.h>
    int main() {
        char buf[8];
        gets(buf);
        return 0;
    }
    """
    planner = RepairPlanner()

    # Run 1: Clean code
    _, baseline_1 = planner.analyze_program(clean_code, filename="main.c", language="c")
    assert baseline_1["vulnerability_risk"] == 0.0
    assert baseline_1["overall_code_quality"] > 80.0

    # Run 2: Vulnerable code
    _, baseline_2 = planner.analyze_program(vuln_code, filename="main.c", language="c")
    assert baseline_2["vulnerability_risk"] > 50.0
    assert baseline_2["overall_code_quality"] < baseline_1["overall_code_quality"]

    # Run 3: Clean code again - must not carry over Run 2's vulnerability risk
    _, baseline_3 = planner.analyze_program(clean_code, filename="main.c", language="c")
    assert baseline_3["vulnerability_risk"] == 0.0
    assert baseline_3["overall_code_quality"] == baseline_1["overall_code_quality"]


# -----------------------------------------------------------------------------
# 7. Flask API Endpoints Return Clarified Metrics
# -----------------------------------------------------------------------------
def test_api_coordinator_analyze_and_plan_returns_metrics():
    """Verify that POST /api/coordinator/analyze_and_plan returns the 4 code-quality metrics."""
    client = app.test_client()
    payload = {
        "code": "#include <stdio.h>\nint main() { printf(\"Test\\n\"); return 0; }\n",
        "filename": "main.c",
        "language": "c"
    }
    res = client.post("/api/coordinator/analyze_and_plan", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    assert "baseline_scores" in data
    bs = data["baseline_scores"]
    assert "overall_code_quality" in bs
    assert "optimal_code" in bs
    assert "poor_code" in bs
    assert "vulnerability_risk" in bs
    assert bs["overall_code_quality"] is not None
    assert bs["optimal_code"] is not None
    assert bs["poor_code"] is not None
    assert bs["vulnerability_risk"] is not None

    # Verify formula match
    q = bs["quality_score"]
    o = bs["optimization_potential"]
    v = bs["vulnerability_risk"]
    expected_ov = round(0.50 * q + 0.25 * (100 - o) + 0.25 * (100 - v), 1)
    assert bs["overall_code_quality"] == expected_ov


def test_api_patch_compare_returns_metrics():
    """Verify that POST /api/dashboard/before_after includes the 4 metrics in before and after."""
    client = app.test_client()
    payload = {
        "before_code": "#include <stdio.h>\nint main() { char b[16]; gets(b); return 0; }\n",
        "after_code": "#include <stdio.h>\nint main() { char b[16]; fgets(b, sizeof(b), stdin); return 0; }\n",
        "filename": "main.c"
    }
    res = client.post("/api/dashboard/before_after", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    assert data["success"] is True
    assert "overall_code_quality" in data["before"]
    assert "optimal_code" in data["before"]
    assert "poor_code" in data["before"]
    assert "vulnerability_risk" in data["before"]

    assert "overall_code_quality" in data["after"]
    assert "optimal_code" in data["after"]
    assert "poor_code" in data["after"]
    assert "vulnerability_risk" in data["after"]

    # Security risk should decrease after replacing gets with fgets
    assert data["after"]["vulnerability_risk"] < data["before"]["vulnerability_risk"]
