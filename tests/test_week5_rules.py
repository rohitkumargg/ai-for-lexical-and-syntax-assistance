import pytest
from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener
from generated.SimpleCLexer import SimpleCLexer
from generated.SimpleCParser import SimpleCParser

from compiler.error_classifier import classify_error_message
from compiler.error_corrector import apply_correction

class _Collector(ErrorListener):
    def __init__(self):
        self.errors = []
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append((line, column, msg))

def _parse_errors(code: str):
    lexer = SimpleCLexer(InputStream(code))
    collector = _Collector()
    lexer.removeErrorListeners()
    lexer.addErrorListener(collector)
    parser = SimpleCParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(collector)
    parser.program()
    return collector.errors

def test_rule_missing_semicolon_after_prototype():
    code = "int add(int a, int b)\nint main() {\n    return 0;\n}\n"
    errs = _parse_errors(code)
    assert len(errs) > 0
    # Line 1 or line 2 error
    line, col, msg = errs[0]
    c = classify_error_message(msg)
    if c.reason != "missing_semicolon_after_prototype":
        # Look for mismatched input ')' expecting ';' or use known classification
        for e in errs:
            c_cand = classify_error_message(e[2])
            if c_cand.reason == "missing_semicolon_after_prototype":
                line, col, msg = e
                c = c_cand
                break

    fixed, applied = apply_correction(code, line, col, c)
    assert applied is not None
    assert "add(int a, int b);" in fixed
    assert len(_parse_errors(fixed)) == 0

def test_rule_missing_comma_params():
    code = "int add(int a int b);\nint main() { return 0; }\n"
    errs = _parse_errors(code)
    assert len(errs) > 0
    line, col, msg = errs[0]
    c = classify_error_message(msg)
    assert c.reason == "missing_comma_params"

    fixed, applied = apply_correction(code, line, col, c)
    assert applied is not None
    assert "int a, int b" in fixed
    assert len(_parse_errors(fixed)) == 0

def test_rule_missing_rparen_params_proto():
    code = "int add(int a, int b;\nint main() { return 0; }\n"
    errs = _parse_errors(code)
    assert len(errs) > 0
    line, col, msg = errs[0]
    c = classify_error_message(msg)
    assert c.reason == "missing_rparen_params"

    fixed, applied = apply_correction(code, line, col, c)
    assert applied is not None
    assert "int add(int a, int b);" in fixed
    assert len(_parse_errors(fixed)) == 0

def test_rule_missing_rparen_params_def():
    code = "int add(int a, int b {\n    return 0;\n}\nint main() { return 0; }\n"
    errs = _parse_errors(code)
    assert len(errs) > 0
    line, col, msg = errs[0]
    c = classify_error_message(msg)
    assert c.reason == "missing_rparen_params"

    fixed, applied = apply_correction(code, line, col, c)
    assert applied is not None
    assert "int add(int a, int b)" in fixed
    assert len(_parse_errors(fixed)) == 0

def test_rule_missing_semicolon_after_global():
    code = "int g = 5\nint main() {\n    return 0;\n}\n"
    errs = _parse_errors(code)
    assert len(errs) > 0
    line, col, msg = errs[0]
    c = classify_error_message(msg)
    assert c.reason == "missing_semicolon_after_global"

    fixed, applied = apply_correction(code, line, col, c)
    assert applied is not None
    assert "int g = 5;" in fixed
    assert len(_parse_errors(fixed)) == 0

def test_clean_code_not_modified():
    code = "int main() {\n    return 0;\n}\n"
    assert len(_parse_errors(code)) == 0
    # Any classification on clean code
    c = classify_error_message("missing ';' at 'int'")
    fixed, applied = apply_correction(code, 1, 0, c)
    assert applied is None
    assert fixed == code


# =====================================================================
# Week 5 Fix Tests: Split Operators & Fuzzy Keyword Typos
# =====================================================================
from compiler.week5_repair_helpers import (
    fix_split_operators,
    fix_keyword_typos_fuzzy,
    check_parser_status,
)
from compiler.gui_bridge import repair_source_for_gui


def test_fix_split_operators_cases():
    test_cases = [
        ("int c = a & = b;", "int c = a &= b;", "& ="),
        ("int c = a | = b;", "int c = a |= b;", "| ="),
        ("int c = a ^ = b;", "int c = a ^= b;", "^ ="),
        ("int c = a % = b;", "int c = a %= b;", "% ="),
        ("int c = a < < 2;", "int c = a << 2;", "< <"),
        ("int c = a > > 1;", "int c = a >> 1;", "> >"),
        ("int c = a <<< 1;", "int c = a << 1;", "<<<"),
        ("int c = a >>> 1;", "int c = a >> 1;", ">>>"),
        ("int c = a <<= = 1;", "int c = a <<= 1;", "<<= ="),
        ("int c = a >>= = 1;", "int c = a >>= 1;", ">>= ="),
    ]
    for broken, expected, op_name in test_cases:
        fixed, applied = fix_split_operators(broken)
        assert applied is not None, f"Failed to fix {broken}"
        assert fixed == expected, f"Expected {expected}, got {fixed}"
        assert op_name in applied

    # Also verify through repair pipeline that parse errors drop to 0
    pipeline_cases = [
        "int main() { int a = 5; int b = 3; int c = a & = b; return 0; }",
        "int main() { int a = 5; int b = 3; int c = a | = b; return 0; }",
        "int main() { int a = 5; int b = 3; int c = a ^ = b; return 0; }",
        "int main() { int a = 5; int b = 3; int c = a % = b; return 0; }",
        "int main() { int a = 8; int c = a < < 2; return 0; }",
        "int main() { int a = 8; int c = a > > 1; return 0; }",
        "int main() { int a = 8; int c = a <<< 1; return 0; }",
        "int main() { int a = 8; int c = a >>> 1; return 0; }",
        "int main() { int a = 8; a <<= = 1; return 0; }",
        "int main() { int a = 8; a >>= = 1; return 0; }",
    ]
    for code in pipeline_cases:
        res = repair_source_for_gui(code, enable_ai=False)
        assert len(res["errors"]) == 0, f"Parse errors remaining for {code}: {res['errors']}"
        assert res["stats"]["rule_fixes"] > 0


def test_fix_keyword_typos_fuzzy_cases():
    fuzzy_cases = [
        ("unsgined int x = 1;", "unsigned int x = 1;", "unsigned"),
        ("lng int x = 1;", "long int x = 1;", "long"),
        ("shrt int x = 1;", "short int x = 1;", "short"),
        ("dobule x = 1.0;", "double x = 1.0;", "double"),
        ("inte x = 1;", "int x = 1;", "int"),
    ]
    for broken, expected, target_kw in fuzzy_cases:
        fixed, applied = fix_keyword_typos_fuzzy(broken)
        assert applied is not None, f"Failed to fix {broken}"
        assert fixed == expected, f"Expected {expected}, got {fixed}"
        assert target_kw in applied

    # Also verify through repair pipeline that parse errors drop to 0
    pipeline_cases = [
        "int main() { unsgined int x = 1; return 0; }",
        "int main() { lng int x = 1; return 0; }",
        "int main() { shrt int x = 1; return 0; }",
        "int main() { dobule x = 1.0; return 0; }",
        "int main() { inte x = 1; return 0; }",
    ]
    for code in pipeline_cases:
        res = repair_source_for_gui(code, enable_ai=False)
        assert len(res["errors"]) == 0, f"Parse errors remaining for {code}: {res['errors']}"
        assert res["stats"]["rule_fixes"] > 0


def test_valid_code_and_identifiers_stay_unchanged():
    # 1) Specific valid expression test
    code1 = "int main(){int a=3;return a>>1 | a<<1;}"
    f1, a1 = fix_split_operators(code1)
    assert a1 is None
    assert f1 == code1
    f1_fuzz, a1_fuzz = fix_keyword_typos_fuzzy(code1)
    assert a1_fuzz is None
    assert f1_fuzz == code1
    res1 = repair_source_for_gui(code1, enable_ai=False)
    assert res1["corrected_code"] == code1

    # 2) If statement test
    code2 = "if (x) y = 1;"
    f2, a2 = fix_split_operators(code2)
    assert a2 is None
    assert f2 == code2
    f2_fuzz, a2_fuzz = fix_keyword_typos_fuzzy(code2)
    assert a2_fuzz is None
    assert f2_fuzz == code2

    # 3) Identifiers like count and point
    code3 = "int main() {\n    int count = 5;\n    count = count + 1;\n    int point = 10;\n    point = 20;\n    return count + point;\n}\n"
    f3, a3 = fix_split_operators(code3)
    assert a3 is None
    assert f3 == code3
    f3_fuzz, a3_fuzz = fix_keyword_typos_fuzzy(code3)
    assert a3_fuzz is None
    assert f3_fuzz == code3
    res3 = repair_source_for_gui(code3, enable_ai=False)
    assert res3["corrected_code"] == code3


def test_parser_knows_caret_tilde_pipe():
    # Test that SimpleCParser defines CARET, TILDE, and PIPE token IDs
    assert hasattr(SimpleCParser, "CARET")
    assert SimpleCParser.CARET > 0
    assert hasattr(SimpleCParser, "TILDE")
    assert SimpleCParser.TILDE > 0
    assert hasattr(SimpleCParser, "PIPE")
    assert SimpleCParser.PIPE > 0

    is_fresh, info_line, warning_line = check_parser_status()
    assert is_fresh is True
    assert warning_line is None
    assert "CARET=True" in info_line
    assert "TILDE=True" in info_line
    assert "PIPE=True" in info_line
