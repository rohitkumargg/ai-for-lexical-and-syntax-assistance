"""Unit tests for Stage 4 SemanticAIFixer."""
import pytest
from compiler.semantic_ai_fixer import SemanticAIFixer


def test_apply_predicted_patch_line_format():
    fixer = SemanticAIFixer()
    source = "int main() {\n    int x = 1;\n    int x = 2;\n    return x;\n}\n"
    prediction = "LINE 3:     int y = 2;"
    res = fixer.apply_predicted_patch(source, prediction, fallback_line=3)
    assert "int y = 2;" in res
    assert "int x = 2;" not in res


def test_apply_predicted_patch_fallback():
    fixer = SemanticAIFixer()
    source = "int main() {\n    int a = b + 1;\n    return a;\n}\n"
    prediction = "int b = 0; int a = b + 1;"
    res = fixer.apply_predicted_patch(source, prediction, fallback_line=2)
    assert "int b = 0; int a = b + 1;" in res


def test_verify_candidate_rejection_on_syntax_error():
    fixer = SemanticAIFixer()
    bad_code = "int main() { return ;;; {{{"
    issue = {"kind": "undeclared", "name": "foo", "line": 1, "col": 1}
    assert not fixer.verify_candidate(bad_code, issue, [issue])


def test_verify_candidate_rejection_on_unresolved_issue():
    fixer = SemanticAIFixer()
    code = "int main() { int a = foo + 1; return a; }"
    issue = {"kind": "undeclared", "name": "foo", "line": 1, "col": 22}
    assert not fixer.verify_candidate(code, issue, [issue])


def test_verify_candidate_acceptance_on_clean_fix():
    fixer = SemanticAIFixer()
    code = "int main() { int foo = 10; int a = foo + 1; return a; }"
    issue = {"kind": "undeclared", "name": "foo", "line": 1, "col": 22}
    assert fixer.verify_candidate(code, issue, [issue])


def test_non_model_kind_ignored():
    fixer = SemanticAIFixer()
    source = "int main() { return 0; }"
    issue = {"kind": "type_mismatch", "name": "x", "line": 1, "col": 1}
    src_out, msg = fixer.fix_semantic_issue_ai(source, issue)
    assert src_out == source
    assert msg is None
