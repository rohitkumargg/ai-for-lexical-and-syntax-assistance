"""
Unit and integration tests for Phase 1: Candidate eligibility, application integrity,
and user approval safety lifecycle.
"""

import pytest
import hashlib
from app import app
from compiler.improvement_advisor import (
    ImprovementAdvisor,
    ImprovementCandidate,
    ImprovementStrategy,
    CandidateRegistry,
    candidate_registry,
)
from compiler.orchestrator import DecisionState
from compiler.patch_validator import PatchValidator, PatchValidationReport, ValidationVerdict, StructuredDiff


def test_candidate_has_required_metadata_and_hashes():
    """Verify that every generated candidate contains original and proposed source hashes, filename, and eligibility flags."""
    advisor = ImprovementAdvisor()
    c_code = """#include <stdio.h>
void main() {
    printf("hello");
}
"""
    report = advisor.analyze_and_advise(c_code, filename="main.c")
    assert report.total_candidates >= 1

    cand = report.candidates[0]
    orig_hash = hashlib.sha256(c_code.encode("utf-8")).hexdigest()[:12]
    prop_hash = hashlib.sha256(cand.proposed_code.encode("utf-8")).hexdigest()[:12]

    assert cand.original_source_hash == orig_hash
    assert cand.proposed_source_hash == prop_hash
    assert cand.filename == "main.c"
    assert cand.validation_state in [DecisionState.VALIDATED.value, DecisionState.VALIDATION_FAILED.value]
    assert isinstance(cand.is_eligible_for_application, bool)
    assert cand.user_decision_state == DecisionState.AWAITING_USER_DECISION.value


def test_candidate_eligibility_when_validation_passes():
    """Valid patch must be marked VALIDATED and eligible for application."""
    advisor = ImprovementAdvisor()
    c_code = """#include <stdio.h>
void main() {
    printf("test\\n");
}
"""
    report = advisor.analyze_and_advise(c_code, filename="eligible.c")
    cand = report.candidates[0]

    assert cand.validation_passed is True
    assert cand.validation_state == DecisionState.VALIDATED.value
    assert cand.is_eligible_for_application is True
    assert cand.user_decision_state == DecisionState.AWAITING_USER_DECISION.value


def test_candidate_ineligibility_when_validation_fails():
    """Candidate with failed validation must be marked VALIDATION_FAILED and ineligible."""
    registry = CandidateRegistry()
    fake_val_report = PatchValidationReport(
        verdict=ValidationVerdict.FAILED_SYNTAX,
        is_valid=False,
        syntax_passed=False,
        semantic_passed=False,
        compilation_passed=False,
        security_passed=False,
        tests_passed=False,
        remaining_risks=["Syntax error in candidate"],
        stage_results={},
        structured_diff=StructuredDiff(
            original_code="int x;",
            patched_code="int x",
            unified_diff="",
            additions_count=0,
            deletions_count=0,
            changed_lines=[],
            diff_chunks=[],
        ),
    )

    advisor = ImprovementAdvisor()
    cand = advisor._build_candidate(
        strategy=ImprovementStrategy.CONSERVATIVE,
        category="Test Category",
        priority="LOW",
        title="Failing Candidate",
        explanation="Simulated validation failure",
        line=1,
        col=0,
        evidence="int x",
        source="int x;",
        proposed_code="int x",
        filename="fail.c",
        diff="fake diff",
        expected_effect="None",
        assumptions=[],
        trade_offs="Fails syntax",
        relevant_metric="Code Quality",
        predicted_metric_delta="0%",
        confidence=0.5,
        val_report=fake_val_report,
        base_scores={},
        after_scores={},
    )

    assert cand.validation_passed is False
    assert cand.validation_state == DecisionState.VALIDATION_FAILED.value
    assert cand.is_eligible_for_application is False
    assert cand.user_decision_state == DecisionState.VALIDATION_FAILED.value

    # Registry must refuse application
    registry.register(cand)
    success, msg, _ = registry.verify_and_apply(cand.id, current_source="int x;")
    assert success is False
    assert "ineligible" in msg.lower()


def test_apply_endpoint_rejects_stale_baseline_source():
    """Apply endpoint must reject application if editor source was modified since candidate proposal."""
    client = app.test_client()
    initial_code = """#include <stdio.h>
void main() {
    printf("hello");
}
"""
    # 1. Generate advisories for initial code
    resp = client.post("/api/improvement/advise", json={"code": initial_code, "filename": "stale_test.c"})
    assert resp.status_code == 200
    data = resp.get_json()
    cand_id = data["candidates"][0]["id"]

    # 2. Attempt to apply with modified (stale) editor source
    stale_code = """#include <stdio.h>
// User typed something else in editor!
void main() {
    printf("hello world");
}
"""
    apply_resp = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={"current_code": stale_code})
    assert apply_resp.status_code == 409  # Conflict / Stale baseline
    apply_data = apply_resp.get_json()
    assert apply_data["success"] is False
    assert "Stale" in apply_data["error"]


def test_apply_endpoint_rejects_duplicate_application():
    """Applying an already applied candidate must be rejected."""
    client = app.test_client()
    c_code = """#include <stdio.h>
void main() {
    printf("once");
}
"""
    resp = client.post("/api/improvement/advise", json={"code": c_code, "filename": "dup_test.c"})
    cand_id = resp.get_json()["candidates"][0]["id"]

    # First application: succeeds
    res1 = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={"current_code": c_code})
    assert res1.status_code == 200
    assert res1.get_json()["success"] is True

    # Second application: rejected
    res2 = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={"current_code": c_code})
    assert res2.status_code == 409
    assert res2.get_json()["success"] is False
    assert "already" in res2.get_json()["error"]


def test_reject_lifecycle_and_prevent_subsequent_application():
    """Explicitly rejected candidate cannot be applied."""
    client = app.test_client()
    c_code = """#include <stdio.h>
void main() {
    printf("reject_me");
}
"""
    resp = client.post("/api/improvement/advise", json={"code": c_code, "filename": "rej_test.c"})
    cand_id = resp.get_json()["candidates"][0]["id"]

    # Reject
    rej_resp = client.post(f"/api/improvement/candidate/{cand_id}/reject")
    assert rej_resp.status_code == 200
    assert rej_resp.get_json()["user_decision"] == "USER_REJECTED"

    # Attempt to apply rejected candidate
    app_resp = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={"current_code": c_code})
    assert app_resp.status_code in [400, 422, 409]
    assert app_resp.get_json()["success"] is False
    assert "rejected" in app_resp.get_json()["error"].lower()


def test_unique_candidate_id_no_collision():
    """Multiple candidates at identical line numbers across different code versions must have distinct IDs."""
    advisor = ImprovementAdvisor()
    code1 = """#include <stdio.h>
void main() {
    printf("version1");
}
"""
    code2 = """#include <stdio.h>
void main() {
    printf("version2");
}
"""
    rep1 = advisor.analyze_and_advise(code1, filename="v1.c")
    rep2 = advisor.analyze_and_advise(code2, filename="v2.c")

    cand1 = rep1.candidates[0]
    cand2 = rep2.candidates[0]

    assert cand1.id != cand2.id
    assert cand1.original_source_hash != cand2.original_source_hash


def test_original_source_preserved_until_explicit_apply():
    """Editor source code must remain unmodified until apply is explicitly invoked."""
    editor_source = """#include <stdio.h>
void main() {
    printf("preserved");
}
"""
    client = app.test_client()
    # Analysis only advises, does not change source
    resp = client.post("/api/improvement/advise", json={"code": editor_source, "filename": "preserve.c"})
    assert resp.status_code == 200

    cand = resp.get_json()["candidates"][0]
    # Decision state is strictly AWAITING_USER_DECISION
    assert cand["user_decision_state"] == "AWAITING_USER_DECISION"
    assert cand["original_code"] == editor_source
    assert cand["proposed_code"] != editor_source


# =========================================================================
# Focused Tests for Candidate Application Bug Fix
# =========================================================================

def test_valid_suggestion_inserted_exactly_into_editor():
    """Requirement 1: A valid suggestion is inserted exactly into the editor."""
    client = app.test_client()
    initial_code = """#include <stdio.h>
void main() {
    printf("exact");
}
"""
    resp = client.post("/api/improvement/advise", json={"code": initial_code, "filename": "exact.c"})
    assert resp.status_code == 200
    data = resp.get_json()
    cand = data["candidates"][0]
    cand_id = cand["id"]
    expected_code = cand["proposed_code"]

    # Apply candidate
    apply_resp = client.post(
        f"/api/improvement/candidate/{cand_id}/apply",
        json={"current_code": initial_code, "filename": "exact.c"}
    )
    assert apply_resp.status_code == 200
    apply_data = apply_resp.get_json()

    assert apply_data["success"] is True
    assert apply_data["candidate_id"] == cand_id
    assert apply_data["filename"] == "exact.c"
    assert apply_data["user_decision"] == "APPLIED"

    # Verify returned code exactly matches the proposed transformation
    applied_code = apply_data["applied_code"]
    assert applied_code == expected_code
    assert applied_code != initial_code

    # Simulate editor update: editor receives exact applied_code
    editor_content = applied_code
    assert editor_content == expected_code


def test_stale_suggestion_rejected_with_clear_message():
    """Requirement 2: A stale suggestion is rejected with a clear message."""
    client = app.test_client()
    initial_code = """#include <stdio.h>
void main() {
    printf("fresh");
}
"""
    resp = client.post("/api/improvement/advise", json={"code": initial_code, "filename": "stale_clear.c"})
    cand_id = resp.get_json()["candidates"][0]["id"]

    # Code modified in editor since proposal
    modified_code = """#include <stdio.h>
void main() {
    printf("stale_now");
}
"""
    apply_resp = client.post(
        f"/api/improvement/candidate/{cand_id}/apply",
        json={"current_code": modified_code, "filename": "stale_clear.c"}
    )
    assert apply_resp.status_code == 409
    data = apply_resp.get_json()
    assert data["success"] is False
    assert "Stale candidate: source modified since proposal" in data["error"]
    assert "baseline hash" in data["error"]


def test_failed_editor_application_does_not_permanently_consume_candidate():
    """Requirement 3: A failed editor application does not falsely report success or permanently consume the candidate."""
    client = app.test_client()
    initial_code = """#include <stdio.h>
void main() {
    printf("rollback_test");
}
"""
    resp = client.post("/api/improvement/advise", json={"code": initial_code, "filename": "rollback.c"})
    cand_id = resp.get_json()["candidates"][0]["id"]

    # 1. Backend application succeeds
    apply_resp = client.post(
        f"/api/improvement/candidate/{cand_id}/apply",
        json={"current_code": initial_code, "filename": "rollback.c"}
    )
    assert apply_resp.status_code == 200

    # 2. Simulate editor insertion failure in UI -> UI invokes rollback endpoint
    rollback_resp = client.post(
        f"/api/improvement/candidate/{cand_id}/rollback",
        json={"reason": "Editor instance unavailable / update failed"}
    )
    assert rollback_resp.status_code == 200
    rb_data = rollback_resp.get_json()
    assert rb_data["success"] is True
    assert rb_data["user_decision"] == DecisionState.AWAITING_USER_DECISION.value

    # 3. Candidate is NOT permanently consumed: user can apply again safely
    reapply_resp = client.post(
        f"/api/improvement/candidate/{cand_id}/apply",
        json={"current_code": initial_code, "filename": "rollback.c"}
    )
    assert reapply_resp.status_code == 200
    assert reapply_resp.get_json()["success"] is True
    assert reapply_resp.get_json()["user_decision"] == "APPLIED"


def test_both_apply_paths_use_consistent_backend_rules():
    """Requirement 4: Both Apply buttons use consistent backend rules."""
    client = app.test_client()
    code = """#include <stdio.h>
void main() {
    printf("consistent");
}
"""
    resp = client.post("/api/improvement/advise", json={"code": code, "filename": "consistent.c"})
    cand_id = resp.get_json()["candidates"][0]["id"]

    # Rule A: Missing current_code must be rejected with 400 (cannot bypass stale check)
    no_code_resp = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={})
    assert no_code_resp.status_code == 400
    assert "required" in no_code_resp.get_json()["error"].lower()

    # Rule B: Stale code must be rejected with 409
    stale_resp = client.post(
        f"/api/improvement/candidate/{cand_id}/apply",
        json={"current_code": "modified code"}
    )
    assert stale_resp.status_code == 409
    assert "stale" in stale_resp.get_json()["error"].lower()

    # Rule C: Fresh code succeeds
    fresh_resp = client.post(
        f"/api/improvement/candidate/{cand_id}/apply",
        json={"current_code": code}
    )
    assert fresh_resp.status_code == 200
    assert fresh_resp.get_json()["success"] is True


def test_applying_suggestion_while_another_file_tab_is_active_does_not_overwrite_wrong_file():
    """Requirement 5: Applying a suggestion while another file/tab is active does not overwrite the wrong file."""
    client = app.test_client()
    main_code = """#include <stdio.h>
void main() {
    printf("main_file");
}
"""
    # Candidate generated for main.c
    resp = client.post("/api/improvement/advise", json={"code": main_code, "filename": "main.c"})
    cand_id = resp.get_json()["candidates"][0]["id"]

    # Active tab in editor is helper.c
    mismatch_resp = client.post(
        f"/api/improvement/candidate/{cand_id}/apply",
        json={"current_code": main_code, "filename": "helper.c"}
    )
    assert mismatch_resp.status_code == 400
    data = mismatch_resp.get_json()
    assert data["success"] is False
    assert "Target file mismatch" in data["error"]
    assert "main.c" in data["error"]
    assert "helper.c" in data["error"]

    # Candidate was NOT applied: state remains unconsumed
    cand_obj = candidate_registry.get(cand_id)
    assert cand_obj.user_decision_state == DecisionState.AWAITING_USER_DECISION.value


def test_duplicate_concurrent_clicks_cannot_apply_same_candidate_twice():
    """Requirement 6: Duplicate clicks cannot apply the same candidate twice."""
    import concurrent.futures

    client = app.test_client()
    code = """#include <stdio.h>
void main() {
    printf("concurrent");
}
"""
    resp = client.post("/api/improvement/advise", json={"code": code, "filename": "concurrent.c"})
    cand_id = resp.get_json()["candidates"][0]["id"]

    # Sequential duplicate click check
    res1 = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={"current_code": code, "filename": "concurrent.c"})
    assert res1.status_code == 200

    res2 = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={"current_code": code, "filename": "concurrent.c"})
    assert res2.status_code == 409
    assert "already" in res2.get_json()["error"]

    # Concurrent race simulation with thread lock
    resp2 = client.post("/api/improvement/advise", json={"code": code, "filename": "concurrent2.c"})
    cand_id2 = resp2.get_json()["candidates"][0]["id"]

    results = []
    def do_apply():
        c = app.test_client()
        return c.post(f"/api/improvement/candidate/{cand_id2}/apply", json={"current_code": code, "filename": "concurrent2.c"})

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futs = [executor.submit(do_apply) for _ in range(4)]
        results = [f.result() for f in futs]

    status_codes = [r.status_code for r in results]
    # Exactly one request must succeed (200), and all other duplicate requests must fail (409)
    assert status_codes.count(200) == 1
    assert status_codes.count(409) == 3


def test_rejected_or_validation_failed_candidate_cannot_be_applied():
    """Requirement 7: A rejected or validation-failed candidate cannot be applied."""
    client = app.test_client()

    # Part A: User rejected candidate
    code = """#include <stdio.h>
void main() {
    printf("reject_guard");
}
"""
    resp = client.post("/api/improvement/advise", json={"code": code, "filename": "rej_guard.c"})
    cand_id = resp.get_json()["candidates"][0]["id"]

    rej_resp = client.post(f"/api/improvement/candidate/{cand_id}/reject")
    assert rej_resp.status_code == 200

    app_resp = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={"current_code": code})
    assert app_resp.status_code in [409, 422]
    assert "rejected" in app_resp.get_json()["error"].lower()

    # Part B: Ineligible validation-failed candidate
    registry = candidate_registry
    advisor = ImprovementAdvisor()
    fake_val = PatchValidationReport(
        verdict=ValidationVerdict.FAILED_SYNTAX,
        is_valid=False,
        syntax_passed=False,
        semantic_passed=False,
        compilation_passed=False,
        security_passed=False,
        tests_passed=False,
        remaining_risks=["syntax error"],
        stage_results={},
        structured_diff=StructuredDiff("int a;", "int a", "", 0, 0, [], []),
    )
    bad_cand = advisor._build_candidate(
        strategy=ImprovementStrategy.CONSERVATIVE,
        category="Test Ineligible",
        priority="LOW",
        title="Invalid Syntax Candidate",
        explanation="Simulated validation failure",
        line=1,
        col=0,
        evidence="int a",
        source="int a;",
        proposed_code="int a",
        filename="bad.c",
        diff="diff",
        expected_effect="None",
        assumptions=[],
        trade_offs="None",
        relevant_metric="Quality",
        predicted_metric_delta="0%",
        confidence=0.1,
        val_report=fake_val,
        base_scores={},
        after_scores={},
    )
    registry.register(bad_cand)

    bad_resp = client.post(
        f"/api/improvement/candidate/{bad_cand.id}/apply",
        json={"current_code": "int a;"}
    )
    assert bad_resp.status_code == 422
    assert "ineligible" in bad_resp.get_json()["error"].lower()
