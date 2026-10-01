import os
import pytest
from test_parser import parse_source, has_any_errors, get_all_error_strings
from compiler.semantic_checker import SemanticChecker
from tools.check_baseline import check_baseline


WEEK5_DIR = os.path.join("examples", "week5_grammar_2026")
SEMANTICS_DIR = os.path.join(WEEK5_DIR, "semantics")


@pytest.mark.parametrize("feature", ["prototype", "globals", "types", "bitwise_ops", "shift_ops"])
def test_valid_files_parse(feature):
    fname = f"{feature}_valid.c"
    fpath = os.path.join(WEEK5_DIR, fname)
    assert os.path.exists(fpath), f"File {fpath} does not exist"

    with open(fpath, "r", encoding="utf-8") as f:
        code = f.read()

    tree, listeners, _ = parse_source(code, fname)
    assert tree is not None, f"Parsing returned None for {fname}"
    errors = get_all_error_strings(listeners)
    assert not errors, f"Unexpected parse errors in {fname}: {errors}"


@pytest.mark.parametrize("sem_file,expected_kind", [
    ("prototype_mismatch_err.c", "prototype_mismatch"),
    ("shadow_warning_err.c", "shadow_warning"),
    ("invalid_operand_type_err.c", "invalid_operand_type"),
    ("narrowing_err.c", "type_mismatch"),
])
def test_semantic_issue_kinds_fire(sem_file, expected_kind):
    fpath = os.path.join(SEMANTICS_DIR, sem_file)
    assert os.path.exists(fpath), f"File {fpath} does not exist"

    with open(fpath, "r", encoding="utf-8") as f:
        code = f.read()

    tree, listeners, _ = parse_source(code, sem_file)
    assert tree is not None and not has_any_errors(listeners), f"Unexpected parse error in {sem_file}"

    checker = SemanticChecker()
    checker.visit(tree)
    issues = checker.get_issues()
    kinds = [i.get("kind") for i in issues]

    assert expected_kind in kinds, f"Expected {expected_kind} to fire in {sem_file}, but found: {kinds}"


@pytest.mark.parametrize("guard_file", [
    "prototype_mismatch_guard.c",
    "shadow_warning_guard.c",
    "invalid_operand_type_guard.c",
    "narrowing_guard.c",
])
def test_semantic_guards_stay_silent(guard_file):
    fpath = os.path.join(SEMANTICS_DIR, guard_file)
    assert os.path.exists(fpath), f"File {fpath} does not exist"

    with open(fpath, "r", encoding="utf-8") as f:
        code = f.read()

    tree, listeners, _ = parse_source(code, guard_file)
    assert tree is not None and not has_any_errors(listeners), f"Unexpected parse error in {guard_file}"

    checker = SemanticChecker()
    checker.visit(tree)
    issues = checker.get_issues()

    assert len(issues) == 0, f"Expected 0 issues in guard file {guard_file}, but found: {issues}"


def test_baseline_70_files_zero_regressions():
    baseline_file = os.path.join("examples", "baseline_before_week5.json")
    assert os.path.exists(baseline_file), "Baseline file missing"

    ok, regressions = check_baseline(baseline_file, verbose=False)
    assert ok, f"Baseline check failed with {regressions} regressions"
    assert regressions == 0, f"Expected 0 regressions, got {regressions}"
