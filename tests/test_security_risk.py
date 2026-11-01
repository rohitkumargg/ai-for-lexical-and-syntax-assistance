"""
Unit and Integration Tests for Security Risk Score (%) Engine and API.

Validates:
1. Normalized Security Risk Score (0% to 100%) derived from supported security findings.
2. Multi-factor formula:
   - Severity (Critical, High, Medium, Low, Info)
   - Exploitability
   - Exposure
   - Confidence
3. Separate counts for Critical, High, Medium, and Low findings.
4. Transparent explanation of finding risk point contributions.
5. Unresolved findings enumeration.
6. Epistemological disclaimer (risk indicator, NOT calibrated attack probability).
7. Refusal to fabricate on empty or insufficient sources (INCOMPLETE_ASSESSMENT).
8. Recalculation after fixes with before-and-after delta preservation.
9. Flask REST endpoints (/api/security/risk, /api/security/risk/delta, /api/security/risk/config).
10. Integration into /api/repair payload.
"""
import pytest
from compiler.security_risk import (
    SecurityRiskScorer,
    SecurityRiskReport,
    SecurityRiskStatus,
    FindingRiskContribution,
    SECURITY_RISK_DISCLAIMER,
)
from app import app


def test_zero_fabrication_on_empty_source():
    """Refuse to fabricate security risk score when source code is empty."""
    scorer = SecurityRiskScorer()
    report = scorer.assess(findings=[], source_code="")

    assert report.can_score is False
    assert report.risk_score is None
    assert report.status == SecurityRiskStatus.EMPTY_SOURCE
    assert "empty" in report.status_reason.lower()
    assert report.disclaimer == SECURITY_RISK_DISCLAIMER


def test_zero_fabrication_on_insufficient_fragment():
    """Refuse to fabricate security risk score on trivial fragments (< 15 characters)."""
    scorer = SecurityRiskScorer()
    report = scorer.assess(findings=[], source_code="int z;")

    assert report.can_score is False
    assert report.risk_score is None
    assert report.status == SecurityRiskStatus.INCOMPLETE_ASSESSMENT
    assert "brief" in report.status_reason.lower() or "incomplete" in report.status_reason.lower()


def test_clean_code_zero_security_risk():
    """Clean code with no security findings has 0.0% security risk score."""
    code = """
    #include <stdio.h>

    int main() {
        printf("Clean program\\n");
        return 0;
    }
    """
    scorer = SecurityRiskScorer()
    report = scorer.assess(findings=[], source_code=code)

    assert report.can_score is True
    assert report.risk_score == 0.0
    assert report.critical_count == 0
    assert report.high_count == 0
    assert report.medium_count == 0
    assert report.low_count == 0
    assert report.unresolved_count == 0
    assert len(report.contributions) == 0


def test_critical_finding_substantial_risk():
    """Confirmed critical unbounded input finding generates substantial risk score."""
    code = """
    #include <stdio.h>

    int main() {
        char buf[32];
        gets(buf);
        return 0;
    }
    """
    finding = {
        "id": "unsafe_fn:gets:6",
        "rule_id": "SEC-BANNED-GETS",
        "category": "UNBOUNDED_INPUT",
        "severity": "CRITICAL",
        "line": 6,
        "evidence": "gets(buf);",
        "potential_impact": "Banned standard function gets() enables stack buffer overflow.",
        "confidence": 1.0,
        "status": "CONFIRMED",
    }
    scorer = SecurityRiskScorer()
    report = scorer.assess(findings=[finding], source_code=code)

    assert report.can_score is True
    assert report.risk_score is not None
    assert report.risk_score >= 60.0
    assert report.critical_count == 1
    assert report.unresolved_count == 1

    # Verify transparent point contribution breakdown
    assert len(report.contributions) == 1
    contrib = report.contributions[0]
    assert contrib.severity == "CRITICAL"
    assert contrib.base_severity_weight == 45.0
    assert contrib.exploitability_factor == 1.0
    assert contrib.confidence_factor == 1.0
    assert contrib.risk_points >= 40.0
    assert "SEC-BANNED-GETS" in contrib.explanation


def test_multi_factor_scaling():
    """Verify severity, exploitability, and exposure scale the risk points."""
    code = "int helper() { return 0; }"

    # Critical finding in helper function
    finding_crit = {
        "id": "crit_vuln",
        "rule_id": "SEC-CRIT",
        "category": "COMMAND_INJECTION",
        "severity": "CRITICAL",
        "line": 1,
        "evidence": "system(cmd);",
        "status": "CONFIRMED",
    }
    # Medium finding in helper function
    finding_med = {
        "id": "med_vuln",
        "rule_id": "SEC-MED",
        "category": "INSECURE_API",
        "severity": "MEDIUM",
        "line": 1,
        "evidence": "rand();",
        "status": "CONFIRMED",
    }

    scorer = SecurityRiskScorer()
    rep = scorer.assess(findings=[finding_crit, finding_med], source_code=code)

    assert rep.critical_count == 1
    assert rep.medium_count == 1
    contrib_map = {c.severity: c for c in rep.contributions}
    assert contrib_map["CRITICAL"].risk_points > contrib_map["MEDIUM"].risk_points


def test_unresolved_findings_enumeration():
    """Verify unresolved findings are listed with line number and impact."""
    code = """
    int main() {
        char b[16];
        gets(b);
        return 0;
    }
    """
    finding = {
        "id": "gets:4",
        "rule_id": "SEC-BANNED-GETS",
        "category": "UNBOUNDED_INPUT",
        "severity": "CRITICAL",
        "line": 4,
        "evidence": "gets(b);",
        "potential_impact": "Stack buffer overflow",
        "status": "CONFIRMED",
    }
    scorer = SecurityRiskScorer()
    report = scorer.assess(findings=[finding], source_code=code)

    assert len(report.unresolved_findings) == 1
    unres = report.unresolved_findings[0]
    assert unres["line"] == 4
    assert unres["rule_id"] == "SEC-BANNED-GETS"
    assert unres["severity"] == "CRITICAL"


def test_recalculation_after_fixes_delta_preservation():
    """Verify delta recalculation across fixes preserves before, after, and delta scores."""
    before_code = """
    #include <stdio.h>
    int main() {
        char buf[16];
        gets(buf);
        return 0;
    }
    """
    after_code = """
    #include <stdio.h>
    int main() {
        char buf[16];
        fgets(buf, sizeof(buf), stdin);
        return 0;
    }
    """
    before_findings = [
        {
            "id": "gets:5",
            "rule_id": "SEC-BANNED-GETS",
            "category": "UNBOUNDED_INPUT",
            "severity": "CRITICAL",
            "line": 5,
            "evidence": "gets(buf);",
            "status": "CONFIRMED",
        }
    ]
    after_findings = []  # gets replaced by safe fgets

    scorer = SecurityRiskScorer()
    delta_rep = scorer.assess_delta(
        before_findings=before_findings,
        after_findings=after_findings,
        before_code=before_code,
        after_code=after_code,
    )

    assert delta_rep.before_score is not None
    assert delta_rep.after_score is not None
    assert delta_rep.delta_score is not None
    assert delta_rep.before_score >= 60.0
    assert delta_rep.after_score == 0.0
    assert delta_rep.delta_score <= -60.0
    assert delta_rep.critical_count == 0


def test_epistemological_disclaimer():
    """Verify disclaimer explicitly states risk indicator is NOT an attack probability."""
    scorer = SecurityRiskScorer()
    report = scorer.assess(findings=[], source_code="int main() { return 0; }")
    assert report.disclaimer == SECURITY_RISK_DISCLAIMER
    assert "NOT a calibrated probability" in report.disclaimer


def test_api_security_risk_config_endpoint():
    """Verify GET /api/security/risk/config returns documented weights, factors, and disclaimer."""
    client = app.test_client()
    resp = client.get("/api/security/risk/config")
    assert resp.status_code == 200

    data = resp.get_json()
    assert "disclaimer" in data
    assert "severity_weights" in data
    assert "formula" in data
    assert "factors" in data
    assert data["disclaimer"] == SECURITY_RISK_DISCLAIMER


def test_api_security_risk_endpoint():
    """Verify POST /api/security/risk computes full assessment over REST."""
    client = app.test_client()
    code = """
    #include <stdio.h>
    int main() {
        char b[32];
        gets(b);
        return 0;
    }
    """
    resp = client.post(
        "/api/security/risk",
        json={"code": code, "filename": "test.c"},
    )
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["can_score"] is True
    assert data["status"] == "ASSESSED"
    assert data["risk_score"] >= 50.0
    assert data["critical_count"] >= 1
    assert "contributions" in data
    assert "unresolved_findings" in data


def test_api_security_risk_delta_endpoint():
    """Verify POST /api/security/risk/delta computes delta scores over REST."""
    client = app.test_client()
    before_code = "int main() { char b[16]; gets(b); return 0; }"
    after_code = "int main() { char b[16]; fgets(b, 16, stdin); return 0; }"

    resp = client.post(
        "/api/security/risk/delta",
        json={
            "before_code": before_code,
            "after_code": after_code,
            "filename": "main.c",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["before_score"] is not None
    assert data["after_score"] is not None
    assert data["delta_score"] is not None
    assert data["delta_score"] <= 0.0


def test_api_repair_includes_security_risk_report():
    """Verify /api/repair response payload includes security_risk_report."""
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

    assert "security_risk_report" in data
    sec_rep = data["security_risk_report"]
    assert sec_rep is not None
    assert sec_rep["can_score"] is True
    assert sec_rep["risk_score"] is not None
