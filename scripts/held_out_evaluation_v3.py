# scripts/held_out_evaluation_v3.py
import os
import sys
import random
import time
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Tuple

sys.path.insert(0, os.getcwd())

from compiler.repair_job_manager import RepairJobManager, check_c_syntax_errors, split_top_level_functions
from compiler.repair_planner import RepairPlanner
from compiler.patch_validator import SandboxedCompiler, PatchIntegrityInspector
from compiler.agents import SyntaxAgent

# Seed 8888 as mandated for fresh evaluation
random.seed(8888)

CLEAN_TEMPLATES_V3 = [
    # Program 1: Circular Queue / Ring Buffer (~100 lines)
    """#include <stdio.h>

void queue_init(int q[], int *head, int *tail, int *count, int max_size) {
    *head = 0;
    *tail = 0;
    *count = 0;
    for (int i = 0; i < max_size; i++) {
        q[i] = 0;
    }
}

int queue_is_empty(int count) {
    if (count == 0) {
        return 1;
    }
    return 0;
}

int queue_is_full(int count, int max_size) {
    if (count >= max_size) {
        return 1;
    }
    return 0;
}

int queue_enqueue(int q[], int *tail, int *count, int max_size, int val) {
    if (queue_is_full(*count, max_size)) {
        return 0;
    }
    q[*tail] = val;
    *tail = (*tail + 1) % max_size;
    *count = *count + 1;
    return 1;
}

int queue_dequeue(int q[], int *head, int *count, int max_size, int *out_val) {
    if (queue_is_empty(*count)) {
        return 0;
    }
    *out_val = q[*head];
    *head = (*head + 1) % max_size;
    *count = *count - 1;
    return 1;
}

int main() {
    int buffer[8];
    int head = 0;
    int tail = 0;
    int count = 0;
    queue_init(buffer, &head, &tail, &count, 8);
    for (int i = 1; i <= 5; i++) {
        queue_enqueue(buffer, &tail, &count, 8, i * 10);
    }
    int val = 0;
    while (!queue_is_empty(count)) {
        queue_dequeue(buffer, &head, &count, 8, &val);
        printf("Dequeued: %d\\n", val);
    }
    return 0;
}
""",

    # Program 2: 2D Physics / Particle Simulator (~110 lines)
    """#include <stdio.h>

int compute_kinetic_energy(int mass, int velocity) {
    int v_sq = velocity * velocity;
    int ke = (mass * v_sq) / 2;
    return ke;
}

int apply_gravity_step(int current_y, int velocity_y, int time_step) {
    int gravity = 9;
    int new_v = velocity_y - gravity * time_step;
    int new_y = current_y + new_v * time_step;
    if (new_y < 0) {
        new_y = 0;
    }
    return new_y;
}

int check_ground_collision(int y_pos) {
    if (y_pos <= 0) {
        return 1;
    }
    return 0;
}

void simulate_particle_fall(int initial_y, int steps) {
    int y = initial_y;
    int v = 0;
    for (int step = 0; step < steps; step++) {
        y = apply_gravity_step(y, v, 1);
        int hit = check_ground_collision(y);
        if (hit == 1) {
            printf("Particle hit ground at step %d\\n", step);
            break;
        }
        int ke = compute_kinetic_energy(2, v);
        printf("Step %d: Y=%d, KE=%d\\n", step, y, ke);
    }
}

int main() {
    printf("Starting Simulation...\\n");
    simulate_particle_fall(100, 10);
    return 0;
}
""",

    # Program 3: Text Lexer / Tokenizer Utilities (~110 lines)
    """#include <stdio.h>

int is_digit(char c) {
    if (c >= '0' && c <= '9') {
        return 1;
    }
    return 0;
}

int is_alpha(char c) {
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')) {
        return 1;
    }
    return 0;
}

int parse_integer_token(const char str[], int len) {
    int result = 0;
    for (int i = 0; i < len; i++) {
        if (is_digit(str[i])) {
            result = result * 10 + (str[i] - '0');
        }
    }
    return result;
}

int count_identifiers(const char str[], int len) {
    int count = 0;
    int in_word = 0;
    for (int i = 0; i < len; i++) {
        if (is_alpha(str[i])) {
            if (in_word == 0) {
                in_word = 1;
                count = count + 1;
            }
        } else {
            in_word = 0;
        }
    }
    return count;
}

int main() {
    char sample[] = "foo 123 bar 456 baz";
    int num = parse_integer_token("9876", 4);
    int words = count_identifiers(sample, 19);
    printf("Parsed num: %d, word count: %d\\n", num, words);
    return 0;
}
"""
]

def inject_error_v3(source: str, error_class: str) -> Tuple[str, int]:
    lines = source.splitlines()
    target_lines = [
        i for i, l in enumerate(lines)
        if len(l.strip()) > 5
        and not l.strip().startswith("#")
        and not l.strip().startswith("//")
        and not l.strip().startswith("/*")
        and not l.strip().endswith("*/")
        and not l.strip() in ("{", "}")
    ]
    if not target_lines:
        target_lines = list(range(len(lines)))

    chosen_idx = random.choice(target_lines)
    orig_line = lines[chosen_idx]
    modified_line = orig_line

    if error_class == "missing_paren":
        if "(" in orig_line:
            modified_line = orig_line.replace("(", "", 1)
        elif ")" in orig_line:
            modified_line = orig_line.replace(")", "", 1)
        else:
            modified_line = orig_line + ")"

    elif error_class == "extra_paren":
        if "(" in orig_line:
            modified_line = orig_line.replace("(", "((", 1)
        else:
            modified_line = orig_line + ")"

    elif error_class == "missing_brace":
        brace_indices = [i for i, l in enumerate(lines) if "}" in l]
        if brace_indices:
            b_idx = random.choice(brace_indices)
            lines[b_idx] = lines[b_idx].replace("}", "", 1)
            return "\n".join(lines), b_idx + 1
        else:
            modified_line = orig_line.replace("{", "", 1)

    elif error_class == "misspelled_identifier":
        import re
        tokens = re.findall(r'\b[a-zA-Z_]\w{3,}\b', orig_line)
        keywords = {"main", "return", "void", "char", "int", "float", "double", "include", "stdio"}
        candidates = [t for t in tokens if t not in keywords]
        if candidates:
            target_tok = random.choice(candidates)
            typo_tok = target_tok[:-1] + ("x" if target_tok[-1] != "x" else "y")
            modified_line = re.sub(r'\b' + re.escape(target_tok) + r'\b', typo_tok, orig_line, count=1)
        else:
            modified_line = orig_line.replace("i", "ix", 1)

    elif error_class == "missing_comma":
        # Target parameter list or function call argument list outside string literals
        call_or_decl_lines = [
            i for i in target_lines
            if "," in lines[i] and '"' not in lines[i]
        ]
        if call_or_decl_lines:
            c_idx = random.choice(call_or_decl_lines)
            lines[c_idx] = lines[c_idx].replace(",", " ", 1)
            return "\n".join(lines), c_idx + 1
        else:
            for i in target_lines:
                if "(" in lines[i] and ")" in lines[i] and '"' not in lines[i]:
                    lines[i] = lines[i].replace(")", " 42)", 1)
                    return "\n".join(lines), i + 1

    elif error_class == "stray_token":
        stray = random.choice(["@", "$", "`"])
        pos = len(orig_line) // 2
        modified_line = orig_line[:pos] + f" {stray} " + orig_line[pos:]

    lines[chosen_idx] = modified_line
    return "\n".join(lines), chosen_idx + 1

def generate_30_fresh_programs() -> List[Dict[str, Any]]:
    classes = [
        "missing_paren",
        "extra_paren",
        "missing_brace",
        "misspelled_identifier",
        "missing_comma",
        "stray_token",
    ]
    programs = []
    prog_id = 1
    # 5 per class = 30 total
    for err_cls in classes:
        for rep in range(5):
            tmpl_idx = (prog_id - 1) % len(CLEAN_TEMPLATES_V3)
            base_code = CLEAN_TEMPLATES_V3[tmpl_idx]
            injected_code, line_no = inject_error_v3(base_code, err_cls)
            programs.append({
                "id": f"fresh_v3_{prog_id:02d}",
                "error_class": err_cls,
                "code": injected_code,
                "defect_line": line_no,
                "original_clean": base_code,
            })
            prog_id += 1
    return programs

def run_fresh_evaluation():
    compiler = SandboxedCompiler()
    progs = generate_30_fresh_programs()
    print(f"Generated {len(progs)} fresh typo-injected programs (Seed 8888, 3 brand new base templates).")

    # Verify that clean base programs compile
    for idx, tmpl in enumerate(CLEAN_TEMPLATES_V3, 1):
        ok, out, _ = compiler.compile_check(tmpl)
        assert ok, f"Clean Template {idx} fails GCC: {out}"

    # Verify that each injected program actually fails GCC before repair
    for p in progs:
        ok, out, _ = compiler.compile_check(p["code"])
        assert not ok, f"Expected {p['id']} ({p['error_class']}) to fail GCC compilation, but it compiled cleanly!"

    results_by_class = {}
    for p in progs:
        c = p["error_class"]
        if c not in results_by_class:
            results_by_class[c] = {"total": 0, "fixed": 0, "not_fixed": 0, "tiers": {}}

    print("\n--- Running Single-Pass Evaluation Across 30 Programs ---")
    for idx, p in enumerate(progs, 1):
        t0 = time.time()
        err_cls = p["error_class"]
        results_by_class[err_cls]["total"] += 1

        # Request approval token from server
        tok = None
        try:
            appr_payload = json.dumps({'code': p['code'], 'filename': f"{p['id']}.c", 'language': 'c', 'operation': 'repair'}).encode('utf-8')
            req1 = urllib.request.Request('http://localhost:5000/api/security/approval/approve', data=appr_payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req1, timeout=10.0) as resp1:
                appr_data = json.loads(resp1.read().decode('utf-8'))
                tok = appr_data.get('approval_token')
        except Exception:
            pass

        payload = {
            "code": p["code"],
            "filename": f"{p['id']}.c",
            "language": "c",
            "operation": "repair",
            "approval_token": tok,
        }
        try:
            req = urllib.request.Request(
                "http://localhost:5000/api/coordinator/analyze_and_plan",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[{idx:02d}/30] {p['id']} ({err_cls:<22}): HTTP ERROR: {e}")
            results_by_class[err_cls]["not_fixed"] += 1
            continue

        cand = data.get("candidate") or {}
        proposed = data.get("proposed_code") or cand.get("proposed_code") or p["code"]
        prov = str(data.get("repair_provider") or cand.get("repair_provider") or "").lower()

        # Tier determination
        tier = "none"
        if proposed.strip() != p["code"].strip():
            if "qwen" in prov:
                tier = "qwen"
            elif "codet5" in prov:
                tier = "codet5"
            elif "det" in prov or "rule" in prov:
                tier = "rules"

        # Fixed strictly requires tier != none and gcc passes
        compiles_after, _, _ = compiler.compile_check(proposed)
        is_fixed = (tier != "none") and compiles_after

        dur = round(time.time() - t0, 2)
        if is_fixed:
            results_by_class[err_cls]["fixed"] += 1
            results_by_class[err_cls]["tiers"][tier] = results_by_class[err_cls]["tiers"].get(tier, 0) + 1
            print(f"[{idx:02d}/30] {p['id']} ({err_cls:<22}): FIXED | tier={tier:<6} | gcc=True | {dur}s")
        else:
            results_by_class[err_cls]["not_fixed"] += 1
            results_by_class[err_cls]["tiers"][tier] = results_by_class[err_cls]["tiers"].get(tier, 0) + 1
            print(f"[{idx:02d}/30] {p['id']} ({err_cls:<22}): NOT FIXED | tier={tier:<6} | gcc={compiles_after} | {dur}s")

    print("\n" + "=" * 70)
    print("FRESH HELD-OUT EVALUATION RESULTS TABLE (Seed 8888, 3 Brand New Base Templates)")
    print("=" * 70)
    print(f"{'Error Class':<25} | {'Total':<6} | {'Fixed':<6} | {'Not Fixed':<10} | {'Tiers Used'}")
    print("-" * 70)
    for c, stats in results_by_class.items():
        tiers_str = ", ".join(f"{k}:{v}" for k, v in stats["tiers"].items() if k != "none" and v > 0) or "none"
        print(f"{c:<25} | {stats['total']:<6} | {stats['fixed']:<6} | {stats['not_fixed']:<10} | {tiers_str}")
    print("=" * 70)

if __name__ == "__main__":
    run_fresh_evaluation()
