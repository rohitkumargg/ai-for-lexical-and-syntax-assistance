import os

import pytest

from compiler.security_checker import SecurityChecker
from compiler.semantic_checker import SemanticChecker
from test_parser import get_all_error_strings, parse_source


from compiler.gui_bridge import repair_source_for_gui


WEEK6_DIR = os.path.join("examples", "week6_grammar_2026")


@pytest.mark.parametrize("filename", ["address_deref.c"])
def test_week6_examples_parse_cleanly(filename):
    with open(os.path.join(WEEK6_DIR, filename), encoding="utf-8") as source:
        tree, listeners, _ = parse_source(source.read(), filename)
    assert tree is not None
    assert not get_all_error_strings(listeners)


@pytest.mark.parametrize("filename", ["sizeof.c", "casts.c", "do_while.c"])
def test_week6_broken_examples_repaired(filename):
    """These example files have intentional syntax errors.  The compiler must
    repair them so the final result parses cleanly."""
    with open(os.path.join(WEEK6_DIR, filename), encoding="utf-8") as source:
        code = source.read()
    result = repair_source_for_gui(code, filename, enable_ai=False)
    assert result["status"] not in {"STOPPED", "UNFIXABLE"}, (
        f"{filename}: repair status was {result['status']}, errors: {result.get('errors', [])}"
    )
    assert result["applied_steps"], f"{filename}: no repair steps applied"


def test_pointer_semantics_and_array_decay():
    code = """
        int *identity(int values[]) { return values; }
        int main() {
            int value = 1;
            int *pointer = &value;
            int **pointer_to_pointer = &pointer;
            int values[2];
            int *from_array = values;
            *pointer = *identity(from_array);
            return **pointer_to_pointer;
        }
    """
    tree, listeners, _ = parse_source(code, "pointer_valid.c")
    assert not get_all_error_strings(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    assert not [issue for issue in checker.get_issues() if issue["kind"] != "unused"]


def test_pointer_misuse_is_diagnosed():
    code = """
        int main() {
            int number = 1;
            int *pointer = number;
            int value = *number;
            return value;
        }
    """
    tree, listeners, _ = parse_source(code, "pointer_misuse.c")
    assert not get_all_error_strings(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    kinds = {issue["kind"] for issue in checker.get_issues()}
    assert "pointer_assignment_warning" in kinds
    assert "invalid_dereference" in kinds


def test_do_while_allows_break_and_continue():
    code = "int main() { do { continue; break; } while (0); return 0; }"
    tree, listeners, _ = parse_source(code, "do_while_control.c")
    assert not get_all_error_strings(listeners)
    checker = SemanticChecker()
    checker.visit(tree)
    kinds = {issue["kind"] for issue in checker.get_issues()}
    assert "break_outside_loop" not in kinds
    assert "continue_outside_loop" not in kinds


def test_security_checker_keeps_pointer_argument_calls_visible():
    issues = SecurityChecker().check("int main() { char *buffer; gets(buffer); strcpy(buffer, buffer); }")
    messages = [issue.message for issue in issues]
    assert any("gets" in message for message in messages)
    assert any("strcpy" in message for message in messages)
