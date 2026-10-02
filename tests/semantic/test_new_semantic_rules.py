import pytest
from test_parser import parse_source, has_any_errors
from compiler.semantic_checker import SemanticChecker
from compiler.semantic_auto_fixer import fix_semantic_issue
from compiler.gui_bridge import repair_source_for_gui


# =====================================================================
# A. Scalar-to-Pointer Assignment
# =====================================================================

def test_scalar_to_pointer_positive_simple_identifier():
    src = (
        "int main() {\n"
        "    int value = 7;\n"
        "    int *pointer = value;\n"
        "    return 0;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if "pointer" in i.get("kind", "")]
    assert len(issues) >= 1
    issue = issues[0]

    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int *pointer = &value;" in fixed

    # Revalidation: reparse + recheck
    tree2, listeners2, _ = parse_source(fixed, "test_fixed.c")
    assert tree2 is not None and not has_any_errors(listeners2)
    checker2 = SemanticChecker()
    checker2.visit(tree2)
    new_issues = [i for i in checker2.get_issues() if "pointer" in i.get("kind", "")]
    assert len(new_issues) == 0


def test_scalar_to_pointer_positive_assignment_statement():
    src = (
        "int main() {\n"
        "    int val = 42;\n"
        "    int *p = 0;\n"
        "    p = val;\n"
        "    return 0;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("line") == 4]
    assert len(issues) >= 1

    fixed, msg = fix_semantic_issue(src, issues[0])
    assert msg is not None
    assert "p = &val;" in fixed


def test_scalar_to_pointer_negative_arbitrary_expression():
    src = (
        "int main() {\n"
        "    int x = 5;\n"
        "    int *p = x + 1;\n"
        "    return 0;\n"
        "}\n"
    )
    issue = {"kind": "pointer_assignment_warning", "line": 3, "col": 9, "msg": "Cannot assign 'int' to 'int*' for variable 'p'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_scalar_to_pointer_negative_function_call():
    src = (
        "int foo() { return 1; }\n"
        "int main() {\n"
        "    int *p = foo();\n"
        "    return 0;\n"
        "}\n"
    )
    issue = {"kind": "pointer_assignment_warning", "line": 3, "col": 9, "msg": "Cannot assign 'int' to 'int*' for variable 'p'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_scalar_to_pointer_negative_constant_literal():
    src = (
        "int main() {\n"
        "    int *p = 10;\n"
        "    return 0;\n"
        "}\n"
    )
    issue = {"kind": "pointer_assignment_warning", "line": 2, "col": 9, "msg": "Cannot assign 'int' to 'int*' for variable 'p'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_scalar_to_pointer_negative_incompatible_type():
    src = (
        "int main() {\n"
        "    float f = 1.0;\n"
        "    int *p = f;\n"
        "    return 0;\n"
        "}\n"
    )
    issue = {"kind": "pointer_assignment_warning", "line": 3, "col": 9, "msg": "Cannot assign 'float' to 'int*' for variable 'p'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_scalar_to_pointer_idempotent():
    src = (
        "int main() {\n"
        "    int value = 7;\n"
        "    int *pointer = &value;\n"
        "    return 0;\n"
        "}\n"
    )
    issue = {"kind": "pointer_assignment_warning", "line": 3, "col": 9, "msg": "Cannot assign 'int' to 'int*' for variable 'pointer'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


# =====================================================================
# B. Invalid Dereference of Scalar
# =====================================================================

def test_invalid_dereference_positive_simple_scalar():
    src = (
        "int main() {\n"
        "    int value = 7;\n"
        "    int result = *value;\n"
        "    return result;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "invalid_dereference"]
    assert len(issues) == 1
    assert issues[0]["name"] == "value"

    fixed, msg = fix_semantic_issue(src, issues[0])
    assert msg is not None
    assert "int result = value;" in fixed

    # Revalidation: reparse + recheck
    tree2, listeners2, _ = parse_source(fixed, "test_fixed.c")
    assert tree2 is not None and not has_any_errors(listeners2)
    checker2 = SemanticChecker()
    checker2.visit(tree2)
    new_issues = [i for i in checker2.get_issues() if i.get("kind") == "invalid_dereference"]
    assert len(new_issues) == 0


def test_invalid_dereference_negative_nested_expression():
    src = (
        "int main() {\n"
        "    int x = 10;\n"
        "    int y = *(x + 1);\n"
        "    return 0;\n"
        "}\n"
    )
    issue = {"kind": "invalid_dereference", "line": 3, "col": 12, "name": "", "msg": "Cannot dereference non-pointer type 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_invalid_dereference_negative_function_call():
    src = (
        "int foo() { return 5; }\n"
        "int main() {\n"
        "    int y = *foo();\n"
        "    return 0;\n"
        "}\n"
    )
    issue = {"kind": "invalid_dereference", "line": 3, "col": 12, "name": "", "msg": "Cannot dereference non-pointer type 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_invalid_dereference_negative_valid_pointer_dereference():
    src = (
        "int main() {\n"
        "    int x = 10;\n"
        "    int *p = &x;\n"
        "    int y = *p;\n"
        "    return y;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    deref_issues = [i for i in checker.get_issues() if i.get("kind") == "invalid_dereference"]
    assert len(deref_issues) == 0


# =====================================================================
# C. Narrowing Conversion
# =====================================================================

def test_narrowing_positive_double_to_int():
    src = (
        "int main() {\n"
        "    double d = 10.5;\n"
        "    int i = d;\n"
        "    return 0;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "type_mismatch"]
    assert len(issues) >= 1

    fixed, msg = fix_semantic_issue(src, issues[0])
    assert msg is not None
    assert "explicit narrowing conversion" in msg
    assert "int i = (int)d;" in fixed

    # Revalidation
    tree2, listeners2, _ = parse_source(fixed, "test_fixed.c")
    assert tree2 is not None and not has_any_errors(listeners2)
    checker2 = SemanticChecker()
    checker2.visit(tree2)
    new_issues = [i for i in checker2.get_issues() if i.get("kind") == "type_mismatch"]
    assert len(new_issues) == 0


def test_narrowing_positive_float_to_short():
    src = (
        "int main() {\n"
        "    float f = 5.5;\n"
        "    short s = f;\n"
        "    return 0;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "type_mismatch"]
    assert len(issues) >= 1

    fixed, msg = fix_semantic_issue(src, issues[0])
    assert msg is not None
    assert "explicit narrowing conversion" in msg
    assert "short s = (short)f;" in fixed

    # Revalidation
    tree2, listeners2, _ = parse_source(fixed, "test_fixed.c")
    assert tree2 is not None and not has_any_errors(listeners2)


def test_narrowing_positive_double_to_char():
    src = (
        "int main() {\n"
        "    double d = 65.2;\n"
        "    char c = d;\n"
        "    return 0;\n"
        "}\n"
    )
    issue = {"kind": "type_mismatch", "line": 3, "col": 9, "msg": "Cannot assign 'double' to 'char' for variable 'c'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "char c = (char)d;" in fixed


def test_narrowing_negative_pointer_to_int():
    src = (
        "int main() {\n"
        "    int *p = 0;\n"
        "    int x = p;\n"
        "    return 0;\n"
        "}\n"
    )
    issue = {"kind": "type_mismatch", "line": 3, "col": 8, "msg": "Cannot assign 'int*' to 'int' for variable 'x'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_narrowing_idempotent():
    src = (
        "int main() {\n"
        "    double d = 10.5;\n"
        "    int i = (int)d;\n"
        "    return 0;\n"
        "}\n"
    )
    issue = {"kind": "type_mismatch", "line": 3, "col": 8, "msg": "Cannot assign 'double' to 'int' for variable 'i'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


# =====================================================================
# D. Uninitialized Variable
# =====================================================================

def test_uninitialized_variable_detection_and_suggestion():
    src = (
        "int main() {\n"
        "    int x;\n"
        "    printf(\"%d\", x);\n"
        "    return 0;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "uninitialized_variable"]
    assert len(issues) == 1
    assert issues[0]["name"] == "x"

    # Preserves source without arbitrary modification
    fixed, msg = fix_semantic_issue(src, issues[0])
    assert msg is None
    assert fixed == src
    assert "uninitialized" in issues[0].get("suggestion", "")


def test_uninitialized_variable_negative_initialized():
    src = (
        "int main() {\n"
        "    int x = 0;\n"
        "    printf(\"%d\", x);\n"
        "    return 0;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "uninitialized_variable"]
    assert len(issues) == 0


def test_uninitialized_variable_negative_address_of():
    src = (
        "int main() {\n"
        "    int x;\n"
        "    scanf(\"%d\", &x);\n"
        "    printf(\"%d\", x);\n"
        "    return 0;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "uninitialized_variable"]
    assert len(issues) == 0


# =====================================================================
# E. Constant Array Out-of-Bounds
# =====================================================================

def test_out_of_bounds_detection_and_suggestion():
    src = (
        "int main() {\n"
        "    int a[3];\n"
        "    int x = a[5];\n"
        "    return x;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "out_of_bounds"]
    assert len(issues) == 1
    assert issues[0]["name"] == "a"
    assert "out of bounds" in issues[0]["msg"]

    fixed, msg = fix_semantic_issue(src, issues[0])
    assert msg is None
    assert fixed == src
    assert "out of bounds" in issues[0].get("suggestion", "")


def test_out_of_bounds_negative_in_bounds():
    src = (
        "int main() {\n"
        "    int a[3];\n"
        "    int x = a[2];\n"
        "    return x;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "out_of_bounds"]
    assert len(issues) == 0


# =====================================================================
# F. Constant Division by Zero
# =====================================================================

def test_division_by_zero_detection_and_suggestion():
    src = (
        "int main() {\n"
        "    int x = 10 / 0;\n"
        "    return x;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "division_by_zero"]
    assert len(issues) == 1

    fixed, msg = fix_semantic_issue(src, issues[0])
    assert msg is None
    assert fixed == src
    assert "zero denominator" in issues[0].get("suggestion", "")


def test_modulo_by_zero_detection():
    src = (
        "int main() {\n"
        "    int x = 10 % 0;\n"
        "    return x;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "division_by_zero"]
    assert len(issues) == 1


def test_division_by_zero_negative_nonzero():
    src = (
        "int main() {\n"
        "    int x = 10 / 2;\n"
        "    return x;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "division_by_zero"]
    assert len(issues) == 0


# =====================================================================
# G. Missing Return
# =====================================================================

def test_missing_return_detection_and_suggestion():
    src = (
        "int f() {\n"
        "    int x = 5;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "missing_return"]
    assert len(issues) == 1
    assert issues[0]["name"] == "f"

    fixed, msg = fix_semantic_issue(src, issues[0])
    assert msg is None
    assert fixed == src
    assert "return statement" in issues[0].get("suggestion", "")


def test_missing_return_negative_has_return():
    src = (
        "int f() {\n"
        "    int x = 5;\n"
        "    return x;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "missing_return"]
    assert len(issues) == 0


def test_missing_return_negative_void_function():
    src = (
        "void f() {\n"
        "    int x = 5;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "missing_return"]
    assert len(issues) == 0


# =====================================================================
# H. Case Outside Switch
# =====================================================================

def test_case_outside_switch_detection():
    src = (
        "int main() {\n"
        "    int x = 1;\n"
        "    case 1:\n"
        "        x = 10;\n"
        "    return x;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "case_outside_switch"]
    assert len(issues) == 1

    # Deterministic repair removes the stray label, never invents an arbitrary switch
    fixed, msg = fix_semantic_issue(src, issues[0])
    assert "switch" not in fixed or "switch (1)" not in fixed
    assert "case 1:" not in fixed


def test_case_outside_switch_negative_inside_switch():
    src = (
        "int main() {\n"
        "    int x = 1;\n"
        "    switch (x) {\n"
        "        case 1:\n"
        "            x = 10;\n"
        "            break;\n"
        "        default:\n"
        "            break;\n"
        "    }\n"
        "    return x;\n"
        "}\n"
    )
    tree, listeners, parser = parse_source(src, "test.c")
    checker = SemanticChecker()
    checker.visit(tree)
    issues = [i for i in checker.get_issues() if i.get("kind") == "case_outside_switch"]
    assert len(issues) == 0


# =====================================================================
# End-to-End GUI Pipeline Revalidation
# =====================================================================

def test_pipeline_scalar_to_pointer_revalidation():
    src = (
        "int main() {\n"
        "    int value = 7;\n"
        "    int *pointer = value;\n"
        "    return 0;\n"
        "}\n"
    )
    res = repair_source_for_gui(src, "test.c", enable_ai=False)
    assert res.get("success") is True
    assert "int *pointer = &value;" in res.get("corrected_code", "")
    assert any("assigned address" in s for s in res.get("applied_steps", []))


def test_pipeline_scalar_deref_revalidation():
    src = (
        "int main() {\n"
        "    int value = 7;\n"
        "    int result = *value;\n"
        "    return result;\n"
        "}\n"
    )
    res = repair_source_for_gui(src, "test.c", enable_ai=False)
    assert res.get("success") is True
    assert "int result = value;" in res.get("corrected_code", "")
    assert any("removed invalid dereference" in s for s in res.get("applied_steps", []))


def test_pipeline_narrowing_revalidation():
    src = (
        "int main() {\n"
        "    double d = 10.5;\n"
        "    int i = d;\n"
        "    return 0;\n"
        "}\n"
    )
    res = repair_source_for_gui(src, "test.c", enable_ai=False)
    assert res.get("success") is True
    assert "int i = (int)d;" in res.get("corrected_code", "")
    assert any("explicit narrowing conversion" in s for s in res.get("applied_steps", []))
