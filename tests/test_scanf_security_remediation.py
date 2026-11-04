import pytest
import os
import json
from compiler.scanf_analyzer import ScanfSecurityAnalyzer
from compiler.repair_planner import RepairPlanner, calculate_six_metrics
from compiler.code_quality import calculate_code_quality_metrics
from compiler.security_auto_fixer import SecurityAutoFixer
from compiler.repair_job_manager import get_repair_job_manager


def test_scanf_20_byte_destination():
    """1. scanf('%s', a) where a is char[20]: identifies capacity 20, recommends %19s, CWE-120."""
    src = "char a[20]; scanf(\"%s\", a);"
    findings = ScanfSecurityAnalyzer.analyze_call(
        fn_name="scanf",
        line=1,
        col=12,
        args_text=['"%s"', "a"],
        fmt_raw="%s",
        source_text=src,
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.dest_var_name == "a"
    assert f.declared_capacity == 20
    assert f.max_safe_width == 19
    assert f.safe_replacement_spec == "%19s"
    assert "CWE-120" in f.message
    assert f.is_vulnerable is True


def test_scanf_20_byte_bounded_safe():
    """2. scanf('%19s', a) with 20-byte buffer: verified safe, no buffer overflow finding."""
    src = "char a[20]; scanf(\"%19s\", a);"
    findings = ScanfSecurityAnalyzer.analyze_call(
        fn_name="scanf",
        line=1,
        col=12,
        args_text=['"%19s"', "a"],
        fmt_raw="%19s",
        source_text=src,
    )
    assert len(findings) == 0


def test_scanf_10_byte_destination():
    """3. scanf('%s', b) where b is char[10]: identifies capacity 10, recommends %9s, CWE-120."""
    src = "char b[10]; scanf(\"%s\", b);"
    findings = ScanfSecurityAnalyzer.analyze_call(
        fn_name="scanf",
        line=1,
        col=12,
        args_text=['"%s"', "b"],
        fmt_raw="%s",
        source_text=src,
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.dest_var_name == "b"
    assert f.declared_capacity == 10
    assert f.max_safe_width == 9
    assert f.safe_replacement_spec == "%9s"
    assert "CWE-120" in f.message
    assert f.is_vulnerable is True


def test_scanf_10_byte_bounded_safe():
    """4. scanf('%9s', b) with 10-byte buffer: verified safe, no buffer overflow finding."""
    src = "char b[10]; scanf(\"%9s\", b);"
    findings = ScanfSecurityAnalyzer.analyze_call(
        fn_name="scanf",
        line=1,
        col=12,
        args_text=['"%9s"', "b"],
        fmt_raw="%9s",
        source_text=src,
    )
    assert len(findings) == 0


def test_scanf_security_autofix_both():
    """5. Two findings processed cleanly by SecurityAutoFixer in one pass."""
    src = """#include <stdio.h>
int main() {
    char a[20];
    char b[10];
    scanf("%s", a);
    scanf("%s", b);
    return 0;
}
"""
    fixer = SecurityAutoFixer()
    res = fixer.apply_fixes(src)
    assert 'scanf("%19s", a)' in res.source
    assert 'scanf("%9s", b)' in res.source
    assert len(res.applied_steps) >= 2


def test_repair_status_consistency():
    """7. Zero applied repairs never produces 100% repair completion."""
    mgr = get_repair_job_manager()
    job = mgr.create_job(
        code="int main() { return 0; }",
        filename="test.c",
        language="c",
        operation="repair",
    )
    status_dict = job.to_status_dict()
    assert status_dict["windows_done"] == 0
    assert status_dict["state"] == "PENDING"


def test_benchmark_contamination_prevention():
    """8. Benchmark file cannot contaminate an unrelated source analysis."""
    src = "int main() { return 0; }"
    planner = RepairPlanner()
    findings, assessment = planner.analyze_program(src, filename="clean.c", language="c")
    # Verify no unrelated functions from benchmark files are injected
    assert len(findings) == 0


def test_metric_formula_consistency():
    """10. Code quality and Poor Code metrics are mathematically consistent."""
    cq = calculate_code_quality_metrics(q=76.0, o=20.0, v=10.0)
    assert cq["overall_code_quality"] is not None
    # Poor code is inverse of quality (100 - 76 = 24)
    assert cq["poor_code"] == 24.0
    assert cq["is_complete"] is True
