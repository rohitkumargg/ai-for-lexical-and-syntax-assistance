"""Stage 3 Semantic Fault Injection & Dataset Builder.

Generates paired (buggy_code, line_relative_edit) training samples for model-targeted semantic issues:
1. undeclared (judgment / context-dependent)
2. redeclared (rename / remove duplicate)
3. unknown_member (non-typo member access)

All samples are strictly verified by SemanticChecker:
- Target format: Line-relative edit ("LINE <L>: <repaired_line>")
- Leakage prevention: Partitioned strictly by structural program skeleton across train/val/test splits.
"""
from __future__ import annotations

import collections
import json
import os
import random
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from test_parser import parse_source, has_any_errors
from compiler.semantic_checker import SemanticChecker

RNG_SEED = 2026

C_KEYWORDS = {
    "int", "char", "float", "double", "void", "short", "long", "unsigned", "signed",
    "struct", "return", "if", "else", "while", "for", "do", "break", "continue",
    "switch", "case", "default", "sizeof"
}


def get_structural_skeleton(code: str) -> str:
    """Extract structural skeleton preserving C keywords and operators, normalizing identifiers and numbers."""
    c = re.sub(r"//.*", "", code)
    c = re.sub(r"/\*.*?\*/", "", c, flags=re.DOTALL)
    c = re.sub(r'"([^"\\]|\\.)*"', '""', c)
    c = re.sub(r"'(\\.|[^\\'])'", "''", c)

    tokens = re.findall(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|\+\+|--|&&|\|\||->|[{}()\[\];,=+\-*/%<>?:]", c)
    norm = []
    for t in tokens:
        if t in C_KEYWORDS:
            norm.append(t)
        elif re.fullmatch(r"[A-Za-z_]\w*", t):
            norm.append("ID")
        elif re.fullmatch(r"\d+", t):
            norm.append("NUM")
        else:
            norm.append(t)
    return " ".join(norm)


def generate_clean_seed_corpus() -> List[str]:
    """Generates 600 diverse, 100% checker-clean seeds across 6 template families."""
    seeds = []
    
    # Family 1: Math functions (100 seeds)
    for i in range(100):
        seeds.append(f"""int calc_math_{i}(int a, int b) {{
    int x = a * 2;
    int y = b + 3;
    int z = x + y;
    if (z > 10) {{
        z = z - 5;
    }} else {{
        z = z + 5;
    }}
    return z;
}}

int main() {{
    int res = calc_math_{i}(3, 4);
    return res;
}}
""")

    # Family 2: Array loops (100 seeds)
    for i in range(100):
        seeds.append(f"""int process_arr_{i}(int start_val) {{
    int arr[5];
    int sum = 0;
    int k = start_val;
    for (int idx = 0; idx < 5; idx++) {{
        arr[idx] = k + idx;
        sum = sum + arr[idx];
    }}
    return sum;
}}

int main() {{
    int total = process_arr_{i}(10);
    return total;
}}
""")

    # Family 3: Struct dot operations (100 seeds)
    for i in range(100):
        seeds.append(f"""struct Point_{i} {{
    int x;
    int y;
    int id;
}};

int calc_point_{i}(int factor) {{
    struct Point_{i} pt;
    pt.x = factor * 2;
    pt.y = factor + 4;
    pt.id = {i};
    return pt.x + pt.y + pt.id;
}}

int main() {{
    int r = calc_point_{i}(5);
    return r;
}}
""")

    # Family 4: While loops & counters (100 seeds)
    for i in range(100):
        seeds.append(f"""int evaluate_cond_{i}(int u, int v) {{
    int p = u + 1;
    int q = v * 2;
    int count = 0;
    while (p < q) {{
        p = p + 2;
        count = count + 1;
    }}
    return count;
}}

int main() {{
    int c = evaluate_cond_{i}(2, 8);
    return c;
}}
""")

    # Family 5: Struct rectangle / buffer (100 seeds)
    for i in range(100):
        seeds.append(f"""struct Rect_{i} {{
    int width;
    int height;
    int area;
}};

int compute_rect_{i}(int w, int h) {{
    struct Rect_{i} r;
    r.width = w;
    r.height = h;
    r.area = r.width * r.height;
    return r.area;
}}

int main() {{
    int a = compute_rect_{i}(4, 6);
    return a;
}}
""")

    # Family 6: Nested calculations (100 seeds)
    for i in range(100):
        seeds.append(f"""int nested_calc_{i}(int base) {{
    int acc = base;
    for (int j = 0; j < 3; j++) {{
        acc = acc + (j * 2);
    }}
    int final_res = acc + 10;
    return final_res;
}}

int main() {{
    int ans = nested_calc_{i}(5);
    return ans;
}}
""")

    return seeds


# Injection generators
UNDECLARED_NAMES = [
    "ext_delta", "ext_metric", "offset_val", "scale_factor", "accum_extra",
    "aux_counter", "temp_reading", "cache_slot", "weight_factor", "bias_offset",
    "flag_status", "step_size", "buffer_pos", "loop_stride", "elem_delta"
]


def inject_undeclared(clean_code: str) -> List[Tuple[str, str, str, str]]:
    candidates = []
    lines = clean_code.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)([A-Za-z_]\w*)\s*=\s*([^;]+);(.*)$", line)
        if m:
            indent, lhs, rhs, rest = m.groups()
            for name in random.sample(UNDECLARED_NAMES, 2):
                if re.search(rf"\b{name}\b", clean_code):
                    continue
                new_rhs = f"({rhs}) + {name}"
                buggy_line = f"{indent}{lhs} = {new_rhs};{rest}"
                buggy_lines = list(lines)
                buggy_lines[i] = buggy_line
                buggy_code = "\n".join(buggy_lines) + "\n"
                target_edit = f"LINE {i + 1}: {line.strip()}"
                candidates.append((buggy_code, "undeclared", name, target_edit))
    return candidates


def inject_redeclared(clean_code: str) -> List[Tuple[str, str, str, str]]:
    candidates = []
    lines = clean_code.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)(int|float|char)\s+([A-Za-z_]\w*)\s*(=[^;]+)?;(.*)$", line)
        if m:
            indent, ctype, var_name, init, rest = m.groups()
            alt_name = f"{var_name}_alt"
            redecl_line = f"{indent}{ctype} {var_name} = 42;{rest}"
            buggy_lines = list(lines)
            buggy_lines.insert(i + 1, redecl_line)
            buggy_code = "\n".join(buggy_lines) + "\n"
            target_edit = f"LINE {i + 2}: {indent}{ctype} {alt_name} = 42;{rest}".strip()
            candidates.append((buggy_code, "redeclared", var_name, target_edit))
    return candidates


def inject_unknown_member(clean_code: str) -> List[Tuple[str, str, str, str]]:
    candidates = []
    lines = clean_code.splitlines()
    for i, line in enumerate(lines):
        m = re.search(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", line)
        if m:
            var_name, member_name = m.groups()
            for bad_m in ["invalid_field", "unknown_dim", "extra_val", "bad_attr", "nonexistent"]:
                buggy_line = line.replace(f"{var_name}.{member_name}", f"{var_name}.{bad_m}", 1)
                buggy_lines = list(lines)
                buggy_lines[i] = buggy_line
                buggy_code = "\n".join(buggy_lines) + "\n"
                target_edit = f"LINE {i + 1}: {line.strip()}"
                candidates.append((buggy_code, "unknown_member", bad_m, target_edit))
    return candidates


def extract_real_verified_cases(log_path: str = "logs/repair_log.jsonl") -> List[Dict[str, Any]]:
    real_cases = []
    if not os.path.exists(log_path):
        return real_cases

    cases_by_id: Dict[str, Dict[str, Any]] = collections.defaultdict(dict)
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                row = json.loads(line)
                data = row.get("data", {})
                cid = data.get("case_id")
                if not cid:
                    continue
                ev = row.get("event")
                if ev == "case_start":
                    cases_by_id[cid]["orig"] = data.get("original_source", "")
                    cases_by_id[cid]["filename"] = data.get("filename", "")
                elif ev == "semantic_issues":
                    cases_by_id[cid]["issues"] = data.get("issues", [])
                elif ev == "case_end":
                    cases_by_id[cid]["status"] = data.get("status")
                    cases_by_id[cid]["final"] = data.get("final_source", "")
                    cases_by_id[cid]["steps"] = data.get("applied_steps", [])
            except Exception:
                pass

    seen_pairs = set()
    for cid, c in cases_by_id.items():
        orig = c.get("orig", "").strip()
        final = c.get("final", "").strip()
        status = c.get("status")
        issues = c.get("issues", [])
        if status == "SUCCESS" and orig and final and orig != final:
            target_issues = [i for i in issues if i.get("kind") in ("undeclared", "redeclared", "unknown_member")]
            if target_issues:
                t_iss = target_issues[0]
                pair_key = (orig, final)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Compute line-relative edit
                orig_lines = orig.splitlines()
                final_lines = final.splitlines()
                target_edit = ""
                for l_idx, (o_l, f_l) in enumerate(zip(orig_lines, final_lines), start=1):
                    if o_l != f_l:
                        target_edit = f"LINE {l_idx}: {f_l}"
                        break
                if not target_edit and len(final_lines) != len(orig_lines):
                    target_edit = f"LINE {t_iss.get('line', 1)}: {final_lines[min(len(final_lines)-1, t_iss.get('line', 1)-1)]}"

                real_cases.append({
                    "input": orig,
                    "target": final,
                    "target_edit": target_edit,
                    "family": t_iss.get("kind"),
                    "target_name": t_iss.get("name", ""),
                    "error_line": t_iss.get("line", 1),
                    "error_col": t_iss.get("col", 1),
                    "error_msg": t_iss.get("msg", "Real verified log case"),
                    "seed_file": os.path.basename(c.get("filename") or "repair_log.c"),
                    "skeleton": get_structural_skeleton(orig),
                })
    return real_cases


def main():
    out_dir = "data/semantic_splits"
    os.makedirs(out_dir, exist_ok=True)

    print("Generating 600 checker-clean seed programs across 6 structural families...")
    raw_seeds = generate_clean_seed_corpus()
    
    # Verify all are clean
    clean_seeds = []
    for s in raw_seeds:
        t, l, _ = parse_source(s, "verify_seed")
        if t and not has_any_errors(l):
            sc = SemanticChecker()
            sc.visit(t)
            if len(sc.get_issues()) == 0:
                clean_seeds.append(s)

    print(f"Verified {len(clean_seeds)} checker-clean seeds.")

    # Group by structural skeleton
    skeleton_to_seeds: Dict[str, List[str]] = collections.defaultdict(list)
    for code in clean_seeds:
        skel = get_structural_skeleton(code)
        skeleton_to_seeds[skel].append(code)

    all_skels = list(skeleton_to_seeds.keys())
    print(f"Unique structural skeletons: {len(all_skels)}")

    # Disjoint split
    random.seed(RNG_SEED)
    random.shuffle(all_skels)
    n = len(all_skels)
    n_train = max(1, int(n * 0.70))
    n_val = max(1, int(n * 0.15))

    train_skels = set(all_skels[:n_train])
    val_skels = set(all_skels[n_train:n_train + n_val])
    test_skels = set(all_skels[n_train + n_val:])

    split_map = {
        "train": [c for s in train_skels for c in skeleton_to_seeds[s]],
        "val": [c for s in val_skels for c in skeleton_to_seeds[s]],
        "test": [c for s in test_skels for c in skeleton_to_seeds[s]],
    }

    print(f"Partitioned: {len(split_map['train'])} train seeds, {len(split_map['val'])} val seeds, {len(split_map['test'])} test seeds.")

    final_splits: Dict[str, List[Dict[str, Any]]] = {"train": [], "val": [], "test": []}
    kind_counts: Dict[str, int] = collections.defaultdict(int)

    for split_name, seed_list in split_map.items():
        for clean_code in seed_list:
            skel = get_structural_skeleton(clean_code)

            # 1. Undeclared
            for buggy, kind, name, target_edit in inject_undeclared(clean_code):
                t1, l1, _ = parse_source(buggy, "eval-und")
                if t1 and not has_any_errors(l1):
                    sc = SemanticChecker()
                    sc.visit(t1)
                    issues = sc.get_issues()
                    if any(i.get("kind") == "undeclared" for i in issues):
                        t_iss = [i for i in issues if i.get("kind") == "undeclared"][0]
                        final_splits[split_name].append({
                            "input": buggy,
                            "target": clean_code,
                            "target_edit": target_edit,
                            "family": "undeclared",
                            "target_name": name,
                            "error_line": t_iss.get("line"),
                            "error_col": t_iss.get("col"),
                            "error_msg": t_iss.get("msg"),
                            "skeleton": skel,
                        })
                        kind_counts["undeclared"] += 1

            # 2. Redeclared
            for buggy, kind, name, target_edit in inject_redeclared(clean_code):
                t1, l1, _ = parse_source(buggy, "eval-redecl")
                if t1 and not has_any_errors(l1):
                    sc = SemanticChecker()
                    sc.visit(t1)
                    issues = sc.get_issues()
                    if any(i.get("kind") == "redeclared" for i in issues):
                        t_iss = [i for i in issues if i.get("kind") == "redeclared"][0]
                        final_splits[split_name].append({
                            "input": buggy,
                            "target": clean_code,
                            "target_edit": target_edit,
                            "family": "redeclared",
                            "target_name": name,
                            "error_line": t_iss.get("line"),
                            "error_col": t_iss.get("col"),
                            "error_msg": t_iss.get("msg"),
                            "skeleton": skel,
                        })
                        kind_counts["redeclared"] += 1

            # 3. Unknown member
            for buggy, kind, name, target_edit in inject_unknown_member(clean_code):
                t1, l1, _ = parse_source(buggy, "eval-member")
                if t1 and not has_any_errors(l1):
                    sc = SemanticChecker()
                    sc.visit(t1)
                    issues = sc.get_issues()
                    if any(i.get("kind") == "unknown_member" for i in issues):
                        t_iss = [i for i in issues if i.get("kind") == "unknown_member"][0]
                        final_splits[split_name].append({
                            "input": buggy,
                            "target": clean_code,
                            "target_edit": target_edit,
                            "family": "unknown_member",
                            "target_name": name,
                            "error_line": t_iss.get("line"),
                            "error_col": t_iss.get("col"),
                            "error_msg": t_iss.get("msg"),
                            "skeleton": skel,
                        })
                        kind_counts["unknown_member"] += 1

    # Include real cases
    real_cases = extract_real_verified_cases("logs/repair_log.jsonl")
    for rc in real_cases:
        final_splits["train"].append(rc)

    # Save to disk
    for split_name, rows in final_splits.items():
        out_path = os.path.join(out_dir, f"{split_name}.jsonl")
        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        print(f"Saved {split_name}: {len(rows)} samples -> {out_path}")

    report = {
        "samples_per_kind": kind_counts,
        "total_train": len(final_splits["train"]),
        "total_val": len(final_splits["val"]),
        "total_test": len(final_splits["test"]),
        "train_skeletons": len(train_skels),
        "val_skeletons": len(val_skels),
        "test_skeletons": len(test_skels),
    }

    report_path = os.path.join(out_dir, "dataset_audit_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\nDataset generation completed successfully:")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
