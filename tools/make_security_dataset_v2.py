"""Generate security training data (v2) for the CodeT5 security adapter.

Changes over v1:
  - Multi-function seeds with distractor declarations (so the model
    learns to localise the unsafe call, not just copy the first array).
  - Buffer sizes vary per sample (no single memorised width like %11s).
  - Targets use sizeof() / correct widths from the declared buffer.
  - Negative examples (already-safe code) included so the model learns
    to output NO_CHANGE.
  - Output format: REPLACE_LINE <n> <replacement>

Usage:
    python tools/make_security_dataset_v2.py \\
        --out data/security_train_v2.jsonl \\
        --count 2000 \\
        --seed 42
"""

import argparse
import json
import os
import random
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Template components
# ---------------------------------------------------------------------------
DISTRACTOR_FUNS = [
    "int helper_add(int a, int b) {{ return a + b; }}",
    "int helper_sum(int arr[], int n) {{ int s = 0; int i = 0; while (i < n) {{ s = s + arr[i]; i = i + 1; }} return s; }}",
    "int helper_max(int arr[], int n) {{ int m = arr[0]; int i = 1; while (i < n) {{ if (arr[i] > m) {{ m = arr[i]; }} i = i + 1; }} return m; }}",
    "void helper_print(int x) {{ printf(\"%d\\n\", x); }}",
    "int helper_abs(int x) {{ if (x < 0) {{ return 0 - x; }} return x; }}",
]

CHAR_NAMES = ["buf", "cmd", "name", "input_str", "line", "data", "msg",
              "path", "text", "str_buf", "dest", "src_buf", "out", "tmp"]
CHAR_SIZES = [8, 10, 16, 20, 25, 32, 40, 50, 64, 80, 100, 128, 200, 256]

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


def _make_function(rng, vuln_kind, buf_name, buf_size, src_name=None):
    """Return (func_src, unsafe_line_idx_relative, target_line)."""
    fn_name = f"vuln_{vuln_kind}_{rng.randint(1, 999)}"
    lines = [f"int {fn_name}() {{"]
    lines.append(f"    char {buf_name}[{buf_size}];")

    extra_vars = rng.randint(0, 2)
    for _ in range(extra_vars):
        vn = rng.choice(["x", "y", "z", "n", "count"])
        lines.append(f"    int {vn} = {rng.randint(0, 100)};")

    if src_name and vuln_kind in ("strcpy", "strcat", "sprintf"):
        lines.append(f'    char {src_name}[{rng.choice(CHAR_SIZES)}] = "test";')

    pat = SAFE_PATTERNS[vuln_kind]
    width = buf_size - 1 if buf_size >= 2 else 1
    unsafe_line = pat["unsafe"].format(buf=buf_name, src=src_name or "x", width=width)
    safe_line = pat["safe"].format(buf=buf_name, src=src_name or "x", width=width)

    lines.append(unsafe_line)
    unsafe_rel = len(lines)  # 1-indexed

    if rng.random() < 0.3:
        lines.append(f"    int result = {rng.randint(0, 10)};")

    lines.append("    return 0;")
    lines.append("}")
    return "\n".join(lines), unsafe_rel, safe_line.strip()


def _make_sample(rng, include_distractor=True):
    vuln_kind = rng.choice(list(SAFE_PATTERNS.keys()))
    buf_name = rng.choice(CHAR_NAMES)
    buf_size = rng.choice(CHAR_SIZES)
    src_name = rng.choice(["src", "input", "msg", "data"]) if vuln_kind in ("strcpy", "strcat", "sprintf") else None

    fn_src, rel_line, safe_line = _make_function(rng, vuln_kind, buf_name, buf_size, src_name)

    parts = []
    # Includes
    parts.append("#include <stdio.h>")
    parts.append("#include <string.h>")
    parts.append("")

    # Distractor functions
    if include_distractor:
        n_distractors = rng.randint(1, 3)
        for d in rng.sample(DISTRACTOR_FUNS, min(n_distractors, len(DISTRACTOR_FUNS))):
            parts.append(d)
            parts.append("")

    parts.append(fn_src)

    full_src = "\n".join(parts)
    # Compute absolute line number of the unsafe line
    prefix_lines = "\n".join(parts[:-1]).count("\n") + 1
    abs_line = prefix_lines + rel_line

    target = f"REPLACE_LINE {abs_line} {safe_line}"

    return {
        "input": full_src,
        "target": target,
        "category": vuln_kind,
        "buf_name": buf_name,
        "buf_size": buf_size,
    }


def _make_negative_sample(rng):
    """Already-safe code -> model should output NO_CHANGE."""
    vuln_kind = rng.choice(list(SAFE_PATTERNS.keys()))
    buf_name = rng.choice(CHAR_NAMES)
    buf_size = rng.choice(CHAR_SIZES)
    src_name = rng.choice(["src", "input"]) if vuln_kind in ("strcpy", "strcat", "sprintf") else None

    pat = SAFE_PATTERNS[vuln_kind]
    width = buf_size - 1 if buf_size >= 2 else 1
    safe_line = pat["safe"].format(buf=buf_name, src=src_name or "x", width=width)

    fn_name = f"safe_{vuln_kind}_{rng.randint(1, 999)}"
    lines = [f"int {fn_name}() {{"]
    lines.append(f"    char {buf_name}[{buf_size}];")
    if src_name:
        lines.append(f'    char {src_name}[32] = "test";')
    lines.append(f"    {safe_line.strip()}")
    lines.append("    return 0;")
    lines.append("}")

    return {
        "input": "#include <stdio.h>\n#include <string.h>\n\n" + "\n".join(lines),
        "target": "NO_CHANGE",
        "category": f"{vuln_kind}_negative",
        "buf_name": buf_name,
        "buf_size": buf_size,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(PROJECT_ROOT, "data", "security_train_v2.jsonl"))
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--negative-ratio", type=float, default=0.15,
                        help="Fraction of negative (already-safe) examples")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    n_negative = int(args.count * args.negative_ratio)
    n_positive = args.count - n_negative

    samples = []
    for _ in range(n_positive):
        samples.append(_make_sample(rng, include_distractor=rng.random() < 0.7))
    for _ in range(n_negative):
        samples.append(_make_negative_sample(rng))

    rng.shuffle(samples)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    # Stats
    cats = {}
    for s in samples:
        cats[s["category"]] = cats.get(s["category"], 0) + 1

    print(f"Generated {len(samples)} samples -> {args.out}")
    print("Category breakdown:")
    for k, v in sorted(cats.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
