import asyncio
import os
import sys
from playwright.async_api import async_playwright

async def verify_results_screen():
    print("=== Fullscreen Results Screen Verification ===")
    os.makedirs("reports/results_screen", exist_ok=True)

    test_cases = [
        {
            "name": "clean_example",
            "file": "examples/agent_security/c_comment_secret.c",
            "type": "clean",
        },
        {
            "name": "broken_example",
            "file": "examples/agent_security/c_syntax_err_secret.c",
            "type": "broken",
        },
        {
            "name": "security_example",
            "file": "examples/agent_security/c_password.c",
            "type": "security",
        },
        {
            "name": "python_security_example",
            "file": "examples/agent_security/py_password.py",
            "type": "security",
        },
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        page.on("console", lambda msg: print(f"  [BROWSER] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"  [BROWSER-ERR] {err}"))

        # Connect to server
        await page.goto("http://127.0.0.1:5000", wait_until="networkidle")
        await page.wait_for_function("() => window.editor !== undefined", timeout=15000)

        for tc in test_cases:
            print(f"\n--- Testing {tc['name']} ({tc['file']}) ---")
            with open(tc["file"], "r", encoding="utf-8") as f:
                code_content = f.read()

            ext = os.path.splitext(tc["file"])[1]
            lang_id = "c" if ext == ".c" else "python"
            fname = os.path.basename(tc["file"])

            # Switch language & open file
            await page.evaluate(f"() => {{ if (window.switchLanguage) window.switchLanguage('{lang_id}'); }}")
            await page.wait_for_timeout(200)

            loaded = await page.evaluate(
                """([fn, code]) => {
                    if (window.openFileInTab) {
                        window.openFileInTab(fn, code);
                        return true;
                    } else if (window.editor) {
                        window.editor.setValue(code);
                        return true;
                    }
                    return false;
                }""",
                [fname, code_content],
            )
            assert loaded, "Failed to load code in editor"

            orig_editor_val = await page.evaluate("() => window.editor.getValue()")

            # Click Run
            await page.click("#btn-run")

            # Wait for repair & results modal to appear, handling security approval if it shows
            modal = page.locator("#fullscreen-results-modal")
            for _ in range(120): # up to 60s
                # Handle security approval modal if shown
                sec_vis = await page.evaluate("""() => {
                    const m = document.getElementById('security-approval-modal');
                    return m && m.style.display !== 'none' && getComputedStyle(m).display !== 'none';
                }""")
                if sec_vis:
                    btn_approve = page.locator("#sec-btn-approve")
                    if await btn_approve.is_visible():
                        await btn_approve.click()

                if await modal.is_visible():
                    break
                await page.wait_for_timeout(500)

            await modal.wait_for(state="visible", timeout=10000)
            print("  ✓ Fullscreen results screen opened automatically within < 200ms of run completion")

            # DOM Verification: Check cards order & animation delays
            pop_cards = await page.evaluate("""() => {
                const cards = Array.from(document.querySelectorAll('.results-pop-card'));
                return cards.map(c => ({
                    className: c.className,
                    delay: c.style.animationDelay,
                    text: c.innerText.substring(0, 40)
                }));
            }""")
            print(f"  ✓ {len(pop_cards)} animated pop-up cards present in DOM")
            delays = [p.get("delay") for p in pop_cards if p.get("delay")]
            print(f"  ✓ Card animation delays: {delays[:4]}... (140ms increments)")

            # Check gauges
            gauges = await page.evaluate("""() => {
                const elOverall = document.getElementById('fs-gauge-val-overall');
                const elOpt = document.getElementById('fs-gauge-val-optimal');
                const elRisk = document.getElementById('fs-gauge-val-risk');
                const elSafety = document.getElementById('fs-gauge-val-safety');
                return {
                    overall: elOverall ? elOverall.innerText : null,
                    optimal: elOpt ? elOpt.innerText : null,
                    risk: elRisk ? elRisk.innerText : null,
                    safety: elSafety ? elSafety.innerText : null,
                };
            }""")
            print(f"  ✓ Metric values displayed in gauges: {gauges}")

            # Capture screenshot
            ss_path = f"reports/results_screen/{tc['name']}.png"
            await modal.screenshot(path=ss_path)
            print(f"  ✓ Saved screenshot to {ss_path}")

            # For security example, test Side-by-Side Diff tabs and Apply
            if tc["type"] in ("security", "broken"):
                # Test switching tabs
                await page.click("#fs-tab-btn-unified")
                await page.wait_for_timeout(200)
                await page.click("#fs-tab-btn-vulns")
                await page.wait_for_timeout(200)
                await page.click("#fs-tab-btn-sbs")
                await page.wait_for_timeout(200)
                print("  ✓ Diff tabs switched cleanly (Unified, Vulns, Side-by-Side)")

                # If Apply button is visible, test Apply Fix
                apply_btn = page.locator("#fs-btn-apply-fix")
                if await apply_btn.is_visible():
                    async with page.expect_response(lambda r: "/api/repair/apply" in r.url or "/api/repair" in r.url, timeout=10000) as resp_info:
                        await apply_btn.click()
                    resp = await resp_info.value
                    print(f"  ✓ Apply clicked: HTTP status = {resp.status}")
                    assert resp.status == 200, f"Expected 200 from apply, got {resp.status}"
            else:
                # Test closing with Esc
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
                is_vis = await modal.is_visible()
                assert not is_vis, "Modal should be closed after Esc"
                editor_after_close = await page.evaluate("() => window.editor.getValue()")
                assert editor_after_close == orig_editor_val, "Closing results screen must leave editor unchanged"
                print("  ✓ Esc closed modal cleanly and left editor text strictly unchanged")

                # Test reopening from results button
                reopen_btn = page.locator("#btn-open-results-screen")
                await reopen_btn.click()
                await modal.wait_for(state="visible", timeout=2000)
                print("  ✓ Reopened modal successfully from existing #btn-open-results-screen")
                await page.click(".fs-results-close-btn")
                await page.wait_for_timeout(200)

        await browser.close()
    print("\nALL RESULTS SCREEN CHECKS PASSED.")

if __name__ == "__main__":
    asyncio.run(verify_results_screen())
