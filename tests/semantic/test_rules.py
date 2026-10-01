import pytest
from compiler.semantic_auto_fixer import fix_semantic_issue, is_lossless_cast


# =====================================================================
# 1. type_mismatch
# =====================================================================
def test_type_mismatch_positive_1_int_to_double():
    src = "int main() {\n    double d = 10;\n    return 0;\n}\n"
    issue = {"kind": "type_mismatch", "line": 2, "col": 15, "msg": "Cannot assign 'int' to 'double' for variable 'd'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "(double)10;" in fixed


def test_type_mismatch_positive_2_char_to_int():
    src = "int main() {\n    char c = 'a';\n    int x = c;\n    return 0;\n}\n"
    issue = {"kind": "type_mismatch", "line": 3, "col": 8, "msg": "Cannot assign 'char' to 'int' for variable 'x'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "(int)c;" in fixed


def test_type_mismatch_positive_3_short_to_long():
    src = "int main() {\n    short s = 5;\n    long l = s;\n    return 0;\n}\n"
    issue = {"kind": "type_mismatch", "line": 3, "col": 9, "msg": "Cannot assign 'short' to 'long' for variable 'l'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "(long)s;" in fixed


def test_type_mismatch_negative_1_lossy_double_to_int():
    src = "int main() {\n    double d = 3.14;\n    int x = d;\n    return 0;\n}\n"
    issue = {"kind": "type_mismatch", "line": 3, "col": 8, "msg": "Cannot assign 'double' to 'int' for variable 'x'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_type_mismatch_negative_2_lossy_float_to_short():
    src = "int main() {\n    float f = 2.5;\n    short s = f;\n    return 0;\n}\n"
    issue = {"kind": "type_mismatch", "line": 3, "col": 10, "msg": "Cannot assign 'float' to 'short' for variable 's'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_type_mismatch_idempotency():
    src = "int main() {\n    double d = 10;\n    return 0;\n}\n"
    issue = {"kind": "type_mismatch", "line": 2, "col": 15, "msg": "Cannot assign 'int' to 'double' for variable 'd'"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 2. call_type_mismatch
# =====================================================================
def test_call_type_mismatch_positive_1_simple_arg():
    src = "int main() {\n    process(10);\n    return 0;\n}\n"
    issue = {"kind": "call_type_mismatch", "line": 2, "col": 4, "name": "process", "msg": "Argument 1 of 'process' expects 'double' but got 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "process((double)10);" in fixed


def test_call_type_mismatch_positive_2_nested_call_arg():
    src = "int main() {\n    foo(bar(1, 2), 10);\n    return 0;\n}\n"
    issue = {"kind": "call_type_mismatch", "line": 2, "col": 4, "name": "foo", "msg": "Argument 2 of 'foo' expects 'double' but got 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "foo(bar(1, 2), (double)10);" in fixed


def test_call_type_mismatch_positive_3_preserves_arg_spaces():
    src = "int main() {\n    compute(  a + b  ,   20  );\n    return 0;\n}\n"
    issue = {"kind": "call_type_mismatch", "line": 2, "col": 4, "name": "compute", "msg": "Argument 2 of 'compute' expects 'double' but got 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "(double)20" in fixed
    assert "a + b" in fixed


def test_call_type_mismatch_negative_1_lossy_conversion():
    src = "int main() {\n    calc(3.14);\n    return 0;\n}\n"
    issue = {"kind": "call_type_mismatch", "line": 2, "col": 4, "name": "calc", "msg": "Argument 1 of 'calc' expects 'int' but got 'double'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_call_type_mismatch_negative_2_arg_index_out_of_bounds():
    src = "int main() {\n    calc(1);\n    return 0;\n}\n"
    issue = {"kind": "call_type_mismatch", "line": 2, "col": 4, "name": "calc", "msg": "Argument 5 of 'calc' expects 'double' but got 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_call_type_mismatch_idempotency():
    src = "int main() {\n    process(10);\n    return 0;\n}\n"
    issue = {"kind": "call_type_mismatch", "line": 2, "col": 4, "name": "process", "msg": "Argument 1 of 'process' expects 'double' but got 'int'"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 3. return_type_mismatch
# =====================================================================
def test_return_type_mismatch_positive_1_int_to_double():
    src = "double get_val() {\n    return 10;\n}\n"
    issue = {"kind": "return_type_mismatch", "line": 2, "col": 4, "msg": "Return type mismatch: function returns 'double' but got 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "return (double)10;" in fixed


def test_return_type_mismatch_positive_2_char_to_int():
    src = "int get_code() {\n    return 'x';\n}\n"
    issue = {"kind": "return_type_mismatch", "line": 2, "col": 4, "msg": "Return type mismatch: function returns 'int' but got 'char'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "return (int)'x';" in fixed


def test_return_type_mismatch_positive_3_expression():
    src = "double calc() {\n    int a = 1, b = 2;\n    return a + b;\n}\n"
    issue = {"kind": "return_type_mismatch", "line": 3, "col": 4, "msg": "Return type mismatch: function returns 'double' but got 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "return (double)(a + b);" in fixed or "return (double)a + b;" in fixed


def test_return_type_mismatch_negative_1_lossy_double_to_int():
    src = "int get_int() {\n    return 3.14;\n}\n"
    issue = {"kind": "return_type_mismatch", "line": 2, "col": 4, "msg": "Return type mismatch: function returns 'int' but got 'double'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_return_type_mismatch_negative_2_no_return_statement():
    src = "int get_int() {\n    int x = 5;\n}\n"
    issue = {"kind": "return_type_mismatch", "line": 2, "col": 4, "msg": "Return type mismatch: function returns 'int' but got 'double'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_return_type_mismatch_idempotency():
    src = "double get_val() {\n    return 10;\n}\n"
    issue = {"kind": "return_type_mismatch", "line": 2, "col": 4, "msg": "Return type mismatch: function returns 'double' but got 'int'"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 4. dot_on_pointer
# =====================================================================
def test_dot_on_pointer_positive_1_simple():
    src = "int main() {\n    struct Point *p;\n    p.x = 10;\n    return 0;\n}\n"
    issue = {"kind": "dot_on_pointer", "line": 3, "col": 5, "name": "x", "msg": "Member access on pointer using '.'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "p->x = 10;" in fixed


def test_dot_on_pointer_positive_2_rvalue():
    src = "int main() {\n    struct Point *p;\n    int val = p.y;\n    return 0;\n}\n"
    issue = {"kind": "dot_on_pointer", "line": 3, "col": 15, "name": "y", "msg": "Member access on pointer using '.'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int val = p->y;" in fixed


def test_dot_on_pointer_positive_3_nested():
    src = "int main() {\n    struct Node *n;\n    n.next.val = 5;\n    return 0;\n}\n"
    issue = {"kind": "dot_on_pointer", "line": 3, "col": 5, "name": "next", "msg": "Member access on pointer using '.'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "n->next.val = 5;" in fixed


def test_dot_on_pointer_negative_1_already_arrow():
    src = "int main() {\n    struct Point *p;\n    p->x = 10;\n    return 0;\n}\n"
    issue = {"kind": "dot_on_pointer", "line": 3, "col": 5, "name": "x", "msg": "Member access on pointer using '.'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_dot_on_pointer_negative_2_line_out_of_range():
    src = "int main() {\n    return 0;\n}\n"
    issue = {"kind": "dot_on_pointer", "line": 10, "col": 5, "name": "x", "msg": "Member access on pointer using '.'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_dot_on_pointer_idempotency():
    src = "int main() {\n    struct Point *p;\n    p.x = 10;\n    return 0;\n}\n"
    issue = {"kind": "dot_on_pointer", "line": 3, "col": 5, "name": "x", "msg": "Member access on pointer using '.'"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 5. arrow_on_value
# =====================================================================
def test_arrow_on_value_positive_1_simple():
    src = "int main() {\n    struct Point p;\n    p->x = 10;\n    return 0;\n}\n"
    issue = {"kind": "arrow_on_value", "line": 3, "col": 5, "name": "x", "msg": "Member access on value using '->'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "p.x = 10;" in fixed


def test_arrow_on_value_positive_2_rvalue():
    src = "int main() {\n    struct Point p;\n    int val = p->y;\n    return 0;\n}\n"
    issue = {"kind": "arrow_on_value", "line": 3, "col": 15, "name": "y", "msg": "Member access on value using '->'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int val = p.y;" in fixed


def test_arrow_on_value_positive_3_with_comment():
    src = "int main() {\n    struct S s;\n    s->val = 1; // update value\n    return 0;\n}\n"
    issue = {"kind": "arrow_on_value", "line": 3, "col": 5, "name": "val", "msg": "Member access on value using '->'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "s.val = 1; // update value" in fixed


def test_arrow_on_value_negative_1_already_dot():
    src = "int main() {\n    struct Point p;\n    p.x = 10;\n    return 0;\n}\n"
    issue = {"kind": "arrow_on_value", "line": 3, "col": 5, "name": "x", "msg": "Member access on value using '->'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_arrow_on_value_negative_2_no_member_name():
    src = "int main() {\n    int a = 5;\n    return 0;\n}\n"
    issue = {"kind": "arrow_on_value", "line": 2, "col": 5, "name": "", "msg": "Member access on value using '->'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_arrow_on_value_idempotency():
    src = "int main() {\n    struct Point p;\n    p->x = 10;\n    return 0;\n}\n"
    issue = {"kind": "arrow_on_value", "line": 3, "col": 5, "name": "x", "msg": "Member access on value using '->'"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 6. case_outside_switch
# =====================================================================
def test_case_outside_switch_positive_1_case_with_stmt():
    src = "int main() {\n    case 1: int x = 5;\n    return 0;\n}\n"
    issue = {"kind": "case_outside_switch", "line": 2, "col": 4, "msg": "'case' outside switch"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "case 1:" not in fixed
    assert "int x = 5;" in fixed


def test_case_outside_switch_positive_2_standalone_label():
    src = "int main() {\n    case 2:\n    int y = 10;\n    return 0;\n}\n"
    issue = {"kind": "case_outside_switch", "line": 2, "col": 4, "msg": "'case' outside switch"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "case 2:" not in fixed
    assert "int y = 10;" in fixed


def test_case_outside_switch_positive_3_default_label():
    src = "int main() {\n    default: return 1;\n}\n"
    issue = {"kind": "case_outside_switch", "line": 2, "col": 4, "msg": "'default' outside switch"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "default:" not in fixed
    assert "return 1;" in fixed


def test_case_outside_switch_negative_1_no_case_label():
    src = "int main() {\n    int x = 5;\n    return 0;\n}\n"
    issue = {"kind": "case_outside_switch", "line": 2, "col": 4, "msg": "'case' outside switch"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_case_outside_switch_negative_2_empty_source():
    src = ""
    issue = {"kind": "case_outside_switch", "line": 1, "col": 1, "msg": "'case' outside switch"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_case_outside_switch_idempotency():
    src = "int main() {\n    case 1: int x = 5;\n    return 0;\n}\n"
    issue = {"kind": "case_outside_switch", "line": 2, "col": 4, "msg": "'case' outside switch"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 7. duplicate_member
# =====================================================================
def test_duplicate_member_positive_1_simple():
    src = "struct S {\n    int a;\n    int b;\n    int a;\n};\n"
    issue = {"kind": "duplicate_member", "line": 4, "col": 8, "name": "a", "msg": "Duplicate member 'a'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert fixed.count("int a;") == 1


def test_duplicate_member_positive_2_char_member():
    src = "struct Config {\n    char flag;\n    char flag;\n};\n"
    issue = {"kind": "duplicate_member", "line": 3, "col": 9, "name": "flag", "msg": "Duplicate member 'flag'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert fixed.count("char flag;") == 1


def test_duplicate_member_positive_3_with_trailing_comment():
    src = "struct Data {\n    double val;\n    double val; // duplicate\n};\n"
    issue = {"kind": "duplicate_member", "line": 3, "col": 11, "name": "val", "msg": "Duplicate member 'val'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert fixed.count("double val;") == 1


def test_duplicate_member_negative_1_member_not_on_line():
    src = "struct S {\n    int a;\n    int b;\n};\n"
    issue = {"kind": "duplicate_member", "line": 2, "col": 8, "name": "c", "msg": "Duplicate member 'c'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_duplicate_member_negative_2_no_member_name():
    src = "struct S {\n    int a;\n};\n"
    issue = {"kind": "duplicate_member", "line": 2, "col": 8, "name": "", "msg": "Duplicate member"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_duplicate_member_idempotency():
    src = "struct S {\n    int a;\n    int a;\n};\n"
    issue = {"kind": "duplicate_member", "line": 3, "col": 8, "name": "a", "msg": "Duplicate member 'a'"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 8. redeclared_struct
# =====================================================================
def test_redeclared_struct_positive_1_simple():
    src = "struct Point { int x; int y; };\nstruct Point { int x; int y; };\nint main() { return 0; }\n"
    issue = {"kind": "redeclared_struct", "line": 2, "col": 7, "name": "Point", "msg": "Redeclaration of struct 'Point'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert fixed.count("struct Point { int x; int y; };") == 1


def test_redeclared_struct_positive_2_multiline():
    src = "struct Node {\n    int v;\n};\nstruct Node {\n    int v;\n};\n"
    issue = {"kind": "redeclared_struct", "line": 4, "col": 7, "name": "Node", "msg": "Redeclaration of struct 'Node'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert fixed.count("struct Node") == 1


def test_redeclared_struct_positive_3_empty_struct():
    src = "struct Empty {};\nstruct Empty {};\n"
    issue = {"kind": "redeclared_struct", "line": 2, "col": 7, "name": "Empty", "msg": "Redeclaration of struct 'Empty'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert fixed.count("struct Empty") == 1


def test_redeclared_struct_negative_1_no_matching_struct_name():
    src = "struct A { int x; };\nstruct B { int y; };\n"
    issue = {"kind": "redeclared_struct", "line": 2, "col": 7, "name": "C", "msg": "Redeclaration of struct 'C'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_redeclared_struct_negative_2_line_out_of_bounds():
    src = "struct A { int x; };\n"
    issue = {"kind": "redeclared_struct", "line": 5, "col": 7, "name": "A", "msg": "Redeclaration of struct 'A'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_redeclared_struct_idempotency():
    src = "struct S { int x; };\nstruct S { int x; };\n"
    issue = {"kind": "redeclared_struct", "line": 2, "col": 7, "name": "S", "msg": "Redeclaration of struct 'S'"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 9. call_arity_mismatch
# =====================================================================
def test_call_arity_mismatch_positive_1_extra_literal_arg():
    src = "int main() {\n    foo(1, 2, 3);\n    return 0;\n}\n"
    issue = {"kind": "call_arity_mismatch", "line": 2, "col": 4, "name": "foo", "msg": "Function 'foo' expects 2 arguments but got 3"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "foo(1, 2);" in fixed


def test_call_arity_mismatch_positive_2_extra_variable_arg():
    src = "int main() {\n    int a = 1, b = 2, c = 3;\n    add(a, b, c);\n    return 0;\n}\n"
    issue = {"kind": "call_arity_mismatch", "line": 3, "col": 4, "name": "add", "msg": "Function 'add' expects 2 arguments but got 3"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "add(a, b);" in fixed


def test_call_arity_mismatch_positive_3_extra_binary_expr():
    src = "int main() {\n    calc(10, 20 + 5);\n    return 0;\n}\n"
    issue = {"kind": "call_arity_mismatch", "line": 2, "col": 4, "name": "calc", "msg": "Function 'calc' expects 1 arguments but got 2"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "calc(10);" in fixed


def test_call_arity_mismatch_negative_1_too_few_args_suggested():
    src = "int main() {\n    foo(1);\n    return 0;\n}\n"
    issue = {"kind": "call_arity_mismatch", "line": 2, "col": 4, "name": "foo", "msg": "Function 'foo' expects 2 arguments but got 1"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_call_arity_mismatch_negative_2_side_effects_in_extra_arg():
    src = "int main() {\n    foo(1, do_important_work());\n    return 0;\n}\n"
    issue = {"kind": "call_arity_mismatch", "line": 2, "col": 4, "name": "foo", "msg": "Function 'foo' expects 1 arguments but got 2"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None  # Side effects must NOT be deleted!
    assert fixed == src


def test_call_arity_mismatch_idempotency():
    src = "int main() {\n    foo(1, 2, 3);\n    return 0;\n}\n"
    issue = {"kind": "call_arity_mismatch", "line": 2, "col": 4, "name": "foo", "msg": "Function 'foo' expects 2 arguments but got 3"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 10. too_many_initializers
# =====================================================================
def test_too_many_initializers_positive_1_fixed_size_array():
    src = "int main() {\n    int arr[2] = {1, 2, 3};\n    return 0;\n}\n"
    issue = {"kind": "too_many_initializers", "line": 2, "col": 8, "name": "arr", "msg": "Array 'arr' has size 2 but 3 initializers"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int arr[3] = {1, 2, 3};" in fixed


def test_too_many_initializers_positive_2_size_1_to_2():
    src = "int main() {\n    int a[1] = {10, 20};\n    return 0;\n}\n"
    issue = {"kind": "too_many_initializers", "line": 2, "col": 8, "name": "a", "msg": "Array 'a' has size 1 but 2 initializers"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int a[2] = {10, 20};" in fixed


def test_too_many_initializers_positive_3_float_array():
    src = "int main() {\n    float vals[3] = {1.0, 2.0, 3.0, 4.0};\n    return 0;\n}\n"
    issue = {"kind": "too_many_initializers", "line": 2, "col": 10, "name": "vals", "msg": "Array 'vals' has size 3 but 4 initializers"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "float vals[4] = {1.0, 2.0, 3.0, 4.0};" in fixed


def test_too_many_initializers_negative_1_no_count_in_message():
    src = "int main() {\n    int arr[2] = {1, 2, 3};\n    return 0;\n}\n"
    issue = {"kind": "too_many_initializers", "line": 2, "col": 8, "name": "arr", "msg": "Too many initializers"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_too_many_initializers_negative_2_variable_not_on_line():
    src = "int main() {\n    int x = 5;\n    return 0;\n}\n"
    issue = {"kind": "too_many_initializers", "line": 2, "col": 8, "name": "arr", "msg": "Array 'arr' has size 2 but 3 initializers"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_too_many_initializers_idempotency():
    src = "int main() {\n    int arr[2] = {1, 2, 3};\n    return 0;\n}\n"
    issue = {"kind": "too_many_initializers", "line": 2, "col": 8, "name": "arr", "msg": "Array 'arr' has size 2 but 3 initializers"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 11. use_before_declare
# =====================================================================
def test_use_before_declare_positive_1_bare_declaration():
    src = "int main() {\n    x = 10;\n    int x;\n    return x;\n}\n"
    issue = {"kind": "use_before_declare", "line": 2, "col": 4, "name": "x", "msg": "Variable 'x' used before declaration"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int x;\n    x = 10;" in fixed


def test_use_before_declare_positive_2_hoist_bare_leave_init_in_place():
    src = "int main() {\n    x = 5;\n    int x = 100;\n    return x;\n}\n"
    issue = {"kind": "use_before_declare", "line": 2, "col": 4, "name": "x", "msg": "Variable 'x' used before declaration"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    # Bare declaration hoisted above line 2
    assert "int x;\n    x = 5;" in fixed
    # Initializer remains as assignment in place at original declaration line
    assert "x = 100;" in fixed


def test_use_before_declare_positive_3_pointer_decl():
    src = "int main() {\n    p = 0;\n    int *p;\n    return 0;\n}\n"
    issue = {"kind": "use_before_declare", "line": 2, "col": 4, "name": "p", "msg": "Variable 'p' used before declaration"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int *p;\n    p = 0;" in fixed


def test_use_before_declare_negative_1_initializer_depends_on_intervening_var():
    src = (
        "int main() {\n"
        "    x = 1;\n"
        "    y = 20;\n"
        "    int x = y + 5;\n"
        "    return x;\n"
        "}\n"
    )
    issue = {"kind": "use_before_declare", "line": 2, "col": 4, "name": "x", "msg": "Variable 'x' used before declaration"}
    fixed, msg = fix_semantic_issue(src, issue)
    # y is assigned between line 2 and line 4, and x's initializer depends on y.
    # Hoisting would change value of x -> must be rejected / SUGGESTED!
    assert msg is None
    assert fixed == src


def test_use_before_declare_negative_2_declaration_not_found():
    src = "int main() {\n    z = 10;\n    return z;\n}\n"
    issue = {"kind": "use_before_declare", "line": 2, "col": 4, "name": "z", "msg": "Variable 'z' used before declaration"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_use_before_declare_idempotency():
    src = "int main() {\n    x = 10;\n    int x;\n    return x;\n}\n"
    issue = {"kind": "use_before_declare", "line": 2, "col": 4, "name": "x", "msg": "Variable 'x' used before declaration"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 12. shadow_warning (Safe renaming avoiding strings, comments, members)
# =====================================================================
def test_shadow_warning_positive_1_avoids_strings_and_members():
    src = (
        "int count = 10;\n"
        "struct S { int count; };\n"
        "int main() {\n"
        "    int count = 5;\n"
        '    printf("count = %d\\n", count);\n'
        "    struct S s;\n"
        "    s.count = count;\n"
        "    return count;\n"
        "}\n"
    )
    issue = {"kind": "shadow_warning", "line": 4, "col": 8, "name": "count", "msg": "Declaration of 'count' shadows global variable"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int local_count = 5;" in fixed
    assert 'printf("count = %d\\n", local_count);' in fixed
    assert "s.count = local_count;" in fixed
    assert "return local_count;" in fixed


def test_shadow_warning_positive_2_avoids_arrow_member():
    src = (
        "int val = 1;\n"
        "struct Item { int val; };\n"
        "int main() {\n"
        "    int val = 2;\n"
        "    struct Item *it;\n"
        "    it->val = val;\n"
        "    return val;\n"
        "}\n"
    )
    issue = {"kind": "shadow_warning", "line": 4, "col": 8, "name": "val", "msg": "Declaration of 'val' shadows global variable"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int local_val = 2;" in fixed
    assert "it->val = local_val;" in fixed


def test_shadow_warning_positive_3_avoids_comments():
    src = (
        "int x = 100;\n"
        "int main() {\n"
        "    int x = 20; // x is shadow\n"
        "    /* print x */\n"
        "    return x;\n"
        "}\n"
    )
    issue = {"kind": "shadow_warning", "line": 3, "col": 8, "name": "x", "msg": "Declaration of 'x' shadows global variable"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int local_x = 20; // x is shadow" in fixed
    assert "/* print x */" in fixed
    assert "return local_x;" in fixed


def test_shadow_warning_negative_1_no_name():
    src = "int main() { int x = 5; return x; }\n"
    issue = {"kind": "shadow_warning", "line": 1, "col": 17, "name": "", "msg": "Shadow warning"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_shadow_warning_negative_2_name_not_on_line():
    src = "int main() { int y = 5; return y; }\n"
    issue = {"kind": "shadow_warning", "line": 1, "col": 17, "name": "x", "msg": "Declaration of 'x' shadows global variable"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_shadow_warning_idempotency():
    src = "int x = 10;\nint main() {\n    int x = 5;\n    return x;\n}\n"
    issue = {"kind": "shadow_warning", "line": 3, "col": 8, "name": "x", "msg": "Declaration of 'x' shadows global variable"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 13. invalid_address_of
# =====================================================================
def test_invalid_address_of_positive_1_literal():
    src = "int main() {\n    int *p = &5;\n    return 0;\n}\n"
    issue = {"kind": "invalid_address_of", "line": 2, "col": 13, "msg": "Address-of operator '&' requires an lvalue"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int *p = 5;" in fixed


def test_invalid_address_of_positive_2_preserves_bitwise_and():
    src = "int main() {\n    int a = 1, b = 2;\n    int c = a & b;\n    int *p = &(a + b);\n    return 0;\n}\n"
    issue = {"kind": "invalid_address_of", "line": 4, "col": 13, "msg": "Address-of operator '&' requires an lvalue"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int c = a & b;" in fixed  # Binary bitwise & untouched!
    assert "int *p = (a + b);" in fixed


def test_invalid_address_of_positive_3_function_call():
    src = "int main() {\n    int *p = &get_val();\n    return 0;\n}\n"
    issue = {"kind": "invalid_address_of", "line": 2, "col": 13, "msg": "Address-of operator '&' requires an lvalue"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int *p = get_val();" in fixed


def test_invalid_address_of_negative_1_no_ampersand():
    src = "int main() {\n    int x = 5;\n    return 0;\n}\n"
    issue = {"kind": "invalid_address_of", "line": 2, "col": 8, "msg": "Address-of operator '&' requires an lvalue"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_invalid_address_of_negative_2_only_binary_and():
    src = "int main() {\n    int c = a & b;\n    return 0;\n}\n"
    issue = {"kind": "invalid_address_of", "line": 2, "col": 14, "msg": "Address-of operator '&' requires an lvalue"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_invalid_address_of_idempotency():
    src = "int main() {\n    int *p = &5;\n    return 0;\n}\n"
    issue = {"kind": "invalid_address_of", "line": 2, "col": 13, "msg": "Address-of operator '&' requires an lvalue"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 14. invalid_dereference
# =====================================================================
def test_invalid_dereference_positive_1_simple():
    src = "int main() {\n    int a = 5;\n    int val = *a;\n    return 0;\n}\n"
    issue = {"kind": "invalid_dereference", "line": 3, "col": 14, "msg": "Cannot dereference non-pointer type 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int val = a;" in fixed


def test_invalid_dereference_positive_2_preserves_multiplication():
    src = "int main() {\n    int a = 3, b = 4;\n    int prod = a * b;\n    int val = *a;\n    return 0;\n}\n"
    issue = {"kind": "invalid_dereference", "line": 4, "col": 14, "msg": "Cannot dereference non-pointer type 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int prod = a * b;" in fixed  # Multiplication * untouched!
    assert "int val = a;" in fixed


def test_invalid_dereference_positive_3_nested_expression():
    src = "int main() {\n    int x = 10;\n    int y = *(x + 1);\n    return 0;\n}\n"
    issue = {"kind": "invalid_dereference", "line": 3, "col": 12, "msg": "Cannot dereference non-pointer type 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is not None
    assert "int y = (x + 1);" in fixed


def test_invalid_dereference_negative_1_no_asterisk():
    src = "int main() {\n    int a = 5;\n    return 0;\n}\n"
    issue = {"kind": "invalid_dereference", "line": 2, "col": 8, "msg": "Cannot dereference non-pointer type 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_invalid_dereference_negative_2_pointer_declaration_only():
    src = "int main() {\n    int *ptr = 0;\n    return 0;\n}\n"
    issue = {"kind": "invalid_dereference", "line": 2, "col": 8, "msg": "Cannot dereference non-pointer type 'int'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert fixed == src


def test_invalid_dereference_idempotency():
    src = "int main() {\n    int a = 5;\n    int val = *a;\n    return 0;\n}\n"
    issue = {"kind": "invalid_dereference", "line": 3, "col": 14, "msg": "Cannot dereference non-pointer type 'int'"}
    fixed, _ = fix_semantic_issue(src, issue)
    second, second_msg = fix_semantic_issue(fixed, issue)
    assert second == fixed
    assert second_msg is None


# =====================================================================
# 15. duplicate_default (Downgraded to SUGGESTED)
# =====================================================================
def test_duplicate_default_always_returns_none_suggested_1():
    src = "int main() {\n    switch (1) {\n        default: break;\n        default: break;\n    }\n    return 0;\n}\n"
    issue = {"kind": "duplicate_default", "line": 4, "col": 8, "msg": "multiple 'default' labels in one switch"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_duplicate_default_always_returns_none_suggested_2():
    src = "int main() {\n    switch (x) {\n        case 1: default: default: break;\n    }\n    return 0;\n}\n"
    issue = {"kind": "duplicate_default", "line": 3, "col": 25, "msg": "multiple 'default' labels in one switch"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


# =====================================================================
# 16. invalid_operand_type (Downgraded to SUGGESTED for float in bitwise/shift)
# =====================================================================
def test_invalid_operand_type_bitwise_float_returns_none_suggested_1():
    src = "int main() {\n    float f = 1.5;\n    int r = f & 2;\n    return 0;\n}\n"
    issue = {"kind": "invalid_operand_type", "line": 3, "col": 12, "msg": "Bitwise operator '&' requires integral operands, got 'float'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src


def test_invalid_operand_type_shift_float_returns_none_suggested_2():
    src = "int main() {\n    float f = 1.5;\n    int r = f << 2;\n    return 0;\n}\n"
    issue = {"kind": "invalid_operand_type", "line": 3, "col": 12, "msg": "Shift operator requires integral operands, got 'float'"}
    fixed, msg = fix_semantic_issue(src, issue)
    assert msg is None
    assert fixed == src
