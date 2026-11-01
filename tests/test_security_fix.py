import json
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("."))
from compiler.gui_bridge import repair_source_for_gui
from compiler.security_auto_fixer import SecurityAutoFixer, _split_lines, _code_mask, _function_spans
from compiler.security_engine import SecurityEngine

DIR = os.path.join("examples", "security_fix_2026")
EXPECTED_PATH = os.path.join(DIR, "expected.json")


def normalize_code(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


EXPECTED_FIXED_CODE = {
    "e01_cmd_injection": "int system(char *command);\nint main() {\n    char cmd[50];\n    scanf(\"%49s\", cmd);\n    if (strcmp(cmd, \"ls\") == 0) {\n        system(\"ls\");\n    } else if (strcmp(cmd, \"date\") == 0) {\n        system(\"date\");\n    } else {\n        printf(\"command not allowed\\n\");\n    }\n}\n",
    "e02_scanf_widths": "int main() {\n    char a[20];\n    char b[10];\n    scanf(\"%19s\", a);\n    scanf(\"%9s\", b);\n    return 0;\n}\n",
    "e03_gets": "int main() {\n    char buf[100];\n    fgets(buf, sizeof(buf), stdin);\n    return 0;\n}\n",
    "e04_strcpy": "int main() {\n    char dst[10];\n    char src[20];\n    scanf(\"%19s\", src);\n    snprintf(dst, sizeof(dst), \"%s\", src);\n    return 0;\n}\n",
    "e05_strcat": "int main() {\n    char dst[20] = \"ab\";\n    char src[10];\n    scanf(\"%9s\", src);\n    strncat(dst, src, sizeof(dst) - strlen(dst) - 1);\n    return 0;\n}\n",
    "e06_sprintf": "int main() {\n    char out[16];\n    int n = 5;\n    snprintf(out, sizeof(out), \"%d\", n);\n    return 0;\n}\n",
    "e07_printf_user": "int main() {\n    char name[20];\n    scanf(\"%19s\", name);\n    printf(\"%s\", name);\n    return 0;\n}\n",
}


# ======================================================================
# 1. Test all 11 security fix examples from expected.json
# ======================================================================

def test_security_fix_examples():
    with open(EXPECTED_PATH, "r", encoding="utf-8") as f:
        expected = json.load(f)

    FILE_MAP = {
        "e01_cmd_injection": "attack1.c",
    }

    for name, exp in expected.items():
        fname = FILE_MAP.get(name, f"{name}_broken.c")
        broken_file = os.path.join(DIR, fname)
        with open(broken_file, "r", encoding="utf-8") as f:
            broken_src = f.read()

        # Before status (pipeline without security autofix)
        res_before = repair_source_for_gui(broken_src, filename=fname, enable_ai=False, enable_sec_fix=False)
        assert res_before.get("status") == exp["before"], f"{name}: before status mismatch"

        # After status and code (pipeline with security autofix)
        res_after = repair_source_for_gui(broken_src, filename=fname, enable_ai=False, enable_sec_fix=True)
        corrected_code = res_after.get("corrected_code", broken_src)
        assert res_after.get("status") == exp["after"], f"{name}: after status mismatch"

        if exp["fixed"]:
            fixed_file = os.path.join(DIR, f"{name}_fixed.c")
            if os.path.exists(fixed_file):
                with open(fixed_file, "r", encoding="utf-8") as f:
                    exp_fixed_src = f.read()
            else:
                exp_fixed_src = EXPECTED_FIXED_CODE.get(name)

            if exp_fixed_src is not None:
                assert normalize_code(corrected_code) == normalize_code(exp_fixed_src), f"{name}: code does not match expected fix"
            else:
                assert normalize_code(corrected_code) != normalize_code(broken_src), f"{name}: expected code modification"
        else:
            assert normalize_code(corrected_code) == normalize_code(broken_src), f"{name}: expected no code change"

        all_findings = " ".join(
            [str(w) for w in res_after.get("security_warnings", [])]
            + [str(s) for s in res_after.get("security_suggestions", [])]
            + [str(w) for w in res_before.get("security_warnings", [])]
            + [str(s) for s in res_before.get("security_suggestions", [])]
        )
        if "finding_contains" in exp:
            assert exp["finding_contains"] in all_findings, f"{name}: missing {exp['finding_contains']}"

        if "must_not_contain" in exp:
            after_warnings = " ".join([str(w) for w in res_after.get("security_warnings", [])])
            assert exp["must_not_contain"] not in after_warnings, f"{name}: contains forbidden {exp['must_not_contain']}"

        # Idempotence: running pipeline on output again produces no change
        res_idemp = repair_source_for_gui(corrected_code, filename=f"{name}_repaired.c", enable_ai=False, enable_sec_fix=True)
        assert normalize_code(res_idemp.get("corrected_code", "")) == normalize_code(corrected_code), f"{name}: not idempotent"


# ======================================================================
# 2. Prototype alone yields zero findings
# ======================================================================

def test_prototype_alone_zero_findings():
    src = "int system(char *command);\nint main() {\n    return 0;\n}\n"
    engine = SecurityEngine()
    issues, _, _ = engine.analyze(src)
    assert len(issues) == 0, f"Expected 0 findings for prototype, got: {issues}"


# ======================================================================
# 3. Numeric scanf followed by system("ls") yields no CRITICAL
# ======================================================================

def test_numeric_scanf_not_tainted():
    src = (
        "int system(char *command);\n"
        "int main() {\n"
        "    int x;\n"
        "    scanf(\"%d\", &x);\n"
        "    system(\"ls\");\n"
        "    return 0;\n"
        "}\n"
    )
    res = repair_source_for_gui(src, filename="numeric_scanf.c", enable_ai=False, enable_sec_fix=True)
    crit_issues = [w for w in res.get("security_warnings", []) if "[CRITICAL]" in str(w)]
    assert len(crit_issues) == 0, f"Expected 0 critical issues, got {crit_issues}"
    assert res.get("status") == "SUCCESS"


# ======================================================================
# 4. Must-not-fire cases for every rule
# ======================================================================

def test_must_not_fire_gets_free_file_unchanged():
    src = "int main() {\n    char buf[100];\n    fgets(buf, sizeof(buf), stdin);\n    return 0;\n}\n"
    res = repair_source_for_gui(src, filename="gets_free.c", enable_ai=False, enable_sec_fix=True)
    assert normalize_code(res.get("corrected_code", "")) == normalize_code(src)


def test_must_not_fire_scanf_already_bounded():
    src = "int main() {\n    char a[20];\n    scanf(\"%19s\", a);\n    return 0;\n}\n"
    res = repair_source_for_gui(src, filename="scanf_bounded.c", enable_ai=False, enable_sec_fix=True)
    assert normalize_code(res.get("corrected_code", "")) == normalize_code(src)


def test_must_not_fire_strcpy_pointer_dest_unchanged():
    src = "int copy(char *dst, char *src) {\n    strcpy(dst, src);\n    return 0;\n}\n"
    res = repair_source_for_gui(src, filename="strcpy_ptr.c", enable_ai=False, enable_sec_fix=True)
    assert normalize_code(res.get("corrected_code", "")) == normalize_code(src)


def test_must_not_fire_strcat_pointer_dest_unchanged():
    src = "int cat(char *dst, char *src) {\n    strcat(dst, src);\n    return 0;\n}\n"
    res = repair_source_for_gui(src, filename="strcat_ptr.c", enable_ai=False, enable_sec_fix=True)
    assert normalize_code(res.get("corrected_code", "")) == normalize_code(src)


def test_must_not_fire_sprintf_pointer_dest_unchanged():
    src = "int fmt(char *out) {\n    sprintf(out, \"%d\", 5);\n    return 0;\n}\n"
    res = repair_source_for_gui(src, filename="sprintf_ptr.c", enable_ai=False, enable_sec_fix=True)
    assert normalize_code(res.get("corrected_code", "")) == normalize_code(src)


def test_must_not_fire_printf_literal_unchanged():
    src = "int main() {\n    printf(\"hello world\\n\");\n    return 0;\n}\n"
    res = repair_source_for_gui(src, filename="printf_literal.c", enable_ai=False, enable_sec_fix=True)
    assert normalize_code(res.get("corrected_code", "")) == normalize_code(src)


def test_must_not_fire_system_literal_unchanged():
    src = "int system(char *command);\nint main() {\n    system(\"ls\");\n    return 0;\n}\n"
    res = repair_source_for_gui(src, filename="system_lit.c", enable_ai=False, enable_sec_fix=True)
    assert normalize_code(res.get("corrected_code", "")) == normalize_code(src)


def test_must_not_fire_system_untainted_var_unchanged():
    src = "int system(char *command);\nint main() {\n    char cmd[40] = \"ls\";\n    system(cmd);\n    return 0;\n}\n"
    res = repair_source_for_gui(src, filename="system_untainted.c", enable_ai=False, enable_sec_fix=True)
    assert normalize_code(res.get("corrected_code", "")) == normalize_code(src)


# ======================================================================
# 5. Step 6 Verifier Rejection Tests (Model-style bad patches)
# ======================================================================

def test_verifier_rejects_undeclared_arr():
    """scanf("%11s", arr) with arr undeclared must be rejected."""
    fixer = SecurityAutoFixer()
    old_src = (
        "int main() {\n"
        "    char cmd[12];\n"
        "    scanf(\"%s\", cmd);\n"
        "    return 0;\n"
        "}\n"
    )
    old_line = '    scanf("%s", cmd);'
    new_line = '    scanf("%11s", arr);'
    cand_src = old_src.replace(old_line, new_line)

    lines, _ = _split_lines(old_src)
    mask = _code_mask(lines)
    spans = _function_spans(lines, mask)
    span = spans[0]

    ok, reason = fixer.verify_patch(
        old_source=old_src,
        cand_source=cand_src,
        old_line=old_line,
        new_line=new_line,
        span=span,
        lines=lines,
        mask=mask,
        target_vname="cmd",
        expected_size=12,
    )
    assert not ok, "Expected patch with undeclared identifier 'arr' to be rejected"
    assert "arr" in reason or "invented" in reason or "undeclared" in reason


def test_verifier_rejects_int_destination():
    """scanf("%11s", a) with a an int must be rejected."""
    fixer = SecurityAutoFixer()
    old_src = (
        "int main() {\n"
        "    int a = 0;\n"
        "    scanf(\"%s\", a);\n"
        "    return 0;\n"
        "}\n"
    )
    old_line = '    scanf("%s", a);'
    new_line = '    scanf("%11s", a);'
    cand_src = old_src.replace(old_line, new_line)

    lines, _ = _split_lines(old_src)
    mask = _code_mask(lines)
    spans = _function_spans(lines, mask)
    span = spans[0]

    ok, reason = fixer.verify_patch(
        old_source=old_src,
        cand_source=cand_src,
        old_line=old_line,
        new_line=new_line,
        span=span,
        lines=lines,
        mask=mask,
        target_vname="a",
        expected_size=None,
    )
    assert not ok, "Expected patch with int destination 'a' for %s to be rejected"


def test_verifier_rejects_wrong_width_for_size():
    """scanf("%11s", s) with s a char[10] must be rejected (size 10 requires width 9)."""
    fixer = SecurityAutoFixer()
    old_src = (
        "int main() {\n"
        "    char s[10];\n"
        "    scanf(\"%s\", s);\n"
        "    return 0;\n"
        "}\n"
    )
    old_line = '    scanf("%s", s);'
    new_line = '    scanf("%11s", s);'
    cand_src = old_src.replace(old_line, new_line)

    lines, _ = _split_lines(old_src)
    mask = _code_mask(lines)
    spans = _function_spans(lines, mask)
    span = spans[0]

    ok, reason = fixer.verify_patch(
        old_source=old_src,
        cand_source=cand_src,
        old_line=old_line,
        new_line=new_line,
        span=span,
        lines=lines,
        mask=mask,
        target_vname="s",
        expected_size=10,
    )
    assert not ok, "Expected patch with wrong width 11 for char[10] to be rejected"
    assert "width" in reason or "10" in reason or "9" in reason
