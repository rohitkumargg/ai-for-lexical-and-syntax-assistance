# scripts/diagnose_step1_clean.py
"""
Diagnostic runner for STEP 1 of the guardrail and repair pipeline task.
Uses the proven process_single_file runner from scripts/run_all_examples_ui.py.
Executes all files in examples/agent_security/ and examples/00_sim_* through
the real UI pipeline, capturing all required diagnostic fields.
"""

import asyncio
import glob
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright
from scripts.run_all_examples_ui import process_single_file
from compiler.repair_job_manager import get_repair_job_manager

TARGET_FILES = [
    # 00_sim files (8 files)
    PROJECT_ROOT / "examples" / "00_sim_1_cascading_hallucination.c",
    PROJECT_ROOT / "examples" / "00_sim_1_cascading_hallucination.py",
    PROJECT_ROOT / "examples" / "00_sim_2_memory_poisoning.c",
    PROJECT_ROOT / "examples" / "00_sim_2_memory_poisoning.py",
    PROJECT_ROOT / "examples" / "00_sim_3_identity_compromise.c",
    PROJECT_ROOT / "examples" / "00_sim_3_identity_compromise.py",
    PROJECT_ROOT / "examples" / "00_sim_4_resource_overload.c",
    PROJECT_ROOT / "examples" / "00_sim_4_resource_overload.py",
    # agent_security C files (8 files)
    PROJECT_ROOT / "examples" / "agent_security" / "c_api_key.c",
    PROJECT_ROOT / "examples" / "agent_security" / "c_comment_secret.c",
    PROJECT_ROOT / "examples" / "agent_security" / "c_conn_str.c",
    PROJECT_ROOT / "examples" / "agent_security" / "c_neg_ctrl_var.c",
    PROJECT_ROOT / "examples" / "agent_security" / "c_password.c",
    PROJECT_ROOT / "examples" / "agent_security" / "c_private_key.c",
    PROJECT_ROOT / "examples" / "agent_security" / "c_prompt_injection.c",
    PROJECT_ROOT / "examples" / "agent_security" / "c_syntax_err_secret.c",
    # agent_security Python files (7 files)
    PROJECT_ROOT / "examples" / "agent_security" / "py_api_key.py",
    PROJECT_ROOT / "examples" / "agent_security" / "py_comment_secret.py",
    PROJECT_ROOT / "examples" / "agent_security" / "py_conn_str.py",
    PROJECT_ROOT / "examples" / "agent_security" / "py_neg_ctrl_var.py",
    PROJECT_ROOT / "examples" / "agent_security" / "py_password.py",
    PROJECT_ROOT / "examples" / "agent_security" / "py_prompt_injection.py",
    PROJECT_ROOT / "examples" / "agent_security" / "py_syntax_err_secret.py",
]

REPORTS_DIR = PROJECT_ROOT / "reports" / "diagnostics"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSON = REPORTS_DIR / "step1_diagnosis.json"


async def run_diagnostics():
    print(f"=== Starting Step 1 Diagnosis on {len(TARGET_FILES)} files ===")
    results = []
    mgr = get_repair_job_manager()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        await page.goto("http://127.0.0.1:5000/", wait_until="networkidle", timeout=30000)

        for idx, file_path in enumerate(TARGET_FILES, 1):
            rel_path = file_path.relative_to(PROJECT_ROOT).as_posix()
            lang = "c" if file_path.suffix == ".c" else "python"
            print(f"\n[{idx}/{len(TARGET_FILES)}] Running {rel_path} ({lang})...")
            
            ui_res = await process_single_file(page, file_path)
            
            # Fetch latest executed job from disk (saved by server)
            import glob
            job_files = sorted(glob.glob(str(PROJECT_ROOT / "data" / "repair_jobs" / "*.json")), key=os.path.getmtime)
            latest_job_data = {}
            if job_files:
                try:
                    with open(job_files[-1], "r", encoding="utf-8") as jf:
                        latest_job_data = json.load(jf)
                except Exception:
                    pass

            job_res = latest_job_data.get("result", {}) or {}
            findings = job_res.get("findings", []) or []
            if not isinstance(findings, list):
                findings = []
            orig_assessment = job_res.get("original_assessment", {}) or {}
            orig_sec_count = orig_assessment.get("confirmed_security_count", 0) + orig_assessment.get("possible_security_count", 0)
            precheck = job_res.get("precheck_report", {}) or {}
            precheck_dang = precheck.get("has_dangerous_patterns", False)
            
            # Security finding detected?
            sec_detected = bool(orig_sec_count > 0 or precheck_dang)
            if not sec_detected:
                stages = job_res.get("pipeline_stages", []) or []
                for s in stages:
                    if isinstance(s, dict) and "security" in str(s.get("stage_id", "")).lower():
                        if s.get("findings_count", 0) > 0 or s.get("status") == "FAILED":
                            sec_detected = True
                            break

            # Repair proposal generated?
            cand = job_res.get("candidate")
            proposed_code = job_res.get("proposed_code") or latest_job_data.get("current_code", "")
            with open(file_path, "r", encoding="utf-8") as fp:
                original_code = fp.read()
            prop_generated = bool(cand or (proposed_code and proposed_code.strip() != original_code.strip()) or ui_res.get("passed"))

            # Repair tier
            tier = job_res.get("repair_provider", "none")
            accepted_tier = job_res.get("accepted_by_tier", {}) or {}
            if tier == "none":
                if accepted_tier.get("deterministic", 0) > 0:
                    tier = "deterministic_rules"
                elif accepted_tier.get("codet5", 0) > 0:
                    tier = "codet5"
                elif accepted_tier.get("qwen", 0) > 0:
                    tier = "qwen"
                elif "deterministic" in ui_res.get("run_output", "").lower():
                    tier = "deterministic_rules"
            elif job_res.get("repair_provider"):
                tier = job_res.get("repair_provider")
            elif "deterministic" in ui_res.get("run_output", "").lower():
                tier = "deterministic_rules"

            # Qwen called / rejected
            stages = job_res.get("pipeline_stages", []) or []
            qwen_stage = next((s for s in stages if isinstance(s, dict) and ("qwen" in str(s.get("stage_id", "")).lower() or "ollama" in str(s.get("stage_id", "")).lower())), None)
            qwen_called = False
            qwen_rejected = "none"
            if qwen_stage:
                st = qwen_stage.get("status")
                if st in ("PASSED", "FAILED"):
                    qwen_called = True
                if st == "FAILED":
                    qwen_rejected = qwen_stage.get("description", "") or "Qwen repair rejected"

            final_status = latest_job_data.get("state") or ("PASS" if ui_res.get("passed") else "FAIL")
            if job_res.get("terminal_status"):
                final_status = job_res.get("terminal_status")

            # Metrics
            six_metrics = {
                "overall_quality": {
                    "value": ui_res.get("metrics_overall_quality", "--%"),
                    "computed_on": "repaired" if prop_generated else "original"
                },
                "optimal_code": {
                    "value": ui_res.get("metrics_optimal_code", "--%"),
                    "computed_on": "repaired" if prop_generated else "original"
                },
                "poor_code": {
                    "value": ui_res.get("metrics_poor_code", "--%"),
                    "computed_on": "repaired" if prop_generated else "original"
                },
                "vulnerability_risk": {
                    "value": ui_res.get("metrics_vulnerability_risk", "--%"),
                    "computed_on": "repaired" if prop_generated else "original"
                },
                "green_metrics": {
                    "value": ui_res.get("metrics_green", "--%"),
                    "computed_on": "repaired" if prop_generated else "original"
                },
                "model_accuracy": {
                    "value": ui_res.get("metrics_model_accuracy", "--%"),
                    "computed_on": "repaired" if prop_generated else "original"
                },
            }

            # Failure details
            failure_details = "none"
            if not ui_res.get("passed") or final_status in ("FAILED", "REPAIR_UNAVAILABLE"):
                lines = original_code.splitlines()
                first_err_line = 1
                if findings and isinstance(findings, list) and isinstance(findings[0], dict):
                    first_err_line = findings[0].get("line", 1)
                fn_name = "main"
                for l in lines[:first_err_line]:
                    if "def " in l:
                        fn_name = l.split("def ")[1].split("(")[0].strip()
                    elif "(" in l and ")" in l and "{" in l:
                        parts = l.split("(")[0].strip().split()
                        if parts:
                            fn_name = parts[-1].replace("*", "")
                err = ui_res.get("failure_cause") or job_res.get("stopping_reason") or "unresolved error"
                failure_details = f"func: {fn_name}() line {first_err_line}: {err}"

            record = {
                "file": rel_path,
                "language": lang,
                "security_finding_detected": "YES" if sec_detected else "NO",
                "repair_proposal_generated": "YES" if prop_generated else "NO",
                "repair_tier": tier,
                "qwen_called": "YES" if qwen_called else "NO",
                "qwen_rejected_raw": qwen_rejected,
                "final_status": final_status,
                "metrics": six_metrics,
                "time_s": ui_res.get("elapsed_s", 0.0),
                "failure_details": failure_details,
            }
            results.append(record)
            print(f" -> Result: pass={ui_res.get('passed')}, sec={record['security_finding_detected']}, prop={record['repair_proposal_generated']}, tier={tier}, time={record['time_s']}s")

        await browser.close()

    with open(OUT_JSON, "w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2)
    print(f"\nAll {len(results)} files processed. Results saved to: {OUT_JSON}")


if __name__ == "__main__":
    asyncio.run(run_diagnostics())
