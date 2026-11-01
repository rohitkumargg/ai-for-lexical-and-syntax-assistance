import pytest
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from compiler.security_reporter import SecurityReporter

def test_scanf_safe_bound_no_false_positive():
    """Verify char cmd[50] with scanf('%49s', cmd) has 0 vulnerabilities."""
    code = """int main() {
    char cmd[50];
    scanf("%49s", cmd);
    return 0;
}"""
    rep = SecurityReporter().analyze_source(code)
    vulns = [f for f in rep.findings if "scanf" in f.rule_id.lower() or "scanf" in str(f.evidence).lower()]
    assert len(vulns) == 0, f"Expected 0 vulnerabilities for safe %49s into 50-byte buffer, got: {vulns}"

def test_scanf_unsafe_bound_detected():
    """Verify char cmd[50] with scanf('%50s', cmd) is flagged as overflow/off-by-one."""
    code = """int main() {
    char cmd[50];
    scanf("%50s", cmd);
    return 0;
}"""
    rep = SecurityReporter().analyze_source(code)
    vulns = [f for f in rep.findings if "scanf" in f.rule_id.lower() or "scanf" in str(f.evidence).lower()]
    assert len(vulns) > 0, "Expected vulnerability for unsafe %50s into 50-byte buffer"
