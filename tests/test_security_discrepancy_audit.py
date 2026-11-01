# tests/test_security_discrepancy_audit.py
"""
Diagnostic & Reproduction Tests for Antigravity Security Risk Audit.
Reproduces:
1. 0% vs 23.3% discrepancy between findings report and risk scorer.
2. assess_delta() invalid 0.0 fallback on incomplete/empty assessments.
3. INFO finding pollution of risk points.
4. Exposure heuristic over-assigning entry-point exposure.
5. Exception swallowing in repair validation.
6. Premature user decision recording during automated validation.
"""
import pytest
from compiler.security_risk import (
    SecurityRiskScorer,
    SecurityRiskStatus,
    SecurityRiskReport,
)
from compiler.security_reporter import (
    SecurityReporter,
    SecurityVulnerability,
    SecuritySeverity,
    VulnerabilityCategory,
)
from compiler.repair_workflow import (
    RepairWorkflowEngine,
    StructuredCandidatePatch,
)
from compiler.finding import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)


class TestSecurityDiscrepancyAudit:
    """Test suite reproducing and verifying the audit findings."""

    def test_reproduce_23_percent_single_high_finding(self):
        """
        Verify that a single HIGH security finding (e.g. unsafe memcpy)
        produces an asymptotic risk score of ~23.3%.
        Formula: 100 * (1 - exp(-raw_points / 40.0))
        With base 25.0, exploitability 0.50, exposure 0.85, confidence 1.0:
        raw_points = 25.0 * 0.50 * 0.85 * 1.0 = 10.625
        Score = 100 * (1 - exp(-10.625 / 40)) = 23.33%
        """
        scorer = SecurityRiskScorer(scale_constant=40.0)
        finding = {
            "id": "SEC-TEST-01",
            "rule_id": "SEC-07",
            "category": "GENERAL_SECURITY",
            "severity": "HIGH",
            "line": 4,
            "evidence": "memcpy(dst, src, 100);",
            "status": "CONFIRMED",
            "confidence": 1.0,
        }
        source = (
            "int main() {\n"
            "  char src[100];\n"
            "  char dst[10];\n"
            "  memcpy(dst, src, 100);\n"
            "  return 0;\n"
            "}\n"
        )
        report = scorer.assess([finding], source_code=source, filename="memcpy_test.c")
        assert report.can_score is True
        assert report.risk_score is not None
        assert 22.0 <= report.risk_score <= 24.5
        assert round(report.risk_score, 1) == 23.3

    def test_reproduce_0_percent_vs_23_percent_desynchronization(self):
        """
        Reproduce how the UI can show 0% risk score while the report shows 23.3%:
        When assess() is passed empty findings (e.g., from an unpopulated payload
        or post-repair code where the finding was removed) on code that has vulnerabilities.
        """
        scorer = SecurityRiskScorer()
        source = (
            "int main() {\n"
            "  char src[100];\n"
            "  char dst[10];\n"
            "  memcpy(dst, src, 100);\n"
            "  return 0;\n"
            "}\n"
        )
        # If findings list is empty:
        report_empty = scorer.assess([], source_code=source, filename="main.c")
        # Scorer reports 0.0% because 0 findings were supplied:
        assert report_empty.risk_score == 0.0

        # But SecurityReporter detects the vulnerability:
        sec_rep = SecurityReporter().analyze_source(source, "main.c")
        assert len(sec_rep.findings) >= 1
        # When assessed with the actual findings:
        report_actual = scorer.assess(sec_rep.findings, source_code=source, filename="main.c")
        assert round(report_actual.risk_score, 1) == 23.3
        # Direct discrepancy: 0.0% vs 23.3%!

    def test_reproduce_assess_delta_invalid_zero_fallback(self):
        """
        Verify that when before_code is incomplete (<15 chars) or empty,
        can_score is False, rep.before_score is preserved as None (not fabricated 0.0),
        status is INCOMPLETE_ASSESSMENT, and delta_score is None.
        """
        scorer = SecurityRiskScorer()
        rep = scorer.assess_delta(
            before_findings=[],
            after_findings=[],
            before_code="short",
            after_code="int main() { return 0; }",
        )
        assert rep.can_score is False
        assert rep.status == SecurityRiskStatus.INCOMPLETE_ASSESSMENT
        assert rep.before_score is None
        assert rep.delta_score is None

    def test_info_advisory_zero_risk_points(self):
        """
        Verify that INFO severity advisories do not contribute raw risk points
        to the risk score and are classified as informational advisories.
        """
        scorer = SecurityRiskScorer()
        source = "int main() {\n  int x = 42;\n  return 0;\n}\n"
        finding = {
            "id": "SEC-INFO-01",
            "rule_id": "INFO-01",
            "category": "GENERAL_SECURITY",
            "severity": "INFO",
            "line": 2,
            "evidence": "int x = 42;",
            "status": "CONFIRMED",
            "confidence": 1.0,
        }
        rep = scorer.assess([finding], source_code=source, filename="main.c")
        assert rep.can_score is True
        assert rep.info_count == 1
        assert rep.critical_count == 0
        assert rep.high_count == 0
        assert rep.risk_score == 0.0  # 0 risk points from INFO
        assert len(rep.contributions) == 1
        assert rep.contributions[0].risk_points == 0.0

    def test_line_in_main_exposure_scoping(self):
        """
        Verify that exposure factor is 0.85 when inside main(),
        but drops to 0.65 when inside an internal helper function.
        """
        scorer = SecurityRiskScorer()
        source = (
            "void helper() {\n"
            "  char buf[64];\n"
            "}\n\n"
            "int main() {\n"
            "  helper();\n"
            "  return 0;\n"
            "}\n"
        )
        finding_in_helper = {
            "id": "SEC-01",
            "rule_id": "SEC-01",
            "category": "GENERAL_SECURITY",
            "severity": "MEDIUM",
            "line": 2,  # inside helper
        }
        finding_in_main = {
            "id": "SEC-02",
            "rule_id": "SEC-02",
            "category": "GENERAL_SECURITY",
            "severity": "MEDIUM",
            "line": 6,  # inside main
        }
        exp_helper, _ = scorer._compute_exposure(finding_in_helper, source, 2)
        exp_main, _ = scorer._compute_exposure(finding_in_main, source, 6)
        assert exp_helper == 0.65  # Internal helper scope
        assert exp_main == 0.85    # Entry point main scope

    def test_correlated_findings_deduplication(self):
        """
        Verify that multiple findings reporting the same rule on the same line
        are deduplicated to prevent artificial score inflation.
        """
        scorer = SecurityRiskScorer()
        source = "int main() {\n  char buf[10];\n  gets(buf);\n  return 0;\n}\n"
        dup1 = {"id": "D1", "rule_id": "SEC-01", "category": "UNBOUNDED_INPUT", "severity": "CRITICAL", "line": 3}
        dup2 = {"id": "D2", "rule_id": "SEC-01", "category": "UNBOUNDED_INPUT", "severity": "CRITICAL", "line": 3}
        rep = scorer.assess([dup1, dup2], source_code=source, filename="main.c")
        # Deduplication ensures only 1 contribution is scored
        assert len(rep.contributions) == 1
        assert rep.critical_count == 1
