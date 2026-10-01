import pytest
from antlr4 import InputStream, CommonTokenStream
from generated.SimpleCLexer import SimpleCLexer
from generated.SimpleCParser import SimpleCParser
from compiler.semantic_checker import SemanticChecker

def _check_source(code: str):
    lexer = SimpleCLexer(InputStream(code))
    tokens = CommonTokenStream(lexer)
    parser = SimpleCParser(tokens)
    tree = parser.program()
    checker = SemanticChecker()
    checker.visit(tree)
    return checker.get_issues()

def test_bug1_bitwise_float_operands():
    code = "int main(){ float f = 2.5; int e = f & 1; int o = f | 1; int x = f ^ 1; return e+o+x; }"
    issues = _check_source(code)
    invalid_ops = [i for i in issues if i["kind"] == "invalid_operand_type"]
    assert len(invalid_ops) == 3, f"Expected 3 invalid_operand_type issues, got {len(invalid_ops)}: {issues}"

def test_bug2_integer_literal_fits_target():
    code_ok = """
    int main() {
        short s = 1;
        char c = 65;
        unsigned int u = 5;
        return s + c + u;
    }
    """
    issues_ok = _check_source(code_ok)
    mismatches = [i for i in issues_ok if i["kind"] == "type_mismatch"]
    assert len(mismatches) == 0, f"Expected 0 type_mismatch for fitting literals, got: {mismatches}"

    code_overflow = """
    int main() {
        short s = 100000;
        char c = 300;
        return s + c;
    }
    """
    issues_overflow = _check_source(code_overflow)
    mismatches_ovf = [i for i in issues_overflow if i["kind"] == "type_mismatch"]
    assert len(mismatches_ovf) == 2, f"Expected 2 type_mismatch for overflowing literals, got: {mismatches_ovf}"

def test_bug3_global_variable_type_resolution():
    code = """
    long long big = 100;
    int main() {
        short x = big;
        return x;
    }
    """
    issues = _check_source(code)
    mismatches = [i for i in issues if i["kind"] == "type_mismatch"]
    assert len(mismatches) == 1, f"Expected 1 type_mismatch, got: {mismatches}"
    assert "long long" in mismatches[0]["msg"], f"Expected 'long long' in error message, got: {mismatches[0]['msg']}"

def test_bug4_narrowing_double_to_int():
    code = """
    double d = 2.5;
    int main() {
        int y = d;
        return y;
    }
    """
    issues = _check_source(code)
    mismatches = [i for i in issues if i["kind"] == "type_mismatch"]
    assert len(mismatches) == 1, f"Expected 1 type_mismatch for double->int, got: {mismatches}"
    assert "double" in mismatches[0]["msg"], f"Expected 'double' in message, got: {mismatches[0]['msg']}"

def test_bug5_unused_globals_not_flagged():
    code = """
    int global_var = 42;
    int main() {
        int local_unused = 10;
        return 0;
    }
    """
    issues = _check_source(code)
    unused_vars = [i["name"] for i in issues if i["kind"] == "unused"]
    assert "global_var" not in unused_vars, f"Global variable should not be marked unused: {unused_vars}"
    assert "local_unused" in unused_vars, f"Local variable should be marked unused: {unused_vars}"
