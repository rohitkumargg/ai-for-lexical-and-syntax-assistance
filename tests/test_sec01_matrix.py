import pytest
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from compiler.security_reporter import SecurityReporter

def test_sec01_exact_matrix_all_rows():
    reporter = SecurityReporter()

    # Row 1: non-overflowing constant
    r1 = reporter.analyze_source("int main() { int a = 2147483646 + 1; return a; }", filename="r1.c")
    f1 = [f for f in r1.findings if "SEC-01" in str(f.rule_id) or "overflow" in str(f.category).lower()]
    assert len(f1) == 0, f"Row 1 should have 0 overflow findings, got: {f1}"

    # Row 2: signed overflow constant (2147483647 + 1)
    r2 = reporter.analyze_source("int main() { long long x = 2147483647 + 1; return 0; }", filename="r2.c")
    f2 = [f for f in r2.findings if "SEC-01" in str(f.rule_id) or "overflow" in str(f.category).lower()]
    assert len(f2) == 1, "Row 2 should detect 1 confirmed overflow"
    assert f2[0].status.upper() == "CONFIRMED"

    # Row 3: unsigned overflow constant (4294967295U + 1)
    r3 = reporter.analyze_source("int main() { unsigned int x = 4294967295U + 1; return (int)x; }", filename="r3.c")
    f3 = [f for f in r3.findings if "SEC-01" in str(f.rule_id) or "overflow" in str(f.category).lower()]
    assert len(f3) == 1, "Row 3 should detect 1 confirmed overflow"
    assert f3[0].status.upper() == "CONFIRMED"

    # Row 4: unknown parameters (a + b)
    r4 = reporter.analyze_source("int foo(int a, int b) { return a + b; }", filename="r4.c")
    f4 = [f for f in r4.findings if "SEC-01" in str(f.rule_id) or "overflow" in str(f.category).lower()]
    assert len(f4) == 0, f"Row 4 should have 0 findings, got: {f4}"

    # Row 5: unsigned runtime addition
    r5 = reporter.analyze_source("int main() { unsigned int a = 2147483647; unsigned int b = a + 1; return (int)b; }", filename="r5.c")
    f5 = [f for f in r5.findings if "SEC-01" in str(f.rule_id) or "overflow" in str(f.category).lower()]
    assert len(f5) == 0, f"Row 5 should have 0 findings, got: {f5}"

    # Row 6: x += 1 after INT_MAX (known miss: constant evaluator lacks inter-statement dataflow)
    r6 = reporter.analyze_source("int main() { int x = 2147483647; x += 1; return x; }", filename="r6.c")
    f6 = [f for f in r6.findings if "SEC-01" in str(f.rule_id) or "overflow" in str(f.category).lower()]
    assert len(f6) == 0, "Row 6 is a documented miss (0 findings)"

    # Row 7: (long long)(a + b) - truncating addition before cast
    r7 = reporter.analyze_source("long long foo(int a, int b) { return (long long)(a + b); }", filename="r7.c")
    f7 = [f for f in r7.findings if "SEC-01" in str(f.rule_id) or "overflow" in str(f.category).lower()]
    assert len(f7) == 1, "Row 7 should detect 1 possible overflow"
    assert f7[0].status.upper() == "POSSIBLE"

    # Row 8: (long long)a + b - promoted operand
    r8 = reporter.analyze_source("long long foo(int a, int b) { return (long long)a + b; }", filename="r8.c")
    f8 = [f for f in r8.findings if "SEC-01" in str(f.rule_id) or "overflow" in str(f.category).lower()]
    assert len(f8) == 0, f"Row 8 should have 0 findings, got: {f8}"
