#!/usr/bin/env python3
"""
scripts/attack_corpus_check.py

Automated Browser Verification for the 12 Known Attack & Agent-Security Files (Step 4a).
Drives the real UI via Playwright (Chromium) and asserts for each file:
1. Results screen appears and marks file as vulnerable (defect count > 0, risk % > 0).
2. A non-empty, non-generic explanation is visible in the fullscreen results screen (length > 80 chars, contains category keyword).
3. Proposed repair is shown OR honest REPAIR_UNAVAILABLE is displayed.
4. Generates the per-file verification table.
"""

import os
import sys
import time
import json
import urllib.request
import subprocess
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5000"

TEST_FILES = [
    {
        "filename": "00_sim_1_cascading_hallucination.c",
        "path": "examples/00_sim_1_cascading_hallucination.c",
        "keyword": "hallucination",
        "category": "Cascading Hallucination",
    },
    {
        "filename": "00_sim_2_memory_poisoning.c",
        "path": "examples/00_sim_2_memory_poisoning.c",
        "keyword": "poisoning",
        "category": "Memory Poisoning",
    },
    {
        "filename": "00_sim_3_identity_compromise.c",
        "path": "examples/00_sim_3_identity_compromise.c",
        "keyword": "identity",
        "category": "Identity Compromise",
    },
    {
        "filename": "00_sim_4_resource_overload.c",
        "path": "examples/00_sim_4_resource_overload.c",
        "keyword": "overload",
        "category": "Resource Overload",
    },
    {
        "filename": "c_api_key.c",
        "path": "examples/agent_security/c_api_key.c",
        "keyword": "key",
        "category": "API Key Exposure",
    },
    {
        "filename": "c_comment_secret.c",
        "path": "examples/agent_security/c_comment_secret.c",
        "keyword": "secret",
        "category": "Comment Secret",
    },
    {
        "filename": "c_conn_str.c",
        "path": "examples/agent_security/c_conn_str.c",
        "keyword": "connection",
        "category": "Connection String",
    },
    {
        "filename": "c_neg_ctrl_var.c",
        "path": "examples/agent_security/c_neg_ctrl_var.c",
        "keyword": "tamper",
        "category": "Negative Control Var",
    },
    {
        "filename": "c_password.c",
        "path": "examples/agent_security/c_password.c",
        "keyword": "password",
        "category": "Hardcoded Password",
    },
    {
        "filename": "c_private_key.c",
        "path": "examples/agent_security/c_private_key.c",
        "keyword": "key",
        "category": "Embedded Private Key",
    },
    {
        "filename": "c_prompt_injection.c",
        "path": "examples/agent_security/c_prompt_injection.c",
        "keyword": "injection",
        "category": "Prompt Injection",
    },
    {
        "filename": "c_syntax_err_secret.c",
        "path": "examples/agent_security/c_syntax_err_secret.c",
        "keyword": "secret",
        "category": "Syntax-Masked Secret",
    },
]

def wait_for_server(timeout=15.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/languages", timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    print("=" * 90)
    print("STARTING BROWSER VERIFICATION SUITE FOR THE 12 ATTACK CORPUS FILES")
    print("=" * 90)

    server_proc = None
    server_log_file = None
    need_server_kill = False

    try:
        # Check if port 5000 is open
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/languages", timeout=1.0) as resp:
                pass
            print("[SERVER] Port 5000 is already active; using active server.")
        except Exception:
            print("[SERVER] Starting Flask server on http://127.0.0.1:5000 ...")
            server_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scratch", "attack_server.log")
            os.makedirs(os.path.dirname(server_log_path), exist_ok=True)
            server_log_file = open(server_log_path, "w", encoding="utf-8", buffering=1)
            server_proc = subprocess.Popen([sys.executable, "app.py"], stdout=server_log_file, stderr=subprocess.STDOUT)
            need_server_kill = True
            if not wait_for_server(15.0):
                print("FATAL: Server failed to start on port 5000 within 15 seconds!")
                sys.exit(1)

        table_rows = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1536, "height": 900})
            page = context.new_page()

            print(f"[UI] Navigating to {BASE_URL} ...")
            page.goto(BASE_URL, wait_until="networkidle")
            page.wait_for_selector("#editor", timeout=10000)

            for idx, item in enumerate(TEST_FILES, 1):
                fname = item["filename"]
                fpath = item["path"]
                kw = item["keyword"].lower()
                cat = item["category"]

                with open(fpath, "r", encoding="utf-8") as fh:
                    code = fh.read()

                print(f"\n[{idx}/12] Testing {fname} ({cat})...")

                page.evaluate("""() => {
                    if (typeof closeFullscreenResults === 'function') closeFullscreenResults();
                    const fs = document.getElementById('fullscreen-results-modal');
                    if (fs) fs.style.display = 'none';
                    window.lastRunResult = null;
                }""")
                time.sleep(0.5)

                page.evaluate("""(payload) => {
                    if (typeof resetExecutionStateOnProblemChange === 'function') resetExecutionStateOnProblemChange();
                    window.currentFilename = payload.filename;
                    if (typeof currentFilename !== 'undefined') currentFilename = payload.filename;
                    if (typeof workspaces !== 'undefined' && workspaces[currentLanguageId]) {
                        workspaces[currentLanguageId].currentFilename = payload.filename;
                    }
                    if (window.editor) window.editor.setValue(payload.code);
                }""", {"code": code, "filename": fname})
                time.sleep(0.5)

                t0 = time.time()
                page.click('#btn-run')

                modal_visible = False
                approved = False
                timeout_s = 40

                for s in range(timeout_s):
                    time.sleep(1)
                    sec = page.evaluate("() => document.getElementById('security-approval-modal')?.style.display")
                    fs = page.evaluate("() => document.getElementById('fullscreen-results-modal')?.style.display")
                    if not approved and sec == 'flex':
                        page.click('#sec-btn-approve')
                        approved = True
                        time.sleep(0.5)
                        continue
                    if fs == 'flex' and (approved or s >= 2):
                        modal_visible = True
                        break

                elapsed_s = round(time.time() - t0, 2)
                if not modal_visible:
                    print(f"  FAILED: Fullscreen modal did not appear within {timeout_s}s!")
                    table_rows.append({
                        "filename": fname,
                        "vulnerable": "N",
                        "expl_shown": "N",
                        "expl_len": 0,
                        "repair_status": "TIMEOUT",
                        "pass": False,
                    })
                    continue

                modal_data = page.evaluate("""() => {
                    const countText = document.getElementById('fs-defects-count-text')?.textContent || '';
                    const cards = Array.from(document.querySelectorAll('#fs-findings-grid .fs-finding-card')).map(c => ({
                        title: c.querySelector('.fs-fc-title')?.textContent?.trim() || '',
                        severity: c.querySelector('.fs-sev-chip')?.textContent?.trim() || '',
                        problem: c.querySelector('.fs-fc-row')?.textContent?.trim() || ''
                    }));
                    const lastResult = window.lastRunResult || null;
                    return {
                        countText,
                        cards,
                        status: lastResult?.status || lastResult?.terminal_status || 'UNKNOWN',
                        vulnerability_risk: lastResult?.baseline_scores?.vulnerability_risk ?? lastResult?.proposed_scores?.vulnerability_risk,
                        findings: lastResult?.findings || [],
                        candidate: lastResult?.candidate || null,
                        has_candidate: !!lastResult?.has_candidate
                    };
                }""")

                page.evaluate("() => { if (typeof closeFullscreenResults === 'function') closeFullscreenResults(); }")

                # Checks
                cards = modal_data.get("cards") or []
                all_problems = [c.get("problem", "") for c in cards]
                explanation_str = " ".join(all_problems)
                
                # Check defect count > 0 and risk % > 0
                count_text = modal_data.get("countText", "")
                is_vulnerable = ("Clean" not in count_text) and (len(cards) > 0)
                risk_val = modal_data.get("vulnerability_risk")
                if risk_val is not None:
                    try:
                        if float(risk_val) > 0.0:
                            is_vulnerable = True
                    except Exception:
                        pass

                # Check explanation
                expl_len = len(explanation_str)
                expl_shown = (expl_len >= 80) and (kw in explanation_str.lower() or any(kw in p.lower() for p in all_problems))

                repair_status = modal_data.get("status", "UNKNOWN")
                if modal_data.get("has_candidate") and repair_status in ("FULLY_REPAIRED", "PROPOSAL_READY"):
                    rep_display = f"PROPOSED ({repair_status})"
                elif repair_status == "REPAIR_UNAVAILABLE":
                    rep_display = "REPAIR_UNAVAILABLE"
                else:
                    rep_display = repair_status

                passed = is_vulnerable and expl_shown and (repair_status in ("FULLY_REPAIRED", "PROPOSAL_READY", "REPAIR_UNAVAILABLE"))

                table_rows.append({
                    "filename": fname,
                    "vulnerable": "Y" if is_vulnerable else "N",
                    "expl_shown": "Y" if expl_shown else "N",
                    "expl_len": expl_len,
                    "repair_status": rep_display,
                    "pass": passed,
                })

                print(f"  Elapsed: {elapsed_s}s | Vulnerable: {'Y' if is_vulnerable else 'N'} | Expl Shown: {'Y' if expl_shown else 'N'} ({expl_len} chars) | Status: {rep_display}")

            browser.close()

        # Print Markdown Table
        print("\n" + "=" * 90)
        print("STEP 4a VERIFICATION TABLE")
        print("=" * 90)
        print("| Filename | Marked Vulnerable | Explanation Shown | Explanation Length | Repair Status | Result |")
        print("| :--- | :---: | :---: | :---: | :--- | :---: |")
        all_passed = True
        for row in table_rows:
            res_str = "PASS" if row["pass"] else "FAIL"
            if not row["pass"]:
                all_passed = False
            print(f"| `{row['filename']}` | {row['vulnerable']} | {row['expl_shown']} | {row['expl_len']} chars | {row['repair_status']} | **{res_str}** |")

        print("=" * 90)
        if all_passed:
            print("ALL 12 ATTACK CORPUS FILES PASSED 100% OF VERIFICATION CHECKS!")
        else:
            print("SOME CHECKS FAILED! Please review above output.")
        print("=" * 90)

    finally:
        if need_server_kill and server_proc:
            print("[SERVER] Shutting down spawned test server...")
            server_proc.kill()
        if server_log_file:
            server_log_file.close()

if __name__ == "__main__":
    main()
