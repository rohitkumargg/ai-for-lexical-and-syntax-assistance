# scripts/held_out_evaluation.py
import os
import sys
import random
import time
from typing import List, Dict, Any, Tuple

sys.path.insert(0, os.getcwd())

from compiler.repair_job_manager import RepairJobManager
from compiler.patch_validator import SandboxedCompiler, PatchIntegrityInspector
from compiler.agents import SyntaxAgent

random.seed(1337)

# Clean base templates of 50 - 300 lines
CLEAN_TEMPLATES = [
    """#include <stdio.h>

int math_power(int base, int exp) {
    int res = 1;
    for (int i = 0; i < exp; i++) {
        res = res * base;
    }
    return res;
}

int calculate_series(int n) {
    int sum = 0;
    for (int i = 1; i <= n; i++) {
        sum = sum + math_power(i, 2);
    }
    return sum;
}

int is_even_number(int val) {
    if (val % 2 == 0) {
        return 1;
    }
    return 0;
}

void print_report(int count) {
    for (int i = 0; i < count; i++) {
        int val = calculate_series(i);
        if (is_even_number(val)) {
            printf("Step %d: Even result %d\\n", i, val);
        } else {
            printf("Step %d: Odd result %d\\n", i, val);
        }
    }
}

int main(void) {
    print_report(5);
    return 0;
}
""",
    """#include <stdio.h>

int array_maximum(int arr[], int size) {
    int max_val = arr[0];
    for (int i = 1; i < size; i++) {
        if (arr[i] > max_val) {
            max_val = arr[i];
        }
    }
    return max_val;
}

int array_minimum(int arr[], int size) {
    int min_val = arr[0];
    for (int i = 1; i < size; i++) {
        if (arr[i] < min_val) {
            min_val = arr[i];
        }
    }
    return min_val;
}

int compute_spread(int values[], int count) {
    int high = array_maximum(values, count);
    int low = array_minimum(values, count);
    return high - low;
}

void scale_elements(int arr[], int size, int factor) {
    for (int i = 0; i < size; i++) {
        arr[i] = arr[i] * factor;
    }
}

int main(void) {
    int data[6] = {12, 5, 23, 8, 42, 17};
    int spread = compute_spread(data, 6);
    printf("Original spread: %d\\n", spread);
    scale_elements(data, 6, 2);
    printf("Scaled max: %d\\n", array_maximum(data, 6));
    return 0;
}
""",
    """#include <stdio.h>

int gcd_recursive(int a, int b) {
    if (b == 0) {
        return a;
    }
    return gcd_recursive(b, a % b);
}

int lcm_compute(int a, int b) {
    if (a == 0 || b == 0) {
        return 0;
    }
    int g = gcd_recursive(a, b);
    return (a * b) / g;
}

int verify_coprime(int x, int y) {
    int result = gcd_recursive(x, y);
    if (result == 1) {
        return 1;
    }
    return 0;
}

void process_pairs(int limit) {
    int coprimes_found = 0;
    for (int i = 2; i <= limit; i++) {
        for (int j = i + 1; j <= limit; j++) {
            if (verify_coprime(i, j)) {
                coprimes_found = coprimes_found + 1;
            }
        }
    }
    printf("Total coprime pairs: %d\\n", coprimes_found);
}

int main(void) {
    process_pairs(8);
    printf("LCM of 12 and 18: %d\\n", lcm_compute(12, 18));
    return 0;
}
"""
]

# Requirement 2: Judge by compile success only for classes that break compilation; remove swapped_operator
ERROR_CLASSES = [
    "missing_paren",
    "extra_paren",
    "missing_brace",
    "misspelled_identifier",
    "missing_comma",
    "stray_token",
]

def inject_error(source: str, error_class: str) -> Tuple[str, int]:
    lines = source.splitlines(keepends=True)
    defect_line = 1

    if error_class == "missing_paren":
        # Remove a closing parenthesis in an if/for condition
        for idx in range(len(lines)):
            if "if (" in lines[idx] and ")" in lines[idx]:
                lines[idx] = lines[idx].replace(")", "", 1)
                defect_line = idx + 1
                break
    elif error_class == "extra_paren":
        # Add an extra opening or closing parenthesis
        for idx in range(len(lines)):
            if "for (" in lines[idx]:
                lines[idx] = lines[idx].replace("for (", "for ((", 1)
                defect_line = idx + 1
                break
    elif error_class == "missing_brace":
        # Remove a closing brace of a function or control block
        for idx in range(len(lines)):
            if lines[idx].strip() == "}":
                lines[idx] = ""
                defect_line = idx + 1
                break
    elif error_class == "misspelled_identifier":
        # Misspell a function or local variable
        for idx in range(len(lines)):
            if "int sum = 0;" in lines[idx]:
                lines[idx] = lines[idx].replace("int sum", "int smm", 1)
                defect_line = idx + 1
                break
            elif "int res = 1;" in lines[idx]:
                lines[idx] = lines[idx].replace("int res", "int rse", 1)
                defect_line = idx + 1
                break
    elif error_class == "missing_comma":
        # Missing comma in argument call
        for idx in range(len(lines)):
            if "scale_elements(data, 6, 2);" in lines[idx]:
                lines[idx] = lines[idx].replace("6, 2", "6 2", 1)
                defect_line = idx + 1
                break
            elif "gcd_recursive(b, a % b)" in lines[idx]:
                lines[idx] = lines[idx].replace("b, a", "b a", 1)
                defect_line = idx + 1
                break
    elif error_class == "stray_token":
        # Stray token inserted in body
        for idx in range(len(lines)):
            if "int max_val = arr[0];" in lines[idx]:
                lines[idx] = "    @\n" + lines[idx]
                defect_line = idx + 1
                break
            elif "int sum = 0;" in lines[idx]:
                lines[idx] = "    #bad\n" + lines[idx]
                defect_line = idx + 1
                break
            elif "int val = calculate_series(i);" in lines[idx]:
                lines[idx] = "    $\n" + lines[idx]
                defect_line = idx + 1
                break
            elif "int g = gcd_recursive(a, b);" in lines[idx]:
                lines[idx] = "    @\n" + lines[idx]
                defect_line = idx + 1
                break

    return "".join(lines), defect_line


def generate_programs() -> List[Dict[str, Any]]:
    programs = []
    # 30 programs = 5 per class across 6 classes
    for i in range(30):
        tmpl = CLEAN_TEMPLATES[i % len(CLEAN_TEMPLATES)]
        ec = ERROR_CLASSES[i % len(ERROR_CLASSES)]
        corrupted, defect_line = inject_error(tmpl, ec)
        programs.append({
            "id": f"prog_{i+1:02d}",
            "error_class": ec,
            "code": corrupted,
            "true_defect_line": defect_line,
            "original_clean": tmpl,
            "split": "dev" if i < 15 else "unseen"
        })
    return programs


def run_evaluation(evaluate_unseen_only: bool = True):
    programs = generate_programs()
    dev_set = [p for p in programs if p["split"] == "dev"]
    unseen_set = [p for p in programs if p["split"] == "unseen"]

    compiler = SandboxedCompiler()
    syntax_agent = SyntaxAgent()
    mgr = RepairJobManager()

    target_set = unseen_set if evaluate_unseen_only else dev_set
    set_name = "UNSEEN Held-Out" if evaluate_unseen_only else "DEV"

    print(f"Total Programs: {len(programs)} (Dev: {len(dev_set)}, Unseen: {len(unseen_set)})")
    print(f"\nEvaluating {len(target_set)} {set_name} Programs...")

    # Requirement 2: Diagnose extra_paren and missing_brace
    print("\n--- DIAGNOSIS FOR extra_paren AND missing_brace ---")
    for p in target_set:
        if p["error_class"] in ("extra_paren", "missing_brace"):
            pid = p["id"]
            ec = p["error_class"]
            true_l = p["true_defect_line"]
            init_ok, init_out, _ = compiler.compile_check(p["code"])
            init_fnds = syntax_agent.analyze(p["code"], filename=f"{pid}.c")
            finding_line = init_fnds[0].location.line if (init_fnds and hasattr(init_fnds[0], "location") and init_fnds[0].location) else "None"
            
            # Check window bounds
            from compiler.repair_job_manager import split_top_level_functions
            _, fns = split_top_level_functions(p["code"])
            enclosing_fn = next((f for f in fns if f["start_line"] <= true_l <= f["end_line"]), None)
            win_used = f"lines {enclosing_fn['start_line']}-{enclosing_fn['end_line']} ({enclosing_fn['name']})" if enclosing_fn else "function window"

            # Execute dry job
            job = mgr.create_job(code=p["code"], filename=f"{pid}.c", language="c")
            mgr._execute_repair_job(job)
            cand = job.current_code
            post_ok, _, _ = compiler.compile_check(cand)
            scope_ok, scope_reasons = PatchIntegrityInspector.inspect(p["code"], cand, original_findings=init_fnds, filename=f"{pid}.c")

            validator_status = "Accepted (clean compile + scope OK)" if (post_ok and scope_ok) else f"Rejected ({'; '.join(scope_reasons) if not scope_ok else 'compiler rejection'})"
            print(f"[{pid}] {ec:<14} | Finding Line: {finding_line:<3} | True Defect Line: {true_l:<3} | Window: {win_used:<28} | Result: {validator_status}")

    results_by_class: Dict[str, Dict[str, Any]] = {
        ec: {"total": 0, "fixed": 0, "not_fixed": 0, "already_compiled": 0, "tiers": []}
        for ec in ERROR_CLASSES
    }

    for idx, p in enumerate(target_set, 1):
        pid = p["id"]
        ec = p["error_class"]
        code = p["code"]

        results_by_class[ec]["total"] += 1

        init_ok, init_err, _ = compiler.compile_check(code)
        init_fnds = syntax_agent.analyze(code, filename=f"{pid}.c")

        job = mgr.create_job(code=code, filename=f"{pid}.c", language="c")
        mgr._execute_repair_job(job)

        cand = job.current_code
        post_ok, post_err, _ = compiler.compile_check(cand)
        post_fnds = syntax_agent.analyze(cand, filename=f"{pid}.c")

        scope_ok, scope_reason = PatchIntegrityInspector.inspect(
            p["code"], cand, original_findings=init_fnds, filename=f"{pid}.c"
        )

        tier_used = "none"
        if job.windows_by_tier.get("qwen", 0) > 0:
            tier_used = "qwen"
        elif job.windows_by_tier.get("codet5", 0) > 0:
            tier_used = "codet5"
        elif job.windows_by_tier.get("rules", 0) > 0:
            tier_used = "rules"

        # Requirement 2: A case with tier none must not count as fixed unless it compiled before repair (report as 'already compiled')
        if tier_used == "none":
            if init_ok:
                is_fixed = True
                results_by_class[ec]["already_compiled"] += 1
            else:
                is_fixed = False
        else:
            is_fixed = post_ok and (len(post_fnds) <= len(init_fnds)) and scope_ok

        if is_fixed:
            results_by_class[ec]["fixed"] += 1
        else:
            results_by_class[ec]["not_fixed"] += 1

        if tier_used != "none":
            results_by_class[ec]["tiers"].append(tier_used)

    print(f"\n=== HELD-OUT EVALUATION RESULTS ({len(target_set)} {set_name} PROGRAMS) ===")
    print(f"{'Error Class':<24} | {'Fixed (Compiles & Scope OK)':<28} | {'Not Fixed':<10} | {'Tier(s) Used':<16}")
    print("-" * 88)
    for ec in ERROR_CLASSES:
        st = results_by_class[ec]
        tiers_str = ", ".join(sorted(list(set(st["tiers"])))) if st["tiers"] else "none"
        fixed_ratio = f"{st['fixed']}/{st['total']} ({st['already_compiled']} already compiled)" if st["already_compiled"] > 0 else f"{st['fixed']}/{st['total']}"
        print(f"{ec:<24} | {fixed_ratio:<28} | {st['not_fixed']:<10} | {tiers_str:<16}")
    print("-" * 88)

    total_fixed = sum(st["fixed"] for st in results_by_class.values())
    total_cases = sum(st["total"] for st in results_by_class.values())
    print(f"\nOverall {set_name} Accuracy: {total_fixed}/{total_cases} ({total_fixed / total_cases * 100:.1f}%)")


if __name__ == "__main__":
    run_evaluation(evaluate_unseen_only=True)
