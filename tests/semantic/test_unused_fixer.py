import pytest
from compiler.unused_var_fixer import remove_unused_decl_at


def test_remove_unused_simple():
    src = "int main() {\n    int unused_var = 10;\n    return 0;\n}\n"
    res, msg = remove_unused_decl_at(src, 2, 4, "unused_var")
    assert msg is not None
    assert "unused_var" not in res
    assert "int unused_var" not in res


def test_preserve_side_effects_function_call():
    # Criterion 3: removing "int x = f();" must keep the call f()
    src = "int main() {\n    int x = compute_val(42);\n    return 0;\n}\n"
    res, msg = remove_unused_decl_at(src, 2, 4, "x")
    assert msg is not None
    assert "compute_val(42);" in res
    assert "int x" not in res


def test_preserve_side_effects_increment():
    src = "int main() {\n    int unused = count++;\n    return 0;\n}\n"
    res, msg = remove_unused_decl_at(src, 2, 4, "unused")
    assert msg is not None
    assert "count++;" in res
    assert "int unused" not in res


def test_multi_variable_decl():
    src = "int main() {\n    int a = 1, b = 2;\n    return a;\n}\n"
    res, msg = remove_unused_decl_at(src, 2, 4, "b")
    assert msg is not None
    assert "int a = 1;" in res
    assert "b = 2" not in res


def test_multi_variable_with_side_effect():
    src = "int main() {\n    int a = 1, b = do_work();\n    return a;\n}\n"
    res, msg = remove_unused_decl_at(src, 2, 4, "b")
    assert msg is not None
    assert "int a = 1;" in res
    assert "do_work();" in res
