"""
Unit and Integration Tests for Code Quality Score (%) Engine and API.

Validates:
1. Documented and configurable scoring formulas with customizable component weights.
2. 5 Dimensions: Correctness, Compliance, Maintainability, Complexity, Efficiency.
3. Distinction between MEASURED compiler properties and HEURISTIC estimates.
4. Refusal to fabricate scores on empty or insufficient sources (status INSUFFICIENT_INFORMATION).
5. Specific findings and prioritized actionable remediation suggestions.
6. Flask REST endpoints (/api/quality/score, /api/quality/config).
7. Integration with /api/repair payload.
"""
import pytest
from compiler.code_quality import (
    CodeQualityScorer,
    QualityConfig,
    QualityStatus,
    MeasurementType,
    QUALITY_DISCLAIMER,
)
from app import app


def test_quality_config_defaults_and_validation():
    """Verify default weights sum to 1.0 and invalid weight configurations raise ValueError."""
    cfg = QualityConfig()
    cfg.validate_weights()
    assert (
        cfg.weight_correctness
        + cfg.weight_compliance
        + cfg.weight_maintainability
        + cfg.weight_complexity
        + cfg.weight_efficiency
    ) == pytest.approx(1.0)

    # Valid custom weights
    custom_cfg = QualityConfig(
        weight_correctness=0.50,
        weight_compliance=0.10,
        weight_maintainability=0.10,
        weight_complexity=0.15,
        weight_efficiency=0.15,
    )
    custom_cfg.validate_weights()

    # Invalid weights
    invalid_cfg = QualityConfig(weight_correctness=0.8)
    with pytest.raises(ValueError, match="weights must sum to 1.0"):
        invalid_cfg.validate_weights()


def test_zero_fabrication_on_empty_source():
    """Refuse to fabricate quality score when source code is empty."""
    scorer = CodeQualityScorer()
    report = scorer.analyze_source("")

    assert report.can_score is False
    assert report.overall_score is None
    assert report.status == QualityStatus.EMPTY_SOURCE
    assert "empty" in report.status_reason.lower()
    assert report.disclaimer == QUALITY_DISCLAIMER


def test_zero_fabrication_on_insufficient_fragment():
    """Refuse to fabricate quality score on trivial fragments (< 15 characters)."""
    scorer = CodeQualityScorer()
    report = scorer.analyze_source("int x;")

    assert report.can_score is False
    assert report.overall_score is None
    assert report.status == QualityStatus.INSUFFICIENT_INFORMATION
    assert "brief" in report.status_reason.lower() or "incomplete" in report.status_reason.lower()


def test_epistemological_distinction_measured_vs_heuristic():
    """Verify distinct classification of MEASURED vs HEURISTIC properties."""
    code = """
    #include <stdio.h>

    // Computes sum of integers
    int compute_sum(int n) {
        int sum = 0;
        for (int i = 0; i < n; i++) {
            sum += i;
        }
        return sum;
    }

    int main() {
        printf("%d\\n", compute_sum(10));
        return 0;
    }
    """
    scorer = CodeQualityScorer()
    report = scorer.analyze_source(code)

    assert report.can_score is True
    assert report.overall_score is not None
    assert report.overall_score >= 85.0

    comps = report.components
    assert comps["correctness"].measurement_type == MeasurementType.MEASURED
    assert comps["complexity"].measurement_type == MeasurementType.MEASURED
    assert comps["maintainability"].measurement_type == MeasurementType.HEURISTIC
    assert comps["compliance"].measurement_type == MeasurementType.HYBRID
    assert comps["efficiency"].measurement_type == MeasurementType.HYBRID


def test_correctness_penalties_and_security_findings():
    """Verify syntax errors and critical security vulnerabilities heavily penalize correctness."""
    insecure_code = """
    #include <stdio.h>

    int main() {
        char buf[32];
        gets(buf);
        return 0;
    }
    """
    scorer = CodeQualityScorer()
    report = scorer.analyze_source(
        insecure_code,
        security_findings=[
            {
                "rule_id": "SEC-BO-002",
                "message": "Use of unsafe gets() causes buffer overflow",
                "severity": "CRITICAL",
                "is_confirmed": True,
                "line": 6,
            }
        ],
    )

    assert report.can_score is True
    correctness = report.components["correctness"]
    assert correctness.score < 80.0
    assert any("gets" in ev for ev in correctness.evidence)

    # Check that remediation suggestion is generated
    sec_sugs = [s for s in report.suggestions if s.category == "security"]
    assert len(sec_sugs) > 0
    assert sec_sugs[0].priority == "CRITICAL"
    assert sec_sugs[0].is_heuristic is False  # Confirmed security is measured


def test_complexity_and_nesting_penalties():
    """Verify deeply nested control flow triggers complexity deductions and actionable suggestions."""
    deep_nesting_code = """
    #include <stdio.h>

    // Deeply nested logic
    int process(int a, int b, int c, int d, int e) {
        if (a > 0) {
            if (b > 0) {
                if (c > 0) {
                    if (d > 0) {
                        if (e > 0) {
                            return 1;
                        }
                    }
                }
            }
        }
        return 0;
    }

    int main() {
        return process(1, 2, 3, 4, 5);
    }
    """
    scorer = CodeQualityScorer()
    report = scorer.analyze_source(deep_nesting_code)

    assert report.can_score is True
    comp = report.components["complexity"]
    assert comp.score < 90.0
    assert any("nesting depth" in ev.lower() for ev in comp.evidence)

    comp_sugs = [s for s in report.suggestions if s.category == "complexity"]
    assert len(comp_sugs) > 0
    assert "nesting" in comp_sugs[0].finding.lower()


def test_efficiency_penalty_for_nested_loops_and_strlen():
    """Verify nested loops and strlen inside loop conditions reduce efficiency score."""
    inefficient_code = """
    #include <stdio.h>
    #include <string.h>

    void sort_matrix(char *str, int n) {
        for (int i = 0; i < strlen(str); i++) {
            for (int j = 0; j < n; j++) {
                for (int k = 0; k < n; k++) {
                    putchar(str[i]);
                }
            }
        }
    }

    int main() {
        char s[] = "hello";
        sort_matrix(s, 5);
        return 0;
    }
    """
    scorer = CodeQualityScorer()
    report = scorer.analyze_source(inefficient_code)

    assert report.can_score is True
    eff = report.components["efficiency"]
    assert eff.score < 80.0
    assert any("strlen" in ev.lower() or "loop" in ev.lower() for ev in eff.evidence)

    eff_sugs = [s for s in report.suggestions if s.category == "efficiency"]
    assert len(eff_sugs) > 0


def test_configurable_weights_affect_overall_score():
    """Verify custom weights change the calculated composite score."""
    flawed_code = """
    #include <stdio.h>
    int main() {
        int x = 1;
        // High complexity nested loops
        for(int i=0; i<10; i++) {
            for(int j=0; j<10; j++) {
                for(int k=0; k<10; k++) {
                    x += i+j+k;
                }
            }
        }
        return x;
    }
    """
    # Config 1: standard weights (efficiency 15%)
    cfg1 = QualityConfig()
    rep1 = CodeQualityScorer(cfg1).analyze_source(flawed_code)

    # Config 2: heavily penalizes efficiency (efficiency 60%, correctness 10%, others 10%)
    cfg2 = QualityConfig(
        weight_efficiency=0.60,
        weight_correctness=0.10,
        weight_compliance=0.10,
        weight_maintainability=0.10,
        weight_complexity=0.10,
    )
    rep2 = CodeQualityScorer(cfg2).analyze_source(flawed_code)

    assert rep1.overall_score is not None
    assert rep2.overall_score is not None
    # Because efficiency is heavily penalized, overall score with cfg2 should be lower
    assert rep2.overall_score < rep1.overall_score


def test_api_quality_config_endpoint():
    """Verify GET /api/quality/config returns documented dimensions and disclaimer."""
    client = app.test_client()
    resp = client.get("/api/quality/config")
    assert resp.status_code == 200

    data = resp.get_json()
    assert "dimensions" in data
    assert "disclaimer" in data
    assert len(data["dimensions"]) == 5
    dim_names = [d["name"] for d in data["dimensions"]]
    assert set(dim_names) == {"correctness", "compliance", "maintainability", "complexity", "efficiency"}
    assert data["disclaimer"] == QUALITY_DISCLAIMER


def test_api_quality_score_endpoint():
    """Verify POST /api/quality/score calculates and returns full quality report."""
    client = app.test_client()
    clean_code = """
    #include <stdio.h>

    // Entry point function
    int main() {
        printf("Hello World\\n");
        return 0;
    }
    """
    resp = client.post(
        "/api/quality/score",
        json={"code": clean_code, "filename": "test.c"},
    )
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["can_score"] is True
    assert data["status"] == "SCORED"
    assert data["overall_score"] >= 80.0
    assert "components" in data
    assert "suggestions" in data
    assert "disclaimer" in data


def test_api_repair_includes_quality_report():
    """Verify /api/repair response payload includes quality_report."""
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

    assert "quality_report" in data
    q_rep = data["quality_report"]
    assert q_rep is not None
    assert q_rep["can_score"] is True
    assert q_rep["overall_score"] is not None
