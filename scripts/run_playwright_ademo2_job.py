import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
from playwright.sync_api import sync_playwright
from compiler.patch_validator import SandboxedCompiler

def run_playwright_ademo2():
    with open("examples/week11_testing/ademo2.c", "r", encoding="utf-8") as f:
        ademo2_code = f.read()

    print("Launching Chromium browser via Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Navigating to http://127.0.0.1:5000 ...")
        page.goto("http://127.0.0.1:5000")
        page.wait_for_selector("#btn-run", timeout=15000)

        # Set code in editor
        page.evaluate("""(code) => {
            currentLanguageId = "c";
            currentFilename = "ademo2.c";
            openFiles["ademo2.c"] = code;
            if (editor) {
                editor.setValue(code);
            }
        }""", ademo2_code)

        # 1. Assert progress text changes - read initial text BEFORE triggering repair
        initial_progress_text = page.inner_text("#repairProgressText")
        print(f"Initial progress text: '{initial_progress_text}'", flush=True)

        print("Triggering runRepair() from UI (non-blocking async schedule)...", flush=True)
        page.evaluate("() => { setTimeout(runRepair, 10); }")

        # Track progress changes and poll raw job status every 10 seconds
        print("\n=== RAW JOB STATUS OVER TIME (EVERY 10 SECONDS) ===", flush=True)
        t_start = time.perf_counter()
        last_log_t = 0
        progress_text_changed = False
        prev_progress = initial_progress_text

        while True:
            time.sleep(1.0)
            elapsed = time.perf_counter() - t_start

            # Read UI progress
            current_progress = page.inner_text("#repairProgressText")
            if current_progress != prev_progress and not progress_text_changed:
                progress_text_changed = True
                print(f"[{elapsed:.1f}s] Progress text changed: '{current_progress}'", flush=True)
                prev_progress = current_progress

            # Read active repair job ID from JS context
            job_id = page.evaluate("() => typeof activeRepairJobId !== 'undefined' ? activeRepairJobId : null")
            job_state = page.evaluate("() => typeof isRepairRunning !== 'undefined' ? isRepairRunning : false")

            # Every 10 seconds, log raw job status fields
            if elapsed - last_log_t >= 10.0:
                last_log_t = elapsed
                if job_id:
                    job_data = page.evaluate("""(jid) => {
                        return fetch('/api/repair/job/' + jid)
                            .then(r => r.json())
                            .catch(e => ({ error: e.toString() }));
                    }""", job_id)
                    print(f"[{elapsed:.1f}s] Raw Job Status: {job_data}", flush=True)
                else:
                    print(f"[{elapsed:.1f}s] Waiting for job start... UI text: '{current_progress}'", flush=True)

            # Check if job completed
            is_running = page.evaluate("() => isRepairRunning")
            plan = page.evaluate("() => typeof currentCoordinatedPlan !== 'undefined' ? currentCoordinatedPlan : null")

            if not is_running and plan:
                print(f"[{elapsed:.1f}s] Job completed!", flush=True)
                break

            if elapsed > 300: # 5 min safety cap
                print("Playwright timeout exceeded.", flush=True)
                break

        # Verification asserts
        assert progress_text_changed, "UI Progress text must change during execution!"
        assert plan is not None, "A coordinated repair plan must be produced!"

        proposed_code = plan.get("proposed_code") or ""
        compiler = SandboxedCompiler()
        from compiler.patch_validator import ensure_c_libc_headers
        compiles, out, _ = compiler.compile_check(ensure_c_libc_headers(proposed_code))
        assert compiles, f"Result must compile with gcc! Errors: {out[:500]}"

        stopping_reason = plan.get("stopping_reason", "none")
        print(f"\nPlan Stopping Reason: '{stopping_reason}'", flush=True)
        assert "budget" not in stopping_reason.lower(), f"Stopping reason must NOT be a time budget! Got: '{stopping_reason}'"

        status = plan.get("status") or plan.get("terminal_status") or "UNKNOWN"
        windows_by_tier = plan.get("windows_by_tier") or plan.get("accepted_by_tier") or {}
        total_time_s = round(elapsed, 2)

        print("\n=== FINAL RESULT SUMMARY ===", flush=True)
        print(f"Status: {status}", flush=True)
        print(f"Compiles: {'YES' if compiles else 'NO'}", flush=True)
        print(f"Windows by Tier: {windows_by_tier}", flush=True)
        print(f"Total Seconds: {total_time_s}s", flush=True)
        print(f"Stopping Reason: {stopping_reason}", flush=True)

        browser.close()

if __name__ == "__main__":
    run_playwright_ademo2()
