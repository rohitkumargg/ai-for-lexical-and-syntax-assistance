# tests/test_deterministic_do_no_harm.py
import glob
import os
import subprocess
import pytest

from compiler.repair_planner import RepairPlanner
from compiler.repair_job_manager import _fix_unambiguous_syntax_delimiters

@pytest.fixture(scope="module")
def planner():
    return RepairPlanner()


def test_do_no_harm_version_string(planner):
    """Asserts that 'version 2 3' inside string literal is never modified by deterministic rules."""
    code = """#include <stdio.h>

int main(void) {
    const char *ver = "version 2 3";
    printf("Application version: %s\\n", ver);
    return 0;
}
"""
    fixed_code, steps = planner._apply_deterministic_rules(code, filename="version_test.c")
    assert fixed_code == code, f"Code was modified! Applied steps: {steps}"

    delim_code, delim_steps = _fix_unambiguous_syntax_delimiters(code)
    assert delim_code == code, f"Delimiters rule modified clean code: {delim_steps}"


def test_do_no_harm_for_loop_equality(planner):
    """Asserts that a for-loop with == in condition is never corrupted by semicolon inserter."""
    code = """#include <stdio.h>

int main(void) {
    int sum = 0;
    for (int i = 0; i == 0; i++) {
        sum += i;
    }
    return sum;
}
"""
    fixed_code, steps = planner._apply_deterministic_rules(code, filename="for_eq_test.c")
    assert fixed_code == code, f"Code was modified! Applied steps: {steps}"

    delim_code, delim_steps = _fix_unambiguous_syntax_delimiters(code)
    assert delim_code == code, f"Delimiters rule modified clean code: {delim_steps}"


def test_do_no_harm_all_valid_c_programs(planner):
    """
    Applies every deterministic rule to every valid C program in the repo
    (examples, week files, test fixtures that compile with gcc).
    Asserts the output is byte-identical.
    """
    c_files = glob.glob("**/*.c", recursive=True)
    valid_files = []

    for f_path in c_files:
        norm_path = f_path.replace("\\", "/")
        if any(ign in norm_path for ign in [
            "data/", "logs/", "scratch/", "reports/", "venv/", ".venv/",
            "_broken", "attack", "overflow", "vuln"
        ]):
            continue
        try:
            res = subprocess.run(["gcc", "-fsyntax-only", f_path], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                valid_files.append(f_path)
        except Exception:
            continue

    assert len(valid_files) >= 10, f"Expected at least 10 valid C programs, found {len(valid_files)}"

    mutated = []
    for f_path in valid_files:
        with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
            original = f.read()

        fixed, steps = planner._apply_deterministic_rules(original, filename=os.path.basename(f_path))
        if fixed != original:
            mutated.append((f_path, steps))

        delim_fixed, delim_steps = _fix_unambiguous_syntax_delimiters(original)
        if delim_fixed != original:
            mutated.append((f_path + " (delim)", delim_steps))

    assert not mutated, f"Deterministic rules corrupted valid C programs: {mutated}"

