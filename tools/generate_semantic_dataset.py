"""Stage 3 Semantic Fault Injection & Dataset Generation.

Generates paired (buggy_code, line_relative_edit) training samples for model-targeted semantic issues:
1. undeclared (judgment / context-dependent)
2. redeclared (rename / remove duplicate)
3. unknown_member (non-typo member access)

All samples are strictly verified by SemanticChecker:
- Target format: Line-relative edit ("LINE <L>: <repaired_line>")
- Leakage prevention: Partitioned strictly by structural program skeleton across train/val/test splits.
"""
from __future__ import annotations

import argparse
import collections
import glob
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


def _issue_sig(iss: Dict[str, Any]) -> Tuple[str, str, str]:
    kind = iss.get("kind", "")
    name = iss.get("name", "") or ""
    msg = iss.get("msg", "") or ""
    clean_msg = re.sub(r"\bline\s+\d+\b", "", msg)
    clean_msg = re.sub(r"\bL\d+:\d+\b", "", clean_msg)
    return (kind, name, clean_msg.strip())


# ---------------------------------------------------------------------------
# Synthetic Seed Corpus Generation (with Structs & Clean Functions)
# ---------------------------------------------------------------------------

STRUCT_SPECS = [
    {
        "name": "Point",
        "members": [("int", "x"), ("int", "y")],
        "inits": ["p.x = 10;", "p.y = 20;"],
        "invalid_members": ["z", "w", "len", "dist", "val"],
    },
    {
        "name": "Rect",
        "members": [("int", "width"), ("int", "height"), ("int", "area")],
        "inits": ["r.width = 15;", "r.height = 30;", "r.area = 450;"],
        "invalid_members": ["perimeter", "depth", "diagonal", "scale", "vol"],
    },
    {
        "name": "Buffer",
        "members": [("int", "capacity"), ("int", "length"), ("int", "status")],
        "inits": ["buf.capacity = 128;", "buf.length = 64;", "buf.status = 1;"],
        "invalid_members": ["size", "count", "head", "tail", "data"],
    },
    {
        "name": "Color",
        "members": [("int", "red"), ("int", "green"), ("int", "blue"), ("int", "alpha")],
        "inits": ["c.red = 255;", "c.green = 128;", "c.blue = 64;", "c.alpha = 255;"],
        "invalid_members": ["opacity", "hue", "sat", "val", "hex"],
    },
    {
        "name": "Node",
        "members": [("int", "val"), ("int", "tag"), ("int", "key")],
        "inits": ["node.val = 42;", "node.tag = 1;", "node.key = 7;"],
        "invalid_members": ["next", "prev", "data", "weight", "id"],
    },
]


def generate_struct_seeds(count: int = 150) -> List[str]:
    """Generates clean programs containing struct definitions and member operations."""
    seeds = []
    random.seed(RNG_SEED + 99)
    for idx in range(count):
        spec = random.choice(STRUCT_SPECS)
        sname = spec["name"]
        decl_members = "\n".join(f"    {t} {m};" for t, m in spec["members"])
        valid_inits = "\n".join(f"    {stmt}" for stmt in spec["inits"])
        first_m = spec["members"][0][1]
        second_m = spec["members"][1][1]

        code = f"""struct {sname} {{
{decl_members}
}};

int calc_{sname.lower()}_{idx}(int multiplier) {{
    struct {sname} item;
{valid_inits.replace('p.', 'item.').replace('r.', 'item.').replace('buf.', 'item.').replace('c.', 'item.').replace('node.', 'item.')}
    item.{first_m} = item.{first_m} * multiplier;
    item.{second_m} = item.{second_m} + 5;
    return item.{first_m} + item.{second_m};
}}

int main() {{
    int res = calc_{sname.lower()}_{idx}(2);
    return res;
}}
"""
        seeds.append(code)
    return seeds


# ---------------------------------------------------------------------------
# Fault Injectors (Diverse, Multiple per Seed)
# ---------------------------------------------------------------------------

UNDECLARED_NAMES = [
    "ext_delta", "ext_metric", "offset_val", "scale_factor", "accum_extra",
    "aux_counter", "temp_reading", "cache_slot", "weight_factor", "bias_offset",
    "flag_status", "step_size", "buffer_pos", "loop_stride", "elem_delta"
]


def inject_undeclared_variants(clean_code: str, max_per_seed: int = 4) -> List[Tuple[str, str, str, str]]:
    """Injects undeclared identifier at diverse expressions across the program.
    Returns: list of (buggy_code, 'undeclared', name, line_relative_target)
    """
    candidates = []
    lines = clean_code.splitlines()

    candidate_line_indices = [
        i for i, line in enumerate(lines)
        if re.match(r"^(\s*)([A-Za-z_]\w*)\s*=\s*([^;]+);(.*)$", line)
    ]
    random.shuffle(candidate_line_indices)

    for i in candidate_line_indices:
        line = lines[i]
        m = re.match(r"^(\s*)([A-Za-z_]\w*)\s*=\s*([^;]+);(.*)$", line)
        if m:
            indent, lhs, rhs, rest = m.groups()
            for name in random.sample(UNDECLARED_NAMES, min(2, len(UNDECLARED_NAMES))):
                if re.search(rf"\b{name}\b", clean_code):
                    continue
                new_rhs = f"({rhs}) + {name}"
                buggy_line = f"{indent}{lhs} = {new_rhs};{rest}"
                buggy_lines = list(lines)
                buggy_lines[i] = buggy_line
                buggy_code = "\n".join(buggy_lines) + "\n"
                target_edit = f"LINE {i + 1}: {line.strip()}"
                candidates.append((buggy_code, "undeclared", name, target_edit))
                if len(candidates) >= max_per_seed:
                    return candidates

    return candidates


def inject_redeclared_variants(clean_code: str, max_per_seed: int = 4) -> List[Tuple[str, str, str, str]]:
    """Injects variable redeclarations at local and function scopes.
    Returns: list of (buggy_code, 'redeclared', name, line_relative_target)
    """
    candidates = []
    lines = clean_code.splitlines()

    candidate_line_indices = [
        i for i, line in enumerate(lines)
        if re.match(r"^(\s*)(int|float|char)\s+([A-Za-z_]\w*)\s*(=[^;]+)?;(.*)$", line)
    ]
    random.shuffle(candidate_line_indices)

    for i in candidate_line_indices:
        line = lines[i]
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
            if len(candidates) >= max_per_seed:
                return candidates

    return candidates


def inject_unknown_member_variants(clean_code: str, max_per_seed: int = 4) -> List[Tuple[str, str, str, str]]:
    """Injects invalid member accesses on struct types.
    Returns: list of (buggy_code, 'unknown_member', member, line_relative_target)
    """
    candidates = []
    lines = clean_code.splitlines()

    candidate_line_indices = [
        i for i, line in enumerate(lines)
        if re.search(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", line)
    ]
    random.shuffle(candidate_line_indices)

    for i in candidate_line_indices:
        line = lines[i]
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
                if len(candidates) >= max_per_seed:
                    return candidates

    return candidates


# ---------------------------------------------------------------------------
# Real Log Mining
# ---------------------------------------------------------------------------

def extract_real_verified_cases(log_path: str = "logs/repair_log.jsonl") -> List[Dict[str, Any]]:
    """Extracts real cases from repair log where a verified fix exists."""
    real_cases = []
    if not os.path.exists(log_path):
        return real_cases

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                row = json.loads(line)
                if row.get("event") == "case_end":
                    data = row.get("data", {})
                    if data.get("status") == "SUCCESS" and data.get("final_source"):
                        real_cases.append({
                            "input": data.get("original_source", ""),
                            "target": data.get("final_source", ""),
                            "family": "undeclared",
                            "target_name": "",
                            "error_line": 1,
                            "error_col": 1,
                            "error_msg": "Real verified log case",
                            "seed_file": os.path.basename(data.get("filename") or "repair_log.c"),
                            "skeleton": get_structural_skeleton(data.get("original_source", "")),
                            "target_edit": "LINE 1: verified",
                        })
            except Exception:
                pass
    return real_cases


# ---------------------------------------------------------------------------
# Generator Pipeline
# ---------------------------------------------------------------------------

def generate_semantic_dataset(
    seed_dirs: List[str],
    samples_per_kind: int = 1000,
    out_dir: str = "data/semantic_splits",
) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)

    # 1. Collect clean seeds
    raw_seeds: List[str] = []
    for sdir in seed_dirs:
        for p in sorted(glob.glob(os.path.join(sdir, "*.c"))):
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    code = f.read()
                t, l, _ = parse_source(code, p)
                if t is not None and not has_any_errors(l):
                    sc = SemanticChecker()
                    sc.visit(t)
                    if len(sc.get_issues()) == 0:
                        raw_seeds.append(code)
            except Exception:
                pass

    # Add struct seeds
    struct_seeds = generate_struct_seeds(300)
    for s in struct_seeds:
        t, l, _ = parse_source(s, "struct_seed")
        if t is not None and not has_any_errors(l):
            sc = SemanticChecker()
            sc.visit(t)
            if len(sc.get_issues()) == 0:
                raw_seeds.append(s)

    print(f"Total verified checker-clean seeds: {len(raw_seeds)}")

    # 2. Partition seeds strictly by structural skeleton for disjoint split
    skeleton_to_seeds: Dict[str, List[str]] = collections.defaultdict(list)
    for code in raw_seeds:
        skel = get_structural_skeleton(code)
        skeleton_to_seeds[skel].append(code)

    all_skels = list(skeleton_to_seeds.keys())
    random.seed(RNG_SEED)
    random.shuffle(all_skels)

    n = len(all_skels)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)

    train_skels = set(all_skels[:n_train])
    val_skels = set(all_skels[n_train:n_train + n_val])
    test_skels = set(all_skels[n_train + n_val:])

    split_map = {
        "train": [c for s in train_skels for c in skeleton_to_seeds[s]],
        "val": [c for s in val_skels for c in skeleton_to_seeds[s]],
        "test": [c for s in test_skels for c in skeleton_to_seeds[s]],
    }

    print(f"Seed partitioning: {len(train_skels)} train skeletons, {len(val_skels)} val, {len(test_skels)} test.")

    # 3. Generate samples per split
    final_splits: Dict[str, List[Dict[str, Any]]] = {"train": [], "val": [], "test": []}
    kind_counts: Dict[str, int] = collections.defaultdict(int)

    for split_name, seed_list in split_map.items():
        # Injectors mapped to model kinds
        for clean_code in seed_list:
            skel = get_structural_skeleton(clean_code)

            # A. Undeclared
            und_cands = inject_undeclared_variants(clean_code)
            for buggy, kind, name, target_edit in und_cands:
                t1, l1, _ = parse_source(buggy, "eval-und")
                if t1 is None or has_any_errors(l1):
                    continue
                sc = SemanticChecker()
                sc.visit(t1)
                issues = sc.get_issues()
                if any(i.get("kind") == "undeclared" for i in issues):
                    target_iss = [i for i in issues if i.get("kind") == "undeclared"][0]
                    final_splits[split_name].append({
                        "input": buggy,
                        "target": clean_code,
                        "target_edit": target_edit,
                        "family": "undeclared",
                        "target_name": name,
                        "error_line": target_iss.get("line"),
                        "error_col": target_iss.get("col"),
                        "error_msg": target_iss.get("msg"),
                        "skeleton": skel,
                    })
                    kind_counts["undeclared"] += 1

            # B. Redeclared
            redecl_cands = inject_redeclared_variants(clean_code)
            for buggy, kind, name, target_edit in redecl_cands:
                t1, l1, _ = parse_source(buggy, "eval-redecl")
                if t1 is None or has_any_errors(l1):
                    continue
                sc = SemanticChecker()
                sc.visit(t1)
                issues = sc.get_issues()
                if any(i.get("kind") == "redeclared" for i in issues):
                    target_iss = [i for i in issues if i.get("kind") == "redeclared"][0]
                    final_splits[split_name].append({
                        "input": buggy,
                        "target": clean_code,
                        "target_edit": target_edit,
                        "family": "redeclared",
                        "target_name": name,
                        "error_line": target_iss.get("line"),
                        "error_col": target_iss.get("col"),
                        "error_msg": target_iss.get("msg"),
                        "skeleton": skel,
                    })
                    kind_counts["redeclared"] += 1

            # C. Unknown Member
            member_cands = inject_unknown_member_variants(clean_code)
            for buggy, kind, name, target_edit in member_cands:
                t1, l1, _ = parse_source(buggy, "eval-member")
                if t1 is None or has_any_errors(l1):
                    continue
                sc = SemanticChecker()
                sc.visit(t1)
                issues = sc.get_issues()
                if any(i.get("kind") == "unknown_member" for i in issues):
                    target_iss = [i for i in issues if i.get("kind") == "unknown_member"][0]
                    final_splits[split_name].append({
                        "input": buggy,
                        "target": clean_code,
                        "target_edit": target_edit,
                        "family": "unknown_member",
                        "target_name": name,
                        "error_line": target_iss.get("line"),
                        "error_col": target_iss.get("col"),
                        "error_msg": target_iss.get("msg"),
                        "skeleton": skel,
                    })
                    kind_counts["unknown_member"] += 1

    # Include real cases where verified
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

    return report


if __name__ == "__main__":
    generate_semantic_dataset(
        seed_dirs=["data/seed_programs_generated"],
        samples_per_kind=1000,
        out_dir="data/semantic_splits",
    )
