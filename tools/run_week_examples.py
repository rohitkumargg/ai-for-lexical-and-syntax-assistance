#!/usr/bin/env python3
"""
Week example runner and regression validator.
Runs Week 5 examples through gui_bridge repair function, compares with expected JSON,
validates semantic rules and guards, and ensures zero baseline regressions.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath("."))

from compiler.gui_bridge import repair_source_for_gui
from compiler.semantic_checker import SemanticChecker
from test_parser import parse_source, has_any_errors, get_all_error_strings
from tools.check_baseline import check_baseline


WEEK5_DIR = os.path.join("examples", "week5_grammar_2026")
SEMANTICS_DIR = os.path.join(WEEK5_DIR, "semantics")
FEATURES = ["prototype", "globals", "types", "bitwise_ops", "shift_ops"]


def determine_fix_method(result):
    stats = result.get("stats", {})
    if stats.get("rule_fixes", 0) > 0:
        return "RULE"
    if stats.get("lex_fixes", 0) > 0:
        return "LEX"
    if stats.get("ai_fixes", 0) > 0:
        return "AI"
    if stats.get("sem_fixes", 0) > 0:
        return "SEM"
    if stats.get("sym_fixes", 0) > 0:
        return "SYM"
    return "NONE"


def run_week5(no_ai=False, verbose=False, generate_mode=False):
    print("=" * 80)
    print(f"RUNNING WEEK 5 EXAMPLES (no_ai={no_ai})")
    print("=" * 80)

    rows = []
    mismatches = 0
    total_files = 0

    header = f"{'File':<32} | {'Status':<12} | {'Err Before':<10} | {'Err After':<9} | {'Fix Method':<10} | {'Time (ms)':<9}"
    print(header)
    print("-" * len(header))

    for feat in FEATURES:
        expected_json_path = os.path.join(WEEK5_DIR, f"{feat}_expected.json")
        expected_data = {}
        if os.path.exists(expected_json_path) and not generate_mode:
            with open(expected_json_path, "r", encoding="utf-8") as f:
                expected_data = json.load(f)

        feat_expected_out = {}

        for suffix in ["valid.c", "broken_1.c", "broken_2.c", "broken_3.c"]:
            fname = f"{feat}_{suffix}"
            fpath = os.path.join(WEEK5_DIR, fname)
            if not os.path.exists(fpath):
                print(f"Missing file: {fpath}")
                mismatches += 1
                continue

            with open(fpath, "r", encoding="utf-8") as f:
                source = f.read()

            # Measure initial errors
            init_tree, init_listeners, _ = parse_source(source, fname)
            errors_before = len(get_all_error_strings(init_listeners)) if init_tree is not None else 1

            t0 = time.perf_counter()
            res = repair_source_for_gui(source, fname, enable_ai=not no_ai)
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

            status = res.get("status", "UNKNOWN")
            errors_after = len(res.get("errors", []))
            fix_method = determine_fix_method(res)
            corrected_code = res.get("corrected_code", source)

            row = {
                "file": fname,
                "status": status,
                "errors_before": errors_before,
                "errors_after": errors_after,
                "fix_method": fix_method,
                "ms": elapsed_ms,
                "corrected_code": corrected_code,
            }
            rows.append(row)
            total_files += 1

            line_str = f"{fname:<32} | {status:<12} | {errors_before:<10} | {errors_after:<9} | {fix_method:<10} | {elapsed_ms:<9.2f}"
            print(line_str)

            if generate_mode:
                feat_expected_out[fname] = {
                    "status": status,
                    "errors_before": errors_before,
                    "errors_after": errors_after,
                    "fix_method": fix_method,
                    "expected_fixed_code": corrected_code,
                }
            else:
                exp = expected_data.get(fname)
                if exp:
                    if exp.get("status") != status:
                        print(f"  MISMATCH status: expected {exp.get('status')} got {status}")
                        mismatches += 1
                    if exp.get("expected_fixed_code") and exp.get("expected_fixed_code") != corrected_code:
                        print(f"  MISMATCH fixed code in {fname}")
                        mismatches += 1
                else:
                    print(f"  WARNING: No expected data for {fname}")
                    mismatches += 1

        if generate_mode:
            with open(expected_json_path, "w", encoding="utf-8") as f:
                json.dump(feat_expected_out, f, indent=2)
            print(f"Generated {expected_json_path}")

    # Semantics checks
    print("\n" + "=" * 80)
    print("RUNNING SEMANTICS CHECKS")
    print("=" * 80)

    sem_checks = [
        ("prototype_mismatch_err.c", "prototype_mismatch", True),
        ("prototype_mismatch_guard.c", "prototype_mismatch", False),
        ("shadow_warning_err.c", "shadow_warning", True),
        ("shadow_warning_guard.c", "shadow_warning", False),
        ("invalid_operand_type_err.c", "invalid_operand_type", True),
        ("invalid_operand_type_guard.c", "invalid_operand_type", False),
        ("narrowing_err.c", "type_mismatch", True),
        ("narrowing_guard.c", "type_mismatch", False),
    ]

    sem_rows = []
    for sem_file, expected_kind, should_fire in sem_checks:
        sem_path = os.path.join(SEMANTICS_DIR, sem_file)
        if not os.path.exists(sem_path):
            print(f"Missing semantics file: {sem_path}")
            mismatches += 1
            continue

        with open(sem_path, "r", encoding="utf-8") as f:
            src = f.read()

        tree, listeners, _ = parse_source(src, sem_file)
        parse_err_count = len(get_all_error_strings(listeners)) if tree is not None else 1
        checker = SemanticChecker()
        if tree is not None and parse_err_count == 0:
            checker.visit(tree)
            issues = checker.get_issues()
        else:
            issues = []

        found_kinds = [i.get("kind") for i in issues]
        passed = False
        if should_fire:
            passed = expected_kind in found_kinds and parse_err_count == 0
        else:
            passed = len(issues) == 0 and parse_err_count == 0

        status_str = "PASS" if passed else "FAIL"
        if not passed:
            mismatches += 1

        sem_rows.append({
            "file": f"semantics/{sem_file}",
            "expected_kind": expected_kind,
            "should_fire": should_fire,
            "found_kinds": found_kinds,
            "issues_count": len(issues),
            "status": status_str,
        })

        print(f"semantics/{sem_file:<28} | Expected {expected_kind} (fire={should_fire}) -> {status_str} (found {len(issues)} issues: {found_kinds})")

    # Baseline regression check
    print("\n" + "=" * 80)
    print("RUNNING BASELINE COMPARISON")
    print("=" * 80)
    baseline_ok, regressions = check_baseline(verbose=verbose)
    if not baseline_ok or regressions > 0:
        print(f"BASELINE REGRESSIONS DETECTED: {regressions}")
        mismatches += regressions

    # Write RESULTS.md
    results_path = os.path.join(WEEK5_DIR, "RESULTS.md")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write("# Week 5 Verification Results\n\n")
        f.write(f"- Mode: `--no-ai={no_ai}`\n")
        f.write(f"- Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- Total feature files: {total_files}\n")
        f.write(f"- Total semantic checks: {len(sem_checks)}\n")
        f.write(f"- Baseline regressions: {regressions}\n")
        f.write(f"- Overall Status: {'PASS' if mismatches == 0 else 'FAIL'}\n\n")

        f.write("## Grammar & Repair Results\n\n")
        f.write("| File | Status | Errors Before | Errors After | Fix Method | Time (ms) |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| `{r['file']}` | {r['status']} | {r['errors_before']} | {r['errors_after']} | {r['fix_method']} | {r['ms']:.2f} |\n")

        f.write("\n## Semantics & Guard Results\n\n")
        f.write("| File | Target Issue | Expected To Fire | Found Issues | Result |\n")
        f.write("|---|---|---|---|---|\n")
        for sr in sem_rows:
            f.write(f"| `{sr['file']}` | `{sr['expected_kind']}` | {sr['should_fire']} | {sr['issues_count']} ({sr['found_kinds']}) | **{sr['status']}** |\n")

        f.write("\n## Baseline Results\n\n")
        f.write(f"70 files checked from `examples/baseline_before_week5.json`: **{regressions} regressions found**.\n")

    print(f"\nResults written to {results_path}")
    print(f"Summary: {total_files} feature files, {len(sem_checks)} semantic checks, {regressions} baseline regressions. Mismatches: {mismatches}")

    return mismatches == 0


def main():
    parser = argparse.ArgumentParser(description="Run week examples through repair pipeline.")
    parser.add_argument("week", nargs="?", default="5", help="Week to run (5 or all)")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI fallback repairs")
    parser.add_argument("--verbose", action="store_true", help="Verbose baseline output")
    parser.add_argument("--generate-expected", action="store_true", help="Generate expected JSON from current pipeline")

    args = parser.parse_args()

    if args.week not in ("5", "all"):
        print(f"Unknown week: {args.week}. Supported: 5, all")
        sys.exit(1)

    success = run_week5(no_ai=args.no_ai, verbose=args.verbose, generate_mode=args.generate_expected)
    if not success:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
