import pytest
import os
import time
import json
import uuid
import hashlib
from app import app
from compiler.repair_planner import RepairPlanner
from compiler.continuation_manager import ContinuationManager
from compiler.security_approval_gate import SecurityApprovalManager, SecurityDecisionGate


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_single_pass_repair_ademo2():
    """
    Single-pass repair requirement: ademo2.c completes in a single request pass.
    No round field above 1, can_continue_repair is False.
    """
    with open("examples/week11_testing/ademo2.c", "r", encoding="utf-8") as f:
        source_code = f.read()

    planner = RepairPlanner()
    res = planner.plan_and_repair(
        source_code,
        filename="ademo2.c",
        language="c",
    )
    assert res.get("round", 1) == 1, f"Round field must be 1, got {res.get('round')}"
    assert not res.get("can_continue_repair"), "can_continue_repair must always be False"
    cand_code = res.get("proposed_code")
    assert cand_code is not None, "Proposed candidate code must be returned"


def test_stale_token_returns_clear_4xx(client):
    """
    Design Rule: stale token returns a clear 4xx the UI displays.
    """
    risky_code = '#include <stdio.h>\n#include <stdlib.h>\nint main() { system("whoami"); return 0; }\n'
    stale_token = "appr_expired_token_00000000"

    resp = client.post(
        "/api/coordinator/analyze_and_plan",
        json={
            "code": risky_code,
            "filename": "risky.c",
            "language": "c",
            "operation": "repair",
            "approval_token": stale_token,
        },
    )

    assert 400 <= resp.status_code < 500, f"Expected 4xx HTTP status code, got {resp.status_code}"
    data = resp.get_json()
    assert data is not None, "Response must be valid JSON"
    err_msg = data.get("message") or data.get("error") or data.get("policy_reason")
    assert err_msg, "Response must include a clear error message explaining token rejection"
    assert any(term in err_msg.lower() for term in ["expired", "invalid", "not found", "consumed", "modified", "blocked", "threat", "security"]), (
        f"Error message must specify clear token or gate rejection reason: {err_msg}"
    )


def test_token_rebinding_refused_on_new_or_escalated_security_finding(client):
    """
    Design Rule (Token Re-binding Case A):
    The server may re-bind an approval token ONLY if the candidate introduces NO new
    or higher-severity security finding. If a candidate introduces a new security finding
    (e.g., adding an unvetted system/exec call or higher risk pattern), re-binding is refused,
    and attempting to continue without fresh user authorization returns 4xx requiring re-approval.
    """
    base_code = "int main() {\n    char buf[16];\n    gets(buf);\n    return 0;\n}\n"
    # Candidate fixes gets() but introduces a critical/new command execution finding:
    hostile_candidate = "int main() {\n    char buf[16];\n    fgets(buf, 16, stdin);\n    system(\"rm -rf /\");\n    return 0;\n}\n"

    # User approves base_code
    ok, token, _ = SecurityApprovalManager.create_one_time_approval(
        source_code=base_code,
        filename="main.c",
        operation="repair",
    )
    assert ok and token is not None

    cont_id = f"cont_sec_test_{uuid.uuid4().hex[:8]}"
    session = ContinuationManager.get_or_create_session(
        continuation_id=cont_id,
        source_code=base_code,
        filename="main.c",
        language="c",
        approval_token=token,
        round_index=1,
    )

    # Attempt to re-bind token to hostile candidate
    rebound_token = ContinuationManager.rebind_token_for_new_code(
        old_token=token,
        new_source_code=hostile_candidate,
        filename="main.c",
        operation="repair",
        continuation_id=cont_id,
        server_generated=True,
    )

    # Must be REFUSED (None)
    assert rebound_token is None, "Token re-binding must be refused when candidate introduces a new/higher security finding"
    assert session.approval_token is None, "Session approval token must be cleared when candidate introduces new security findings"
    assert session.token_rebind_error is not None, "A rebind error explaining the requirement for re-approval must be recorded"
    assert "re-approval required" in session.token_rebind_error.lower()

    # Continuation request to the server with hostile code without re-approval must return 4xx (409)
    resp = client.post(
        "/api/coordinator/analyze_and_plan",
        json={
            "code": hostile_candidate,
            "filename": "main.c",
            "language": "c",
            "operation": "repair",
            "continuation_id": cont_id,
            "round": 2,
        },
    )
    assert 400 <= resp.status_code < 500, f"Expected 4xx response requiring re-approval, got {resp.status_code}"
    data = resp.get_json()
    err_text = data.get("message") or data.get("error") or ""
    assert "re-approval" in err_text.lower() or "security" in err_text.lower()


def test_token_rebinding_allowed_on_server_generated_clean_candidate():
    """
    Design Rule (Token Re-binding Case B):
    The server successfully re-binds the approval token to a candidate it generated itself
    in an approved continuation when the candidate resolves or maintains existing issues without
    introducing any new or higher-severity findings.
    """
    base_code = "int main() {\n    char buf[16];\n    gets(buf);\n    return 0;\n}\n"
    # Safe candidate replaces gets with fgets (resolves finding, introduces zero new threats)
    safe_candidate = "int main() {\n    char buf[16];\n    fgets(buf, sizeof(buf), stdin);\n    return 0;\n}\n"

    ok, token, _ = SecurityApprovalManager.create_one_time_approval(
        source_code=base_code,
        filename="main.c",
        operation="repair",
    )
    assert ok and token is not None

    cont_id = f"cont_clean_test_{uuid.uuid4().hex[:8]}"
    session = ContinuationManager.get_or_create_session(
        continuation_id=cont_id,
        source_code=base_code,
        filename="main.c",
        language="c",
        approval_token=token,
        round_index=1,
    )

    rebound_token = ContinuationManager.rebind_token_for_new_code(
        old_token=token,
        new_source_code=safe_candidate,
        filename="main.c",
        operation="repair",
        continuation_id=cont_id,
        server_generated=True,
    )

    # Must be APPROVED and bound to candidate's hash
    assert rebound_token is not None, "Token re-binding must succeed for server-generated clean candidate"
    assert session.approval_token == rebound_token, "Session token must update to rebound token"
    assert session.token_rebind_error is None

    # Verify that the rebound token is recognized by SecurityApprovalManager for the new hash
    safe_hash = hashlib.sha256(safe_candidate.encode("utf-8")).hexdigest()
    rec = SecurityApprovalManager.get_approval_record(token=rebound_token, source_hash=safe_hash)
    assert rec is not None, "Security approval record must exist for rebound token and new hash"
    assert rec.source_hash == safe_hash


def test_client_forged_server_generated_flag_rejected(client):
    """
    Item 5 Request-Level Test:
    Client sends a forged 'server_generated': True in request JSON.
    The server must never read or honor this client-supplied flag, and must reject unapproved execution with 4xx.
    """
    forged_code = "int main() { system(\"rm -rf /\"); return 0; }\n"
    cont_id = f"cont_forged_{uuid.uuid4().hex[:8]}"

    payload_clean = {
        "code": forged_code,
        "filename": "main.c",
        "language": "c",
        "operation": "repair",
        "continuation_id": cont_id,
        "round": 2,
    }
    payload_forged = dict(payload_clean, server_generated=True)

    resp_clean = client.post("/api/coordinator/analyze_and_plan", json=payload_clean)
    resp_forged = client.post("/api/coordinator/analyze_and_plan", json=payload_forged)

    # Identical responses and gate decision regardless of client forged flag
    assert resp_clean.status_code == resp_forged.status_code, "Status code must be identical"
    assert resp_clean.get_json() == resp_forged.get_json(), "Response payload must be identical"
    assert 400 <= resp_forged.status_code < 500, f"Expected 4xx rejecting unapproved continuation, got {resp_forged.status_code}"
    data = resp_forged.get_json()
    assert data.get("reapproval_required") is True or "security" in str(data).lower()


def test_rebind_token_defaults_to_server_generated_false():
    """
    Item 4 Design Rule: rebind_token_for_new_code defaults to server_generated=False.
    When server_generated is not explicitly passed as True, token re-binding is refused.
    """
    base_code = "int main() {\n    char buf[16];\n    gets(buf);\n    return 0;\n}\n"
    cand_code = "int main() {\n    char buf[16];\n    fgets(buf, sizeof(buf), stdin);\n    return 0;\n}\n"
    ok, token, _ = SecurityApprovalManager.create_one_time_approval(
        source_code=base_code, filename="main.c", operation="repair"
    )
    assert ok and token is not None

    cont_id = f"cont_default_flag_{uuid.uuid4().hex[:8]}"
    ContinuationManager.get_or_create_session(
        continuation_id=cont_id, source_code=base_code, approval_token=token
    )

    # Call with server_generated omitted (tests default=False)
    rebound = ContinuationManager.rebind_token_for_new_code(
        old_token=token,
        new_source_code=cand_code,
        continuation_id=cont_id,
    )
    assert rebound is None, "Token re-binding must be refused when server_generated defaults to False"
    session = ContinuationManager.get_session(cont_id)
    assert "not server-generated" in session.token_rebind_error


def test_rebind_token_never_mints_token_when_no_approval_exists_and_gate_requires_one():
    """
    Item 4 Design Rule: Never mint a token when no approval exists and the gate requires one.
    """
    vuln_code = "int main() {\n    char buf[16];\n    gets(buf);\n    return 0;\n}\n"
    cand_code = "int main() {\n    char buf[16];\n    gets(buf);\n    return 0;\n}\n"
    cont_id = f"cont_no_appr_{uuid.uuid4().hex[:8]}"

    # Session created with NO approval token
    ContinuationManager.get_or_create_session(
        continuation_id=cont_id, source_code=vuln_code, approval_token=None
    )

    rebound = ContinuationManager.rebind_token_for_new_code(
        old_token=None,
        new_source_code=cand_code,
        continuation_id=cont_id,
        server_generated=True,
    )
    assert rebound is None, "Must never mint a token when no approval exists and gate requires one"
    session = ContinuationManager.get_session(cont_id)
    assert session.approval_token is None
    assert session.token_rebind_error is not None


def test_token_rebinding_allowed_when_line_numbers_shift():
    """
    Item 5 Signature Test:
    Signatures are independent of line numbers (rule_id + normalized function or snippet).
    When lines shift due to prepended header/comments but finding rules/severity are unchanged,
    token re-binding succeeds.
    """
    base_code = "int main() {\n    char buf[16];\n    gets(buf);\n    return 0;\n}\n"
    # 5 comment lines prepended -> gets(buf) shifts from line 3 to line 8
    shifted_code = "// Line 1\n// Line 2\n// Line 3\n// Line 4\n// Line 5\nint main() {\n    char buf[16];\n    gets(buf);\n    return 0;\n}\n"

    ok, token, _ = SecurityApprovalManager.create_one_time_approval(
        source_code=base_code,
        filename="main.c",
        operation="repair",
    )
    assert ok and token is not None

    cont_id = f"cont_shift_{uuid.uuid4().hex[:8]}"
    session = ContinuationManager.get_or_create_session(
        continuation_id=cont_id,
        source_code=base_code,
        filename="main.c",
        language="c",
        approval_token=token,
        round_index=1,
    )

    rebound_token = ContinuationManager.rebind_token_for_new_code(
        old_token=token,
        new_source_code=shifted_code,
        filename="main.c",
        operation="repair",
        continuation_id=cont_id,
        server_generated=True,
    )

    assert rebound_token is not None, "Token re-binding must succeed when finding rule/severity is unchanged even if lines shifted"
    assert rebound_token.startswith("appr_cont_")


def test_crlf_file_survives_all_rounds():
    """
    Design Rule: a CRLF file survives repair with \r\n preserved.
    """
    crlf_code = "int main() {\r\n    int a = 5\r\n    return a;\r\n}\r\n"
    assert "\r\n" in crlf_code

    planner = RepairPlanner()
    cont_id = f"cont_crlf_{uuid.uuid4().hex[:8]}"

    res1 = planner.plan_and_repair(
        crlf_code,
        filename="test_crlf.c",
        language="c",
        continuation_id=cont_id,
        round=1,
    )

    cand1 = res1.get("proposed_code")
    assert cand1 is not None, "Proposed candidate code must be returned"
    assert "\r\n" in cand1, "Single pass proposed_code lost CRLF line endings"
    assert res1.get("round", 1) == 1
    assert not res1.get("can_continue_repair")


def test_playwright_continue_repair_success_path():
    """
    Playwright Test (a) Single-pass success path:
    Asserts UI hides '#btn-continue-repair' and '#rec-round-badge'.
    Completes repair in one pass without continuation round.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("http://127.0.0.1:5000")
        page.wait_for_selector("#btn-run", timeout=15000)

        with open("examples/week11_testing/ademo2.c", "r", encoding="utf-8") as f:
            ademo2_code = f.read()

        page.evaluate("""(code) => {
            currentLanguageId = "c";
            currentFilename = "ademo2.c";
            openFiles["ademo2.c"] = code;
            if (editor) {
                editor.setValue(code);
            }
        }""", ademo2_code)

        page.evaluate("runRepair()")

        # Wait for candidate card
        page.wait_for_selector("#recommendedProgramCard", state="visible", timeout=750000)

        # Check typeof window.editor vs editor
        typeof_w = page.evaluate("() => typeof window.editor")
        typeof_e = page.evaluate("() => typeof editor")
        print(f"Playwright Check: typeof window.editor = {typeof_w}, typeof editor = {typeof_e}")

        # Requirement 1: UI hides Continue Repair button and round badge
        btn_cont = page.query_selector("#btn-continue-repair")
        if btn_cont:
            assert not btn_cont.is_visible(), "Continue Repair button must be hidden in single-pass UI"

        round_badge = page.query_selector("#rec-round-badge")
        if round_badge:
            assert not round_badge.is_visible(), "Round badge must be hidden in single-pass UI"

        plan = page.evaluate("() => currentCoordinatedPlan")
        print(f"RAW_RESPONSE: status={plan.get('status')}, windows={plan.get('windows_processed', plan.get('windows', 0))}, seconds={plan.get('total_wall_time_s', plan.get('seconds', 0))}, stopping_reason={plan.get('stopping_reason')}")
        assert plan.get("round", 1) == 1, "Round must be 1"
        assert plan.get("stopping_reason") != "budget expired", "Stopping reason must not be budget expired"
        assert plan.get("compiles") is True or plan.get("status") in ("CLEAN", "SUCCESS", "VALID_WITH_SECURITY_ISSUES", "VALID_WITH_WARNINGS", "PARTIALLY_REPAIRED", "PROPOSAL_READY"), "Candidate must compile or produce valid proposal"

        cand_code = page.evaluate("() => currentCoordinatedPlan && currentCoordinatedPlan.proposed_code")
        assert cand_code, "Must have candidate code from single pass repair"

        browser.close()


def test_playwright_continue_repair_forced_error_path():
    """
    Playwright Test (b) Forced-error path:
    Forces server error on coordinator endpoint. Asserts error is surfaced to user.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("http://127.0.0.1:5000")
        page.wait_for_selector("#btn-run", timeout=15000)

        with open("examples/week11_testing/ademo2.c", "r", encoding="utf-8") as f:
            ademo2_code = f.read()

        page.evaluate("""(code) => {
            currentLanguageId = "c";
            currentFilename = "ademo2.c";
            openFiles["ademo2.c"] = code;
            if (editor) {
                editor.setValue(code);
            }
        }""", ademo2_code)

        # Force error on coordinator repair request
        import re as _re
        page.route(_re.compile(r".*/api/(repair/job|coordinator/analyze_and_plan).*"), lambda route, request: (
            route.fulfill(
                status=500,
                content_type="application/json",
                body='{"error": "Forced server test error during single pass repair"}'
            )
        ))

        page.evaluate("runRepair()")

        # Wait for error toast or banner to appear
        page.wait_for_selector(".toast-error, .toast, #continuation-error-banner", timeout=30000)
        toast = page.query_selector(".toast-error, .toast, #continuation-error-banner")
        assert toast is not None

        browser.close()


def test_candidate_rejected_when_introducing_new_syntax_error():
    """
    Design Rule (Acceptance Rule for Partial Candidates):
    Acceptance requires: security_passed AND no finding in the candidate that is
    absent from the original (match by rule_id + normalized snippet) AND fewer findings than before.
    If a candidate fixes 3 findings but adds 1 new syntax error (even if total count decreases),
    it MUST be rejected.
    """
    from compiler.repair_planner import RepairPlanner, _get_finding_sig

    planner = RepairPlanner()

    # Original code with 4 distinct syntax issues
    orig_code = (
        "int f1() { int a = 1 return a; }\n"
        "int f2() { int b = 2 return b; }\n"
        "int f3() { int c = 3 return c; }\n"
        "int f4() { int d = 4 return d; }\n"
    )

    orch_orig = planner.orchestrator.run_analysis(orig_code, filename="test_syn.c", language="c")
    orig_sigs = {_get_finding_sig(f) for f in orch_orig.findings}
    orig_count = len(orch_orig.findings)

    # Candidate fixes f1, f2, f3 (3 fixes), but introduces a brand-new malformed syntax error in f4
    # Total findings will decrease from 4 to 2 (fewer findings), but introduces a new syntax defect
    cand_code = (
        "int f1() { int a = 1; return a; }\n"
        "int f2() { int b = 2; return b; }\n"
        "int f3() { int c = 3; return c; }\n"
        "int f4() { int d = $$$; return d; }\n"
    )

    orch_cand = planner.orchestrator.run_analysis(cand_code, filename="test_syn.c", language="c")
    cand_sigs = {_get_finding_sig(f) for f in orch_cand.findings}

    has_new_finding = any(s not in orig_sigs for s in cand_sigs)
    assert has_new_finding, "Candidate must contain at least one finding signature absent from original"
    assert len(orch_cand.findings) < orig_count, "Candidate total findings must be fewer than original"

    # Validate that planner acceptance rule rejects this candidate
    val = planner.validate_candidate(orig_code, cand_code, filename="test_syn.c", language="c")
    is_acceptable = False
    if val.is_valid:
        is_acceptable = True
    elif val.security_passed and not getattr(val, "is_security_blocked", False):
        if not has_new_finding and len(orch_cand.findings) < orig_count:
            is_acceptable = True

    assert not is_acceptable, "Candidate fixing 3 findings but introducing 1 new syntax finding MUST be rejected"


def test_finding_at_line_400_produces_window_containing_line_400():
    """
    Regression Test 5(a):
    A finding at line 400 produces a window containing line 400.
    """
    from compiler.repair_planner import _get_f_line
    from compiler.windowed_repair import get_window_for_finding
    from compiler.finding import Finding, FindingCategory, FindingSeverity, FindingStatus, SourceLocation

    # Construct 500-line source
    lines = [f"int func_{i}() {{ return {i}; }}\n" for i in range(1, 501)]
    code = "".join(lines)

    f = Finding(
        id="f_400",
        category=FindingCategory.SYNTAX,
        location=SourceLocation(line=400, col=5),
        evidence="return 400;",
        explanation="Missing semicolon",
        severity=FindingSeverity.HIGH,
        confidence=1.0,
        status=FindingStatus.CONFIRMED,
    )

    extracted_line = _get_f_line(f)
    assert extracted_line == 400, f"Expected extracted line 400, got {extracted_line}"

    win_src, win_start, win_end, win_rel = get_window_for_finding(code, extracted_line, radius=15, max_lines=40)
    assert win_start <= 400 <= win_end, f"Window ({win_start}..{win_end}) must contain line 400"
    assert f"func_400" in win_src, "Window source must include line 400 content"


def test_window_never_defaults_to_lines_1_to_30_for_later_finding():
    """
    Regression Test 5(b):
    Fails if the window defaults to lines 1 to 30 when targeting a later defect.
    """
    from compiler.repair_planner import _get_f_line
    from compiler.windowed_repair import get_window_for_finding
    from compiler.finding import Finding, FindingCategory, FindingSeverity, FindingStatus, SourceLocation

    lines = [f"/* line {i} */ int v{i} = {i};\n" for i in range(1, 501)]
    code = "".join(lines)

    f = Finding(
        id="f_400",
        category=FindingCategory.SYNTAX,
        location=SourceLocation(line=400, col=5),
        evidence="int v400",
        explanation="Syntax error",
        severity=FindingSeverity.HIGH,
        confidence=1.0,
        status=FindingStatus.CONFIRMED,
    )

    target_line = _get_f_line(f)
    win_src, win_start, win_end, win_rel = get_window_for_finding(code, target_line, radius=15, max_lines=40)

    # Must NOT be 1..30 or default to line 1
    assert (win_start, win_end) != (1, 30), f"Window must not default to (1, 30), got ({win_start}, {win_end})"
    assert win_start > 350, f"Window start should be near line 400, got {win_start}"
    assert win_end >= 400, f"Window end should reach or exceed 400, got {win_end}"


def test_scope_guard_rejects_candidate_dropping_neighbouring_function():
    """
    Scope Guard Requirement 4:
    Deterministic scope guard rejects a candidate if the function list (names and count) differs,
    such as dropping a neighbouring function.
    """
    from compiler.patch_validator import PatchIntegrityInspector
    from compiler.finding import Finding, FindingCategory, FindingSeverity, SourceLocation

    original = """int helper() {
    return 42;
}

int main() {
    int a = 10
    return 0;
}
"""
    # Candidate drops neighbouring function helper()
    candidate = """int main() {
    int a = 10;
    return 0;
}
"""
    f = Finding(
        id="f1",
        category=FindingCategory.SYNTAX,
        severity=FindingSeverity.HIGH,
        explanation="missing semicolon",
        evidence="int a = 10",
        location=SourceLocation(line=6, col=10, file_path="main.c"),
    )
    ok, reasons = PatchIntegrityInspector.inspect(original, candidate, original_findings=[f], filename="main.c")
    assert not ok, "Candidate dropping neighbouring function must be rejected by scope guard"
    assert any("Function list" in r for r in reasons), f"Expected function list mismatch in reasons: {reasons}"


def test_scope_guard_rejects_candidate_changing_unrelated_constant():
    """
    Scope Guard Requirement 4:
    Deterministic scope guard rejects a candidate if any line not within 2 lines of a finding changed,
    such as mutating an unrelated constant far from the finding.
    """
    from compiler.patch_validator import PatchIntegrityInspector
    from compiler.finding import Finding, FindingCategory, FindingSeverity, SourceLocation

    original = """int main() {
    const int UNRELATED_BUFFER_SIZE = 1024;
    int x = 1;
    int y = 2;
    int z = 3;
    int a = 10
    return 0;
}
"""
    # Finding is at line 6 (int a = 10). Candidate modifies line 2 (buffer size) which is > 2 lines away.
    candidate = """int main() {
    const int UNRELATED_BUFFER_SIZE = 2048;
    int x = 1;
    int y = 2;
    int z = 3;
    int a = 10;
    return 0;
}
"""
    f = Finding(
        id="f1",
        category=FindingCategory.SYNTAX,
        severity=FindingSeverity.HIGH,
        explanation="missing semicolon",
        evidence="int a = 10",
        location=SourceLocation(line=6, col=10, file_path="main.c"),
    )
    ok, reasons = PatchIntegrityInspector.inspect(original, candidate, original_findings=[f], filename="main.c")
    assert not ok, "Candidate modifying line > 2 lines away from finding must be rejected by scope guard"
    assert any("within 2 lines" in r for r in reasons), f"Expected line distance violation in reasons: {reasons}"
