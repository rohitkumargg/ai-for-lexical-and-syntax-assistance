import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("."))

from compiler.taint_checker import TaintChecker
from compiler.malicious_precheck import MaliciousCodePrecheck
from compiler.security_risk import SecurityRiskScorer
from compiler.repair_planner import RepairPlanner
from compiler.finding import Finding, FindingCategory, FindingSeverity, SourceLocation


def test_tainted_system_high_risk_not_clean():
    """Tainted system() must be classified as CWE-78 CRITICAL, report source->sink, have high risk, and never be CLEAN."""
    code = """#include <stdio.h>
#include <stdlib.h>

int main() {
    char cmd[128];
    printf("Enter command: ");
    scanf("%49s", cmd);
    system(cmd);
    return 0;
}
"""
    # 1. Taint Checker
    tc = TaintChecker()
    issues = tc.check(code)
    assert len(issues) >= 1
    cwe78 = next((i for i in issues if i.cwe == "CWE-78"), None)
    assert cwe78 is not None
    assert cwe78.severity == "CRITICAL"
    assert "source line" in cwe78.message and "sink line" in cwe78.message

    # 2. Malicious Precheck
    pre_rep = MaliciousCodePrecheck.analyze(code, "test.c")
    cmd_fnds = [f for f in pre_rep.findings if "CWE-78" in f.rule_id or f.category == "COMMAND_INJECTION"]
    assert len(cmd_fnds) >= 1
    assert cmd_fnds[0].severity == "CRITICAL"
    assert "Educational/benign or guarded" not in cmd_fnds[0].explanation

    # 3. Security Risk Parity: Tainted sink score >= unbounded scanf
    unbounded_scanf_code = """#include <stdio.h>
int main() {
    char buf[64];
    scanf("%s", buf);
    return 0;
}
"""
    planner = RepairPlanner()
    res_tainted = planner.plan_and_repair(code, filename="test.c", language="c")
    res_scanf = planner.plan_and_repair(unbounded_scanf_code, filename="test.c", language="c")

    assert res_tainted["status"] != "CLEAN"
    assert res_tainted["status"] in ("VALID_WITH_SECURITY_ISSUES", "VALID_WITH_WARNINGS")

    # Risk score parity
    risk_tainted = res_tainted.get("baseline_scores", {}).get("security_risk_score", 0.0)
    risk_scanf = res_scanf.get("baseline_scores", {}).get("security_risk_score", 0.0)
    assert risk_tainted is not None and risk_tainted >= risk_scanf


def test_constant_string_system_lower_severity():
    """Constant-string system() must be reported with lower severity (LOW) and never CLEAN."""
    code = """#include <stdio.h>
#include <stdlib.h>

int main() {
    system("ls -la");
    return 0;
}
"""
    planner = RepairPlanner()
    res = planner.plan_and_repair(code, filename="test.c", language="c")

    # Must never be CLEAN when findings exist
    assert res["status"] != "CLEAN"
    assert res["status"] in ("VALID_WITH_SECURITY_ISSUES", "VALID_WITH_WARNINGS")

    findings = res.get("findings", [])
    assert len(findings) >= 1
    const_shell = next(
        (f for f in findings if "Shell call with constant command" in str(f.get("explanation", ""))
         or "constant command" in str(f.get("title", "")).lower()
         or "SEC-CONSTANT" in str(f.get("rule_id", ""))),
        None
    )
    assert const_shell is not None
    assert const_shell.get("severity", "").upper() == "LOW"
    assert "Educational/benign or guarded" not in str(const_shell.get("explanation", ""))


def test_clean_program_is_clean():
    """Clean program with 0 compiler errors and 0 vulnerabilities must have status CLEAN and empty findings."""
    code = """#include <stdio.h>

int main() {
    int x = 42;
    printf("Result: %d\\n", x);
    return 0;
}
"""
    planner = RepairPlanner()
    res = planner.plan_and_repair(code, filename="test.c", language="c")
    assert res["status"] == "CLEAN"
    assert len(res.get("findings", [])) == 0


def test_property_banner_counts_equal_findings_list_length_10_samples():
    """Property test: Banner counts must exactly equal the findings list length across 10 sample programs."""
    samples = [
        # 1. Clean
        "int main() { return 0; }",
        # 2. Tainted system
        '#include <stdlib.h>\n#include <stdio.h>\nint main() { char b[64]; gets(b); system(b); return 0; }',
        # 3. Constant system
        '#include <stdlib.h>\nint main() { system("whoami"); return 0; }',
        # 4. Unbounded scanf
        '#include <stdio.h>\nint main() { char s[16]; scanf("%s", s); return 0; }',
        # 5. Format string
        '#include <stdio.h>\nint main() { char msg[32] = "hi"; printf(msg); return 0; }',
        # 6. Gets invocation
        '#include <stdio.h>\nint main() { char b[32]; gets(b); return 0; }',
        # 7. Clean function
        'int add(int a, int b) { return a + b; }\nint main() { return add(2, 3); }',
        # 8. Clean calculation
        'int main() { int a = 1; int b = 2; return a + b; }',
        # 9. Clean array loop
        'int main() { int arr[5] = {0}; return arr[0]; }',
        # 10. Clean struct
        'struct S { int x; }; int main() { struct S s = {10}; return s.x; }',
    ]

    planner = RepairPlanner()
    for idx, src in enumerate(samples):
        res = planner.plan_and_repair(src, filename=f"sample_{idx}.c", language="c")
        fnds = res.get("findings", [])
        if len(fnds) == 0:
            assert res["status"] == "CLEAN", f"Sample {idx} had 0 findings but status was {res['status']}"
        else:
            assert res["status"] != "CLEAN", f"Sample {idx} had {len(fnds)} findings but status was CLEAN"
        # Total findings count reported must equal len(findings)
        assert res.get("total_findings", len(fnds)) == len(fnds), f"Sample {idx} count mismatch"
