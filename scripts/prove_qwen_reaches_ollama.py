# scripts/prove_qwen_reaches_ollama.py
import os
import sys
import json
import time
import urllib.request
import re
from typing import Dict, Any, List

sys.path.insert(0, os.getcwd())

from compiler.repair_planner import RepairPlanner
from compiler.patch_validator import SandboxedCompiler, PatchIntegrityInspector
from compiler.local_models import OllamaClient
from scripts.held_out_evaluation import generate_programs

OLLAMA_LOG_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Ollama\server.log")

def get_ollama_generate_requests() -> List[str]:
    if not os.path.exists(OLLAMA_LOG_PATH):
        return []
    with open(OLLAMA_LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    return [l.strip() for l in lines if 'POST     "/api/generate"' in l or 'POST "/api/generate"' in l or '/api/generate' in l]

TARGETS = [
    ("examples/semantic/arrow_on_value.c", "arrow_on_value.c"),
    ("examples/semantic/use_before_declare.c", "use_before_declare.c"),
    ("examples/week12_benchmark/missingrightparen.c", "missingrightparen.c"),
    ("examples/week12_benchmark/benchmark_1.c", "benchmark_1.c"),
    ("examples/week5_grammar_2026/globals_broken_1.c", "globals_broken_1.c"),
]

def get_targets():
    items = []
    for path, fname in TARGETS:
        with open(path, "r", encoding="utf-8") as f:
            items.append((fname, f.read()))
    progs = generate_programs()
    misspelled = next(p for p in progs if p['error_class'] == 'misspelled_identifier')
    items.append(("held_out_misspelled_identifier.c", misspelled['code']))
    return items

def main():
    targets = get_targets()
    print("=" * 80)
    print("PROVE QWEN REACHES OLLAMA - RAW EXECUTION LOG")
    print("=" * 80)
    
    server_reqs_start = get_ollama_generate_requests()
    print(f"Initial Ollama server.log '/api/generate' count: {len(server_reqs_start)}")
    print(f"Total files to test: {len(targets)}")

    results = []

    for idx, (fname, code) in enumerate(targets, 1):
        print("\n" + "-" * 70)
        print(f"FILE [{idx}/{len(targets)}]: {fname} ({len(code.splitlines())} lines)")
        print("-" * 70)

        log_before = get_ollama_generate_requests()
        cnt_before = len(log_before)

        planner = RepairPlanner()
        # Track Qwen details during execution
        t0 = time.perf_counter()

        # Execute plan_and_repair directly
        res = planner.plan_and_repair(
            source_code=code,
            filename=fname,
            language="c",
            time_budget_s=120.0,
            single_fn_only=True,
        )
        elapsed = round(time.perf_counter() - t0, 3)

        log_after = get_ollama_generate_requests()
        cnt_after = len(log_after)
        new_requests = cnt_after - cnt_before

        # Extract stages
        events = {e.get("stage_id"): e for e in res.get("pipeline_events", [])}
        qwen_ev = events.get("qwen_ollama", {})

        print(f"Status: {res.get('status')}")
        print(f"Workflow State: {res.get('workflow_state')}")
        print(f"Stopping Reason: {res.get('stopping_reason')}")
        print(f"Elapsed: {elapsed} s")
        print(f"Ollama server.log '/api/generate' count before: {cnt_before}, after: {cnt_after} (delta: +{new_requests})")
        print(f"Qwen stage status: {qwen_ev.get('status')}")
        print(f"Qwen stage duration_ms: {qwen_ev.get('duration_ms')}")
        print(f"Qwen stage description: {qwen_ev.get('description')}")
        if qwen_ev.get("failure_reason"):
            print(f"Qwen failure_reason: {qwen_ev.get('failure_reason')}")
        if new_requests > 0:
            print("New Ollama requests recorded in server.log:")
            for l in log_after[cnt_before:cnt_after]:
                print(f"  {l}")

        results.append({
            "file": fname,
            "status": res.get("status"),
            "new_ollama_requests": new_requests,
            "qwen_stage": qwen_ev,
        })

    print("\n" + "=" * 80)
    print("SUMMARY TABLE OF QWEN EXECUTION")
    print("=" * 80)
    print(f"{'File':<35} {'Status':<22} {'Ollama Reqs':<12} {'Qwen Status':<12} {'Duration ms':<12}")
    for r in results:
        print(f"{r['file']:<35} {r['status']:<22} {r['new_ollama_requests']:<12} {r['qwen_stage'].get('status','N/A'):<12} {r['qwen_stage'].get('duration_ms', 0.0):<12}")

if __name__ == "__main__":
    main()

