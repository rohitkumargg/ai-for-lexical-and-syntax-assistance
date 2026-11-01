import pytest

from test_parser import parse_source, has_any_errors
from compiler.semantic_checker import SemanticChecker
from compiler.security_checker import SecurityChecker
from compiler.taint_checker import TaintChecker
from compiler.security_engine import SecurityEngine


# =====================================================================
# 1. Struct Type Resolution & Member Access Tests
# =====================================================================

def test_valid_struct_access():
    code = """struct Point {
    int x;
    int y;
};

int main() {
    struct Point pt;
    pt.x = 10;
    return pt.x;
}
"""
    tree, listeners, _ = parse_source(code, "test_valid_struct_access")
    assert not has_any_errors(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    struct_issues = [i for i in checker.get_issues() if i["kind"] in ("unknown_struct_type", "unknown_member")]
    assert len(struct_issues) == 0, f"Unexpected struct issues: {struct_issues}"


def test_valid_pointer_to_struct_access():
    code = """struct Point {
    int x;
    int y;
};

int main() {
    struct Point pt;
    struct Point *p = &pt;
    p->x = 10;
    return p->x;
}
"""
    tree, listeners, _ = parse_source(code, "test_valid_pointer_to_struct_access")
    assert not has_any_errors(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    struct_issues = [i for i in checker.get_issues() if i["kind"] in ("unknown_struct_type", "unknown_member")]
    assert len(struct_issues) == 0, f"Unexpected struct issues: {struct_issues}"


def test_invalid_struct_field():
    code = """struct Point {
    int x;
};

int main() {
    struct Point pt;
    pt.z = 10;
}
"""
    tree, listeners, _ = parse_source(code, "test_invalid_struct_field")
    assert not has_any_errors(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    unknown_member_issues = [i for i in checker.get_issues() if i["kind"] == "unknown_member"]
    assert len(unknown_member_issues) == 1
    assert unknown_member_issues[0]["name"] == "z"
    assert "'struct Point' has no member named 'z'" in unknown_member_issues[0]["msg"]


def test_struct_tag_case_sensitivity():
    code = """struct Point {
    int x;
};

int main() {
    struct point pt;
    return 0;
}
"""
    tree, listeners, _ = parse_source(code, "test_struct_tag_case_sensitivity")
    assert not has_any_errors(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    unknown_struct_issues = [i for i in checker.get_issues() if i["kind"] == "unknown_struct_type"]
    assert len(unknown_struct_issues) >= 1
    assert "point" in unknown_struct_issues[0]["msg"]


# =====================================================================
# 2. Dangerous API & Taint Correlation Tests
# =====================================================================

def test_actual_dangerous_system_consolidated_warning():
    code = """int system(char *command);

int main() {
    char cmd[100];
    scanf("%99s", cmd);
    system(cmd);
}
"""
    engine = SecurityEngine()
    issues, blocked, categorized = engine.analyze(code)

    # Must produce exactly one consolidated vulnerability report
    system_issues = [i for i in issues if "system" in getattr(i, "message", "")]
    assert len(system_issues) == 1, f"Expected 1 issue for system, got: {system_issues}"
    issue = system_issues[0]
    assert issue.severity == "CRITICAL"
    assert "Tainted input 'cmd' passed to dangerous sink 'system'" in issue.message
    assert "Sanitize or validate the input before use" in getattr(issue, "suggestion", "")


def test_generic_dangerous_api_when_untainted():
    code = """int system(char *command);

int main() {
    char *computed_path = 0;
    system(computed_path);
}
"""
    engine = SecurityEngine()
    issues, blocked, categorized = engine.analyze(code)
    system_issues = [i for i in issues if "system" in getattr(i, "message", "")]
    assert len(system_issues) == 1
    assert system_issues[0].severity == "WARNING"
    assert "Dangerous API used with non-constant input: system" in system_issues[0].message


def test_dangerous_api_with_constant_string():
    code = """int system(char *command);

int main() {
    system("echo hello");
}
"""
    engine = SecurityEngine()
    issues, blocked, categorized = engine.analyze(code)
    system_issues = [i for i in issues if "system" in getattr(i, "message", "")]
    assert len(system_issues) == 1
    assert system_issues[0].severity in ("WARNING", "INFO")
    assert ("Dangerous API used with constant string: system" in system_issues[0].message
            or "system() runs a fixed command" in system_issues[0].message)


# =====================================================================
# 3. Gets vs Fgets & Exact Function Name Matching Tests
# =====================================================================

def test_actual_gets_warning():
    code = """char *gets(char *str);

int main() {
    char buf[100];
    gets(buf);
}
"""
    engine = SecurityEngine()
    issues, blocked, categorized = engine.analyze(code)
    gets_issues = [i for i in issues if "gets" in getattr(i, "message", "")]
    assert len(gets_issues) == 1
    assert gets_issues[0].severity == "CRITICAL"
    assert "Unsafe function detected: gets" in gets_issues[0].message


def test_safe_fgets_no_gets_warning():
    code = """char *gets(char *str);

int main() {
    char buf[100];
    fgets(buf, sizeof(buf), stdin);
}
"""
    engine = SecurityEngine()
    issues, blocked, categorized = engine.analyze(code)
    gets_issues = [i for i in issues if "Unsafe function detected: gets" in getattr(i, "message", "")]
    assert len(gets_issues) == 0, f"Expected no gets warning, got: {gets_issues}"


def test_similar_function_names_not_classified_as_gets():
    code = """void mygets(char *s) {}
void getstring(char *s) {}

int main() {
    char buf[100];
    fgets(buf, 100, stdin);
    mygets(buf);
    getstring(buf);
}
"""
    engine = SecurityEngine()
    issues, blocked, categorized = engine.analyze(code)
    gets_issues = [i for i in issues if "Unsafe function detected: gets" in getattr(i, "message", "")]
    assert len(gets_issues) == 0, f"Expected no gets warning for similar names, got: {gets_issues}"


def test_safe_declaration_only_no_gets_or_system_warning():
    code = """char *gets(char *str);
int system(char *command);

int main() {
    return 0;
}
"""
    engine = SecurityEngine()
    issues, blocked, categorized = engine.analyze(code)
    gets_issues = [i for i in issues if "gets" in getattr(i, "message", "")]
    system_issues = [i for i in issues if "system" in getattr(i, "message", "")]
    assert len(gets_issues) == 0, f"Expected no gets warning for declaration, got: {gets_issues}"
    assert len(system_issues) == 0, f"Expected no system warning for declaration, got: {system_issues}"


# =====================================================================
# 4. Scanf Argument/Type Analysis & Undeclared / Unused Symbols
# =====================================================================

def test_scanf_invalid_argument_type_int_scalar():
    code = """int main() {
    int a = 5;
    scanf("%11s", a);
    return 0;
}
"""
    tree, listeners, _ = parse_source(code, "test_scanf_invalid_argument_type_int_scalar")
    assert not has_any_errors(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    type_issues = [i for i in checker.get_issues() if "Invalid argument type for scanf format %s" in i.get("msg", "")]
    assert len(type_issues) >= 1, f"Expected scanf format type mismatch, got: {checker.get_issues()}"

    # Verify 'a' is NOT marked as tainted
    engine = SecurityEngine()
    issues, blocked, categorized = engine.analyze(code)
    taint_issues = [i for i in issues if "Tainted" in getattr(i, "message", "")]
    assert len(taint_issues) == 0, f"Expected no taint findings for int a, got: {taint_issues}"


def test_scanf_invalid_argument_type_int_array():
    code = """int main() {
    int arr[5];
    scanf("%11s", arr);
    return 0;
}
"""
    tree, listeners, _ = parse_source(code, "test_scanf_invalid_argument_type_int_array")
    assert not has_any_errors(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    type_issues = [i for i in checker.get_issues() if "Invalid argument type for scanf format %s" in i.get("msg", "")]
    assert len(type_issues) >= 1, f"Expected scanf format type mismatch, got: {checker.get_issues()}"

    # Verify 'arr' is NOT marked as tainted and no SEC-09 unsafe_scanf
    engine = SecurityEngine()
    issues, blocked, categorized = engine.analyze(code)
    taint_issues = [i for i in issues if "Tainted" in getattr(i, "message", "")]
    assert len(taint_issues) == 0, f"Expected no taint findings for int arr, got: {taint_issues}"
    scanf_sec = [i for i in issues if "unsafe_scanf" in getattr(i, "rule", "") or "overflows buffer" in getattr(i, "message", "")]
    assert len(scanf_sec) == 0, f"Expected no unsafe_scanf for int arr, got: {scanf_sec}"


def test_undeclared_identifier_not_turned_into_security_finding():
    code = """int main() {
    scanf("%11s", arr);
    return 0;
}
"""
    tree, listeners, _ = parse_source(code, "test_undeclared_identifier_not_turned_into_security_finding")
    assert not has_any_errors(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    undeclared = [i for i in checker.get_issues() if i["kind"] == "undeclared" and i["name"] == "arr"]
    assert len(undeclared) >= 1, f"Expected undeclared identifier 'arr', got: {checker.get_issues()}"

    # Security engine must NOT fabricate type information or produce taint / buffer overflow
    engine = SecurityEngine()
    issues, blocked, categorized = engine.analyze(code)
    taint_issues = [i for i in issues if "Tainted" in getattr(i, "message", "")]
    assert len(taint_issues) == 0, f"Expected no taint findings for undeclared arr, got: {taint_issues}"
    overflow_issues = [i for i in issues if "overflow" in getattr(i, "message", "").lower()]
    assert len(overflow_issues) == 0, f"Expected no overflow findings for undeclared arr, got: {overflow_issues}"


def test_unused_variable_with_undeclared_nearby():
    code = """int main() {
    char source[30];
    char dest[10];
    scanf("%11s", arr);
    return 0;
}
"""
    tree, listeners, _ = parse_source(code, "test_unused_variable_with_undeclared_nearby")
    assert not has_any_errors(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    unused_names = {i["name"] for i in checker.get_issues() if i["kind"] == "unused"}
    assert "source" in unused_names
    assert "dest" in unused_names


# =====================================================================
# 5. Multiple Distinct Sink Calls
# =====================================================================

def test_multiple_system_calls_produce_two_critical_findings():
    code = """int system(char *command);

int main() {
    char cmd1[50];
    char cmd2[50];

    scanf("%49s", cmd1);
    scanf("%49s", cmd2);

    system(cmd1);
    system(cmd2);

    return 0;
}
"""
    engine = SecurityEngine()
    issues, blocked, categorized = engine.analyze(code)
    system_issues = [i for i in issues if "Tainted input" in getattr(i, "message", "") and "system" in getattr(i, "message", "")]
    assert len(system_issues) == 2, f"Expected 2 separate CRITICAL findings, got: {system_issues}"
    messages = [i.message for i in system_issues]
    assert any("cmd1" in m for m in messages)
    assert any("cmd2" in m for m in messages)
    # Check that generic warning is NOT emitted
    generic_warnings = [i for i in issues if "Dangerous API used with non-constant input" in getattr(i, "message", "")]
    assert len(generic_warnings) == 0, f"Generic warning should be suppressed when taint flow exists, got: {generic_warnings}"

