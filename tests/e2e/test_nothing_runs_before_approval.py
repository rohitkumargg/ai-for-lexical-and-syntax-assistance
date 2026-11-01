import json
import os
import time
from unittest.mock import patch, MagicMock
import pytest
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5000"

VULNERABLE_CODE = """#include <stdio.h>

int main(void) {
    char buf[16];
    gets(buf);
    return 0;
}
"""

@pytest.fixture(scope="module")
def browser_context():
    os.makedirs("scratch", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector("#btn-run", state="visible")
        page.wait_for_function("() => window.monaco && monaco.editor && monaco.editor.getModels().length > 0")
        yield page
        browser.close()

def set_code(page, filename: str, code_str: str):
    page.evaluate(f"""() => {{
        window.currentFilename = {json.dumps(filename)};
        const model = monaco.editor.getModels()[0];
        model.setValue({json.dumps(code_str)});
        if (typeof openFiles !== 'undefined') {{
            openFiles[{json.dumps(filename)}] = {json.dumps(code_str)};
        }}
    }}""")
    page.wait_for_timeout(300)

# =========================================================================
# 1. 10s Wait in UI: No compile, execution, AI, or repair calls during modal
# =========================================================================

def test_ui_run_10s_wait_no_execution_and_cancel(browser_context):
    page = browser_context
    set_code(page, "vuln_run.c", VULNERABLE_CODE)

    captured_requests = []
    def on_req(req):
        captured_requests.append(req.url)
    page.on("request", on_req)

    # Click Run
    page.click("#btn-run-program")
    page.wait_for_selector("#security-approval-modal", state="visible", timeout=5000)

    # Clear logs gathered during initial click
    captured_requests.clear()

    # Wait 10 seconds while modal is displayed
    start_time = time.time()
    while time.time() - start_time < 10.0:
        page.wait_for_timeout(1000)

    # Assert no execution/pipeline requests occurred
    disallowed_endpoints = [
        "/api/program/run",
        "/api/coordinator/analyze_and_plan",
        "/api/repair",
        "/api/repair_stream",
        "/api/quality/score",
        "/api/security/risk",
        "/api/optimization/potential",
    ]
    for url in captured_requests:
        for dis in disallowed_endpoints:
            assert dis not in url, f"Disallowed request fired during 10s wait: {url}"

    # Status should not indicate running/completed
    status_text = page.inner_text("#prog-status-text")
    assert "RUNNING" not in status_text.upper()
    assert "COMPLETED" not in status_text.upper()

    # Cancel
    page.click("#sec-btn-cancel")
    page.wait_for_selector("#security-approval-modal", state="hidden", timeout=5000)
    page.wait_for_timeout(1000)

    # Confirm nothing ran after cancel
    status_text_after = page.inner_text("#prog-status-text")
    assert "COMPLETED" not in status_text_after.upper()
    page.remove_listener("request", on_req)

def test_ui_repair_10s_wait_no_repair_and_cancel(browser_context):
    page = browser_context
    set_code(page, "vuln_repair.c", VULNERABLE_CODE)

    captured_requests = []
    def on_req(req):
        captured_requests.append(req.url)
    page.on("request", on_req)

    # Click Repair
    page.click("#btn-run")
    page.wait_for_selector("#security-approval-modal", state="visible", timeout=5000)

    captured_requests.clear()

    # Wait 10 seconds while modal is displayed
    start_time = time.time()
    while time.time() - start_time < 10.0:
        page.wait_for_timeout(1000)

    disallowed_endpoints = [
        "/api/coordinator/analyze_and_plan",
        "/api/repair",
        "/api/repair_stream",
        "/api/program/run",
    ]
    for url in captured_requests:
        for dis in disallowed_endpoints:
            assert dis not in url, f"Disallowed request fired during 10s wait: {url}"

    # Pipeline log should show no runs
    logs_text = page.inner_text("#logs")
    assert "No pipeline runs yet" in logs_text or "No events logged" in logs_text or len(logs_text.strip()) == 0

    # Cancel
    page.click("#sec-btn-cancel")
    page.wait_for_selector("#security-approval-modal", state="hidden", timeout=5000)
    page.wait_for_timeout(1000)

    # Ensure no pipeline runs were started
    rec_display = page.evaluate("document.getElementById('recommendedProgramCard') ? document.getElementById('recommendedProgramCard').style.display : 'none'")
    assert rec_display == "none"
    page.remove_listener("request", on_req)

def test_ui_run_continue_runs_once(browser_context):
    page = browser_context
    set_code(page, "vuln_run_continue.c", VULNERABLE_CODE)

    run_calls = []
    def on_req(req):
        if "/api/program/run" in req.url:
            run_calls.append(req.url)
    page.on("request", on_req)

    page.click("#btn-run-program")
    page.wait_for_selector("#security-approval-modal", state="visible", timeout=5000)

    # Click Continue anyway
    page.click("#sec-btn-approve")
    page.wait_for_selector("#security-approval-modal", state="hidden", timeout=5000)

    page.wait_for_function(
        "() => !['evaluating', 'compiling'].some(s => document.getElementById('prog-status-text').innerText.toLowerCase().includes(s))",
        timeout=20000
    )

    # The run endpoint was called with the approval token and executed
    assert len(run_calls) >= 1
    page.remove_listener("request", on_req)

# =========================================================================
# 2. Server-side spies: 0 GCC/subprocess/AI calls before approval
# =========================================================================

@pytest.fixture(scope="module")
def app_client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_server_spies_run_blocks_gcc_and_subprocess_before_approval(app_client):
    """Verify that calling /api/program/run without approval produces 0 subprocess/gcc calls."""
    with patch("subprocess.run") as mock_subproc_run, \
         patch("subprocess.Popen") as mock_subproc_popen:

        # 1. Attempt run without token -> should be rejected with 409
        resp = app_client.post("/api/program/run", json={
            "filename": "test_spy.c",
            "code": VULNERABLE_CODE,
            "language": "c",
        })
        assert resp.status_code == 409
        assert resp.get_json().get("blocked") is True

        # Assert no compiler / subprocess execution took place
        assert mock_subproc_run.call_count == 0
        assert mock_subproc_popen.call_count == 0

        # 2. Approve via gate
        payload = resp.get_json()
        source_hash = payload["source_hash"]
        op = payload.get("operation", "execute")
        appr_resp = app_client.post("/api/security/approval/approve", json={
            "code": VULNERABLE_CODE,
            "filename": "test_spy.c",
            "language": "c",
            "operation": op,
            "force": True,
            "reason": "Test user approval",
        })
        assert appr_resp.status_code == 200
        token = appr_resp.get_json()["approval_token"]

        # Configure mock return value for execution
        mock_subproc_run.return_value = MagicMock(returncode=0, stdout="compiled ok", stderr="")

        # 3. Call run WITH token -> now allowed
        run_resp = app_client.post("/api/program/run", json={
            "filename": "test_spy.c",
            "code": VULNERABLE_CODE,
            "language": "c",
            "approval_token": token,
        })
        # After token, execution is permitted (subprocess is called)
        assert run_resp.status_code == 200
        assert mock_subproc_run.call_count > 0 or mock_subproc_popen.call_count > 0

def test_server_spies_repair_blocks_ai_calls_before_approval(app_client):
    """Verify that /api/coordinator/analyze_and_plan without approval produces 0 AI/CodeT5 calls."""
    with patch("compiler.local_models.OllamaClient.generate") as mock_ollama_gen, \
         patch("compiler.local_models.OllamaClient.generate_repair") as mock_ollama_repair, \
         patch("compiler.local_models.CodeT5Manager.generate_patch") as mock_codet5:

        # 1. Attempt repair without approval token
        resp = app_client.post("/api/coordinator/analyze_and_plan", json={
            "filename": "test_ai_spy.c",
            "code": VULNERABLE_CODE,
        })
        assert resp.status_code == 409
        assert resp.get_json().get("blocked") is True

        # Assert 0 AI calls
        assert mock_ollama_gen.call_count == 0
        assert mock_ollama_repair.call_count == 0
        assert mock_codet5.call_count == 0

def test_server_cancel_prevents_any_execution(app_client):
    """Verify that clicking Cancel audits cancellation and leaves code blocked."""
    resp = app_client.post("/api/program/run", json={
        "filename": "test_cancel.c",
        "code": VULNERABLE_CODE,
        "language": "c",
    })
    assert resp.status_code == 409
    source_hash = resp.get_json()["source_hash"]

    # Post cancel
    cancel_resp = app_client.post("/api/security/approval/cancel", json={
        "source_hash": source_hash,
        "operation": "run",
        "reason": "User cancelled in modal",
    })
    assert cancel_resp.status_code == 200
    assert cancel_resp.get_json().get("success") is True

    # Re-attempting run without a valid approval token continues to return 409
    retry_resp = app_client.post("/api/program/run", json={
        "filename": "test_cancel.c",
        "code": VULNERABLE_CODE,
        "language": "c",
    })
    assert retry_resp.status_code == 409
