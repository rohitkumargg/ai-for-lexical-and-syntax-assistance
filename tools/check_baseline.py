import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from test_parser import parse_source, has_any_errors, get_all_error_strings
from compiler.semantic_checker import SemanticChecker

def check_baseline(baseline_file="examples/baseline_before_week5.json", verbose=False):
    if not os.path.exists(baseline_file):
        print(f"Baseline file not found: {baseline_file}")
        return False, 1

    with open(baseline_file, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    regressions = 0
    total = len(baseline)

    for idx, (path, base) in enumerate(baseline.items(), 1):
        if not os.path.exists(path):
            print(f"Missing file: {path}")
            regressions += 1
            continue

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        tree, listeners, parser = parse_source(content, path)
        is_clean = (tree is not None) and (not has_any_errors(listeners))
        errs = get_all_error_strings(listeners) if tree is not None else ["Tree is None"]

        sem_issues = []
        if is_clean and tree is not None:
            checker = SemanticChecker()
            try:
                checker.visit(tree)
                sem_issues = checker.get_issues()
            except Exception as e:
                sem_issues = [{"kind": "exception", "msg": str(e)}]

        if verbose:
            print(f"[{idx}/{total}] Checking {path}...", flush=True)

        if is_clean != base["initial_clean"]:
            print(f"REGRESSION: Parse status diff in {path}: expected {base['initial_clean']}, got {is_clean}", flush=True)
            regressions += 1
        elif is_clean and len(sem_issues) != base["semantic_issue_count"]:
            # Check if semantic issues differ
            print(f"SEMANTIC DIFF in {path}: expected {base['semantic_issue_count']} issues, got {len(sem_issues)}", flush=True)
            if verbose:
                print(f"  Expected: {base['semantic_issues']}", flush=True)
                print(f"  Current:  {sem_issues}", flush=True)
            regressions += 1
        else:
            if verbose:
                print(f"OK: {path}")

    print(f"Baseline comparison: {total} files checked, {regressions} regressions found.")
    return (regressions == 0), regressions

if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    success, count = check_baseline(verbose=verbose)
    sys.exit(0 if success else 1)
