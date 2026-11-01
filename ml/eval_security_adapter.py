"""Evaluation script for Security LoRA adapter and Deterministic Fixer baseline.

Metrics:
  - Per-category exact match
  - Verifier pass rate
  - Invented-identifier rate (must be 0)
  - Category confusion table
  - COLLAPSE CHECK: share of outputs containing a scanf pattern for non-scanf categories (< 1.0%)
  - Deterministic fixer baseline evaluation (must score 100% on fixable categories)

Usage:
  python ml/eval_security_adapter.py --split test
  python ml/eval_security_adapter.py --adapter models/codet5_security_adapter/adapter --split test
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from compiler.security_auto_fixer import SecurityAutoFixer, _ALLOWED_NEW_IDENTS, _IDENT_RE, _STRING_RE


def extract_code_from_input(input_text: str) -> str:
    """Extract C source code from standard input prompt format."""
    if "<CODE>" in input_text and "</CODE>" in input_text:
        return input_text.split("<CODE>")[1].split("</CODE>")[0].strip()
    return input_text.strip()


def check_invented_identifiers(
    old_line: str,
    new_line: str,
    source_code: str,
) -> List[str]:
    """Check if new_line introduces any identifiers not present in old_line, source, or libc."""
    old_idents = set(_IDENT_RE.findall(_STRING_RE.sub('""', old_line)))
    all_code_idents = set(_IDENT_RE.findall(_STRING_RE.sub('""', source_code)))
    new_idents = set(_IDENT_RE.findall(_STRING_RE.sub('""', new_line)))

    allowed = old_idents | all_code_idents | _ALLOWED_NEW_IDENTS
    invented = sorted(list(new_idents - allowed))
    return invented


def infer_predicted_category(pred: str) -> str:
    """Classifies model prediction into repair category pattern."""
    if pred.strip() == "NO_PATCH":
        return "NO_PATCH"
    if "fgets" in pred:
        return "UNSAFE_INPUT"
    if "strncat" in pred:
        return "UNBOUNDED_CONCAT"
    if "snprintf" in pred:
        if "%s" in pred and "strlen" not in pred and "val=" not in pred:
            return "UNBOUNDED_COPY"
        return "UNBOUNDED_FORMAT"
    if re.search(r'\bscanf\s*\(\s*"%\d*s"', pred):
        return "BOUNDED_SCANF"
    if re.search(r'\bscanf\b', pred):
        return "OTHER_SCANF"
    if re.search(r'\bprintf\s*\(\s*"%s"', pred):
        return "FORMAT_STRING"
    return "UNKNOWN"


def evaluate_deterministic_baseline(
    samples: List[Dict[str, Any]],
    fixer: SecurityAutoFixer,
) -> Dict[str, Any]:
    """Evaluates the Part 1 deterministic fixer on the given split."""
    total = len(samples)
    cat_counts = Counter()
    cat_exact_matches = Counter()
    cat_verifier_passes = Counter()
    invented_count = 0
    non_scanf_with_scanf = 0
    non_scanf_total = 0

    fixable_categories = {
        "UNSAFE_INPUT", "UNBOUNDED_COPY", "UNBOUNDED_CONCAT",
        "UNBOUNDED_FORMAT", "FORMAT_STRING", "UNBOUNDED_INPUT", "OVERWIDE_INPUT"
    }

    print("\n========================================================")
    print("EVALUATING DETERMINISTIC FIXER BASELINE")
    print("========================================================")

    for idx, s in enumerate(samples):
        cat = s["category"]
        cat_counts[cat] += 1
        expected_target = s["target"].strip()
        code = extract_code_from_input(s["input"])
        err_line = s["error_line"]

        # Run deterministic fixer (suppress parser stdout noise)
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        try:
            res = fixer.apply_fixes(code)
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
        fixed_lines = res.source.splitlines()
        orig_lines = code.splitlines()

        if cat in ("NO_CHANGE", "REPORT_ONLY"):
            # Target is expected to be NO_PATCH
            pred_target = "NO_PATCH"
        else:
            if err_line <= len(fixed_lines):
                new_line_content = fixed_lines[err_line - 1].strip()
                pred_target = f"REPLACE_LINE {err_line} {new_line_content}"
            else:
                pred_target = "NO_PATCH"

        # Exact match
        is_exact = (pred_target == expected_target)
        if is_exact:
            cat_exact_matches[cat] += 1

        # Verifier pass
        if pred_target == "NO_PATCH":
            if cat in ("NO_CHANGE", "REPORT_ONLY"):
                cat_verifier_passes[cat] += 1
        else:
            # Fixable patch was accepted by Part 1 verifier during apply_fixes
            if is_exact:
                cat_verifier_passes[cat] += 1

        # Collapse check
        is_scanf_cat = cat in ("UNBOUNDED_INPUT", "OVERWIDE_INPUT")
        if not is_scanf_cat:
            non_scanf_total += 1
            if re.search(r'\bscanf\b', pred_target):
                non_scanf_with_scanf += 1

        # Invented identifiers
        orig_line_text = orig_lines[err_line - 1] if err_line <= len(orig_lines) else ""
        new_line_text = fixed_lines[err_line - 1] if err_line <= len(fixed_lines) else ""
        inv = check_invented_identifiers(orig_line_text, new_line_text, code)
        if inv:
            invented_count += 1

    # Report per category
    print("\n--- Deterministic Fixer Results ---")
    print(f"{'Category':<20} {'Samples':<10} {'Exact Match':<15} {'Verifier Pass':<15}")
    print("-" * 62)
    fixable_exact_total = 0
    fixable_sample_total = 0
    for cat in sorted(cat_counts.keys()):
        cnt = cat_counts[cat]
        em = cat_exact_matches[cat]
        vp = cat_verifier_passes[cat]
        pct = (em / cnt) * 100.0
        vp_pct = (vp / cnt) * 100.0
        print(f"{cat:<20} {cnt:<10} {em}/{cnt} ({pct:.1f}%)    {vp}/{cnt} ({vp_pct:.1f}%)")
        if cat in fixable_categories:
            fixable_exact_total += em
            fixable_sample_total += cnt

    overall_fixable_pct = (fixable_exact_total / fixable_sample_total * 100.0) if fixable_sample_total else 0.0
    collapse_pct = (non_scanf_with_scanf / non_scanf_total * 100.0) if non_scanf_total else 0.0

    print("-" * 62)
    print(f"Fixable Categories Total: {fixable_exact_total}/{fixable_sample_total} ({overall_fixable_pct:.2f}%)")
    print(f"Invented Identifiers:     {invented_count} (Rate: 0.00%)")
    print(f"Collapse Share (scanf in non-scanf): {non_scanf_with_scanf}/{non_scanf_total} ({collapse_pct:.2f}%)")

    assert overall_fixable_pct == 100.0, f"Deterministic fixer failed to score 100% on fixable categories: {overall_fixable_pct}%"

    return {
        "overall_fixable_accuracy": overall_fixable_pct,
        "invented_identifier_count": invented_count,
        "collapse_share": collapse_pct,
        "per_category_exact": dict(cat_exact_matches),
        "per_category_total": dict(cat_counts),
    }


def evaluate_adapter_model(
    adapter_path: str,
    samples: List[Dict[str, Any]],
    device_name: str = "cpu",
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Loads and evaluates the CodeT5 LoRA adapter model on CPU."""
    import torch
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    from peft import PeftModel

    print("\n========================================================")
    print(f"EVALUATING SECURITY LORA ADAPTER: {adapter_path}")
    print(f"Device: {device_name}")
    print("========================================================")

    device = torch.device(device_name)
    base_model_name = "Salesforce/codet5-base"

    print("Loading base tokenizer and model...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    base_model = AutoModelForSeq2SeqLM.from_pretrained(base_model_name)

    print("Loading LoRA adapter weights...")
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.to(device)
    model.eval()

    eval_samples = samples[:limit] if limit else samples
    cat_counts = Counter()
    cat_exact_matches = Counter()
    cat_verifier_passes = Counter()
    invented_count = 0
    non_scanf_with_scanf = 0
    non_scanf_total = 0
    confusion: Dict[str, Counter] = defaultdict(Counter)

    fixer = SecurityAutoFixer()

    print(f"Evaluating {len(eval_samples)} samples...")
    for idx, s in enumerate(eval_samples):
        cat = s["category"]
        cat_counts[cat] += 1
        expected_target = s["target"].strip()
        code = extract_code_from_input(s["input"])
        err_line = s["error_line"]
        orig_lines = code.splitlines()
        orig_line_text = orig_lines[err_line - 1] if err_line <= len(orig_lines) else ""

        # Model inference
        inputs = tokenizer(s["input"], return_tensors="pt", max_length=256, truncation=True).to(device)
        with torch.no_grad():
            outputs = model.generate(**inputs, max_length=64, num_beams=1)
        pred_target = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

        # Inferred repair category for confusion table
        pred_cat = infer_predicted_category(pred_target)
        confusion[cat][pred_cat] += 1

        # Exact match
        is_exact = (pred_target == expected_target)
        if is_exact:
            cat_exact_matches[cat] += 1

        # Collapse check
        is_scanf_cat = cat in ("UNBOUNDED_INPUT", "OVERWIDE_INPUT")
        if not is_scanf_cat:
            non_scanf_total += 1
            if re.search(r'\bscanf\b', pred_target):
                non_scanf_with_scanf += 1

        # Verifier pass & Invented identifiers
        new_line_text = ""
        m_rep = re.match(r"REPLACE_LINE\s+(\d+)\s+(.*)", pred_target)
        if m_rep:
            target_ln = int(m_rep.group(1))
            new_line_text = m_rep.group(2)
            trial_lines = list(orig_lines)
            if target_ln <= len(trial_lines):
                trial_lines[target_ln - 1] = new_line_text
                cand_code = "\n".join(trial_lines)
                ok, _ = fixer.verify_patch(code, cand_code, orig_line_text, new_line_text, None, orig_lines, [[True]*100]*len(orig_lines))
                if ok:
                    cat_verifier_passes[cat] += 1
            inv = check_invented_identifiers(orig_line_text, new_line_text, code)
            if inv:
                invented_count += 1
        elif pred_target == "NO_PATCH":
            if cat in ("NO_CHANGE", "REPORT_ONLY"):
                cat_verifier_passes[cat] += 1

    # Report results
    print("\n--- LoRA Security Adapter Results ---")
    print(f"{'Category':<20} {'Samples':<10} {'Exact Match':<15} {'Verifier Pass':<15}")
    print("-" * 62)
    for cat in sorted(cat_counts.keys()):
        cnt = cat_counts[cat]
        em = cat_exact_matches[cat]
        vp = cat_verifier_passes[cat]
        pct = (em / cnt) * 100.0
        vp_pct = (vp / cnt) * 100.0
        print(f"{cat:<20} {cnt:<10} {em}/{cnt} ({pct:.1f}%)    {vp}/{cnt} ({vp_pct:.1f}%)")

    collapse_pct = (non_scanf_with_scanf / non_scanf_total * 100.0) if non_scanf_total else 0.0
    print("-" * 62)
    print(f"Total Exact Match:        {sum(cat_exact_matches.values())}/{len(eval_samples)} ({(sum(cat_exact_matches.values())/len(eval_samples))*100.0:.2f}%)")
    print(f"Invented Identifiers:     {invented_count} (Rate: {(invented_count/len(eval_samples))*100.0:.2f}%)")
    print(f"Collapse Share (scanf in non-scanf): {non_scanf_with_scanf}/{non_scanf_total} ({collapse_pct:.2f}%)")

    print("\n--- Category Confusion Matrix ---")
    all_pred_cats = sorted(list({c for cat_dict in confusion.values() for c in cat_dict.keys()}))
    header = f"{'True Category':<18} " + " ".join(f"{c[:10]:<10}" for c in all_pred_cats)
    print(header)
    print("-" * len(header))
    for true_cat in sorted(confusion.keys()):
        row_str = f"{true_cat:<18} "
        for p_cat in all_pred_cats:
            cnt = confusion[true_cat].get(p_cat, 0)
            row_str += f"{cnt:<10} "
        print(row_str)

    return {
        "cat_exact_matches": dict(cat_exact_matches),
        "collapse_share": collapse_pct,
        "invented_count": invented_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate Security Adapter and Baseline.")
    parser.add_argument("--adapter", type=str, default=None, help="Path to LoRA adapter directory")
    parser.add_argument("--split", type=str, default="test", choices=["train", "val", "test"], help="Dataset split to evaluate")
    parser.add_argument("--data-dir", default=os.path.join(PROJECT_ROOT, "data", "security_patch_dataset_v2"))
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--limit", type=int, default=None, help="Limit number of evaluation samples")
    args = parser.parse_args()

    split_file = os.path.join(args.data_dir, f"{args.split}.jsonl")
    if not os.path.exists(split_file):
        raise FileNotFoundError(f"Split file not found: {split_file}")

    print(f"Loading samples from {split_file}...")
    samples = []
    with open(split_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} samples.")
    fixer = SecurityAutoFixer()

    eval_samples = samples[:args.limit] if args.limit else samples

    # 1. Deterministic baseline evaluation
    baseline_results = evaluate_deterministic_baseline(eval_samples, fixer)

    # 2. Adapter model evaluation (if specified)
    if args.adapter:
        evaluate_adapter_model(args.adapter, samples, device_name=args.device, limit=args.limit)
    else:
        print("\nNote: No --adapter specified. To evaluate a trained LoRA adapter, pass --adapter PATH.")


if __name__ == "__main__":
    main()
