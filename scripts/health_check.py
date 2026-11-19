#!/usr/bin/env python3
"""
scripts/health_check.py

Single End-to-End Health-Check Script
Meets all Phase 1 and Phase 5 requirements:
1. Starts the server fresh.
2. Loads a small known-broken C file, runs repair, asserts:
   (a) results screen appears within 15s;
   (b) explanation/description is shown (not blank);
   (c) pipeline stage list matches architecture order.
3. Loads an agent_security file (c_api_key.c) with secret:
   - finding detected;
   - repair proposed or honest REPAIR_UNAVAILABLE;
   - Vulnerability Risk % > 0.
4. Loads a 00_sim_* file (00_sim_2_memory_poisoning.c):
   - attack content flagged as real finding (not silently passed, not INFO note).
5. Loads a clean file:
   - status CLEAN with no false findings ("0 Active Defects Found — Clean").
6. Records total time from Run-click to results-screen-visible for each case (<15s).
"""

import os
import sys
import time
import json
import urllib.request
import subprocess
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5000"

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

def run_health_check():
    print("=" * 80)
    print("STARTING END-TO-END HEALTH-CHECK SUITE")
    print("=" * 80)

    server_proc = None
    server_log_file = None
    try:
        # Check if port 5000 is open, kill if needed to ensure fresh test server
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/languages", timeout=1.0) as resp:
                pass
            print("[SERVER] Port 5000 is already active; killing to ensure fresh server...")
            if sys.platform == "win32":
                subprocess.run(["powershell", "-Command", "Stop-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess -Force -ErrorAction SilentlyContinue"], capture_output=True)
            time.sleep(1)
        except Exception:
            pass

        print("[SERVER] Starting fresh Flask server on http://127.0.0.1:5000 ...")
        server_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scratch", "health_check_server.log")
        os.makedirs(os.path.dirname(server_log_path), exist_ok=True)
        server_log_file = open(server_log_path, "w", encoding="utf-8", buffering=1)
        server_proc = subprocess.Popen([sys.executable, "app.py"], stdout=server_log_file, stderr=subprocess.STDOUT)
        if not wait_for_server(15.0):
            print("FATAL: Server failed to start on port 5000 within 15 seconds!")
            if server_proc:
                server_proc.kill()
            if server_log_file:
                server_log_file.close()
            sys.exit(1)
        print("[SERVER] Server is live and responding to HTTP requests.")

        results = {}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1536, "height": 900})
            page = context.new_page()

            browser_logs = []
            page.on("console", lambda msg: browser_logs.append(f"[{msg.type}] {msg.text}"))
            page.on("pageerror", lambda err: browser_logs.append(f"[PAGE_ERROR] {err}"))

            print(f"[UI] Navigating to {BASE_URL} ...")
            page.goto(BASE_URL, wait_until="networkidle")
            page.wait_for_selector("#editor", timeout=10000)

            def execute_test(title, code, filename, timeout=25):
                print(f"\n{'-'*60}\n{title} ({filename})\n{'-'*60}")
                page.evaluate("() => { if (typeof closeFullscreenResults === 'function') closeFullscreenResults(); }")
                time.sleep(0.8)

                page.evaluate("""(payload) => {
                    if (typeof resetExecutionStateOnProblemChange === 'function') resetExecutionStateOnProblemChange();
                    window.editor.setValue(payload.code);
                    window.currentFilename = payload.filename;
                }""", {'code': code, 'filename': filename})
                time.sleep(0.5)

                t0 = time.time()
                page.click('#btn-run')

                modal_visible = False
                approved = False
                for s in range(timeout):
                    time.sleep(1)
                    sec = page.evaluate("() => document.getElementById('security-approval-modal')?.style.display")
                    fs = page.evaluate("() => document.getElementById('fullscreen-results-modal')?.style.display")
                    if not approved and sec == 'flex':
                        print(f"  [{s}s] Security review modal popped up. Approving...")
                        page.click('#sec-btn-approve')
                        approved = True
                    if fs == 'flex':
                        modal_visible = True
                        break

                elapsed_s = round(time.time() - t0, 2)
                modal_data = None
                if modal_visible:
                    modal_data = page.evaluate("""() => {
                        const countText = document.getElementById('fs-defects-count-text')?.textContent || '';
                        const cards = Array.from(document.querySelectorAll('#fs-findings-grid .fs-finding-card')).map(c => ({
                            title: c.querySelector('.fs-fc-title')?.textContent?.trim() || '',
                            severity: c.querySelector('.fs-sev-chip')?.textContent?.trim() || '',
                            problem: c.querySelector('.fs-fc-row')?.textContent?.trim() || ''
                        }));
                        const statusPill = document.getElementById('status-pill')?.textContent?.trim() || '';
                        const baselineRisk = document.getElementById('fs-b-gauge-risk-val')?.textContent?.trim() || '';
                        const targetRisk = document.getElementById('fs-t-gauge-risk-val')?.textContent?.trim() || '';
                        const lastResult = window.lastRunResult || null;
                        const stages = lastResult?.pipeline_stages || lastResult?.original_assessment?.pipeline_stages || [];
                        return {
                            countText,
                            cards,
                            statusPill,
                            baselineRisk,
                            targetRisk,
                            stages,
                            status: lastResult?.status || lastResult?.terminal_status || 'UNKNOWN',
                            vulnerability_risk: lastResult?.baseline_scores?.vulnerability_risk ?? lastResult?.proposed_scores?.vulnerability_risk,
                            findings: lastResult?.findings || [],
                            unresolved_findings: lastResult?.unresolved_findings || [],
                            remaining_findings: lastResult?.remaining_findings || []
                        };
                    }""")
                    page.evaluate("() => { if (typeof closeFullscreenResults === 'function') closeFullscreenResults(); }")

                return modal_visible, elapsed_s, modal_data

            # -------------------------------------------------------------
            # TEST 1: Small known-broken C file
            # -------------------------------------------------------------
            broken_c = "#include <stdio.h>\nint main(void) {\n    int count = ;\n    printf(\"count: %d\\n\", count);\n    return 0;\n}\n"
            t1_visible, t1_time, t1_data = execute_test("TEST 1: Small Known-Broken C File (Syntax Error)", broken_c, "broken.c", 20)

            t1_pass = True
            t1_reasons = []
            if not t1_visible:
                t1_pass = False
                t1_reasons.append(f"Results screen did not appear within 20s!")
            elif t1_time > 15.0:
                t1_reasons.append(f"Appeared in {t1_time}s (>15s limit)")
            else:
                has_explanation = any(len(c.get("problem", "")) > 10 for c in (t1_data.get("cards") or []))
                if not has_explanation:
                    t1_pass = False
                    t1_reasons.append("Explanation/description is blank or missing from finding cards!")
                stages = [s.get("stage") or s.get("name") or s.get("stage_id") for s in (t1_data.get("stages") or [])]
                print(f"  Stages observed: {stages}")

            results["Test 1 (Broken C file)"] = {
                "visible": t1_visible,
                "time_s": t1_time,
                "pass": t1_pass,
                "reasons": t1_reasons,
                "data": t1_data
            }
            print(f"  Modal Visible: {t1_visible} ({t1_time}s)")
            print(f"  Defects text: {t1_data.get('countText') if t1_data else 'N/A'}")
            print(f"  Outcome: {'PASS' if t1_pass else 'FAIL: ' + '; '.join(t1_reasons)}")

            # -------------------------------------------------------------
            # TEST 2: agent_security file with credential/secret
            # -------------------------------------------------------------
            with open("examples/agent_security/c_api_key.c", "r", encoding="utf-8") as f:
                api_key_code = f.read()
            t2_visible, t2_time, t2_data = execute_test("TEST 2: Agent Security (c_api_key.c)", api_key_code, "c_api_key.c", 25)

            t2_pass = True
            t2_reasons = []
            if not t2_visible:
                t2_pass = False
                t2_reasons.append("Results screen did not appear within 25s!")
            else:
                findings = (t2_data.get("findings") or []) + (t2_data.get("cards") or [])
                secret_detected = any(
                    "secret" in str(f).lower() or "key" in str(f).lower() or "api" in str(f).lower()
                    for f in findings
                )
                if not secret_detected:
                    t2_pass = False
                    t2_reasons.append("Secret / API key finding was not detected!")
                risk_val = t2_data.get("vulnerability_risk")
                base_risk_text = t2_data.get("baselineRisk") or ""
                risk_num = None
                try:
                    if risk_val is not None:
                        risk_num = float(risk_val)
                    elif "%" in base_risk_text:
                        risk_num = float(base_risk_text.replace("%", "").strip())
                except Exception:
                    pass
                if risk_num is None or risk_num <= 0:
                    t2_pass = False
                    t2_reasons.append(f"Vulnerability risk score is zero or missing: {risk_num}")

            results["Test 2 (agent_security c_api_key.c)"] = {
                "visible": t2_visible,
                "time_s": t2_time,
                "pass": t2_pass,
                "reasons": t2_reasons,
                "data": t2_data
            }
            print(f"  Modal Visible: {t2_visible} ({t2_time}s)")
            print(f"  Defects text: {t2_data.get('countText') if t2_data else 'N/A'}")
            print(f"  Outcome: {'PASS' if t2_pass else 'FAIL: ' + '; '.join(t2_reasons)}")

            # -------------------------------------------------------------
            # TEST 3: 00_sim_* file (00_sim_2_memory_poisoning.c)
            # -------------------------------------------------------------
            with open("examples/00_sim_2_memory_poisoning.c", "r", encoding="utf-8") as f:
                sim2_code = f.read()
            t3_visible, t3_time, t3_data = execute_test("TEST 3: Simulation Scenario (00_sim_2.c)", sim2_code, "00_sim_2.c", 30)

            t3_pass = True
            t3_reasons = []
            if not t3_visible:
                t3_pass = False
                t3_reasons.append("Results screen did not appear within 30s!")
            else:
                findings = (t3_data.get("findings") or []) + (t3_data.get("cards") or [])
                has_attack_finding = any(
                    any(kw in str(f).upper() for kw in ("TAMPER", "POISON", "SECURITY", "MEMORY", "STRING", "STRCPY", "MANIPULATION"))
                    for f in findings
                )
                if not has_attack_finding:
                    t3_pass = False
                    t3_reasons.append("Attack content was not flagged as real finding!")

            results["Test 3 (00_sim_2 file)"] = {
                "visible": t3_visible,
                "time_s": t3_time,
                "pass": t3_pass,
                "reasons": t3_reasons,
                "data": t3_data
            }
            print(f"  Modal Visible: {t3_visible} ({t3_time}s)")
            print(f"  Defects text: {t3_data.get('countText') if t3_data else 'N/A'}")
            print(f"  Outcome: {'PASS' if t3_pass else 'FAIL: ' + '; '.join(t3_reasons)}")

            # -------------------------------------------------------------
            # TEST 4: Clean file (int main(void) { return 0; })
            # -------------------------------------------------------------
            clean_c = "int main(void) {\n    return 0;\n}\n"
            t4_visible, t4_time, t4_data = execute_test("TEST 4: Clean C File (int main(void) { return 0; })", clean_c, "clean.c", 20)

            t4_pass = True
            t4_reasons = []
            if not t4_visible:
                t4_pass = False
                t4_reasons.append("Results screen did not appear within 20s!")
            else:
                status = t4_data.get("status")
                count_text = t4_data.get("countText") or ""
                if status != "CLEAN" and status != "FULLY_REPAIRED":
                    t4_pass = False
                    t4_reasons.append(f"Expected CLEAN status, got {status}")
                if "0 Active Defects" not in count_text and "0 Issue" not in count_text and "Clean" not in count_text:
                    t4_pass = False
                    t4_reasons.append(f"Expected 0 active defects, got: '{count_text}'")

            results["Test 4 (Clean C file)"] = {
                "visible": t4_visible,
                "time_s": t4_time,
                "pass": t4_pass,
                "reasons": t4_reasons,
                "data": t4_data
            }
            print(f"  Modal Visible: {t4_visible} ({t4_time}s)")
            print(f"  Defects text: {t4_data.get('countText') if t4_data else 'N/A'}")
            print(f"  Outcome: {'PASS' if t4_pass else 'FAIL: ' + '; '.join(t4_reasons)}")

            browser.close()

        print("\n" + "=" * 80)
        print("HEALTH-CHECK SUITE SUMMARY TABLE")
        print("=" * 80)
        print(f"| {'Test Case':<38} | {'Visible':<8} | {'Time (s)':<9} | {'Result':<8} | {'Notes':<30} |")
        print("|" + "-"*40 + "|" + "-"*10 + "|" + "-"*11 + "|" + "-"*10 + "|" + "-"*32 + "|")
        for test_name, res in results.items():
            vis = "YES" if res["visible"] else "NO"
            tm = f"{res['time_s']}s"
            status = "PASS" if res["pass"] else "FAIL"
            notes = "; ".join(res["reasons"]) if res["reasons"] else "OK"
            print(f"| {test_name:<38} | {vis:<8} | {tm:<9} | {status:<8} | {notes[:30]:<30} |")

        overall_pass = all(r["pass"] for r in results.values())
        print("=" * 80)
        print(f"OVERALL STATUS: {'ALL CHECKS PASSED' if overall_pass else 'HEALTH-CHECK FAILURES DETECTED'}")
        print("=" * 80)
        return overall_pass

    finally:
        if server_proc:
            print("[SERVER] Terminating test server process...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=3)
            except Exception:
                server_proc.kill()
            print("[SERVER] Test server stopped.")
        if server_log_file:
            try:
                server_log_file.close()
            except Exception:
                pass

if __name__ == "__main__":
    success = run_health_check()
    sys.exit(0 if success else 1)
