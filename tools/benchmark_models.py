# tools/benchmark_models.py
"""
Local Model Benchmark Harness
Evaluates Deterministic Rules vs. CodeT5+LoRA vs. Qwen2.5-Coder (Ollama)
on C/SimpleC compiler repair tasks to determine category routing.
"""
from __future__ import annotations

import os
import sys
import time
import json
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from compiler.finding import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)
from compiler.local_models import (
    EscalationTier,
    CodeT5Manager,
    OllamaClient,
    LocalModelPipeline,
)


BENCHMARK_CASES = [
    {
        "id": "SYN-01-SEMICOLON",
        "category": FindingCategory.SYNTAX,
        "name": "Missing Semicolon",
        "code": """int main() {
    int x = 42
    return x;
}
""",
        "error_line": 2,
        "error_col": 14,
        "reason": "missing_semicolon",
        "explanation": "missing ';' at 'return'",
        "evidence": "    int x = 42",
    },
    {
        "id": "SYN-02-PARAM-COMMA",
        "category": FindingCategory.SYNTAX,
        "name": "Missing Comma in Params",
        "code": """int add(int a int b) {
    return a + b;
}
int main() {
    return add(1, 2);
}
""",
        "error_line": 1,
        "error_col": 15,
        "reason": "missing_comma_params",
        "explanation": "missing ',' in parameter list",
        "evidence": "int add(int a int b) {",
    },
    {
        "id": "SYN-03-PAREN-BRACKET",
        "category": FindingCategory.SYNTAX,
        "name": "Bracket/Paren Mismatch",
        "code": """int main() {
    int arr[10);
    return 0;
}
""",
        "error_line": 2,
        "error_col": 15,
        "reason": "mismatch_lparen_to_lbrack",
        "explanation": "mismatched input ')' expecting ']'",
        "evidence": "    int arr[10);",
    },
    {
        "id": "SEC-01-GETS-BUFFER",
        "category": FindingCategory.SECURITY,
        "name": "Insecure gets() Call",
        "code": """#include <stdio.h>
int main() {
    char buf[32];
    gets(buf);
    return 0;
}
""",
        "error_line": 4,
        "error_col": 4,
        "reason": "unsafe_banned_function",
        "explanation": "Banned insecure function 'gets' called",
        "evidence": "    gets(buf);",
    },
    {
        "id": "SEM-01-UNDECLARED",
        "category": FindingCategory.SEMANTIC,
        "name": "Undeclared Variable",
        "code": """int main() {
    val = 100;
    return val;
}
""",
        "error_line": 2,
        "error_col": 4,
        "reason": "undeclared",
        "explanation": "Use of undeclared identifier 'val'",
        "evidence": "    val = 100;",
    },
]


def run_benchmark(output_json: Optional[str] = None) -> Dict[str, Any]:
    pipeline = LocalModelPipeline()
    status = pipeline.get_system_status()

    print("=" * 72)
    print("LOCAL MODEL BENCHMARK HARNESS (RTX 4050 6GB / System RAM)")
    print("=" * 72)
    print(f"CodeT5 Available : {status['codet5']['available']}")
    print(f"Ollama Available : {status['ollama']['running']} ({status['ollama']['endpoint']})")
    print(f"Configured Model : {status['ollama']['configured_model']}")
    print(f"Device / PyTorch : {status['vram_info']['device']} (CUDA={status['vram_info']['cuda_available']})")
    print("=" * 72)

    results = []

    for tc in BENCHMARK_CASES:
        fnd = Finding.create(
            category=tc["category"],
            line=tc["error_line"],
            col=tc["error_col"],
            explanation=tc["explanation"],
            evidence=tc["evidence"],
            metadata={"reason": tc["reason"]},
        )

        case_res = {
            "case_id": tc["id"],
            "name": tc["name"],
            "category": tc["category"].value,
            "tiers": {},
        }

        print(f"\nEvaluating Case: [{tc['id']}] {tc['name']}")

        # 1. Evaluate Deterministic Tier
        t0 = time.perf_counter()
        det_cand, det_desc = pipeline._try_deterministic(tc["code"], fnd)
        det_time = (time.perf_counter() - t0) * 1000.0
        det_val, _ = pipeline._validate_repair(tc["code"], det_cand) if det_cand else (False, -1)
        case_res["tiers"]["DETERMINISTIC"] = {
            "produced_patch": det_cand is not None and det_cand != tc["code"],
            "validation_passed": det_val,
            "latency_ms": round(det_time, 2),
            "description": det_desc,
        }
        print(f"  - DETERMINISTIC : {'PASS' if det_val else 'FAIL'} ({det_time:.1f}ms) - {det_desc or 'No rule'}")

        # 2. Evaluate CodeT5 Tier
        if pipeline.codet5.is_available():
            t0 = time.perf_counter()
            c5_cand, c5_desc = pipeline.codet5.generate_patch(
                tc["code"], tc["reason"], tc["error_line"], tc["error_col"]
            )
            c5_time = (time.perf_counter() - t0) * 1000.0
            c5_val, _ = pipeline._validate_repair(tc["code"], c5_cand) if c5_cand else (False, -1)
            case_res["tiers"]["CODET5"] = {
                "produced_patch": c5_cand is not None and c5_cand != tc["code"],
                "validation_passed": c5_val,
                "latency_ms": round(c5_time, 2),
                "description": c5_desc,
            }
            print(f"  - CODET5+LoRA   : {'PASS' if c5_val else 'FAIL'} ({c5_time:.1f}ms) - {c5_desc or 'No patch'}")
        else:
            case_res["tiers"]["CODET5"] = {"available": False}
            print("  - CODET5+LoRA   : SKIPPED (Weights not loaded)")

        # 3. Evaluate Qwen via Ollama Tier
        if pipeline.ollama.is_available():
            t0 = time.perf_counter()
            qw_cand, qw_desc = pipeline.ollama.generate_repair(tc["code"], fnd)
            qw_time = (time.perf_counter() - t0) * 1000.0
            qw_val, _ = pipeline._validate_repair(tc["code"], qw_cand) if qw_cand else (False, -1)
            case_res["tiers"]["QWEN_CODER"] = {
                "produced_patch": qw_cand is not None and qw_cand != tc["code"],
                "validation_passed": qw_val,
                "latency_ms": round(qw_time, 2),
                "description": qw_desc,
            }
            print(f"  - QWEN-CODER    : {'PASS' if qw_val else 'FAIL'} ({qw_time:.1f}ms) - {qw_desc or 'No patch'}")
        else:
            case_res["tiers"]["QWEN_CODER"] = {"available": False, "note": "Ollama service offline"}
            print("  - QWEN-CODER    : SKIPPED (Ollama daemon offline on 11434)")

        results.append(case_res)

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "system_status": status,
        "cases": results,
        "recommendation": {
            "primary": "DETERMINISTIC",
            "learned_specialized": "CODET5",
            "fallback_reasoning": "QWEN_CODER",
            "category_routing": {
                "missing_tokens_and_delimiters": "Deterministic -> CodeT5 -> Qwen",
                "insecure_c_apis": "Deterministic SecurityAutoFixer -> CodeT5 Security -> Qwen",
                "unsupported_grammar_or_logic": "Qwen2.5-Coder directly",
            },
        },
    }

    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"\nSaved benchmark results to {output_json}")

    return summary


if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else None
    run_benchmark(out_file)
