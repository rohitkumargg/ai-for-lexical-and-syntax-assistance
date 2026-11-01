"""
tools/evaluate_p6_generalization.py

Runs generalization evaluation for P6 Agent Manipulation Detector:
1. Evaluates on train vs held-out families across 7 carriers and transforms.
2. Evaluates on negative corpus (benign developer comments, C headers, clean code).
3. Produces reports/p6/evaluation.json, reports/p6/per_family_table.md,
   reports/p6/sampled_misses.json, reports/p6/sampled_false_positives.json,
   and reports/p6/README.md.
"""

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from compiler.agent_manipulation.detector import AgentManipulationDetector
from tests.fixtures.agent_manipulation_dataset import get_dataset, TRAIN_FAMILIES, HELDOUT_FAMILIES

REPORTS_DIR = REPO_ROOT / "reports" / "p6"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def evaluate():
    detector = AgentManipulationDetector()
    pos_samples, neg_samples = get_dataset()

    print(f"Loaded {len(pos_samples)} positive samples and {len(neg_samples)} negative samples.")

    family_stats = {}
    for f in TRAIN_FAMILIES + HELDOUT_FAMILIES:
        family_stats[f] = {
            "split": "heldout" if f in HELDOUT_FAMILIES else "train",
            "total": 0,
            "detected": 0,
            "missed": 0,
        }

    misses = []
    fps = []

    # Evaluate Positives
    tp = 0
    fn = 0
    for s in pos_samples:
        fam = s["family"]
        family_stats[fam]["total"] += 1

        result = detector.analyze(s["code"], language=s.get("language", "c"))
        is_detected = result.has_manipulation

        if is_detected:
            tp += 1
            family_stats[fam]["detected"] += 1
        else:
            fn += 1
            family_stats[fam]["missed"] += 1
            misses.append({
                "family": fam,
                "split": s["split"],
                "carrier": s.get("carrier"),
                "transform": s.get("transform"),
                "text": s["text"],
                "max_score": max([f.confidence for f in result.findings], default=0.0),
                "reasons": [f.manipulation_reason for f in result.findings],
            })

    # Evaluate Negatives
    tn = 0
    fp = 0
    for s in neg_samples:
        result = detector.analyze(s["code"], language=s.get("language", "c"))
        is_detected = result.has_manipulation

        if is_detected:
            fp += 1
            fps.append({
                "source": s.get("source"),
                "text": s["text"],
                "max_score": max([f.confidence for f in result.findings], default=0.0),
                "reasons": [f.manipulation_reason for f in result.findings],
            })
        else:
            tn += 1

    total_samples = len(pos_samples) + len(neg_samples)
    accuracy = (tp + tn) / total_samples if total_samples else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    # Calculate per-family recall
    for f, st in family_stats.items():
        st["recall"] = round(st["detected"] / st["total"], 4) if st["total"] else 0.0

    eval_data = {
        "summary": {
            "total_samples": total_samples,
            "positives": len(pos_samples),
            "negatives": len(neg_samples),
            "tp": tp,
            "fn": fn,
            "tn": tn,
            "fp": fp,
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
        "family_stats": family_stats,
    }

    # Write evaluation.json
    with open(REPORTS_DIR / "evaluation.json", "w", encoding="utf-8") as f:
        json.dump(eval_data, f, indent=2)

    # Write sampled_misses.json (up to 30)
    with open(REPORTS_DIR / "sampled_misses.json", "w", encoding="utf-8") as f:
        json.dump(misses[:30], f, indent=2)

    # Write sampled_false_positives.json (up to 30)
    with open(REPORTS_DIR / "sampled_false_positives.json", "w", encoding="utf-8") as f:
        json.dump(fps[:30], f, indent=2)

    # Write per_family_table.md
    md_table = [
        "# Agent Manipulation Detection: Per-Family Generalization Matrix",
        "",
        "| Family | Split | Total | Detected | Missed | Recall |",
        "|---|---|---|---|---|---|",
    ]
    for fam, st in sorted(family_stats.items(), key=lambda x: (x[1]["split"], x[0])):
        md_table.append(f"| `{fam}` | {st['split'].upper()} | {st['total']} | {st['detected']} | {st['missed']} | {st['recall']*100:.1f}% |")

    with open(REPORTS_DIR / "per_family_table.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_table) + "\n")

    # Write README.md with Epistemological Limitations
    readme_content = f"""# P6: Agent-Manipulation Detection Generalization Report

## Evaluation Summary
- **Total Test Cases**: {total_samples} ({len(pos_samples)} positives, {len(neg_samples)} negatives)
- **Precision**: {precision*100:.2f}%
- **Recall**: {recall*100:.2f}%
- **F1 Score**: {f1*100:.2f}%
- **Accuracy**: {accuracy*100:.2f}%
- **False Positives**: {fp} (out of {len(neg_samples)} benign cases)
- **False Negatives**: {fn} (out of {len(pos_samples)} adversarial cases)

## Breakdown by Template Family
See [`per_family_table.md`](per_family_table.md) for individual family metrics across the 5 training families and 3 held-out families.

## Epistemological Limitations of Generalization Measurement
Static testing against a fixed evaluation distribution can prove the presence of generalized pattern recognition within the evaluated manifold, but it fundamentally cannot prove universal robustness against out-of-distribution adversarial attacks. Because natural language and programming syntax form an open-ended semantic space, an attacker with white-box or gray-box knowledge of the detector can synthesize novel steganographic encodings, semantic circumlocutions, or multi-turn prompt injections that decouple the lexical markers ($A, I, T$) while retaining pragmatic intent. Consequently, while our multi-layer architecture (L1 structural co-occurrence, L2 isolated local LLM classification, and L3 behavioral cross-checking with AI prompt masking) raises the attacker's required work factor substantially above naive regex matching, empirical generalization metrics should be understood as empirical lower bounds under defined carrier transformations rather than mathematical guarantees of safety.
"""
    with open(REPORTS_DIR / "README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("\n================ P6 EVALUATION SUMMARY ================")
    print(f"Total: {total_samples} | TP: {tp} | FN: {fn} | TN: {tn} | FP: {fp}")
    print(f"Accuracy:  {accuracy*100:.2f}%")
    print(f"Precision: {precision*100:.2f}%")
    print(f"Recall:    {recall*100:.2f}%")
    print(f"F1 Score:  {f1*100:.2f}%")
    print(f"Outputs written to {REPORTS_DIR}")


if __name__ == "__main__":
    evaluate()
