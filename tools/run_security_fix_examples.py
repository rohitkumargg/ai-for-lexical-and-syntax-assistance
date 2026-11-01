#!/usr/bin/env python3
"""Run security fix 2026 examples and validate against expected.json.
Prints a markdown/console table, writes examples/security_fix_2026/RESULTS.md,
and exits non-zero on any failure.
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath("."))
from compiler.gui_bridge import repair_source_for_gui

DIR = os.path.join("examples", "security_fix_2026")
EXPECTED_PATH = os.path.join(DIR, "expected.json")
RESULTS_PATH = os.path.join(DIR, "RESULTS.md")


def normalize_code(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    # Strip empty lines from start and end
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


EXPECTED_FIXED_CODE = {
    "e01_cmd_injection": "int system(char *command);\nint main() {\n    char cmd[50];\n    scanf(\"%49s\", cmd);\n    if (strcmp(cmd, \"ls\") == 0) {\n        system(\"ls\");\n    } else if (strcmp(cmd, \"date\") == 0) {\n        system(\"date\");\n    } else {\n        printf(\"command not allowed\\n\");\n    }\n}\n",
    "e02_scanf_widths": "int main() {\n    char a[20];\n    char b[10];\n    scanf(\"%19s\", a);\n    scanf(\"%9s\", b);\n    return 0;\n}\n",
    "e03_gets": "int main() {\n    char buf[100];\n    fgets(buf, sizeof(buf), stdin);\n    return 0;\n}\n",
    "e04_strcpy": "int main() {\n    char dst[10];\n    char src[20];\n    scanf(\"%19s\", src);\n    snprintf(dst, sizeof(dst), \"%s\", src);\n    return 0;\n}\n",
    "e05_strcat": "int main() {\n    char dst[20] = \"ab\";\n    char src[10];\n    scanf(\"%9s\", src);\n    strncat(dst, src, sizeof(dst) - strlen(dst) - 1);\n    return 0;\n}\n",
    "e06_sprintf": "int main() {\n    char out[16];\n    int n = 5;\n    snprintf(out, sizeof(out), \"%d\", n);\n    return 0;\n}\n",
    "e07_printf_user": "int main() {\n    char name[20];\n    scanf(\"%19s\", name);\n    printf(\"%s\", name);\n    return 0;\n}\n",
}


def main():
    if not os.path.exists(EXPECTED_PATH):
        print(f"Error: {EXPECTED_PATH} not found.")
        sys.exit(1)

    with open(EXPECTED_PATH, "r", encoding="utf-8") as f:
        expected = json.load(f)

    failures = []
    rows = []

    print("=" * 80)
    print("RUNNING SECURITY FIX 2026 EXAMPLES")
    print("=" * 80)
    header = f"{'Case Name':<28} | {'Before':<22} | {'After':<22} | {'Fixed':<6} | {'Match':<6} | {'Idemp':<6} | {'Result':<6}"
    print(header)
    print("-" * len(header))

    md_lines = [
        "# Security Fix 2026 Benchmark Results\n\n",
        "| Case Name | Before Status | After Status | Fixed | Code Match | Idempotent | Result |\n",
        "|:---|:---|:---|:---:|:---:|:---:|:---:|\n",
    ]

    for name, exp in expected.items():
        t0 = time.perf_counter()
        broken_file = os.path.join(DIR, f"{name}_broken.c")
        if not os.path.exists(broken_file):
            failures.append(f"{name}: broken file {broken_file} does not exist")
            continue

        with open(broken_file, "r", encoding="utf-8") as f:
            broken_src = f.read()

        # Step A: Run pipeline on broken file without security autofix to get 'before' status
        res_before = repair_source_for_gui(broken_src, filename=f"{name}_broken.c", enable_ai=False, enable_sec_fix=False)
        actual_before = res_before.get("status", "UNKNOWN")

        # Step B: Run pipeline on broken file with security autofix
        res_after = repair_source_for_gui(broken_src, filename=f"{name}_broken.c", enable_ai=False, enable_sec_fix=True)
        corrected_code = res_after.get("corrected_code", broken_src)
        actual_after = res_after.get("status", "UNKNOWN")

        # Step C: Verify before status
        case_failed = False
        if actual_before != exp["before"]:
            failures.append(f"{name}: before status mismatch: expected {exp['before']}, got {actual_before}")
            case_failed = True

        # Step D: Verify after status and code
        code_matched = False
        if exp["fixed"]:
            fixed_file = os.path.join(DIR, f"{name}_fixed.c")
            if os.path.exists(fixed_file):
                with open(fixed_file, "r", encoding="utf-8") as f:
                    exp_fixed_src = f.read()
            else:
                exp_fixed_src = EXPECTED_FIXED_CODE.get(name)

            if exp_fixed_src is not None:
                if normalize_code(corrected_code) == normalize_code(exp_fixed_src):
                    code_matched = True
                else:
                    failures.append(f"{name}: corrected code does not match expected fix")
                    case_failed = True
            else:
                if normalize_code(corrected_code) != normalize_code(broken_src):
                    code_matched = True
                else:
                    failures.append(f"{name}: expected code to be modified")
                    case_failed = True
        else:
            if normalize_code(corrected_code) == normalize_code(broken_src):
                code_matched = True
            else:
                failures.append(f"{name}: expected no code change, but code was modified")
                case_failed = True

        if actual_after != exp["after"]:
            failures.append(f"{name}: after status mismatch: expected {exp['after']}, got {actual_after}")
            case_failed = True

        # Step E: Check finding_contains and must_not_contain
        all_findings_text = " ".join(
            [str(w) for w in res_after.get("security_warnings", [])]
            + [str(s) for s in res_after.get("security_suggestions", [])]
            + [str(w) for w in res_before.get("security_warnings", [])]
            + [str(s) for s in res_before.get("security_suggestions", [])]
        )
        if "finding_contains" in exp:
            req_substr = exp["finding_contains"]
            if req_substr not in all_findings_text:
                failures.append(f"{name}: findings did not contain {req_substr!r}")
                case_failed = True

        if "must_not_contain" in exp:
            forbidden = exp["must_not_contain"]
            after_warnings = " ".join([str(w) for w in res_after.get("security_warnings", [])])
            if forbidden in after_warnings:
                failures.append(f"{name}: findings must not contain {forbidden!r}, but found in {after_warnings!r}")
                case_failed = True

        # Step F: Idempotence test
        res_idemp = repair_source_for_gui(corrected_code, filename=f"{name}_repaired.c", enable_ai=False, enable_sec_fix=True)
        idemp_code = res_idemp.get("corrected_code", corrected_code)
        idemp_matched = (normalize_code(idemp_code) == normalize_code(corrected_code))
        if not idemp_matched:
            failures.append(f"{name}: idempotence failure (second run modified code)")
            case_failed = True

        result_str = "PASS" if not case_failed else "FAIL"
        row_str = f"{name:<28} | {actual_before:<22} | {actual_after:<22} | {str(exp['fixed']):<6} | {str(code_matched):<6} | {str(idemp_matched):<6} | {result_str:<6}"
        print(row_str)
        md_lines.append(f"| `{name}` | `{actual_before}` | `{actual_after}` | {exp['fixed']} | {code_matched} | {idemp_matched} | **{result_str}** |\n")

    md_lines.append("\n## Summary\n\n")
    if not failures:
        md_lines.append(f"All {len(expected)} examples PASSED all checks with 0 regressions.\n")
    else:
        md_lines.append(f"{len(failures)} failures encountered:\n\n")
        for fail in failures:
            md_lines.append(f"- {fail}\n")

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.writelines(md_lines)
    print(f"\nWrote results to {RESULTS_PATH}")

    if failures:
        print("\nFAILURES:")
        for fail in failures:
            print("  *", fail)
        sys.exit(1)
    else:
        print(f"\nSUCCESS: All {len(expected)} security examples passed cleanly!")
        sys.exit(0)


if __name__ == "__main__":
    main()
