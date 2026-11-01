"""Tests for Security Patch Dataset V2 generation, balance, verification, and splits.

NOTE: Do NOT import torch in this test file (per task requirements).
"""
import json
import os
import random
import re
from collections import Counter
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "data" / "security_patch_dataset_v2"


def test_generator_deterministic():
    """Verify that the generator is completely deterministic for a fixed seed."""
    from ml.make_security_dataset_v2 import generate_dataset_split

    rng1 = random.Random(1337)
    rng2 = random.Random(1337)

    samples1 = generate_dataset_split(rng1, "val", 100, no_change_quota=15, report_only_quota=10)
    samples2 = generate_dataset_split(rng2, "val", 100, no_change_quota=15, report_only_quota=10)

    assert len(samples1) == len(samples2) == 100
    for s1, s2 in zip(samples1, samples2):
        assert s1["input"] == s2["input"]
        assert s1["target"] == s2["target"]
        assert s1["category"] == s2["category"]
        assert s1["error_line"] == s2["error_line"]
        assert s1["skeleton_hash"] == s2["skeleton_hash"]


def test_split_sizes():
    """Verify exact sample counts: 12,000 train, 1,200 validation, 1,200 test."""
    train_file = DATASET_DIR / "train.jsonl"
    val_file = DATASET_DIR / "val.jsonl"
    test_file = DATASET_DIR / "test.jsonl"

    assert train_file.exists(), f"Missing {train_file}"
    assert val_file.exists(), f"Missing {val_file}"
    assert test_file.exists(), f"Missing {test_file}"

    with open(train_file, "r", encoding="utf-8") as f:
        train_count = sum(1 for line in f if line.strip())
    with open(val_file, "r", encoding="utf-8") as f:
        val_count = sum(1 for line in f if line.strip())
    with open(test_file, "r", encoding="utf-8") as f:
        test_count = sum(1 for line in f if line.strip())

    assert train_count == 12000, f"Expected 12000 train samples, got {train_count}"
    assert val_count == 1200, f"Expected 1200 val samples, got {val_count}"
    assert test_count == 1200, f"Expected 1200 test samples, got {test_count}"


def test_schema_matches_v1():
    """Verify schema matches v1 record format and target conventions."""
    required_keys = {"task", "split_hint", "family", "category", "error_line", "input", "target", "metadata"}
    patch_pattern = re.compile(r"^REPLACE_LINE\s+\d+\s+.+$")

    for split_name in ("train", "val", "test"):
        split_path = DATASET_DIR / f"{split_name}.jsonl"
        with open(split_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                row = json.loads(line)
                assert required_keys.issubset(row.keys()), f"Row {idx} in {split_name} missing keys: {required_keys - set(row.keys())}"
                assert row["task"] == "security_repair_line"
                assert row["split_hint"] == split_name
                assert isinstance(row["error_line"], int)
                assert isinstance(row["input"], str) and "SECURITY_FIX" in row["input"]
                assert "vulnerable_line" in row["metadata"]
                assert "fixed_line" in row["metadata"]

                target = row["target"]
                if row["category"] in ("NO_CHANGE", "REPORT_ONLY"):
                    assert target == "NO_PATCH", f"Expected NO_PATCH for category {row['category']}, got: {target}"
                else:
                    assert patch_pattern.match(target), f"Invalid patch format in {split_name} row {idx}: {target}"


def test_categories_balanced():
    """Verify categories are balanced according to specification: NO_CHANGE 15%, REPORT_ONLY 10%, fixable balanced."""
    fixable_categories = [
        "UNSAFE_INPUT", "UNBOUNDED_COPY", "UNBOUNDED_CONCAT",
        "UNBOUNDED_FORMAT", "FORMAT_STRING", "UNBOUNDED_INPUT", "OVERWIDE_INPUT"
    ]

    for split_name, total, exp_no_change, exp_report_only in [
        ("train", 12000, 1800, 1200),
        ("val", 1200, 180, 120),
        ("test", 1200, 180, 120),
    ]:
        split_path = DATASET_DIR / f"{split_name}.jsonl"
        with open(split_path, "r", encoding="utf-8") as f:
            categories = [json.loads(l)["category"] for l in f if l.strip()]

        counts = Counter(categories)
        assert len(categories) == total
        assert counts["NO_CHANGE"] == exp_no_change, f"NO_CHANGE count mismatch in {split_name}: {counts['NO_CHANGE']} != {exp_no_change}"
        assert counts["REPORT_ONLY"] == exp_report_only, f"REPORT_ONLY count mismatch in {split_name}: {counts['REPORT_ONLY']} != {exp_report_only}"

        fixable_counts = [counts[c] for c in fixable_categories]
        max_c, min_c = max(fixable_counts), min(fixable_counts)
        # Fixable categories must be balanced (equal counts within 2 samples due to integer division)
        assert max_c - min_c <= 2, f"Fixable categories unbalanced in {split_name}: max={max_c}, min={min_c}, counts={counts}"


def test_no_skeleton_leakage():
    """Verify that no function-skeleton appears in more than one split (zero leakage)."""
    def load_skeletons(path: Path):
        skels = set()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                skels.add(row["skeleton_hash"])
        return skels

    train_skels = load_skeletons(DATASET_DIR / "train.jsonl")
    val_skels = load_skeletons(DATASET_DIR / "val.jsonl")
    test_skels = load_skeletons(DATASET_DIR / "test.jsonl")

    assert len(train_skels & val_skels) == 0, f"Leakage detected between train and val: {len(train_skels & val_skels)}"
    assert len(train_skels & test_skels) == 0, f"Leakage detected between train and test: {len(train_skels & test_skels)}"
    assert len(val_skels & test_skels) == 0, f"Leakage detected between val and test: {len(val_skels & test_skels)}"


def test_samples_pass_verifier():
    """Verify that samples across all categories pass the Part 1 accept-only-if-safer verifier."""
    from compiler.security_auto_fixer import SecurityAutoFixer
    from test_parser import parse_source, has_any_errors

    fixer = SecurityAutoFixer()
    test_path = DATASET_DIR / "test.jsonl"

    # Select representative samples per category
    samples_by_cat = {}
    with open(test_path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            cat = row["category"]
            samples_by_cat.setdefault(cat, []).append(row)

    for cat, cat_samples in samples_by_cat.items():
        for s in cat_samples[:5]:  # test first 5 samples per category
            input_text = s["input"]
            code = input_text.split("<CODE>")[1].split("</CODE>")[0].strip()
            target = s["target"].strip()
            orig_lines = code.splitlines()

            if target == "NO_PATCH":
                # Verify code parses cleanly and has no syntax errors
                tree, errs, _ = parse_source(code, "test-verifier-check")
                assert tree is not None and not has_any_errors(errs)
            else:
                m = re.match(r"REPLACE_LINE\s+(\d+)\s+(.+)", target)
                assert m is not None, f"Malformed target: {target}"
                line_idx = int(m.group(1)) - 1
                new_line_text = m.group(2)

                trial_lines = list(orig_lines)
                old_line_text = trial_lines[line_idx]
                trial_lines[line_idx] = new_line_text
                cand_code = "\n".join(trial_lines)

                ok, reason = fixer.verify_patch(
                    code,
                    cand_code,
                    old_line_text,
                    new_line_text,
                    None,
                    orig_lines,
                    [[True] * 120] * len(orig_lines),
                )
                assert ok is True, f"Verifier rejected patch for category {cat}: {reason}"
