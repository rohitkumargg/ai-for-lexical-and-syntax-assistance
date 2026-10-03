import json
import os
import pytest

from compiler.security_rules import run_security_rules
from compiler.semantic_checker import SemanticChecker
from compiler.gui_bridge import repair_source_for_gui
from test_parser import parse_source, get_all_error_strings


WEEK8_DIR = os.path.join("examples", "week8_2026")


# ======================================================================
# STEP 0b TESTS: Semantic Checker Init Declarator Fix
# ======================================================================

def test_semantic_init_declarator_undeclared():
    """(1) int y = zzz + 1; -> undeclared zzz"""
    code = "int main() { int y = zzz + 1; return y; }"
    tree, listeners, _ = parse_source(code, "test_0b_1.c")
    assert not get_all_error_strings(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    issues = checker.get_issues()
    undeclared = [i for i in issues if i["kind"] == "undeclared"]
    assert len(undeclared) == 1
    assert undeclared[0]["name"] == "zzz"


def test_semantic_init_declarator_type_mismatch():
    """(2) char *s = 5; -> type_mismatch / pointer assignment warning"""
    code = "int main() { char *s = 5; return 0; }"
    tree, listeners, _ = parse_source(code, "test_0b_2.c")
    assert not get_all_error_strings(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    issues = checker.get_issues()
    type_issues = [i for i in issues if i["kind"] in ("pointer_assignment_warning", "type_mismatch")]
    assert len(type_issues) >= 1
    assert type_issues[0]["name"] == "s"


def test_semantic_init_declarator_used_var():
    """(3) int x = 1; int y = x; return y; -> no issues"""
    code = "int main() { int x = 1; int y = x; return y; }"
    tree, listeners, _ = parse_source(code, "test_0b_3.c")
    assert not get_all_error_strings(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i["kind"] != "unused"]
    assert len(issues) == 0
    # Also verify x is NOT reported as unused
    unused = [i for i in checker.get_issues() if i["kind"] == "unused"]
    assert len(unused) == 0


def test_semantic_init_declarator_multi_declarators():
    """(4) int a = 1, b = 2; return a + b; -> no issues"""
    code = "int main() { int a = 1, b = 2; return a + b; }"
    tree, listeners, _ = parse_source(code, "test_0b_4.c")
    assert not get_all_error_strings(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    issues = checker.get_issues()
    assert len(issues) == 0


# ======================================================================
# STEP 0c TESTS: Allowlist of standard library functions & NULL
# ======================================================================

def test_semantic_allowlist_functions_and_null():
    """memcpy, memmove, memset, malloc, calloc, free, fgets, strlen, NULL must not be undeclared."""
    code = """
    int main() {
        char *p = NULL;
        p = malloc(100);
        char *q = calloc(10, 10);
        memset(p, 0, 100);
        memcpy(p, q, 10);
        memmove(p, q, 5);
        int len = strlen(p);
        free(p);
        free(q);
        return len;
    }
    """
    tree, listeners, _ = parse_source(code, "test_0c.c")
    assert not get_all_error_strings(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    undeclared = [i for i in checker.get_issues() if i["kind"] == "undeclared"]
    assert len(undeclared) == 0


# ======================================================================
# SEC-01 INLINE TEST
# ======================================================================

def test_sec01_inline_test():
    """long long r = a * b; with int a, b becomes long long r = (long long)a * b;"""
    code = (
        "int main() {\n"
        "    int a = 100000;\n"
        "    int b = 100000;\n"
        "    long long r = a * b;\n"
        "    return 0;\n"
        "}"
    )
    fixed, findings, steps = run_security_rules(code)
    assert "(long long)a * b" in fixed
    assert any(f.rule == "SEC-01" and f.action == "auto_fixed" for f in findings)
    assert any("SEC-01" in s for s in steps)


# ======================================================================
# EXAMPLES/WEEK8_2026 TESTS AGAINST expected.json
# ======================================================================

def test_week8_examples_against_expected():
    expected_path = os.path.join(WEEK8_DIR, "expected.json")
    with open(expected_path, "r", encoding="utf-8") as f:
        expected_data = json.load(f)

    for filename, exp in expected_data.items():
        file_path = os.path.join(WEEK8_DIR, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            original_code = f.read()

        fixed_source, findings, steps = run_security_rules(original_code)

        if exp["rule"] is None:
            # Clean / suggested file: should produce 0 findings
            rule_findings = [f for f in findings if f.action != "unchanged"]
            assert len(rule_findings) == 0, f"{filename} expected 0 findings, got {rule_findings}"
            assert fixed_source == original_code, f"{filename} was unexpectedly modified"
            continue

        target_rule = exp["rule"]
        matching_findings = [f for f in findings if f.rule == target_rule]
        assert len(matching_findings) >= 1, f"{filename} missing finding for {target_rule}"
        finding = matching_findings[0]

        assert finding.kind == exp["finding"], f"{filename} finding mismatch"
        assert finding.line == exp["line"], f"{filename} line mismatch"
        assert finding.action == exp["action"], f"{filename} action mismatch"

        if "suggestion_contains" in exp:
            assert exp["suggestion_contains"] in (finding.suggestion or ""), (
                f"{filename} suggestion {finding.suggestion!r} missing {exp['suggestion_contains']!r}"
            )

        if exp.get("also_reports"):
            for extra_rule in exp["also_reports"]:
                assert any(f.rule == extra_rule for f in findings), (
                    f"{filename} expected extra rule {extra_rule}"
                )

        if exp.get("fixed_file"):
            expected_fixed_path = os.path.join(WEEK8_DIR, exp["fixed_file"])
            with open(expected_fixed_path, "r", encoding="utf-8") as f:
                expected_fixed = f.read()
            assert fixed_source.strip() == expected_fixed.strip(), (
                f"{filename} fixed source does not match {exp['fixed_file']}"
            )


def test_clean_guard_byte_identical():
    """clean_guard.c must stay byte-identical and produce zero findings."""
    clean_path = os.path.join(WEEK8_DIR, "clean_guard.c")
    with open(clean_path, "rb") as f:
        original_bytes = f.read()

    source = original_bytes.decode("utf-8")
    fixed_source, findings, steps = run_security_rules(source)

    assert fixed_source.encode("utf-8") == original_bytes, "clean_guard.c was modified"
    assert len(findings) == 0, f"clean_guard.c produced unexpected findings: {findings}"
    assert len(steps) == 0, f"clean_guard.c produced unexpected steps: {steps}"


def test_gui_bridge_integration():
    """Test full pipeline integration via repair_source_for_gui on week8 examples."""
    for fn in ["01_integer_overflow_broken.c", "03_null_dereference_broken.c", "06_off_by_one_broken.c"]:
        path = os.path.join(WEEK8_DIR, fn)
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        res = repair_source_for_gui(code, fn, enable_ai=False)
        assert res["status"] in ("SUCCESS", "SUCCESS_WITH_WARNINGS")
        assert any(s.startswith("SEC-") for s in res.get("applied_steps", []))
