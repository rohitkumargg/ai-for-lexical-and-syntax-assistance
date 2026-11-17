# scripts/diagnose_step1.py
"""
Diagnostic runner for STEP 1 of the guardrail and repair pipeline task.
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

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright
from compiler.repair_job_manager import get_repair_job_manager

TARGET_FILES = sorted(
    glob.glob(str(PROJECT_ROOT / "examples" / "agent_security" / "*.c"))
    + glob.glob(str(PROJECT_ROOT / "examples" / "agent_security" / "*.py"))
    + glob.glob(str(PROJECT_ROOT / "examples" / "00_sim_*"))
)

REPORTS_DIR = PROJECT_ROOT / "reports" / "diagnostics"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSON = REPORTS_DIR / "step1_diagnosis.json"


async def diagnose_file(page, file_path_str: str) -> dict:
    file_path = Path(file_path_str)
    rel_path = file_path.relative_to(PROJECT_ROOT).as_posix()
    lang = "c" if file_path.suffix == ".c" else "python"
    
    with open(file_path, "r", encoding="utf-8") as f:
        source_code = f.read()

    t0 = time.perf_counter()

    # 0. Close any modal and clear caches
    await page.evaluate("""() => {
        if (typeof closeFullscreenResults === 'function') closeFullscreenResults();
        const modal = document.getElementById('fullscreen-results-modal');
        if (modal) modal.style.display = 'none';
        const secModal = document.getElementById('security-approval-modal');
        if (secModal) secModal.style.display = 'none';
        const prModal = document.getElementById('patch-review-modal');
        if (prModal) prModal.style.display = 'none';
        if (window.clearLocalCaches) window.clearLocalCaches();
    }""")
    await page.wait_for_timeout(300)

    # 1. Switch language and load file in Monaco
    await page.evaluate(
        """([langId, filename, code]) => {
            if (typeof switchLanguage === 'function') switchLanguage(langId);
            if (typeof openFileInTab === 'function') openFileInTab(filename, code);
        }""",
        [lang, file_path.name, source_code]
    )
    await page.wait_for_timeout(400)

    # Capture the repair job creation response
    job_id = None
    try:
        async with page.expect_response(
            lambda r: "/api/repair/job" in r.url and r.request.method == "POST",
            timeout=10000
        ) as resp_info:
            await page.evaluate("""() => {
                if (typeof closeFullscreenResults === 'function') closeFullscreenResults();
                const m = document.getElementById('fullscreen-results-modal');
                if (m) m.style.display = 'none';
                const btn = document.getElementById('btn-run');
                if (btn) btn.click();
            }""")
        resp = await resp_info.value
        if resp.status in (200, 202):
            resp_data = await resp.json()
            job_id = resp_data.get("job_id")
    except Exception as e:
        print(f"Warning: job creation response wait: {e}")

    # 3. Wait for finish and handle approval modal
    modal_approved = False
    has_started = False
    start_wait = time.time()
    timeout_s = 60.0

    while (time.time() - start_wait) < timeout_s:
        # Check security approval modal
        modal_visible = await page.evaluate(
            """() => {
                const modal = document.getElementById('security-approval-modal');
                return modal && modal.style.display !== 'none' && getComputedStyle(modal).display !== 'none';
            }"""
        )
        if modal_visible and not modal_approved:
            approve_btn = page.locator("#sec-btn-approve")
            if await approve_btn.is_visible() and await approve_btn.is_enabled():
                try:
                    await approve_btn.click(timeout=3000)
                    modal_approved = True
                except Exception:
                    pass
            await page.wait_for_timeout(300)

        # Check if job running
        is_running = await page.evaluate(
            """() => {
                const btn = document.getElementById('btn-run');
                const cancelBtn = document.getElementById('btn-cancel-repair');
                const runningFlag = Boolean(window.isRepairRunning);
                const btnDisabled = btn ? btn.disabled : false;
                const cancelVisible = cancelBtn && cancelBtn.style.display !== 'none';
                const hasJob = Boolean(window.activeRepairJobId);
                return runningFlag || btnDisabled || cancelVisible || hasJob;
            }"""
        )
        if is_running:
            has_started = True

        if has_started and not is_running:
            await page.wait_for_timeout(800)
            break

        await page.wait_for_timeout(400)

    elapsed_s = time.perf_counter() - t0

    # 4. Extract Job ID and telemetry from client state
    job_info = await page.evaluate(
        """() => {
            const lastJob = window.lastExecutedRepairJob || {};
            const res = window.currentRepairResult || {};
            const statusEl = document.getElementById('compiler-status-badge');
            const jobEl = document.getElementById('pipeline-progress-text');

            const getVal = (id) => {
                const el = document.getElementById(id);
                return el ? el.innerText.trim() : '--%';
            };

            return {
                activeJobId: window.activeRepairJobId || lastJob.job_id || res.job_id || '',
                uiStatus: statusEl ? statusEl.innerText.trim() : '',
                uiProgress: jobEl ? jobEl.innerText.trim() : '',
                metrics: {
                    overall_quality: getVal('pi-val-overall'),
                    optimal_code: getVal('pi-val-optimal'),
                    poor_code: getVal('pi-val-poor'),
                    vulnerability_risk: getVal('pi-val-vulnerability'),
                    green_metrics: getVal('pi-val-green'),
                    model_accuracy: getVal('pi-val-benchmark'),
                }
            };
        }"""
    )

    final_job_id = job_id or job_info["activeJobId"]

    # Query job manager on server for deep diagnostics
    mgr = get_repair_job_manager()
    active_job = mgr.get_job(final_job_id) if final_job_id else None

    # Inspect job result fields
    job_res = active_job.result if (active_job and active_job.result) else {}
    findings_before = job_res.get("findings_before", []) or job_res.get("findings", [])
    security_detected = any(
        (f.get("category") == "SECURITY" or "security" in str(f.get("id", "")).lower())
        for f in findings_before
    ) if findings_before else False

    cands = job_res.get("candidate")
    proposed_code = job_res.get("proposed_code") or (active_job.current_code if active_job else "")
    proposal_generated = bool(cands or (proposed_code and proposed_code.strip() != source_code.strip()))

    accepted_tier = job_res.get("accepted_by_tier", {}) or {}
    prov = job_res.get("repair_provider", "none")
    strat = job_res.get("repair_strategy", "none")
    
    tier_name = "none"
    if accepted_tier.get("deterministic", 0) > 0:
        tier_name = "deterministic_rules"
    elif accepted_tier.get("codet5", 0) > 0:
        tier_name = "codet5"
    elif accepted_tier.get("qwen", 0) > 0:
        tier_name = "qwen"
    elif prov and prov != "none":
        tier_name = prov

    # Check Qwen logs / calls
    pipeline_stages = job_res.get("pipeline_stages", [])
    qwen_stage = next((s for s in pipeline_stages if "qwen" in s.get("stage_id", "").lower() or "ollama" in s.get("stage_id", "").lower()), None)
    qwen_called = False
    qwen_rejected_raw = "none"

    if qwen_stage:
        qwen_called = qwen_stage.get("status") in ("PASSED", "FAILED")
        if qwen_stage.get("status") == "FAILED":
            qwen_rejected_raw = qwen_stage.get("description", "") or "unknown failure"
    if not qwen_called and (job_res.get("codet5_calls", 0) > 0 or job_res.get("llm_calls", 0) > 0):
        if job_res.get("llm_calls", 0) > 0:
            qwen_called = True

    final_status = active_job.state if active_job else job_info.get("uiStatus", "UNKNOWN")
    if job_res.get("terminal_status"):
        final_status = job_res.get("terminal_status")

    # Metrics analysis
    six_before = job_res.get("before_six_metrics", {}) or {}
    six_after = job_res.get("after_six_metrics", {}) or {}

    metric_details = {}
    for m_key, m_val in job_info["metrics"].items():
        is_computed_on = "repaired" if proposal_generated else "original"
        metric_details[m_key] = {
            "displayed": m_val,
            "computed_on": is_computed_on,
            "before_raw": six_before.get(m_key),
            "after_raw": six_after.get(m_key),
        }

    # Failure detail analysis
    failure_details = "none"
    if final_status in ("FAILED", "REPAIR_UNAVAILABLE", "CRASHED") or not proposal_generated:
        # Locate exact function and line
        lines = source_code.splitlines()
        first_err_line = 1
        if findings_before:
            f0 = findings_before[0]
            first_err_line = f0.get("line", 1)
        
        # Function name heuristic
        fn_name = "global"
        for i, l in enumerate(lines[:first_err_line]):
            if "def " in l:
                fn_name = l.split("def ")[1].split("(")[0].strip()
            elif "(" in l and ")" in l and "{" in l:
                parts = l.split("(")[0].strip().split()
                if parts:
                    fn_name = parts[-1].replace("*", "")

        err_msg = getattr(active_job, "error_message", None) if active_job else None
        reason = job_res.get("stopping_reason") or job_res.get("message") or err_msg or "No repair proposal generated"
        failure_details = f"func: {fn_name}() at line {first_err_line}: {reason}"

    record = {
        "file": rel_path,
        "language": lang,
        "security_finding_detected": "YES" if security_detected else "NO",
        "repair_proposal_generated": "YES" if proposal_generated else "NO",
        "repair_tier": tier_name,
        "qwen_called": "YES" if qwen_called else "NO",
        "qwen_rejected_raw": qwen_rejected_raw,
        "final_status": final_status,
        "metrics": metric_details,
        "time_s": round(elapsed_s, 2),
        "failure_details": failure_details,
    }
    print(f"[{lang.upper()}] {rel_path} -> status={final_status}, tier={tier_name}, sec={record['security_finding_detected']}, prop={record['repair_proposal_generated']}, time={record['time_s']}s")

    # Dismiss any fullscreen modal for next iteration
    await page.evaluate("""() => {
        if (typeof closeFullscreenResults === 'function') closeFullscreenResults();
        const modal = document.getElementById('fullscreen-results-modal');
        if (modal) modal.style.display = 'none';
    }""")
    return record


async def run_diagnostics():
    print(f"Starting diagnosis of {len(TARGET_FILES)} files...")
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        await page.goto("http://127.0.0.1:5000/", wait_until="networkidle", timeout=30000)

        for f in TARGET_FILES:
            try:
                res = await diagnose_file(page, f)
                results.append(res)
            except Exception as e:
                print(f"ERROR on {f}: {e}")
                try:
                    await page.evaluate("""() => {
                        if (typeof closeFullscreenResults === 'function') closeFullscreenResults();
                        const modal = document.getElementById('fullscreen-results-modal');
                        if (modal) modal.style.display = 'none';
                    }""")
                except Exception:
                    pass
                results.append({
                    "file": Path(f).relative_to(PROJECT_ROOT).as_posix(),
                    "language": "c" if f.endswith(".c") else "python",
                    "security_finding_detected": "unknown",
                    "repair_proposal_generated": "NO",
                    "repair_tier": "none",
                    "qwen_called": "NO",
                    "qwen_rejected_raw": str(e),
                    "final_status": "CRASHED",
                    "metrics": {},
                    "time_s": 0.0,
                    "failure_details": f"uncaught exception: {e}",
                })

        await browser.close()

    with open(OUT_JSON, "w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2)
    print(f"\nSaved diagnosis results to: {OUT_JSON}")


if __name__ == "__main__":
    asyncio.run(run_diagnostics())
