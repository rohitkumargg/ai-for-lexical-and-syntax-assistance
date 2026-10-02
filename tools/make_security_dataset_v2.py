"""Generate security training data (v2) for the CodeT5 security adapter.

Dataset requirements:
- The prompt contains the enclosing function plus 1-3 unrelated distractor functions,
  with different variable names (arr, a, str, n, ...);
- The vulnerable line sits at varied positions (early, middle, late);
- Buffer names and sizes vary, and the target always uses ONLY the buffer from the
  vulnerable line, with the width/size taken from its declaration;
- Negative samples: pointer parameters and unknown sizes, where the target is NO_FIX;
- Splits are partitioned strictly by program skeleton, preventing leakage across
  train, validation, and test sets.

Usage:
    python tools/make_security_dataset_v2.py --count 2000 --seed 42
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Distractor functions with distinct variable names
# ---------------------------------------------------------------------------
DISTRACTOR_FUNS = [
    "int helper_add(int a, int b) {\n    return a + b;\n}",
    "int helper_sum(int arr[], int n) {\n    int s = 0;\n    int i = 0;\n    while (i < n) {\n        s = s + arr[i];\n        i = i + 1;\n    }\n    return s;\n}",
    "int helper_max(int arr[], int n) {\n    int m = arr[0];\n    int i = 1;\n    while (i < n) {\n        if (arr[i] > m) {\n            m = arr[i];\n        }\n        i = i + 1;\n    }\n    return m;\n}",
    "void helper_print(int x) {\n    printf(\"%d\\n\", x);\n}",
    "int helper_abs(int x) {\n    if (x < 0) {\n        return 0 - x;\n    }\n    return x;\n}",
    "int helper_search(int str[], int n, int val) {\n    int idx = 0;\n    while (idx < n) {\n        if (str[idx] == val) {\n            return idx;\n        }\n        idx = idx + 1;\n    }\n    return -1;\n}",
    "void helper_copy(int dest[], int src[], int count) {\n    int j = 0;\n    while (j < count) {\n        dest[j] = src[j];\n        j = j + 1;\n    }\n}",
]

CHAR_NAMES = [
    "buf", "cmd", "name", "input_str", "line", "data", "msg",
    "path", "text", "str_buf", "dest", "src_buf", "out", "tmp", "record"
]

CHAR_SIZES = [16, 20, 24, 32, 40, 48, 50, 64, 80, 100, 128, 200, 256, 512]

SAFE_PATTERNS = {
    "gets": {
        "unsafe": "    gets({buf});",
        "safe":   "    fgets({buf}, sizeof({buf}), stdin);",
    },
    "scanf": {
        "unsafe": '    scanf("%s", {buf});',
        "safe":   '    scanf("%{width}s", {buf});',
    },
    "strcpy": {
        "unsafe": "    strcpy({buf}, {src});",
        "safe":   '    snprintf({buf}, sizeof({buf}), "%s", {src});',
    },
    "strcat": {
        "unsafe": "    strcat({buf}, {src});",
        "safe":   "    strncat({buf}, {src}, sizeof({buf}) - strlen({buf}) - 1);",
    },
    "sprintf": {
        "unsafe": '    sprintf({buf}, "%s", {src});',
        "safe":   '    snprintf({buf}, sizeof({buf}), "%s", {src});',
    },
    "printf_var": {
        "unsafe": "    printf({buf});",
        "safe":   '    printf("%s", {buf});',
    },
}

_IDENT = re.compile(r"\b[_A-Za-z][_A-Za-z0-9]*\b")
_NUM = re.compile(r"\b\d+\b")


def skeleton(code: str) -> str:
    """Normalize identifiers and numbers to extract program structure."""
    code = _IDENT.sub("ID", code)
    code = _NUM.sub("NUM", code)
    return re.sub(r"\s+", " ", code).strip()


def sha1_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def _make_positive_function(
    rng: random.Random,
    vuln_kind: str,
    buf_name: str,
    buf_size: int,
    src_name: str | None,
    position: str = "middle",
) -> Tuple[str, int, str]:
    """Build positive vulnerable function with varied position."""
    fn_name = f"vuln_{vuln_kind}_{rng.randint(100, 999)}"
    lines = [f"int {fn_name}() {{"]
    lines.append(f"    char {buf_name}[{buf_size}];")

    if src_name and vuln_kind in ("strcpy", "strcat", "sprintf"):
        lines.append(f'    char {src_name}[{rng.choice(CHAR_SIZES)}] = "test";')

    pre_statements = []
    if position in ("middle", "late"):
        pre_statements.append("    int count = 0;")
        if rng.random() < 0.5:
            pre_statements.append("    int status = 1;")
        if rng.random() < 0.4:
            pre_statements.append("    if (count < 5) {\n        count = count + 1;\n    }")

    post_statements = []
    if position in ("early", "middle"):
        post_statements.append("    int exit_code = 0;")
        if rng.random() < 0.4:
            post_statements.append("    while (exit_code < 1) {\n        exit_code = exit_code + 1;\n    }")

    lines.extend(pre_statements)

    width = buf_size - 1 if buf_size >= 2 else 1
    pat = SAFE_PATTERNS[vuln_kind]
    unsafe_call = pat["unsafe"].format(buf=buf_name, src=src_name or "x", width=width)
    safe_call = pat["safe"].format(buf=buf_name, src=src_name or "x", width=width)

    lines.append(unsafe_call)
    unsafe_rel_idx = len(lines)  # 1-indexed

    lines.extend(post_statements)
    lines.append("    return 0;")
    lines.append("}")

    return "\n".join(lines), unsafe_rel_idx, safe_call.strip()


def _make_negative_function(rng: random.Random, neg_type: str) -> Tuple[str, str]:
    """Generate negative samples: pointer parameters or unsized array parameters -> target NO_FIX."""
    vuln_kind = rng.choice(["gets", "scanf", "strcpy", "strcat"])
    fn_name = f"neg_{neg_type}_{rng.randint(100, 999)}"
    lines = []

    if neg_type == "pointer_param":
        param_name = rng.choice(["ptr", "buf", "p_data", "str"])
        if vuln_kind == "gets":
            lines = [
                f"int {fn_name}(char *{param_name}) {{",
                f"    gets({param_name});",
                "    return 0;",
                "}",
            ]
        elif vuln_kind == "scanf":
            lines = [
                f"int {fn_name}(char *{param_name}) {{",
                f'    scanf("%s", {param_name});',
                "    return 0;",
                "}",
            ]
        elif vuln_kind == "strcpy":
            lines = [
                f"int {fn_name}(char *{param_name}, const char *src) {{",
                f"    strcpy({param_name}, src);",
                "    return 0;",
                "}",
            ]
        else:
            lines = [
                f"int {fn_name}(char *{param_name}, const char *src) {{",
                f"    strcat({param_name}, src);",
                "    return 0;",
                "}",
            ]
    else:  # unsized array parameter
        param_name = rng.choice(["buf", "arr", "input_str"])
        if vuln_kind == "gets":
            lines = [
                f"int {fn_name}(char {param_name}[]) {{",
                f"    gets({param_name});",
                "    return 0;",
                "}",
            ]
        elif vuln_kind == "scanf":
            lines = [
                f"int {fn_name}(char {param_name}[]) {{",
                f'    scanf("%s", {param_name});',
                "    return 0;",
                "}",
            ]
        elif vuln_kind == "strcpy":
            lines = [
                f"int {fn_name}(char {param_name}[], const char *src) {{",
                f"    strcpy({param_name}, src);",
                "    return 0;",
                "}",
            ]
        else:
            lines = [
                f"int {fn_name}(char {param_name}[], const char *src) {{",
                f"    strcat({param_name}, src);",
                "    return 0;",
                "}",
            ]

    return "\n".join(lines), vuln_kind


def generate_sample(rng: random.Random, is_negative: bool = False) -> Dict[str, Any]:
    parts = [
        "#include <stdio.h>",
        "#include <string.h>",
        "",
    ]

    # 1 to 3 distractor functions with distinct identifiers
    n_distractors = rng.randint(1, 3)
    chosen_distractors = rng.sample(DISTRACTOR_FUNS, n_distractors)
    for d in chosen_distractors:
        parts.append(d)
        parts.append("")

    if is_negative:
        neg_type = rng.choice(["pointer_param", "unsized_array_param"])
        fn_code, v_kind = _make_negative_function(rng, neg_type)
        parts.append(fn_code)
        full_src = "\n".join(parts)
        return {
            "input": full_src,
            "src": full_src,
            "target": "NO_FIX",
            "tgt": "NO_FIX",
            "category": f"negative_{neg_type}",
            "family": f"{v_kind}_negative",
            "is_negative": True,
        }

    vuln_kind = rng.choice(list(SAFE_PATTERNS.keys()))
    buf_name = rng.choice(CHAR_NAMES)
    buf_size = rng.choice(CHAR_SIZES)
    src_name = rng.choice(["src_data", "source", "input", "temp"]) if vuln_kind in ("strcpy", "strcat", "sprintf") else None
    position = rng.choice(["early", "middle", "late"])

    fn_code, rel_line, safe_line = _make_positive_function(
        rng, vuln_kind, buf_name, buf_size, src_name, position=position
    )

    prefix_code = "\n".join(parts)
    prefix_lines = prefix_code.count("\n")
    abs_line = prefix_lines + rel_line

    parts.append(fn_code)
    full_src = "\n".join(parts)
    target = f"REPLACE_LINE {abs_line} {safe_line}"

    return {
        "input": full_src,
        "src": full_src,
        "target": target,
        "tgt": target,
        "category": vuln_kind,
        "family": vuln_kind,
        "buf_name": buf_name,
        "buf_size": buf_size,
        "is_negative": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--negative-ratio", type=float, default=0.15)
    parser.add_argument("--out-dir", default=os.path.join(PROJECT_ROOT, "data"))
    args = parser.parse_args()

    rng = random.Random(args.seed)
    n_negative = int(args.count * args.negative_ratio)
    n_positive = args.count - n_negative

    all_samples: List[Dict[str, Any]] = []
    for _ in range(n_positive):
        all_samples.append(generate_sample(rng, is_negative=False))
    for _ in range(n_negative):
        all_samples.append(generate_sample(rng, is_negative=True))

    rng.shuffle(all_samples)

    # Group by program skeleton to guarantee zero leakage across splits
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for sample in all_samples:
        skel = skeleton(sample["input"])
        skel_id = sha1_hash(skel)
        sample["skeleton_hash"] = skel_id
        groups[skel_id].append(sample)

    unique_skeletons = list(groups.keys())
    rng.shuffle(unique_skeletons)

    n_skels = len(unique_skeletons)
    n_val = max(1, int(n_skels * 0.10))
    n_test = max(1, int(n_skels * 0.10))

    val_skels = set(unique_skeletons[:n_val])
    test_skels = set(unique_skeletons[n_val : n_val + n_test])
    train_skels = set(unique_skeletons[n_val + n_test :])

    train_samples, val_samples, test_samples = [], [], []
    for skel_id, samples in groups.items():
        if skel_id in val_skels:
            val_samples.extend(samples)
        elif skel_id in test_skels:
            test_samples.extend(samples)
        else:
            train_samples.extend(samples)

    rng.shuffle(train_samples)
    rng.shuffle(val_samples)
    rng.shuffle(test_samples)

    os.makedirs(args.out_dir, exist_ok=True)
    train_path = os.path.join(args.out_dir, "security_train_v2.jsonl")
    val_path = os.path.join(args.out_dir, "security_val_v2.jsonl")
    test_path = os.path.join(args.out_dir, "security_test_v2.jsonl")

    for path, data in [
        (train_path, train_samples),
        (val_path, val_samples),
        (test_path, test_samples),
    ]:
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Total samples: {len(all_samples)} (Unique skeletons: {n_skels})")
    print(f"Train split: {len(train_samples)} samples ({len(train_skels)} skeletons) -> {train_path}")
    print(f"Val split:   {len(val_samples)} samples ({len(val_skels)} skeletons) -> {val_path}")
    print(f"Test split:  {len(test_samples)} samples ({len(test_skels)} skeletons) -> {test_path}")

    # Family breakdown
    fam_counts = defaultdict(int)
    for s in all_samples:
        fam_counts[s["family"]] += 1
    print("\nFamily breakdown:")
    for f, c in sorted(fam_counts.items()):
        print(f"  {f:25s}: {c}")


if __name__ == "__main__":
    main()
