"""
tests/test_final_dashboard.py
Unit and integration tests for Phase 13: Final Website Dashboard.

Verifies:
1. Integration of the 5 primary indicators:
   - Code Quality Score (%)
   - Optimization Potential (%)
   - Security Risk Score (%)
   - Green Metrics Score
   - Model Accuracy and Repair Performance
2. Before-and-after fix comparisons for approved fixes (/api/dashboard/before_after).
3. Clear distinction between live session measurements and fixed benchmark dataset.
4. Epistemological badges (MEASURED, ESTIMATED, INCOMPLETE, NOT YET BENCHMARKED).
5. Zero hardcoded demonstration percentages as real results.
"""

import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_dashboard_five_indicators_availability(client):
    """Verifies that all 5 indicator data endpoints are accessible and functional."""
    # 1. Code Quality
    res_q = client.post("/api/quality/score", json={"code": "int main() { return 0; }", "filename": "test.c"})
    assert res_q.status_code == 200
    data_q = res_q.get_json()
    assert "overall_score" in data_q
    assert data_q["can_score"] is True

    # 2. Optimization Potential
    res_opt = client.post("/api/optimization/potential", json={"code": "int main() { return 0; }", "filename": "test.c"})
    assert res_opt.status_code == 200
    data_opt = res_opt.get_json()
    assert "optimization_potential" in data_opt

    # 3. Security Risk Score
    res_sec = client.post("/api/security/risk", json={"code": "int main() { return 0; }", "filename": "test.c"})
    assert res_sec.status_code == 200
    data_sec = res_sec.get_json()
    assert "risk_score" in data_sec

    # 4. Green Metrics Engine
    res_grn = client.get("/api/green/config")
    assert res_grn.status_code == 200
    data_grn = res_grn.get_json()
    assert "scoring_weights" in data_grn
    assert "baseline" in data_grn
    assert "methodology" in data_grn

    # 5. Model Accuracy & Benchmark
    res_bm = client.get("/api/benchmark/dataset")
    assert res_bm.status_code == 200
    data_bm = res_bm.get_json()
    assert data_bm["size"] >= 16
    assert "definitions" in data_bm


def test_dashboard_before_after_comparison_repair_fix(client):
    """
    Tests before-and-after fix comparison when a faulty/vulnerable code snippet
    is repaired by a safe fix.
    """
    before_code = """
    #include <stdio.h>
    #include <string.h>

    void vulnerable_copy(char *src) {
        char buf[16];
        strcpy(buf, src);
        printf(buf);
    }

    int main() {
        vulnerable_copy("hello world");
        return 0;
    }
    """

    after_code = """
    #include <stdio.h>
    #include <string.h>

    void vulnerable_copy(char *src) {
        char buf[16];
        strncpy(buf, src, sizeof(buf) - 1);
        buf[sizeof(buf) - 1] = 0;
        printf("%s", buf);
    }

    int main() {
        vulnerable_copy("hello world");
        return 0;
    }
    """

    payload = {
        "before_code": before_code,
        "after_code": after_code,
        "filename": "vuln_test.c",
        "green_report": {
            "total_runtime_ms": 142.5,
            "energy_metrics": {
                "estimated_joules": 8.35,
                "estimated_co2_mg": 1.10,
                "measurement_mode": "HARDWARE_TDP_LINEAR_POWER_MODEL"
            },
            "system_metrics": {
                "peak_memory_mb": 42.1
            },
            "model_metrics": {
                "total_tokens": 128
            }
        },
        "applied_steps": [
            "Replaced unsafe strcpy with bounded strncpy",
            "Sanitized printf format string"
        ]
    }

    res = client.post("/api/dashboard/before_after", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    assert data["success"] is True
    before = data["before"]
    after = data["after"]
    delta = data["delta"]
    resource = data["resource_overhead"]
    badges = data["epistemic_badges"]

    # Security risk should drop or remain bounded
    assert before["security_risk_score"] is not None
    assert after["security_risk_score"] is not None
    assert delta["security_risk_delta"] is not None
    assert delta["security_risk_delta"] <= 0  # Risk decreased or non-negative delta

    # Quality score should be computed
    assert before["quality_score"] is not None
    assert after["quality_score"] is not None

    # Vulnerability delta
    assert delta["resolved_vulnerabilities_count"] >= 1
    assert delta["introduced_vulnerabilities_count"] == 0

    # Resource overhead
    assert resource["runtime_ms"] == 142.5
    assert resource["estimated_joules"] == 8.35
    assert resource["estimated_carbon_mg"] == 1.10
    assert resource["peak_memory_mb"] == 42.1
    assert resource["model_tokens"] == 128

    # Epistemic badges
    assert badges["quality"] == "LIVE SESSION: MEASURED"
    assert badges["optimization"] == "STATIC HEURISTIC ESTIMATE"
    assert badges["security_risk"] == "LIVE SESSION: RISK INDEX"
    assert badges["green_metrics"] == "HARDWARE POWER MODEL: ESTIMATED"
    assert badges["benchmark"] == "FIXED BENCHMARK DATASET"


def test_dashboard_before_after_empty_incomplete_code(client):
    """
    Verifies that empty or incomplete code does not receive fabricated demonstration percentages.
    """
    payload = {
        "before_code": "",
        "after_code": "",
        "filename": "empty.c"
    }
    res = client.post("/api/dashboard/before_after", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    assert data["before"]["quality_score"] is None
    assert data["before"]["quality_status"] == "EMPTY_SOURCE"
    assert data["before"]["optimization_potential"] is None
    assert data["before"]["security_risk_score"] is None


def test_dashboard_html_templates_contain_executive_indicators():
    """
    Verifies that gui/templates/index.html includes all required Phase 13 dashboard elements:
    - Primary Indicators Card (#primaryIndicatorsSummary)
    - All 5 Primary Indicator Tiles
    - Before-and-After Comparison Card (#beforeAfterCard)
    """
    with open("gui/templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Five primary indicators summary card
    assert 'id="primaryIndicatorsSummary"' in html
    assert 'id="pi-val-quality"' in html
    assert 'id="pi-val-opt"' in html
    assert 'id="pi-val-sec"' in html
    assert 'id="pi-val-green"' in html
    assert 'id="pi-val-benchmark"' in html

    # Epistemic badges
    assert 'id="pi-badge-quality"' in html
    assert 'id="pi-badge-opt"' in html
    assert 'id="pi-badge-sec"' in html
    assert 'id="pi-badge-green"' in html
    assert 'id="pi-badge-benchmark"' in html

    # Before vs After card
    assert 'id="beforeAfterCard"' in html
    assert 'id="before-after-tbody"' in html
    assert 'id="ba-overhead-box"' in html


def test_dashboard_css_contains_indicator_styles():
    """Verifies that gui/static/style.css defines styling for indicators grid and before-after matrix."""
    with open("gui/static/style.css", "r", encoding="utf-8") as f:
        css = f.read()

    assert ".primary-indicators-card" in css
    assert ".primary-indicators-grid" in css
    assert ".primary-tile" in css
    assert ".before-after-card" in css
    assert ".before-after-table" in css
    assert ".delta-pill" in css
    assert ".ba-overhead-box" in css
