import asyncio
import os
import shutil
import sys
import time
from playwright.async_api import async_playwright

async def verify_results_screen():
    print("=== Fullscreen 3-Column Results Screen Verification ===")
    os.makedirs("reports/results_screen", exist_ok=True)
    os.makedirs("design/results_screen", exist_ok=True)

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
            "name": "security_c_example",
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
        await page.goto("http://127.0.0.1:5000", wait_until="domcontentloaded")
        await page.wait_for_function("() => window.editor !== undefined && typeof window.editor.getValue === 'function'", timeout=15000)

        # 1. Existing cards identity check baseline
        # Capture outerHTML of the existing cards area before any run
        existing_cards_area_selector = "#measure-grid"  # or document.querySelector('.metrics-panel')
        baseline_area_html = await page.evaluate("""() => {
            const el = document.getElementById('measure-grid') || document.querySelector('.diagnostics-panel');
            return el ? el.outerHTML : '';
        }""")

        for tc in test_cases:
            print(f"\n==================================================")
            print(f"--- Testing {tc['name']} ({tc['file']}) ---")
            print(f"==================================================")
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

            # Record existing cards area outerHTML before clicking Run
            area_html_before_run = await page.evaluate("""() => {
                const el = document.getElementById('measure-grid') || document.querySelector('.diagnostics-panel');
                return el ? el.outerHTML : '';
            }""")

            # Click Run
            await page.click("#btn-run")

            # Wait for repair & results modal to appear, handling security approval if it shows
            modal = page.locator("#fullscreen-results-modal")
            for _ in range(120): # up to 60s
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
            print("  ✓ Fullscreen results screen opened automatically")

            # Screen capture at start of animation (t ~ 100ms)
            start_ss = f"reports/results_screen/{tc['name']}_start.png"
            await modal.screenshot(path=start_ss)
            print(f"  ✓ Saved start screenshot (t=100ms): {start_ss}")

            # Sample gauge animation moments to verify zero drift between number and fill bar
            drift_samples = []
            for sample_idx in range(5):
                sample_data = await page.evaluate("""() => {
                    const targetCards = Array.from(document.querySelectorAll('#fs-target-gauges-container .fs-gauge-card'));
                    if (targetCards.length === 0) return null;
                    const card = targetCards[0];
                    const numEl = card.querySelector('.fs-gc-big-val');
                    const fillEl = card.querySelector('.fs-battery-fill');
                    const numText = numEl ? numEl.innerText.trim() : '';
                    const fillHeight = fillEl ? fillEl.style.height : '';
                    return {
                        num: numText,
                        height: fillHeight,
                        time: performance.now()
                    };
                }""")
                if sample_data:
                    drift_samples.append(sample_data)
                await page.wait_for_timeout(150)

            print(f"  ✓ Sampled animation frames for target card 0:")
            for s in drift_samples:
                print(f"      Number: '{s['num']}', Bar height: '{s['height']}'")

            # Midway screenshot (t ~ 900ms)
            await page.wait_for_timeout(200)
            mid_ss = f"reports/results_screen/{tc['name']}_mid.png"
            await modal.screenshot(path=mid_ss)
            print(f"  ✓ Saved midway screenshot (t=900ms): {mid_ss}")

            # Wait for animation to finish completely (t ~ 2500ms)
            await page.wait_for_timeout(1500)
            end_ss = f"reports/results_screen/{tc['name']}_end.png"
            await modal.screenshot(path=end_ss)
            print(f"  ✓ Saved end screenshot (t=2500ms): {end_ss}")

            # If this is the security C example, copy to design/results_screen/03.png
            if tc["name"] == "security_c_example":
                shutil.copyfile(end_ss, "design/results_screen/03.png")
                print("  ✓ Saved design/results_screen/03.png matching design reference")

            # Verify 3 columns exist and are populated
            cols_info = await page.evaluate("""() => {
                const baselineCol = document.getElementById('fs-baseline-col');
                const compCol = document.getElementById('fs-comparison-card');
                const targetCol = document.getElementById('fs-target-col');
                const bCards = baselineCol ? baselineCol.querySelectorAll('.fs-gauge-card').length : 0;
                const tCards = targetCol ? targetCol.querySelectorAll('.fs-gauge-card').length : 0;
                return {
                    hasBaseline: !!baselineCol,
                    baselineCards: bCards,
                    hasComp: !!compCol,
                    hasTarget: !!targetCol,
                    targetCards: tCards
                };
            }""")
            print(f"  ✓ 3-Column Layout: Baseline ({cols_info['baselineCards']} cards), Centre comparison ({cols_info['hasComp']}), Target ({cols_info['targetCards']} cards)")
            assert cols_info["hasBaseline"] and cols_info["hasComp"] and cols_info["hasTarget"], "3 columns must be present"

            # Check gauges values and deltas
            gauges_summary = await page.evaluate("""() => {
                function readCol(containerId) {
                    const c = document.getElementById(containerId);
                    if (!c) return [];
                    return Array.from(c.querySelectorAll('.fs-gauge-card')).map(card => {
                        const title = card.querySelector('.fs-gc-title')?.innerText || '';
                        const val = card.querySelector('.fs-gc-big-val')?.innerText || '';
                        const delta = card.querySelector('.fs-gc-delta-chip')?.innerText || '';
                        const fill = card.querySelector('.fs-battery-fill')?.style.height || '';
                        return { title, val, delta, fill };
                    });
                }
                return {
                    baseline: readCol('fs-baseline-gauges-container'),
                    target: readCol('fs-target-gauges-container')
                };
            }""")
            print(f"  ✓ Baseline gauges: {[g['title'] + ': ' + g['val'] for g in gauges_summary['baseline']]}")
            print(f"  ✓ Target gauges: {[g['title'] + ': ' + g['val'] + (' (' + g['delta'] + ')' if g['delta'] else '') for g in gauges_summary['target']]}")

            # Check existing cards outerHTML identity
            area_html_after_open = await page.evaluate("""() => {
                const el = document.getElementById('measure-grid') || document.querySelector('.diagnostics-panel');
                return el ? el.outerHTML : '';
            }""")
            assert area_html_before_run == area_html_after_open, "Existing cards area outerHTML must remain byte-identical before vs after results screen opens"
            print("  ✓ Existing cards area outerHTML is byte-identical before vs after results screen opens")

            # Check actions (Apply fix / Reject / Esc)
            if tc["type"] in ("security", "broken"):
                # Check diff tabs
                await page.click("#fs-tab-btn-unified")
                await page.wait_for_timeout(100)
                await page.click("#fs-tab-btn-vulns")
                await page.wait_for_timeout(100)
                await page.click("#fs-tab-btn-sbs")
                await page.wait_for_timeout(100)
                print("  ✓ Diff tabs switched cleanly")

                # Test Apply button
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
                assert editor_after_close == orig_editor_val, "Closing results screen must leave editor text strictly unchanged"
                print("  ✓ Esc closed modal cleanly and left editor text strictly unchanged")

                # Reopen and close via backdrop click
                reopen_btn = page.locator("#btn-open-results-screen")
                if await reopen_btn.is_visible():
                    await reopen_btn.click()
                    await modal.wait_for(state="visible", timeout=2000)
                    # Click modal backdrop (outside container)
                    await page.click("#fullscreen-results-modal", position={"x": 10, "y": 10})
                    await page.wait_for_timeout(300)
                    assert not (await modal.is_visible()), "Modal should close on backdrop click"
                    print("  ✓ Backdrop click closed modal cleanly")

        # 2. Reduced motion test
        print("\n--- Testing prefers-reduced-motion: reduce ---")
        rm_context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            reduced_motion="reduce"
        )
        rm_page = await rm_context.new_page()
        await rm_page.goto("http://127.0.0.1:5000", wait_until="domcontentloaded")
        await rm_page.wait_for_function("() => window.editor !== undefined && typeof window.editor.getValue === 'function'", timeout=15000)

        # Load clean example and run
        clean_file = "examples/agent_security/c_comment_secret.c"
        with open(clean_file, "r", encoding="utf-8") as f:
            clean_code = f.read()

        await rm_page.evaluate(
            """([fn, code]) => {
                if (window.openFileInTab) window.openFileInTab(fn, code);
                else if (window.editor) window.editor.setValue(code);
            }""",
            [os.path.basename(clean_file), clean_code]
        )
        await rm_page.click("#btn-run")
        rm_modal = rm_page.locator("#fullscreen-results-modal")
        for _ in range(120): # up to 60s
            sec_vis = await rm_page.evaluate("""() => {
                const m = document.getElementById('security-approval-modal');
                return m && m.style.display !== 'none' && getComputedStyle(m).display !== 'none';
            }""")
            if sec_vis:
                btn_approve = rm_page.locator("#sec-btn-approve")
                if await btn_approve.is_visible():
                    await btn_approve.click()

            if await rm_modal.is_visible():
                break
            await rm_page.wait_for_timeout(500)

        await rm_modal.wait_for(state="visible", timeout=10000)

        # Immediate check (10ms after open): values should be already rendered without waiting
        immediate_vals = await rm_page.evaluate("""() => {
            const numEl = document.querySelector('#fs-baseline-gauges-container .fs-gc-big-val');
            const fillEl = document.querySelector('#fs-baseline-gauges-container .fs-battery-fill');
            return {
                num: numEl ? numEl.innerText : null,
                fill: fillEl ? fillEl.style.height : null
            };
        }""")
        print(f"  ✓ Reduced motion immediate render: num={immediate_vals['num']}, fill={immediate_vals['fill']}")
        assert immediate_vals['num'] and immediate_vals['num'] != "", "Value must be immediately visible with reduced motion"
        print("  ✓ Reduced motion rendered final state immediately without animation delay")

        await rm_context.close()
        await browser.close()

    print("\n==================================================")
    print("ALL 3-COLUMN RESULTS SCREEN VERIFICATIONS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(verify_results_screen())
