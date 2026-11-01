import json
import os
import pytest
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5000"
VALID_EXEC_STATUSES = ("COMPLETED", "RUNTIME ERROR", "COMPILATION FAILED", "TIMED OUT")


@pytest.fixture(scope="module")
def browser_context():
    os.makedirs("scratch", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector("#editor", timeout=10000)
        page.wait_for_function("() => window.editor !== undefined")
        yield page
        browser.close()


def set_code(page, code_str: str, lang_id: str = "c"):
    if lang_id == "python":
        page.evaluate("switchLanguage('python')")
    else:
        page.evaluate("switchLanguage('c')")
    page.wait_for_timeout(300)
    page.evaluate(f"editor.setValue({json.dumps(code_str)})")
    page.wait_for_timeout(300)


def test_e2e_c_vulnerable_warning_and_continue(browser_context):
    page = browser_context
    c_code = "#include <stdio.h>\nint main() {\n    char buf[16];\n    gets(buf);\n    return 0;\n}\n"
    set_code(page, c_code, "c")

    page.click("#btn-run-program")
    page.wait_for_selector("#security-approval-modal", state="visible", timeout=5000)
    assert page.evaluate("document.getElementById('security-approval-modal').style.display === 'flex'")

    # Verify modal contents
    title = page.inner_text("#sec-modal-title")
    assert "Security Review" in title
    findings_html = page.inner_html("#sec-findings-container")
    assert "gets" in findings_html

    # Continue anyway
    page.click("#sec-btn-approve")
    page.wait_for_function("() => document.getElementById('security-approval-modal').style.display === 'none'", timeout=5000)
    page.wait_for_function("() => !['evaluating', 'compiling'].some(s => document.getElementById('prog-status-text').innerText.toLowerCase().includes(s))", timeout=20000)

    page.screenshot(path="scratch/ui_after_1.png")
    assert page.evaluate("document.getElementById('security-approval-modal').style.display === 'none'")
    status_text = page.inner_text("#prog-status-text")
    assert status_text.upper() in VALID_EXEC_STATUSES


def test_e2e_python_vulnerable_warning_and_continue(browser_context):
    page = browser_context
    py_code = "print('Starting python test')\nx = eval('1 + 2')\nprint('Result:', x)\n"
    set_code(page, py_code, "python")

    page.click("#btn-run-program")
    page.wait_for_selector("#security-approval-modal", state="visible", timeout=5000)
    assert page.evaluate("document.getElementById('security-approval-modal').style.display === 'flex'")

    # Verify findings contain CWE and plain language reason
    findings_html = page.inner_html("#sec-findings-container")
    assert "CWE" in findings_html

    # Continue anyway
    page.click("#sec-btn-approve")
    page.wait_for_function("() => document.getElementById('security-approval-modal').style.display === 'none'", timeout=5000)
    page.wait_for_function("() => !['evaluating', 'compiling'].some(s => document.getElementById('prog-status-text').innerText.toLowerCase().includes(s))", timeout=20000)

    page.screenshot(path="scratch/ui_after_2.png")
    assert page.evaluate("document.getElementById('security-approval-modal').style.display === 'none'")
    status_text = page.inner_text("#prog-status-text")
    assert status_text.upper() in VALID_EXEC_STATUSES


def test_e2e_manipulation_directive_warning_and_continue(browser_context):
    page = browser_context
    with open("examples/untitled1.c", "r", encoding="utf-8") as f:
        untitled1_code = f.read()
    set_code(page, untitled1_code, "c")

    page.click("#btn-run-program")
    page.wait_for_selector("#security-approval-modal", state="visible", timeout=5000)
    assert page.evaluate("document.getElementById('security-approval-modal').style.display === 'flex'")

    # Check for manipulation callouts showing flagged text and reason
    callout_count = page.evaluate("document.querySelectorAll('.sec-manipulation-callout').length")
    assert callout_count > 0

    # Continue anyway
    page.click("#sec-btn-approve")
    page.wait_for_function("() => document.getElementById('security-approval-modal').style.display === 'none'", timeout=5000)
    page.wait_for_function("() => !document.getElementById('prog-status-text').innerText.toLowerCase().includes('evaluating')", timeout=15000)

    page.screenshot(path="scratch/ui_after_3.png")
    assert page.evaluate("document.getElementById('security-approval-modal').style.display === 'none'")
    status_text = page.inner_text("#prog-status-text")
    assert status_text.upper() in VALID_EXEC_STATUSES


def test_e2e_clean_code_never_shows_modal(browser_context):
    page = browser_context
    clean_code = "#include <stdio.h>\nint main() {\n    printf(\"Hello Clean World!\\n\");\n    return 0;\n}\n"
    set_code(page, clean_code, "c")

    page.click("#btn-run-program")
    page.wait_for_function("() => !document.getElementById('prog-status-text').innerText.toLowerCase().includes('evaluating')", timeout=15000)

    page.screenshot(path="scratch/ui_after_4.png")
    modal_visible = page.evaluate("document.getElementById('security-approval-modal').style.display === 'flex'")
    assert not modal_visible, "Modal should NEVER appear for clean code"
    status_text = page.inner_text("#prog-status-text")
    assert status_text.upper() in ("COMPLETED", "READY", "CLEAN", "0")


def test_e2e_cancel_aborts_without_execution(browser_context):
    page = browser_context
    c_code = "#include <stdio.h>\nint main() {\n    char buf[16];\n    gets(buf);\n    return 0;\n}\n"
    set_code(page, c_code, "c")

    page.click("#btn-run-program")
    page.wait_for_selector("#security-approval-modal", state="visible", timeout=5000)

    # Cancel
    page.click("#sec-btn-cancel")
    page.wait_for_function("() => document.getElementById('security-approval-modal').style.display === 'none'", timeout=5000)
    page.wait_for_timeout(500)

    page.screenshot(path="scratch/ui_after_5.png")
    assert page.evaluate("document.getElementById('security-approval-modal').style.display === 'none'")
    status_text = page.inner_text("#prog-status-text")
    assert status_text.upper() == "CANCELLED"


def test_e2e_token_expiry_reshows_modal(browser_context):
    page = browser_context
    c_code = "#include <stdio.h>\nint main() {\n    char buf[16];\n    gets(buf);\n    return 0;\n}\n"
    set_code(page, c_code, "c")

    # Call with an invalid/expired token
    page.evaluate("""() => {
        callWithGate('/api/program/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code: '#include <stdio.h>\\nint main() { char b[16]; gets(b); return 0; }',
                filename: 'main.c',
                language: 'c',
                operation: 'execute',
                approval_token: 'sec_tok_expired_9999999999'
            })
        });
    }""")
    page.wait_for_selector("#security-approval-modal", state="visible", timeout=5000)
    page.screenshot(path="scratch/ui_after_6.png")

    modal_visible = page.evaluate("document.getElementById('security-approval-modal').style.display === 'flex'")
    assert modal_visible, "Modal must automatically re-show upon expired/invalid token"

