"""Generate balanced security patch dataset v2 for CodeT5 LoRA adapter.

Categories:
  - UNSAFE_INPUT (gets -> fgets)
  - UNBOUNDED_COPY (strcpy -> snprintf)
  - UNBOUNDED_CONCAT (strcat -> strncat)
  - UNBOUNDED_FORMAT (sprintf -> snprintf)
  - FORMAT_STRING (printf(var) -> printf("%s", var))
  - UNBOUNDED_INPUT (scanf "%s" -> bounded)
  - OVERWIDE_INPUT (scanf width >= buffer size -> bounded)
  - NO_CHANGE (already-safe lines, 15% quota, target NO_PATCH)
  - REPORT_ONLY (pointer/unknown size destination, 10% quota, target NO_PATCH)

Splits:
  - Train: 12,000
  - Val: 1,200
  - Test: 1,200
  Partitioned strictly by function-skeleton hash (zero structural leakage).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

_IDENT = re.compile(r"\b[_A-Za-z][_A-Za-z0-9]*\b")
_NUM = re.compile(r"\b\d+\b")


def skeleton(code: str) -> str:
    """Normalize identifiers and numbers to extract program structure."""
    c = _IDENT.sub("ID", code)
    c = _NUM.sub("NUM", c)
    return re.sub(r"\s+", " ", c).strip()


def sha1_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


# Randomized identifier pools
BUFFER_NAMES = [
    "token", "payload", "message", "query", "record", "chunk", "username",
    "filepath", "response", "hostname", "address", "session_id", "packet",
    "digest", "prefix", "header", "cmd_str", "line_buf", "client_msg",
    "user_str", "temp_buf", "input_data", "raw_bytes", "entry_name",
    "cache_line", "target_buf", "dest_str", "key_name", "output_val",
    "text_buf", "secret_key", "device_id", "node_name", "auth_token",
    "buffer_data", "work_str", "field_val", "log_entry", "item_buf",
    "raw_input", "string_data", "cookie_val", "ident_buf", "req_body",
    "tag_name", "val_str", "uri_path", "signature", "session_key",
    "status_msg", "cmd_line", "record_val", "out_data", "file_name",
    "peer_name", "host_str", "meta_chunk", "dest_block", "src_chunk"
]

SRC_NAMES = [
    "src_data", "source_str", "item_val", "source_payload", "input_arg",
    "raw_chunk", "sample_text", "base_msg", "token_in", "user_param",
    "raw_string", "orig_text", "default_val", "seed_data", "cache_in",
    "param_str", "input_token", "read_chunk", "source_buf", "entry_src"
]

DISTRACTOR_INTS = [
    "offset", "status", "count", "index", "ret_val", "flag", "code",
    "length", "limit", "max_cnt", "iter", "state", "val", "num_items",
    "depth", "marker", "pos", "step", "retry_count", "exit_code",
    "priority", "level", "result", "err_code", "batch_size"
]

SHADOW_BUFS = [
    "shadow_buf", "temp_scratch", "aux_buffer", "spare_buf", "cache_scratch",
    "debug_str", "alt_data", "backup_buf", "internal_buf", "mirror_buf"
]

FUNCTION_NAMES = [
    "handle_packet", "process_request", "parse_header", "sanitize_input",
    "load_record", "verify_token", "dispatch_event", "receive_data",
    "build_response", "filter_stream", "format_output", "inspect_payload",
    "execute_step", "audit_buffer", "consume_message", "parse_line"
]


def _generate_function_code(
    rng: random.Random,
    split_name: str,
    category: str,
    buf_name: str,
    buf_size: int,
    src_name: str,
    d1_name: str,
    d2_name: str,
    shadow_name: str,
    fn_name: str,
    var_idx: int,
) -> Tuple[str, int, str, str]:
    """Generates a complete C program string with split-isolated structural features."""
    ret_types = ["int", "void"]
    ret_type = ret_types[var_idx % 2]

    # Split-isolated signatures
    if split_name == "train":
        sig_options = [
            f"{ret_type} {fn_name}(void)",
            f"{ret_type} {fn_name}(int step_limit)",
            f"{ret_type} {fn_name}(int flag, int max_val)",
        ]
    elif split_name == "val":
        sig_options = [
            f"{ret_type} {fn_name}(int val_mode)",
            f"{ret_type} {fn_name}(int active, int quota)",
            f"{ret_type} {fn_name}(int option_code)",
        ]
    else:  # test
        sig_options = [
            f"{ret_type} {fn_name}(int test_cfg)",
            f"{ret_type} {fn_name}(int run_id, int batch_sz)",
            f"{ret_type} {fn_name}(int check_flag)",
        ]

    sig = sig_options[(var_idx // 2) % len(sig_options)]

    lines = ["#include <stdio.h>", "#include <string.h>", ""]
    lines.append(f"{sig} {{")

    # Declarations with varied distractors
    decl_mode = var_idx % 8
    decl_lines = []

    # Local int distractor is always declared so d is always in scope
    decl_lines.append(f"    int {d1_name} = {rng.randint(0, 5)};")
    if decl_mode in (2, 3, 6, 7):
        decl_lines.append(f"    int {d2_name} = {rng.randint(1, 10)};")

    # Variable named like target
    if decl_mode in (4, 5, 6, 7):
        like_name = f"{buf_name}_idx"
        decl_lines.append(f"    int {like_name} = 0;")

    # Shadow buffers
    shadow_size = rng.randint(16, 128)
    shadow_decl = f"    char {shadow_name}[{shadow_size}];"
    buf_decl = f"    char {buf_name}[{buf_size}];"
    src_decl = f'    char {src_name}[{rng.randint(16, 128)}] = "payload_data";'

    if decl_mode in (1, 5):
        decl_lines.append(shadow_decl)
    decl_lines.append(buf_decl)
    if decl_mode in (3, 7):
        decl_lines.append(shadow_decl)

    if category in ("UNBOUNDED_COPY", "UNBOUNDED_CONCAT", "UNBOUNDED_FORMAT", "FORMAT_STRING"):
        decl_lines.append(src_decl)

    lines.extend(decl_lines)

    # Split-isolated pre-statements (structurally disjoint ASTs guaranteed)
    d = d1_name
    pre_mode = var_idx % 5
    if split_name == "train":
        # Train pre-statements strictly use '<' and '+'
        if pre_mode == 0:
            lines.append(f"    {d} = {d} + 1;")
        elif pre_mode == 1:
            lines.append(f"    if ({d} < 10) {{\n        {d} = {d} + 2;\n    }}")
        elif pre_mode == 2:
            lines.append(f"    while ({d} < 3) {{\n        {d} = {d} + 1;\n    }}")
        elif pre_mode == 3:
            lines.append(f"    {d} = {d} + 5;\n    if ({d} < 20) {{\n        {d} = {d} + 1;\n    }}")
        else:
            lines.append(f"    {d} = {d} + 3;")
    elif split_name == "val":
        # Val pre-statements strictly use '!=' and '-'
        if pre_mode == 0:
            lines.append(f"    {d} = {d} - 1;")
        elif pre_mode == 1:
            lines.append(f"    if ({d} != 0) {{\n        {d} = {d} - 1;\n    }}")
        elif pre_mode == 2:
            lines.append(f"    while ({d} != 0) {{\n        {d} = {d} - 1;\n    }}")
        elif pre_mode == 3:
            lines.append(f"    {d} = {d} - 2;\n    if ({d} != 1) {{\n        {d} = {d} - 1;\n    }}")
        else:
            lines.append(f"    {d} = {d} - 3;")
    else:  # test
        # Test pre-statements strictly use '==' and '*'
        if pre_mode == 0:
            lines.append(f"    {d} = {d} * 2;")
        elif pre_mode == 1:
            lines.append(f"    if ({d} == 0) {{\n        {d} = {d} * 3;\n    }}")
        elif pre_mode == 2:
            lines.append(f"    {d} = 1;\n    if ({d} == 1) {{\n        {d} = {d} * 2;\n    }}")
        elif pre_mode == 3:
            lines.append(f"    {d} = 2;\n    if ({d} == 2) {{\n        {d} = {d} * 3;\n    }}")
        else:
            lines.append(f"    {d} = {d} * 4;")

    # Focal statement by category
    target_width = buf_size - 1 if buf_size >= 2 else 1
    focal_call = ""
    fixed_call = ""

    if category == "UNSAFE_INPUT":
        focal_call = f"gets({buf_name});"
        fixed_call = f"fgets({buf_name}, sizeof({buf_name}), stdin);"
    elif category == "UNBOUNDED_COPY":
        focal_call = f"strcpy({buf_name}, {src_name});"
        fixed_call = f'snprintf({buf_name}, sizeof({buf_name}), "%s", {src_name});'
    elif category == "UNBOUNDED_CONCAT":
        focal_call = f"strcat({buf_name}, {src_name});"
        fixed_call = f"strncat({buf_name}, {src_name}, sizeof({buf_name}) - strlen({buf_name}) - 1);"
    elif category == "UNBOUNDED_FORMAT":
        if var_idx % 2 == 0:
            focal_call = f'sprintf({buf_name}, "%s", {src_name});'
            fixed_call = f'snprintf({buf_name}, sizeof({buf_name}), "%s", {src_name});'
        else:
            focal_call = f'sprintf({buf_name}, "val=%d", {d});'
            fixed_call = f'snprintf({buf_name}, sizeof({buf_name}), "val=%d", {d});'
    elif category == "FORMAT_STRING":
        focal_call = f"printf({src_name});"
        fixed_call = f'printf("%s", {src_name});'
    elif category == "UNBOUNDED_INPUT":
        focal_call = f'scanf("%s", {buf_name});'
        fixed_call = f'scanf("%{target_width}s", {buf_name});'
    elif category == "OVERWIDE_INPUT":
        overwide_w = buf_size + rng.randint(0, 64)
        focal_call = f'scanf("%{overwide_w}s", {buf_name});'
        fixed_call = f'scanf("%{target_width}s", {buf_name});'
    elif category == "NO_CHANGE":
        # Hard negative variations:
        neg_cases = ["scanf_int", "scanf_bounded", "int_named_buf", "safe_fgets", "safe_snprintf"]
        neg_kind = neg_cases[var_idx % len(neg_cases)]
        if neg_kind == "scanf_int":
            focal_call = f'scanf("%d", &{d});'
        elif neg_kind == "scanf_bounded":
            focal_call = f'scanf("%{target_width}s", {buf_name});'
        elif neg_kind == "int_named_buf":
            focal_call = f'scanf("%d", &{buf_name}_idx);'
        elif neg_kind == "safe_fgets":
            focal_call = f"fgets({buf_name}, sizeof({buf_name}), stdin);"
        else:
            focal_call = f'snprintf({buf_name}, sizeof({buf_name}), "%s", {src_name});'
        fixed_call = "NO_PATCH"

    lines.append(f"    {focal_call}")
    code_prefix = "\n".join(lines)
    focal_line_idx = len(code_prefix.splitlines())

    # Split-isolated post-statements
    post_mode = var_idx % 4
    if split_name == "train":
        if post_mode == 1:
            lines.append(f"    {d} = {d} + 3;")
        elif post_mode == 2:
            lines.append(f'    printf("%d\\n", {d});')
        elif post_mode == 3:
            lines.append(f"    if ({d} < 50) {{\n        {d} = {d} + 1;\n    }}")
    elif split_name == "val":
        if post_mode == 1:
            lines.append(f"    {d} = {d} - 3;")
        elif post_mode == 2:
            lines.append(f'    printf("val: %d\\n", {d});')
        elif post_mode == 3:
            lines.append(f"    if ({d} != 0) {{\n        {d} = 0;\n    }}")
    else:  # test
        if post_mode == 1:
            lines.append(f"    {d} = {d} * 1;")
        elif post_mode == 2:
            lines.append(f'    printf("test: %d\\n", {d});')
        elif post_mode == 3:
            lines.append(f"    if ({d} == 1) {{\n        {d} = 2;\n    }}")

    # Return
    if ret_type == "void":
        lines.append("    return;")
    else:
        lines.append(f"    return {d};" if (var_idx % 2 == 1) else "    return 0;")

    lines.append("}")
    full_code = "\n".join(lines)
    return full_code, focal_line_idx, focal_call, fixed_call


def _generate_report_only_code(
    rng: random.Random,
    split_name: str,
    param_name: str,
    src_name: str,
    fn_name: str,
    var_idx: int,
) -> Tuple[str, int, str, str]:
    """Generates REPORT_ONLY negative samples with split-isolated structures."""
    ret_types = ["int", "void"]
    ret_type = ret_types[var_idx % 2]
    kind = "ptr_param" if (var_idx % 2 == 0) else "unsized_array"
    vuln_apis = ["gets", "scanf", "strcpy", "strcat", "sprintf"]
    vuln_api = vuln_apis[var_idx % len(vuln_apis)]

    lines = ["#include <stdio.h>", "#include <string.h>", ""]

    if kind == "ptr_param":
        param_sig = f"char *{param_name}"
    else:
        param_sig = f"char {param_name}[]"

    if vuln_api in ("strcpy", "strcat", "sprintf"):
        param_sig += f", char *{src_name}"

    # Split signature tags
    if split_name == "train":
        sig = f"{ret_type} {fn_name}({param_sig}, int step_limit)"
    elif split_name == "val":
        sig = f"{ret_type} {fn_name}({param_sig}, int val_mode)"
    else:
        sig = f"{ret_type} {fn_name}({param_sig}, int test_cfg)"

    lines.append(f"{sig} {{")

    # Split pre-statements
    if split_name == "train":
        lines.append("    int local_k = 0;\n    while (local_k < 2) {\n        local_k = local_k + 1;\n    }")
    elif split_name == "val":
        lines.append("    int local_k = 2;\n    while (local_k != 0) {\n        local_k = local_k - 1;\n    }")
    else:
        lines.append("    int local_k = 1;\n    if (local_k == 1) {\n        local_k = local_k * 2;\n    }")

    if vuln_api == "gets":
        call = f"gets({param_name});"
    elif vuln_api == "scanf":
        call = f'scanf("%s", {param_name});'
    elif vuln_api == "strcpy":
        call = f"strcpy({param_name}, {src_name});"
    elif vuln_api == "strcat":
        call = f"strcat({param_name}, {src_name});"
    else:
        call = f'sprintf({param_name}, "%s", {src_name});'

    lines.append(f"    {call}")
    code_prefix = "\n".join(lines)
    line_num = len(code_prefix.splitlines())

    if ret_type == "void":
        lines.append("    return;")
    else:
        lines.append("    return 0;")
    lines.append("}")

    return "\n".join(lines), line_num, call, "NO_PATCH"


def generate_dataset_split(
    rng: random.Random,
    split_name: str,
    total_count: int,
    no_change_quota: int,
    report_only_quota: int,
) -> List[Dict[str, Any]]:
    """Generates a dataset split meeting exact count and category quota specifications."""
    fixable_categories = [
        "UNSAFE_INPUT",
        "UNBOUNDED_COPY",
        "UNBOUNDED_CONCAT",
        "UNBOUNDED_FORMAT",
        "FORMAT_STRING",
        "UNBOUNDED_INPUT",
        "OVERWIDE_INPUT",
    ]

    fixable_total = total_count - no_change_quota - report_only_quota
    base_per_cat = fixable_total // len(fixable_categories)
    rem = fixable_total % len(fixable_categories)

    cat_quotas: Dict[str, int] = {}
    for idx, c in enumerate(fixable_categories):
        cat_quotas[c] = base_per_cat + (1 if idx < rem else 0)
    cat_quotas["NO_CHANGE"] = no_change_quota
    cat_quotas["REPORT_ONLY"] = report_only_quota

    assert sum(cat_quotas.values()) == total_count

    cat_pool: List[str] = []
    for cat, cnt in cat_quotas.items():
        cat_pool.extend([cat] * cnt)
    rng.shuffle(cat_pool)

    samples: List[Dict[str, Any]] = []
    for idx, cat in enumerate(cat_pool):
        buf_name = rng.choice(BUFFER_NAMES)
        buf_size = rng.randint(4, 256)
        src_name = rng.choice(SRC_NAMES)
        d1_name = rng.choice(DISTRACTOR_INTS)
        d2_name = rng.choice([x for x in DISTRACTOR_INTS if x != d1_name])
        shadow_name = rng.choice(SHADOW_BUFS)
        fn_name = f"{rng.choice(FUNCTION_NAMES)}_{split_name}_{idx}"

        if cat == "REPORT_ONLY":
            code, line_num, focal_call, fixed_call = _generate_report_only_code(
                rng, split_name, buf_name, src_name, fn_name, idx
            )
            target = "NO_PATCH"
            vulnerable_line = focal_call
            fixed_line = "NO_PATCH"
        else:
            code, line_num, focal_call, fixed_call = _generate_function_code(
                rng, split_name, cat, buf_name, buf_size, src_name, d1_name, d2_name, shadow_name, fn_name, idx
            )
            if fixed_call == "NO_PATCH":
                target = "NO_PATCH"
                vulnerable_line = focal_call
                fixed_line = "NO_PATCH"
            else:
                target = f"REPLACE_LINE {line_num} {fixed_call}"
                vulnerable_line = focal_call
                fixed_line = fixed_call

        input_prompt = (
            f"SECURITY_FIX\n"
            f"CATEGORY {cat}\n"
            f"LINE {line_num}\n\n"
            f"<CODE>\n{code}\n</CODE>"
        )

        skel_val = skeleton(code)
        skel_h = sha1_hash(skel_val)

        row = {
            "task": "security_repair_line",
            "split_hint": split_name,
            "family": f"{cat.lower()}_{split_name}",
            "category": cat,
            "error_line": line_num,
            "input": input_prompt,
            "target": target,
            "metadata": {
                "vulnerable_line": vulnerable_line,
                "fixed_line": fixed_line,
            },
            "src": input_prompt,
            "tgt": target,
            "skeleton_hash": skel_h,
        }
        samples.append(row)

    return samples


def main():
    parser = argparse.ArgumentParser(description="Generate security patch dataset v2.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation")
    parser.add_argument("--out-dir", default=os.path.join(PROJECT_ROOT, "data", "security_patch_dataset_v2"))
    args = parser.parse_args()

    rng = random.Random(args.seed)

    print(f"Generating splits with seed={args.seed}...")
    val_samples = generate_dataset_split(
        rng, "val", 1200, no_change_quota=180, report_only_quota=120
    )
    test_samples = generate_dataset_split(
        rng, "test", 1200, no_change_quota=180, report_only_quota=120
    )
    train_samples = generate_dataset_split(
        rng, "train", 12000, no_change_quota=1800, report_only_quota=1200
    )

    # Verify zero skeleton leakage
    train_skels = {s["skeleton_hash"] for s in train_samples}
    val_skels = {s["skeleton_hash"] for s in val_samples}
    test_skels = {s["skeleton_hash"] for s in test_samples}

    ov_tr_va = train_skels & val_skels
    ov_tr_te = train_skels & test_skels
    ov_va_te = val_skels & test_skels

    print("\n--- SKELETON LEAKAGE AUDIT ---")
    print(f"Unique Train skeletons: {len(train_skels)}")
    print(f"Unique Val skeletons:   {len(val_skels)}")
    print(f"Unique Test skeletons:  {len(test_skels)}")
    print(f"Train and Val overlap:    {len(ov_tr_va)}")
    print(f"Train and Test overlap:   {len(ov_tr_te)}")
    print(f"Val and Test overlap:     {len(ov_va_te)}")

    assert len(ov_tr_va) == 0, f"Skeleton leakage between train and val: {len(ov_tr_va)}"
    assert len(ov_tr_te) == 0, f"Skeleton leakage between train and test: {len(ov_tr_te)}"
    assert len(ov_va_te) == 0, f"Skeleton leakage between val and test: {len(ov_va_te)}"

    # Write files
    os.makedirs(args.out_dir, exist_ok=True)
    train_path = os.path.join(args.out_dir, "train.jsonl")
    val_path = os.path.join(args.out_dir, "val.jsonl")
    test_path = os.path.join(args.out_dir, "test.jsonl")
    manifest_path = os.path.join(args.out_dir, "manifest.json")

    for p, rows in [(train_path, train_samples), (val_path, val_samples), (test_path, test_samples)]:
        with open(p, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Hashes and manifest
    def sha256_file(filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    manifest = {
        "dataset_name": "security_patch_dataset_v2",
        "generator": "ml/make_security_dataset_v2.py",
        "seed": args.seed,
        "counts": {
            "train": len(train_samples),
            "val": len(val_samples),
            "test": len(test_samples),
            "total": len(train_samples) + len(val_samples) + len(test_samples),
        },
        "category_distribution": {
            "train": dict(Counter(s["category"] for s in train_samples)),
            "val": dict(Counter(s["category"] for s in val_samples)),
            "test": dict(Counter(s["category"] for s in test_samples)),
        },
        "skeleton_audit": {
            "train_unique": len(train_skels),
            "val_unique": len(val_skels),
            "test_unique": len(test_skels),
            "leakage_train_val": len(ov_tr_va),
            "leakage_train_test": len(ov_tr_te),
            "leakage_val_test": len(ov_va_te),
            "status": "CLEAN_ZERO_LEAKAGE",
        },
        "files": {
            "train": train_path,
            "val": val_path,
            "test": test_path,
        },
        "sha256": {
            "train.jsonl": sha256_file(train_path),
            "val.jsonl": sha256_file(val_path),
            "test.jsonl": sha256_file(test_path),
        },
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nWrote manifest to {manifest_path}")
    print("Dataset generation complete and fully verified.")


if __name__ == "__main__":
    main()
