# tests/test_security_reporting.py
import pytest
import json
from compiler.security_reporter import (
    SecurityReporter,
    SecurityVulnerability,
    ComprehensiveSecurityReport,
    SecurityDeltaReport,
    SecurityBenchmarkEvaluator,
    VulnerabilityCategory,
    SecuritySeverity,
    ConfidenceStatus,
    SECURITY_DISCLAIMER,
)


def test_security_vulnerability_structure():
    """
    Report all supported findings from the security analysis, including affected line
    or source range, vulnerability category, severity, evidence, potential impact,
    confidence where meaningful, and remediation suggestions.
    """
    reporter = SecurityReporter()
    code = (
        "int main() {\n"
        "    char buf[16];\n"
        "    gets(buf);\n"
        "    return 0;\n"
        "}\n"
    )
    report = reporter.analyze_source(code, filename="main.c")
    assert report.total_findings >= 1
    assert report.is_blocked is True
    assert report.critical_count >= 1

    vuln = report.findings[0]
    assert isinstance(vuln, SecurityVulnerability)
    assert vuln.line == 3
    assert vuln.category == VulnerabilityCategory.UNBOUNDED_INPUT
    assert vuln.severity == SecuritySeverity.CRITICAL
    assert "gets" in vuln.evidence
    assert len(vuln.potential_impact) > 10
    assert "buffer overflow" in vuln.potential_impact.lower()
    assert vuln.cwe_id == "CWE-120"
    assert vuln.confidence == 1.0
    assert vuln.status == ConfidenceStatus.CONFIRMED
    assert len(vuln.remediation_suggestions) >= 1
    assert any("fgets" in s for s in vuln.remediation_suggestions)
    assert vuln.to_dict()["line"] == 3


def test_prioritization_and_confirmed_vs_heuristic():
    """
    Prioritize serious findings, but distinguish confirmed vulnerabilities
    from heuristic warnings.
    """
    reporter = SecurityReporter()
    # Code with a CRITICAL confirmed vulnerability (gets) and a HEURISTIC/LOW warning (system("pause"))
    code = (
        "int system(const char *cmd);\n"
        "int main() {\n"
        "    char buf[16];\n"
        "    system(\"pause\");\n"
        "    gets(buf);\n"
        "    return 0;\n"
        "}\n"
    )
    report = reporter.analyze_source(code, filename="main.c")
    assert len(report.findings) >= 2

    # Prioritization check: CRITICAL must appear before lower severities
    first = report.findings[0]
    assert first.severity == SecuritySeverity.CRITICAL
    assert first.status == ConfidenceStatus.CONFIRMED
    assert "gets" in first.evidence

    # Heuristic check
    heuristic_findings = [f for f in report.findings if f.status == ConfidenceStatus.HEURISTIC]
    assert len(heuristic_findings) >= 1
    const_cmd = heuristic_findings[0]
    assert const_cmd.severity in (SecuritySeverity.LOW, SecuritySeverity.INFO, SecuritySeverity.MEDIUM)


def test_reject_unsupported_ai_findings():
    """
    Avoid reporting unsupported findings merely because a model suspects a problem.
    """
    reporter = SecurityReporter()
    clean_code = "int main() { int x = 42; return x; }"
    report = reporter.analyze_source(clean_code, filter_unsupported_ai=True)
    # Static analysis confirms no issues; clean code must produce 0 findings
    assert len(report.findings) == 0
    assert report.is_blocked is False


def test_post_repair_delta_resolved_and_regressions():
    """
    After a repair, rerun relevant security checks and compare results with original findings.
    Show resolved vulnerabilities, remaining vulnerabilities, and any new findings introduced.
    """
    reporter = SecurityReporter()

    # Case 1: Successful repair (resolves gets vulnerability)
    original_vuln = (
        "int main() {\n"
        "    char buf[16];\n"
        "    gets(buf);\n"
        "    return 0;\n"
        "}\n"
    )
    patched_clean = (
        "#include <stdio.h>\n"
        "int main() {\n"
        "    char buf[16];\n"
        "    fgets(buf, sizeof(buf), stdin);\n"
        "    return 0;\n"
        "}\n"
    )
    delta_good = reporter.compare_patches(original_vuln, patched_clean)
    assert delta_good.is_security_improved is True
    assert delta_good.has_regressions is False
    assert len(delta_good.resolved_vulnerabilities) == 1
    assert len(delta_good.remaining_vulnerabilities) == 0
    assert len(delta_good.introduced_vulnerabilities) == 0
    assert delta_good.resolved_vulnerabilities[0].category == VulnerabilityCategory.UNBOUNDED_INPUT

    # Case 2: Regression introduced (clean code modified by faulty patch introducing gets)
    clean_orig = "int main() { char buf[16]; return 0; }"
    regression_patch = "int main() { char buf[16]; gets(buf); return 0; }"
    delta_bad = reporter.compare_patches(clean_orig, regression_patch)
    assert delta_bad.is_security_improved is False
    assert delta_bad.has_regressions is True
    assert len(delta_bad.introduced_vulnerabilities) == 1
    assert delta_bad.introduced_vulnerabilities[0].severity == SecuritySeverity.CRITICAL


def test_security_disclaimer_present():
    """
    Do not claim that the system detects every vulnerability or that a program is completely secure.
    """
    reporter = SecurityReporter()
    report = reporter.analyze_source("int main() { return 0; }")
    assert report.disclaimer is not None
    assert "cannot guarantee" in report.disclaimer.lower()
    assert "completely secure" in report.disclaimer.lower()

    delta = reporter.compare_patches("int main() { return 0; }", "int main() { return 0; }")
    assert delta.disclaimer is not None


def test_benchmark_evaluation_metrics():
    """
    Where suitable benchmark labels exist, measure false positives, false negatives,
    precision, and recall.
    """
    evaluator = SecurityBenchmarkEvaluator()
    res = evaluator.evaluate_directory("examples/security_fix_2026")
    assert res.total_cases > 0
    assert res.true_positives >= 7
    assert res.false_negatives == 0
    assert res.recall == 1.0  # 100% recall on ground truth vulnerable benchmarks
    assert res.precision >= 0.90
    assert res.f1_score >= 0.90
    assert res.accuracy >= 0.90

    # Test serialization
    data = res.to_dict()
    assert "true_positives" in data
    assert "precision" in data
    assert "recall" in data
    assert "f1_score" in data


def test_security_api_endpoints():
    """
    Test Flask API endpoints for security report, delta compare, and benchmarks.
    """
    from app import app
    client = app.test_client()

    # 1. /api/security/report
    resp = client.post("/api/security/report", json={
        "code": "int main() { char buf[16]; gets(buf); return 0; }",
        "filename": "vuln.c"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["critical_count"] >= 1
    assert data["is_blocked"] is True
    assert len(data["findings"]) >= 1
    assert "disclaimer" in data

    # 2. /api/security/compare
    resp = client.post("/api/security/compare", json={
        "original_code": "int main() { char buf[16]; gets(buf); return 0; }",
        "patched_code": "int main() { char buf[16]; fgets(buf, sizeof(buf), stdin); return 0; }",
        "filename": "repair.c"
    })
    assert resp.status_code == 200
    delta = resp.get_json()
    assert delta["is_security_improved"] is True
    assert delta["has_regressions"] is False
    assert delta["resolved_count"] == 1

    # 3. /api/security/benchmark
    resp = client.get("/api/security/benchmark?dir=examples/security_fix_2026")
    assert resp.status_code == 200
    bench = resp.get_json()
    assert bench["recall"] == 1.0
    assert bench["precision"] >= 0.90
    assert bench["total_cases"] >= 10
