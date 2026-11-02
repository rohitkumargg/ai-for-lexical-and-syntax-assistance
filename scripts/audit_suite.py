# scripts/audit_suite.py
import os
import sys
import glob
import json
import csv
import time
import subprocess
import re
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.getcwd())

from compiler.repair_job_manager import split_top_level_functions, get_repair_job_manager
from compiler.repair_planner import RepairPlanner
from compiler.security_approval_gate import SecurityApprovalManager
from compiler.patch_validator import SandboxedCompiler
from scripts.held_out_evaluation import generate_programs

os.makedirs("reports/audit", exist_ok=True)
CSV_PATH = os.path.join("reports", "audit", "audit_results.csv")

compiler = SandboxedCompiler()
planner = RepairPlanner()

def check_gcc(code_str: str) -> bool:
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False, encoding="utf-8") as tmp:
            tmp.write(code_str)
            tmp_path = tmp.name
        try:
            res = subprocess.run(["gcc", "-fsyntax-only", tmp_path], capture_output=True, text=True, timeout=5)
            return res.returncode == 0
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception:
        return False

def audit_file(file_name: str, code: str) -> Dict[str, Any]:
    lines_count = len(code.splitlines())
    gcc_before = check_gcc(code)

    t0 = time.perf_counter()
    pre, fns = split_top_level_functions(code, language="c")

    # Get approval token if needed
    ok_tok, tok, _ = SecurityApprovalManager.create_one_time_approval(code, file_name, "c")

    # Path matching UI
    if len(fns) > 3 or lines_count > 150:
        mgr = get_repair_job_manager()
        job = mgr.create_job(
            code=code,
            filename=file_name,
            language="c",
            operation="repair",
            approval_token=tok
        )
        mgr._execute_repair_job(job)
        res = job.result or {}
        cand_dict = res.get("candidate") or {}
        patched_code = job.current_code if job.current_code else code
        windows_done = job.windows_done
        windows_by_tier = job.windows_by_tier
        stopping_reason = job.stage
    else:
        res = planner.plan_and_repair(
            code,
            filename=file_name,
            language="c",
            operation="repair",
            approval_token=tok
        )
        cand_dict = res.get("candidate") or {} if isinstance(res.get("candidate"), dict) else {}
        patched_code = cand_dict.get("proposed_code", code)
        windows_done = 1 if cand_dict else 0
        tier_p = cand_dict.get("repair_provider", "none")
        if tier_p in ("deterministic_rules", "deterministic"):
            windows_by_tier = {"rules": 1, "codet5": 0, "qwen": 0}
        elif tier_p == "codet5":
            windows_by_tier = {"rules": 0, "codet5": 1, "qwen": 0}
        elif tier_p == "qwen":
            windows_by_tier = {"rules": 0, "codet5": 0, "qwen": 1}
        else:
            windows_by_tier = {"rules": 0, "codet5": 0, "qwen": 0}
        stopping_reason = cand_dict.get("stopping_reason") or cand_dict.get("fallback_reason") or ""

    gcc_after = check_gcc(patched_code) if patched_code != code else gcc_before

    status = res.get("status", "UNKNOWN")
    rep_status = cand_dict.get("terminal_status") or cand_dict.get("validation_state") or ("FULLY_REPAIRED" if gcc_after and not gcc_before else ("CLEAN" if gcc_before else "REPAIR_UNAVAILABLE"))
    
    tier_used = "none"
    if windows_by_tier.get("qwen", 0) > 0 or cand_dict.get("repair_provider") == "qwen":
        tier_used = "qwen"
    elif windows_by_tier.get("codet5", 0) > 0 or cand_dict.get("repair_provider") == "codet5":
        tier_used = "codet5"
    elif windows_by_tier.get("rules", 0) > 0 or cand_dict.get("repair_provider") in ("deterministic_rules", "deterministic"):
        tier_used = "rules"

    # Findings
    fnds = res.get("findings", [])
    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in fnds:
        sev = str(f.get("severity", "") if isinstance(f, dict) else getattr(f, "severity", "")).lower()
        if "crit" in sev: sev_counts["critical"] += 1
        elif "high" in sev: sev_counts["high"] += 1
        elif "med" in sev: sev_counts["medium"] += 1
        elif "low" in sev: sev_counts["low"] += 1
        elif "info" in sev: sev_counts["info"] += 1

    # Scores
    bs = res.get("baseline_scores") or {}
    ps = res.get("proposed_scores") or {}
    scores = {
        "overall_code_quality": ps.get("overall_code_quality", bs.get("overall_code_quality", 100.0 if gcc_before else 0.0)),
        "quality_score": ps.get("quality_score", bs.get("quality_score", 100.0 if gcc_before else 0.0)),
        "optimization_potential": ps.get("optimization_potential", bs.get("optimization_potential", 0.0)),
        "optimal_code": ps.get("optimal_code", bs.get("optimal_code", 100.0)),
        "security_risk": ps.get("security_risk", bs.get("security_risk", 0.0)),
        "green_metrics": ps.get("green_metrics", bs.get("green_metrics", 75.0)),
    }

    unavail_reason = ""
    if rep_status == "REPAIR_UNAVAILABLE" or tier_used == "none":
        unavail_reason = stopping_reason or res.get("message") or "No candidate generated or validated"

    return {
        "file": file_name,
        "lines": lines_count,
        "status": status,
        "repair_status": rep_status,
        "tier_used": tier_used,
        "windows_done": windows_done,
        "windows_by_tier": json.dumps(windows_by_tier),
        "gcc_before": gcc_before,
        "gcc_after": gcc_after,
        "findings_by_severity": json.dumps(sev_counts),
        "score_metrics": json.dumps(scores),
        "unavailable_reason": unavail_reason,
        "elapsed_s": round(time.perf_counter() - t0, 2)
    }

def main():
    print("Collecting files for audit...")
    all_targets: List[Tuple[str, str]] = []

    # 1. examples/**/*.c
    ex_files = sorted(glob.glob("examples/**/*.c", recursive=True))
    for f in ex_files:
        norm_name = f.replace("\\", "/")
        try:
            with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                all_targets.append((norm_name, fp.read()))
        except Exception:
            pass

    # 2. 30 held-out generated programs
    progs = generate_programs()
    for p in progs:
        all_targets.append((f"held_out/{p['id']}_{p['error_class']}.c", p["code"]))

    # 3. 5-line small syntax error file
    small_5_line = """#include <stdio.h>
int main(void) {
    int x = 10
    return x;
}
"""
    all_targets.append(("examples/unit_test_5_line.c", small_5_line))

    print(f"Total files to audit: {len(all_targets)}")
    results = []

    fieldnames = [
        "file", "lines", "status", "repair_status", "tier_used",
        "windows_done", "windows_by_tier", "gcc_before", "gcc_after",
        "findings_by_severity", "score_metrics", "unavailable_reason"
    ]

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for idx, (fname, code) in enumerate(all_targets, 1):
            t_s = time.perf_counter()
            try:
                row = audit_file(fname, code)
            except Exception as e:
                row = {
                    "file": fname,
                    "lines": len(code.splitlines()),
                    "status": "ERROR",
                    "repair_status": "REPAIR_UNAVAILABLE",
                    "tier_used": "none",
                    "windows_done": 0,
                    "windows_by_tier": "{}",
                    "gcc_before": False,
                    "gcc_after": False,
                    "findings_by_severity": "{}",
                    "score_metrics": "{}",
                    "unavailable_reason": f"Exception: {str(e)}",
                    "elapsed_s": round(time.perf_counter() - t_s, 2)
                }
            
            results.append(row)
            # Write to CSV immediately
            csv_row = {k: row[k] for k in fieldnames}
            writer.writerow(csv_row)
            csvfile.flush()

            if idx % 10 == 0 or idx == len(all_targets) or "held_out" in fname or "5_line" in fname:
                print(f"[{idx:03d}/{len(all_targets):03d}] {fname:<45} | gcc_b: {str(row['gcc_before']):<5} | gcc_a: {str(row['gcc_after']):<5} | tier: {row['tier_used']:<6} | {row['elapsed_s']}s")

    print("\nAudit complete! Saved to:", CSV_PATH)

if __name__ == "__main__":
    main()
