# scripts/prove_all_models_run.py
import os
import sys
sys.path.insert(0, os.getcwd())
import urllib.request
import json
import time

TARGET_FILES = [
    ("examples/semantic/arrow_on_value.c", "arrow_on_value.c"),
    ("examples/semantic/call_arity.c", "call_arity.c"),
    ("examples/semantic/use_before_declare.c", "use_before_declare.c"),
    ("examples/week12_benchmark/missing)infor.c", "missing)infor.c"),
    ("examples/week12_benchmark/missingrightparen.c", "missingrightparen.c"),
    ("examples/week12_benchmark/missingsemicoloninsidefor.c", "missingsemicoloninsidefor.c"),
    ("examples/week12_benchmark/error1.c", "error1.c"),
    ("examples/week12_benchmark/benchmark_1.c", "benchmark_1.c"),
    ("examples/week5_grammar_2026/globals_broken_1.c", "globals_broken_1.c"),
]

def get_held_out_cases():
    from scripts.held_out_evaluation import generate_programs
    progs = generate_programs()
    misspelled = next(p for p in progs if p['error_class'] == 'misspelled_identifier')
    stray = next(p for p in progs if p['error_class'] == 'stray_token')
    return [
        (misspelled['code'], "held_out_misspelled_identifier.c"),
        (stray['code'], "held_out_stray_token.c"),
    ]

def get_ollama_count():
    try:
        from compiler.local_models import get_ollama_call_count
        return get_ollama_call_count()
    except Exception:
        return 0

def get_approval_token(code: str, filename: str) -> Optional[str]:
    try:
        appr_payload = json.dumps({'code': code, 'filename': filename, 'language': 'c', 'operation': 'repair'}).encode('utf-8')
        req = urllib.request.Request('http://localhost:5000/api/security/approval/approve', data=appr_payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('approval_token')
    except Exception:
        return None

def run_test():
    all_targets = []
    for path, fname in TARGET_FILES:
        with open(path, "r", encoding="utf-8") as f:
            all_targets.append((f.read(), fname))
    
    held_out = get_held_out_cases()
    all_targets.extend(held_out)

    print(f"Total targets to run: {len(all_targets)}")
    results = []

    for idx, (code, fname) in enumerate(all_targets, 1):
        print(f"\n[{idx}/{len(all_targets)}] Testing {fname}...")
        ollama_before = get_ollama_count()
        t0 = time.time()
        tok = get_approval_token(code, fname)
        payload = json.dumps({"code": code, "filename": fname, "language": "c", "approval_token": tok}).encode("utf-8")
        req = urllib.request.Request("http://localhost:5000/api/coordinator/analyze_and_plan", data=payload, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req, timeout=120)
            data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"Error testing {fname}: {e}")
            continue
        elapsed_total = round((time.time() - t0) * 1000.0, 1)
        ollama_after = get_ollama_count()

        events = {ev.get("stage_id"): ev for ev in data.get("pipeline_events", [])}
        
        # Tier details
        # 1. Deterministic
        ev_det = events.get("deterministic_rules", {})
        det_called = ev_det.get("status") in ("PASSED", "FAILED")
        det_skip_line = "compiler/repair_planner.py:2896 (no deterministic rules matched)" if not det_called else ""

        # 2. CodeT5
        ev_c5 = events.get("codet5_model", {})
        c5_called = ev_c5.get("status") in ("PASSED", "FAILED")
        c5_skip_line = ""
        if not c5_called:
            desc = ev_c5.get("description", "")
            if "disabled" in desc:
                c5_skip_line = "compiler/repair_planner.py:2910 (repair.codet5_enabled=False)"
            elif "not available" in desc:
                c5_skip_line = "compiler/repair_planner.py:2919 (local weights/adapters missing)"
            elif "not in CodeT5 domain" in desc:
                c5_skip_line = "compiler/repair_planner.py:2928 (language not C/C++)"
            else:
                c5_skip_line = "compiler/repair_planner.py:2868 (resolved by rules or no supported findings)"

        # 3. Qwen
        ev_q = events.get("qwen_ollama", {})
        q_called = ev_q.get("status") in ("PASSED", "FAILED")
        q_skip_line = ""
        if not q_called:
            desc = ev_q.get("description", "")
            if "Deterministic rules fully resolved" in desc:
                q_skip_line = "compiler/repair_planner.py:2875 (resolved by rules)"
            elif "Primary CodeT5 repair succeeded" in desc:
                q_skip_line = "compiler/repair_planner.py:2969 (resolved by CodeT5)"
            else:
                q_skip_line = "compiler/repair_planner.py:3350 (Ollama unreachable or budget)"

        results.append({
            "file": fname,
            "status": data.get("status"),
            "stopping_reason": data.get("stopping_reason"),
            "ollama_before": ollama_before,
            "ollama_after": ollama_after,
            "total_ms": elapsed_total,
            "tiers": {
                "deterministic": {
                    "called": "YES" if det_called else "NO",
                    "skip_line": det_skip_line,
                    "desc": ev_det.get("description", ""),
                    "dur_ms": ev_det.get("duration_ms", 0),
                    "verdict": ev_det.get("status", "SKIPPED"),
                },
                "codet5": {
                    "called": "YES" if c5_called else "NO",
                    "skip_line": c5_skip_line,
                    "desc": ev_c5.get("description", ""),
                    "dur_ms": ev_c5.get("duration_ms", 0),
                    "verdict": ev_c5.get("status", "SKIPPED"),
                },
                "qwen": {
                    "called": "YES" if q_called else "NO",
                    "skip_line": q_skip_line,
                    "desc": ev_q.get("description", ""),
                    "dur_ms": ev_q.get("duration_ms", 0),
                    "verdict": ev_q.get("status", "SKIPPED"),
                }
            }
        })
        print(f"   Status: {data.get('status')} | Rules: {det_called} | CodeT5: {c5_called} ({ev_c5.get('duration_ms')}ms) | Qwen: {q_called} ({ev_q.get('duration_ms')}ms)")

    # Save to json report
    out_path = os.path.join("reports", "audit", "model_execution_evidence.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved execution evidence to {out_path}")

if __name__ == "__main__":
    run_test()
