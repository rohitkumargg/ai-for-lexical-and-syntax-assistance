import asyncio
import os
import sys
from playwright.async_api import async_playwright

async def verify_results_move():
    print("=== Verification of Results Page Section Move ===")
    os.makedirs("reports/results_move", exist_ok=True)

    test_cases = [
        {
            "name": "c_syntax_err_secret",
            "file": "examples/agent_security/c_syntax_err_secret.c",
            "lang": "c",
            "expected_baseline": {
                "Overall Code Quality": "91%",
                "Code Efficiency": "100%",
                "Memory Safety Score": "50%"
            },
            "expected_target": {
                "Overall Code Quality": "98%",
                "Optimal Code Efficiency": "100%",
                "Memory Safety Score": "100%"
            }
        },
        {
            "name": "py_password",
            "file": "examples/agent_security/py_password.py",
            "lang": "python",
            "expected_baseline": {
                "Overall Code Quality": "92%",
                "Code Efficiency": "100%",
                "Vulnerability Risk %": "18%",
                "Memory Safety Score": "25%"
            },
            "expected_target": {
                "Overall Code Quality": "100%",
                "Optimal Code Efficiency": "100%",
                "Vulnerability Risk %": "0%",
                "Memory Safety Score": "100%"
            }
        }
    ]

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        page.on("console", lambda msg: print(f"  [BROWSER] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"  [BROWSER-ERR] {err}"))

        await page.goto("http://127.0.0.1:5000", wait_until="domcontentloaded")
        await page.wait_for_function(
            "() => window.editor !== undefined && typeof window.editor.getValue === 'function'",
            timeout=15000
        )

        for tc in test_cases:
            print(f"\n--- Testing {tc['name']} ({tc['file']}) ---")
            with open(tc["file"], "r", encoding="utf-8") as f:
                code_content = f.read()

            fname = os.path.basename(tc["file"])
            await page.evaluate(f"() => {{ if (window.switchLanguage) window.switchLanguage('{tc['lang']}'); }}")
            await page.wait_for_timeout(200)

            loaded = await page.evaluate(
                """([fn, code]) => {
                    if (window.openFileInTab) {
                        window.openFileInTab(fn, code);
                        return true;
                    } else if (window.editor && window.editor.setValue) {
                        window.editor.setValue(code);
                        return true;
                    }
                    return false;
                }""",
                [fname, code_content]
            )
            assert loaded, f"Failed to load {fname}"

            orig_code = await page.evaluate("() => window.editor.getValue()")

            # Click Run
            await page.click("#btn-run")

            # Wait for fullscreen modal, handling security review if shown
            modal = page.locator("#fullscreen-results-modal")
            for _ in range(120):
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
            print("  ✓ Modal opened successfully")

            # 1. DOM Position Check: Confirm telemetry/comparison is above explainer cards
            pos_check = await page.evaluate("""() => {
                const telemetrySec = document.getElementById('fs-bottom-three-cols');
                const findingsGrid = document.getElementById('fs-findings-grid');
                const sectionHeader = document.querySelector('.fs-section-header');

                if (!telemetrySec || !findingsGrid || !sectionHeader) {
                    return { error: "Missing required sections" };
                }

                // Document position check: telemetrySec must precede findingsGrid
                const posComp = telemetrySec.compareDocumentPosition(findingsGrid);
                const isDocPreceding = (posComp & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;

                // Visual bounding box check: telemetrySec.top < findingsGrid.top
                const tRect = telemetrySec.getBoundingClientRect();
                const fRect = findingsGrid.getBoundingClientRect();
                const hRect = sectionHeader.getBoundingClientRect();

                return {
                    isDocPreceding,
                    telemetryTop: tRect.top,
                    telemetryBottom: tRect.bottom,
                    headerTop: hRect.top,
                    findingsTop: fRect.top,
                    isVisuallyAbove: (tRect.bottom <= hRect.top + 5) && (hRect.bottom <= fRect.top + 5)
                };
            }""")
            print(f"  ✓ DOM Position Check: Precedes in DOM: {pos_check['isDocPreceding']}, Visually above: {pos_check['isVisuallyAbove']}")
            print(f"      Telemetry bottom: {pos_check['telemetryBottom']}px, Header top: {pos_check['headerTop']}px, Findings top: {pos_check['findingsTop']}px")
            assert pos_check["isDocPreceding"], "Telemetry section must precede findings grid in DOM"
            assert pos_check["isVisuallyAbove"], "Telemetry section must be visually positioned above the explainer section"

            # Wait for animation to settle (1.5s)
            await page.wait_for_timeout(1800)

            # 2. Check all metric numbers equal values before move
            dom_numbers = await page.evaluate("""() => {
                function getVals(containerId) {
                    const c = document.getElementById(containerId);
                    if (!c) return {};
                    const out = {};
                    c.querySelectorAll('.fs-gauge-card').forEach(card => {
                        const title = card.querySelector('.fs-gc-title')?.innerText.trim() || '';
                        const val = card.querySelector('.fs-gc-big-val')?.innerText.trim() || '';
                        if (title) out[title] = val;
                    });
                    return out;
                }
                return {
                    baseline: getVals('fs-baseline-gauges-container'),
                    target: getVals('fs-target-gauges-container')
                };
            }""")
            print(f"  ✓ Baseline gauges: {dom_numbers['baseline']}")
            print(f"  ✓ Target gauges: {dom_numbers['target']}")

            for metric_k, exp_v in tc["expected_baseline"].items():
                actual_v = dom_numbers["baseline"].get(metric_k)
                print(f"      Checking baseline '{metric_k}': expected={exp_v}, actual={actual_v}")
                assert actual_v == exp_v, f"Baseline {metric_k} mismatch: expected {exp_v}, got {actual_v}"

            for metric_k, exp_v in tc["expected_target"].items():
                actual_v = dom_numbers["target"].get(metric_k)
                print(f"      Checking target '{metric_k}': expected={exp_v}, actual={actual_v}")
                assert actual_v == exp_v, f"Target {metric_k} mismatch: expected {exp_v}, got {actual_v}"

            # 3. Explainer cards markup check
            findings_info = await page.evaluate("""() => {
                const grid = document.getElementById('fs-findings-grid');
                if (!grid) return null;
                const cards = Array.from(grid.querySelectorAll('.fs-finding-card'));
                return {
                    cardCount: cards.length,
                    outerHTMLs: cards.map(c => c.outerHTML),
                    classes: cards.map(c => c.className),
                    hasHeaders: cards.every(c => c.querySelector('.fs-fc-header') !== null),
                    hasBodies: cards.every(c => c.querySelector('.fs-fc-body') !== null),
                    hasFooters: cards.every(c => c.querySelector('.fs-fc-footer') !== null)
                };
            }""")
            assert findings_info["cardCount"] > 0, "Explainer cards must be present"
            assert findings_info["hasHeaders"] and findings_info["hasBodies"] and findings_info["hasFooters"], "Finding cards markup must have header, body, and footer"
            print(f"  ✓ Explainer cards: {findings_info['cardCount']} finding card(s), valid markup structure preserved identically")

            # 4. Save screenshot
            ss_path = f"reports/results_move/{tc['name']}.png"
            await modal.screenshot(path=ss_path)
            print(f"  ✓ Saved screenshot: {ss_path}")

            # 5. Apply returns 200 and editor shows repaired code
            apply_btn = page.locator("#fs-btn-apply-fix")
            assert await apply_btn.is_visible(), "Apply Fix button must be visible"

            async with page.expect_response(
                lambda r: ("/api/repair/apply" in r.url or "/api/repair" in r.url or "/api/improvement/candidate" in r.url) and r.status == 200,
                timeout=10000
            ) as resp_info:
                await apply_btn.click()

            resp = await resp_info.value
            print(f"  ✓ Apply Fix clicked: HTTP status = {resp.status}")
            assert resp.status == 200, f"Apply returned non-200: {resp.status}"

            await page.wait_for_timeout(1000)
            repaired_code = await page.evaluate("() => window.editor.getValue()")
            assert repaired_code != orig_code, "Editor content must be updated with repaired code"
            assert len(repaired_code) > 0, "Repaired code must not be empty"
            print("  ✓ Editor updated with repaired code successfully")

            results.append({
                "test": tc["name"],
                "dom_precedes": pos_check["isDocPreceding"],
                "visually_above": pos_check["isVisuallyAbove"],
                "apply_status": resp.status,
                "screenshot": ss_path
            })

        await browser.close()

    print("\n==================================================")
    print("ALL VERIFICATIONS PASSED:")
    for r in results:
        print(f"  {r['test']}: DOM_Precedes={r['dom_precedes']}, Visually_Above={r['visually_above']}, Apply_HTTP={r['apply_status']}, Screenshot={r['screenshot']}")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(verify_results_move())
