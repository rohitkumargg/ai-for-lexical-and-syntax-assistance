"""
tests/e2e/test_p2_run_button_all.py

Playwright E2E tests for the Run button behavior:
1. Verifies #btn-run-program executes programs and resets correctly.
2. Verifies button never stays stuck disabled.
3. Verifies switching problems / files does not disable or break the run button.
4. Verifies security gate modal interception and post-continue execution.
5. Verifies zero uncaught JavaScript console exceptions.
"""

import json
import pytest
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5000"


def set_code(page, code_str: str, lang_id: str = "c"):
    if lang_id == "python":
        page.evaluate("switchLanguage('python')")
    else:
        page.evaluate("switchLanguage('c')")
    page.wait_for_timeout(300)
    page.evaluate(f"editor.setValue({json.dumps(code_str)})")
    page.wait_for_timeout(300)


def test_p2_run_button_clean_c():
    """Assert Run button executes clean C code, outputs result, and resets button state."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(str(err)))

        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector("#editor", timeout=10000)
        page.wait_for_function("() => window.editor !== undefined")

        clean_c = '#include <stdio.h>\nint main() { printf("P2_CLEAN_C_PASSED\\n"); return 0; }\n'
        set_code(page, clean_c, "c")

        btn = page.locator("#btn-run-program")
        assert btn.is_visible()
        assert btn.is_enabled()

        btn.click()

        # Wait for execution to finish and button to reset
        page.wait_for_function(
            "() => (document.getElementById('prog-status-text')?.innerText || '').toLowerCase().includes('completed') || "
            "(document.getElementById('prog-stdout')?.textContent || '').includes('P2_CLEAN_C_PASSED')",
            timeout=20000
        )

        # Button must be enabled and ready
        assert btn.is_enabled(), "Run button remained disabled after execution"
        assert len(js_errors) == 0, f"Uncaught JS errors: {js_errors}"

        browser.close()


def test_p2_run_button_clean_python():
    """Assert Run button executes Python code and resets state."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(str(err)))

        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector("#editor", timeout=10000)
        page.wait_for_function("() => window.editor !== undefined")

        clean_py = 'print("P2_PYTHON_OUTPUT_123")\n'
        set_code(page, clean_py, "python")

        btn = page.locator("#btn-run-program")
        btn.click()

        page.wait_for_function(
            "() => (document.getElementById('prog-status-text')?.innerText || '').toLowerCase().includes('completed') || "
            "(document.getElementById('prog-stdout')?.textContent || '').includes('P2_PYTHON_OUTPUT_123')",
            timeout=20000
        )
        assert btn.is_enabled(), "Run button remained disabled after Python execution"
        assert len(js_errors) == 0, f"Uncaught JS errors: {js_errors}"

        browser.close()


def test_p2_run_button_problem_switching():
    """
    Regression test: switching between problems/examples must never disable
    or break the Run button.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(str(err)))

        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector("#editor", timeout=10000)
        page.wait_for_function("() => window.editor !== undefined")

        btn = page.locator("#btn-run-program")

        # 1. First program
        set_code(page, "int main() { return 1; }\n", "c")
        btn.click()
        page.wait_for_function(
            "() => !document.getElementById('btn-run-program').disabled",
            timeout=15000
        )
        assert btn.is_enabled()

        # 2. Switch problem / change code
        set_code(page, '#include <stdio.h>\nint main() { printf("switched\\n"); return 0; }\n', "c")
        page.wait_for_timeout(500)
        assert btn.is_enabled(), "Run button became disabled upon problem switch"

        # 3. Click run on switched problem
        btn.click()
        page.wait_for_function(
            "() => !document.getElementById('btn-run-program').disabled",
            timeout=15000
        )
        assert btn.is_enabled(), "Run button stuck after running switched problem"
        assert len(js_errors) == 0, f"Uncaught JS errors: {js_errors}"

        browser.close()


def test_p2_run_button_security_gate_continue():
    """Assert security finding displays warning modal, Continue anyway proceeds, and button resets."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(str(err)))

        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector("#editor", timeout=10000)
        page.wait_for_function("() => window.editor !== undefined")

        # Code with gets()
        vulnerable_code = '#include <stdio.h>\nint main() {\n    char buf[16];\n    gets(buf);\n    return 0;\n}\n'
        set_code(page, vulnerable_code, "c")

        btn = page.locator("#btn-run-program")
        btn.click()

        # Security modal must pop up
        page.wait_for_selector("#security-approval-modal", state="visible", timeout=6000)

        # Verify Continue button exists and is clickable
        approve_btn = page.locator("#sec-btn-approve")
        assert approve_btn.is_visible()
        assert approve_btn.is_enabled()

        # Click Continue anyway
        approve_btn.click()

        # Modal should close
        page.wait_for_function("() => document.getElementById('security-approval-modal').style.display === 'none'", timeout=5000)

        # Wait for execution
        page.wait_for_function(
            "() => !document.getElementById('btn-run-program').disabled",
            timeout=15000
        )

        # Run button must be enabled and ready
        assert btn.is_enabled(), "Run button stuck disabled after security continue"
        assert len(js_errors) == 0, f"Uncaught JS errors: {js_errors}"

        browser.close()
