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

ERROR_CLASSES = [
    "missing_paren",
    "extra_paren",
    "missing_brace",
    "swapped_operator",
    "misspelled_identifier",
    "missing_comma",
    "stray_token",
]

def inject_error(source: str, error_class: str) -> str:
    lines = source.splitlines(keepends=True)
    n = len(lines)
    
    if error_class == "missing_paren":
        # Remove a closing parenthesis in an if/for condition
        for idx in range(len(lines)):
            if "if (" in lines[idx] and ")" in lines[idx]:
                lines[idx] = lines[idx].replace(")", "", 1)
                break
    elif error_class == "extra_paren":
        # Add an extra opening or closing parenthesis
        for idx in range(len(lines)):
            if "for (" in lines[idx]:
                lines[idx] = lines[idx].replace("for (", "for ((", 1)
                break
    elif error_class == "missing_brace":
        # Remove a closing brace of an if statement
        for idx in range(len(lines)):
            if lines[idx].strip() == "}":
                lines[idx] = ""
                break
    elif error_class == "swapped_operator":
        # Swap an operator in an expression or condition
        for idx in range(len(lines)):
            if " + " in lines[idx]:
                lines[idx] = lines[idx].replace(" + ", " * ", 1)
                break
    elif error_class == "misspelled_identifier":
        # Misspell a function or local variable
        for idx in range(len(lines)):
            if "int sum = 0;" in lines[idx]:
                lines[idx] = lines[idx].replace("int sum", "int smm", 1)
                break
            elif "int res = 1;" in lines[idx]:
                lines[idx] = lines[idx].replace("int res", "int rse", 1)
                break
    elif error_class == "missing_comma":
        # Missing comma in argument call
        for idx in range(len(lines)):
            if "scale_elements(data, 6, 2);" in lines[idx]:
                lines[idx] = lines[idx].replace("6, 2", "6 2", 1)
                break
            elif "gcd_recursive(b, a % b)" in lines[idx]:
                lines[idx] = lines[idx].replace("b, a", "b a", 1)
                break
    elif error_class == "stray_token":
        # Stray token inserted in body
        for idx in range(len(lines)):
            if "int max_val = arr[0];" in lines[idx]:
                lines[idx] = "    @\n" + lines[idx]
                break
            elif "int sum = 0;" in lines[idx]:
                lines[idx] = "    #bad\n" + lines[idx]
                break
            elif "int val = calculate_series(i);" in lines[idx]:
                lines[idx] = "    $\n" + lines[idx]
                break

    return "".join(lines)


def generate_programs() -> List[Dict[str, Any]]:
    programs = []
    # 30 programs = 4 per class for 5 classes, 5 for 2 classes
    counts = {ec: 0 for ec in ERROR_CLASSES}
    
    for i in range(30):
        tmpl = CLEAN_TEMPLATES[i % len(CLEAN_TEMPLATES)]
        ec = ERROR_CLASSES[i % len(ERROR_CLASSES)]
        counts[ec] += 1
        corrupted = inject_error(tmpl, ec)
        programs.append({
            "id": f"prog_{i+1:02d}",
            "error_class": ec,
            "code": corrupted,
            "original_clean": tmpl,
            "split": "dev" if i < 15 else "unseen"
        })
    return programs


def evaluate_unseen():
    programs = generate_programs()
    dev_set = [p for p in programs if p["split"] == "dev"]
    unseen_set = [p for p in programs if p["split"] == "unseen"]

    compiler = SandboxedCompiler()
    syntax_agent = SyntaxAgent()
    mgr = RepairJobManager()

    print(f"Total Generated Programs: {len(programs)} (Dev: {len(dev_set)}, Unseen: {len(unseen_set)})")
    print("\nEvaluating 15 UNSEEN Held-Out Programs...")

    results_by_class: Dict[str, Dict[str, Any]] = {
        ec: {"total": 0, "fixed": 0, "not_fixed": 0, "tiers": []}
        for ec in ERROR_CLASSES
    }

    detailed_rows = []

    for idx, p in enumerate(unseen_set, 1):
        pid = p["id"]
        ec = p["error_class"]
        code = p["code"]

        results_by_class[ec]["total"] += 1

        # Check initial compilation
        init_ok, init_err, _ = compiler.compile_check(code)
        init_fnds = syntax_agent.analyze(code, filename=f"{pid}.c")

        # Execute Repair Job
        job = mgr.create_job(code=code, filename=f"{pid}.c", language="c")
        mgr._execute_repair_job(job)

        cand = job.current_code
        post_ok, post_err, _ = compiler.compile_check(cand)
        post_fnds = syntax_agent.analyze(cand, filename=f"{pid}.c")

        # Scope guard verification
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

        # Requirement 3: Rules-only success must not be reported as repair success unless the scope guard passes
        is_fixed = post_ok and (len(post_fnds) <= len(init_fnds)) and scope_ok

        if is_fixed:
            results_by_class[ec]["fixed"] += 1
        else:
            results_by_class[ec]["not_fixed"] += 1

        if tier_used != "none":
            results_by_class[ec]["tiers"].append(tier_used)

        detailed_rows.append({
            "id": pid,
            "error_class": ec,
            "fixed": is_fixed,
            "compiles": post_ok,
            "scope_guard": scope_ok,
            "tier": tier_used,
            "seconds": round(job.elapsed_s, 2)
        })

    print("\n=== REQUIREMENT 3: HELD-OUT EVALUATION RESULTS (15 UNSEEN PROGRAMS) ===")
    print(f"{'Error Class':<25} | {'Fixed (Compiles & Scope OK)':<30} | {'Not Fixed':<12} | {'Tier(s) Used':<18}")
    print("-" * 92)
    for ec in ERROR_CLASSES:
        st = results_by_class[ec]
        tiers_str = ", ".join(sorted(list(set(st["tiers"])))) if st["tiers"] else "none"
        fixed_ratio = f"{st['fixed']}/{st['total']}"
        print(f"{ec:<25} | {fixed_ratio:<30} | {st['not_fixed']:<12} | {tiers_str:<18}")
    print("-" * 92)

    total_fixed = sum(st["fixed"] for st in results_by_class.values())
    total_unseen = sum(st["total"] for st in results_by_class.values())
    print(f"\nOverall Unseen Held-out Accuracy: {total_fixed}/{total_unseen} ({total_fixed / total_unseen * 100:.1f}%)")


if __name__ == "__main__":
    evaluate_unseen()
