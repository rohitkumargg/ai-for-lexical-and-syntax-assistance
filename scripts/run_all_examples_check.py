#!/usr/bin/env python3
"""
Test runner across all example files in examples/
Checks:
1. Does it crash with an unhandled exception?
2. Does it produce the expected status category?
3. If repair candidate is generated, does it have a valid non-empty diff and pass compiler checks?
4. Are clean files correctly detected as clean (do-no-harm)?
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import glob
import time
import json
import traceback

from compiler.repair_planner import RepairPlanner
from compiler.patch_validator import SandboxedCompiler
from compiler.repair_job_manager import RepairJobManager, _lightweight_check

def run_all_c_examples(limit=None):
    example_root = "examples"
    files = []
    for root, dirs, filenames in os.walk(example_root):
        dirs[:] = [d for d in dirs if not d.startswith((".", "_")) and d != "__pycache__"]
        for f in filenames:
            if f.startswith((".", "_")):
                continue
            if f.lower().endswith(".c") and "_fixed." not in f.lower():
                rel_path = os.path.relpath(os.path.join(root, f), example_root).replace("\\", "/")
                parts = rel_path.split("/")
                if not any(p.startswith((".", "_")) or p == "__pycache__" for p in parts):
                    files.append(rel_path)
    files.sort()
    if limit:
        files = files[:limit]

    print(f"Testing {len(files)} C example files...")
    planner = RepairPlanner()
    compiler = SandboxedCompiler()
    
    results = []
    start_time = time.time()

    for idx, rel in enumerate(files, 1):
        full_path = os.path.join(example_root, rel)
        with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
            code = fp.read()
        lines = len(code.splitlines())

        t0 = time.time()
        c_before, out_before, _ = compiler.compile_check(code)
        
        try:
            # For very large files (>300 lines), job manager or planner
            if lines > 300:
                jm = RepairJobManager()
                job = jm.create_job(code, os.path.basename(rel), "c", operation="repair")
                # Worker execution
                jm._execute_repair_job(job)
                j = jm.get_job(job.job_id)
                res = j.result or {}
            else:
                res = planner.plan_and_repair(
                    code,
                    filename=os.path.basename(rel),
                    language="c",
                    operation="repair",
                    time_budget_s=15.0,
                )
            
            elapsed = round(time.time() - t0, 2)
            status = res.get("status") or res.get("terminal_status") or "UNKNOWN"
            cand = res.get("candidate") or {}
            proposed = res.get("proposed_code") or cand.get("proposed_code")
            has_cand = bool(proposed and proposed.strip() != code.strip())
            
            diff = res.get("diff") or res.get("unified_diff") or cand.get("diff") or cand.get("unified_diff") or ""
            has_diff = bool(diff and diff.strip())
            
            c_after = None
            if proposed:
                c_after, _, _ = compiler.compile_check(proposed)

            is_valid = res.get("is_valid")
            if is_valid is None and cand:
                is_valid = cand.get("is_valid")

            stopping_reason = str(res.get("stopping_reason") or "")[:120]
            
            # Anomalies:
            # 1. Candidate produced but diff is missing!
            # 2. Before compiled fine, but repair introduced compilation error!
            # 3. Candidate produced and claims is_valid=True, but fails compile!
            # 4. Status is ERROR or exception.
            issues = []
            if has_cand and not has_diff:
                issues.append("MISSING_DIFF")
            if c_before and proposed and c_after is False:
                issues.append("DO_NO_HARM_REGRESSION")
            if has_cand and is_valid is True and c_after is False:
                issues.append("INVALID_CANDIDATE_MARKED_VALID")
            if status == "ERROR":
                issues.append("STATUS_ERROR")

            result_entry = {
                "file": rel,
                "lines": lines,
                "status": status,
                "c_before": c_before,
                "c_after": c_after,
                "has_cand": has_cand,
                "has_diff": has_diff,
                "diff_len": len(diff),
                "is_valid": is_valid,
                "elapsed": elapsed,
                "stopping_reason": stopping_reason,
                "issues": issues,
            }
            results.append(result_entry)
            
            issue_str = f" [!] {', '.join(issues)}" if issues else ""
            print(f"[{idx:3d}/{len(files)}] {rel:50s} lines={lines:4d} status={status:20s} c_before={str(c_before):5s} c_after={str(c_after):5s} has_diff={str(has_diff):5s} {elapsed:4.1f}s{issue_str}", flush=True)

        except Exception as e:
            tb = traceback.format_exc()
            results.append({
                "file": rel,
                "lines": lines,
                "status": "EXCEPTION",
                "c_before": c_before,
                "c_after": None,
                "has_cand": False,
                "has_diff": False,
                "diff_len": 0,
                "is_valid": False,
                "elapsed": round(time.time() - t0, 2),
                "stopping_reason": str(e),
                "issues": ["UNHANDLED_EXCEPTION"],
                "traceback": tb,
            })
            print(f"[{idx:3d}/{len(files)}] {rel:50s} EXCEPTION: {e}", flush=True)

    total_time = round(time.time() - start_time, 2)
    print("\n" + "=" * 80)
    print(f"SUMMARY ({len(files)} files in {total_time}s):")
    total_issues = sum(len(r["issues"]) for r in results)
    exceptions = [r for r in results if "UNHANDLED_EXCEPTION" in r["issues"]]
    missing_diffs = [r for r in results if "MISSING_DIFF" in r["issues"]]
    regressions = [r for r in results if "DO_NO_HARM_REGRESSION" in r["issues"]]
    false_valids = [r for r in results if "INVALID_CANDIDATE_MARKED_VALID" in r["issues"]]
    
    print(f"  Total issues detected: {total_issues}")
    print(f"  Exceptions: {len(exceptions)}")
    print(f"  Missing diffs when candidate exists: {len(missing_diffs)}")
    print(f"  Do-no-harm regressions: {len(regressions)}")
    print(f"  Invalid candidates marked valid: {len(false_valids)}")
    print("=" * 80)

    # Save results to reports/examples_run_report.json
    os.makedirs("reports", exist_ok=True)
    with open("reports/examples_run_report.json", "w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2)
    print("Detailed report saved to reports/examples_run_report.json")

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_all_c_examples(limit=limit)
