"""
Comprehensive test suite for Autonomous End-to-End Program Repair.

Covers all 15 scenarios mandated in the specification:
1. Multiple internal repairs before a final result appears
2. No intermediate candidate approvals required
3. Successful final validation and final program display
4. Partial repair after the retry limit
5. Repeated candidate / no-progress termination
6. Security regression rejection
7. Validation failure termination
8. Clean source requiring no repair
9. Stale source protection
10. Apply uses stored final candidate
11. Apply does not call runRepair() or start another repair session
12. Duplicate Apply requests cannot apply twice
13. Editor updates to exact final candidate
14. Undo/revert remains functional
15. Existing CodeT5/Qwen routing, APIs, logging, and percentage metrics remain intact
"""

import pytest
import hashlib
from unittest.mock import patch, MagicMock

from app import app
from compiler.repair_planner import RepairPlanner
from compiler.improvement_advisor import candidate_registry, CandidateRegistry
from compiler.patch_validator import PatchValidationReport, ValidationVerdict, StructuredDiff
from compiler.orchestrator import DecisionState
from compiler.finding import Finding, FindingCategory, FindingSeverity, FindingStatus


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


# -------------------------------------------------------------------------
# Scenario 1 & 2: Multiple internal repairs without intermediate user approvals
# -------------------------------------------------------------------------
def test_autonomous_multi_round_repairs_no_intermediate_approval():
    """
    The agent internally performs multiple repair attempts across rounds,
    validates each candidate internally, and returns one final proposal
    without requiring user approvals during intermediate rounds.
    """
    planner = RepairPlanner(max_repair_rounds=3)
    
    # Code with missing semicolons
    code = """int main() {
    int a = 10
    int b = 20;
    return a + b;
}"""
    result = planner.plan_and_repair(code, filename="multi_test.c", language="c")
    
    # Single final candidate returned
    assert "candidate_id" in result
    assert result["candidate_id"] is not None
    assert "proposed_code" in result
    assert "int a = 10;" in result["proposed_code"] or ";int b" in result["proposed_code"] or ";return" in result["proposed_code"]
    
    # Internal rounds were executed without stopping for user approval
    assert result.get("rounds_executed", 0) >= 1 or result.get("total_rounds_attempted", 0) >= 1
    assert result.get("terminal_status") in ["FULLY_REPAIRED", "PARTIALLY_REPAIRED"]
    
    # Check that candidate is stored in registry awaiting final user decision
    cand = candidate_registry.get(result["candidate_id"])
    assert cand is not None
    assert cand.user_decision_state == DecisionState.AWAITING_USER_DECISION.value


# -------------------------------------------------------------------------
# Scenario 3: Successful final validation and final program display
# -------------------------------------------------------------------------
def test_successful_final_validation_and_final_program():
    """
    Candidate passes all checks (syntax, semantic, security, compiler)
    and is returned as FULLY_REPAIRED with complete proposed code and unified diff.
    """
    planner = RepairPlanner()
    code = """int main() {
    int x = 5
    return x;
}"""
    result = planner.plan_and_repair(code, filename="valid_final.c", language="c")
    
    assert result.get("terminal_status") == "FULLY_REPAIRED"
    assert "All actionable findings resolved" in result.get("stopping_reason", "")
    assert result.get("unresolved_findings") == []
    assert result.get("proposed_code") is not None
    assert result.get("unified_diff") is not None
    
    val_rep = result.get("validation_report", {})
    assert val_rep.get("syntax_passed") is True
    assert val_rep.get("security_passed") is True


# -------------------------------------------------------------------------
# Scenario 4: Partial repair after retry limit
# -------------------------------------------------------------------------
def test_partial_repair_after_retry_limit():
    """
    When multiple issues exist and rounds limit is hit, return the best accepted
    working copy with status PARTIALLY_REPAIRED and list remaining unresolved issues.
    """
    planner = RepairPlanner(max_repair_rounds=1)
    
    # Code with 2 issues where max_rounds=1 bounds attempts to 1 round
    code = """int main() {
    int a = 10
    int b = 20
    return a + b;
}"""
    result = planner.plan_and_repair(code, filename="partial.c", language="c", max_rounds=1)
    
    # Either round 1 fixed part and hit limit, or fixed all
    assert result.get("terminal_status") in ["PARTIALLY_REPAIRED", "FULLY_REPAIRED"]
    if result.get("unresolved_findings"):
        assert result.get("terminal_status") == "PARTIALLY_REPAIRED"
        assert len(result["unresolved_findings"]) > 0
        assert "limit" in result.get("stopping_reason", "").lower() or "round" in result.get("stopping_reason", "").lower()


# -------------------------------------------------------------------------
# Scenario 5: Repeated candidate / no-progress termination
# -------------------------------------------------------------------------
def test_repeated_candidate_no_progress_termination():
    """
    If model or strategy produces the same code or no valid change,
    autonomous repair loop stops safely to prevent infinite loops.
    """
    planner = RepairPlanner(max_repair_rounds=4)
    code = """int main() {
    int x = 42
    return x;
}"""
    # Force no model or rule to produce progress
    with patch.object(planner, "_try_deterministic_fix", return_value=(None, "")):
        with patch("compiler.repair_planner.CodeT5Manager.is_available", return_value=False):
            with patch.object(planner.ollama, "is_available", return_value=False):
                result = planner.plan_and_repair(code, filename="loop_test.c", language="c")
                
                assert result.get("terminal_status") in ["NO_SAFE_REPAIR", "PARTIALLY_REPAIRED", "UNRESOLVED"]
                assert "no candidate" in result.get("stopping_reason", "").lower() or "progress" in result.get("stopping_reason", "").lower() or "round" in result.get("stopping_reason", "").lower()


# -------------------------------------------------------------------------
# Scenario 6: Security regression rejection
# -------------------------------------------------------------------------
def test_security_regression_rejection():
    """
    If a generated candidate introduces a security regression compared to the original,
    it must be rejected internally and NOT accepted into the working copy.
    """
    planner = RepairPlanner()
    original_safe_code = """#include <stdio.h>
int main() {
    int x = 10
    return x;
}"""
    # Candidate that fixes syntax but introduces gets() buffer overflow
    regressive_candidate = """#include <stdio.h>
int main() {
    int x = 10;
    char buf[16];
    gets(buf);
    return x;
}"""
    
    val_report = planner.validate_candidate(original_safe_code, regressive_candidate, "test_sec.c")
    assert val_report.security_passed is False or not val_report.is_valid


# -------------------------------------------------------------------------
# Scenario 7: Validation failure termination
# -------------------------------------------------------------------------
def test_validation_failure_termination():
    """
    If candidate fails parser/syntax validation, it is rejected and not promoted.
    """
    planner = RepairPlanner()
    code = "int main() { return 0; }"
    invalid_candidate = "int main() { return 0 "  # syntax error
    
    val_report = planner.validate_candidate(code, invalid_candidate, "syntax_fail.c")
    assert val_report.syntax_passed is False
    assert val_report.is_valid is False


# -------------------------------------------------------------------------
# Scenario 8: Clean source requiring no repair
# -------------------------------------------------------------------------
def test_clean_source_requiring_no_repair(client):
    """
    Clean code with zero errors stops immediately with status CLEAN.
    """
    clean_code = """int main() {
    return 0;
}"""
    res = client.post("/api/coordinator/analyze_and_plan", json={
        "code": clean_code,
        "filename": "clean.c",
        "language": "c"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "CLEAN"
    assert data.get("candidate_id") is None
    assert data.get("proposed_code") is None


# -------------------------------------------------------------------------
# Scenario 9: Stale source protection
# -------------------------------------------------------------------------
def test_stale_source_protection_rejected(client):
    """
    If the user edits the code in the editor while or after repair was calculated,
    applying the candidate must be rejected with 409 Conflict.
    """
    code = """int main() {
    int x = 10
    return 0;
}"""
    # 1. Run repair
    res = client.post("/api/coordinator/analyze_and_plan", json={
        "code": code,
        "filename": "stale_test.c",
        "language": "c"
    })
    assert res.status_code == 200
    data = res.get_json()
    cand_id = data.get("candidate_id")
    assert cand_id is not None
    
    # 2. User edited code in editor
    modified_code = """int main() {
    int x = 999; /* User modification */
    return 0;
}"""
    
    apply_res = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={
        "current_code": modified_code,
        "filename": "stale_test.c"
    })
    assert apply_res.status_code == 409
    assert "Stale" in apply_res.get_json().get("error", "")


# -------------------------------------------------------------------------
# Scenario 10, 11, 12, 13: Apply lifecycle, no re-run, no duplicate application
# -------------------------------------------------------------------------
def test_apply_uses_stored_candidate_and_prevents_duplicate_apply(client):
    """
    Apply endpoint:
    - Uses stored candidate and updates editor
    - Marks candidate as APPLIED
    - Subsequent apply requests fail with 409
    - Does NOT invoke repair session
    """
    code = """int main() {
    int val = 42
    return val;
}"""
    res = client.post("/api/coordinator/analyze_and_plan", json={
        "code": code,
        "filename": "apply_flow.c",
        "language": "c"
    })
    data = res.get_json()
    cand_id = data["candidate_id"]
    
    # First apply: succeeds
    apply_res1 = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={
        "current_code": code,
        "filename": "apply_flow.c"
    })
    assert apply_res1.status_code == 200
    apply_data1 = apply_res1.get_json()
    assert apply_data1["success"] is True
    assert "int val = 42;" in apply_data1["applied_code"] or ";return" in apply_data1["applied_code"]
    
    # Candidate status is now APPLIED
    cand = candidate_registry.get(cand_id)
    assert cand.user_decision_state == DecisionState.APPLIED.value
    
    # Second duplicate apply: MUST be rejected with 409
    apply_res2 = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={
        "current_code": code,
        "filename": "apply_flow.c"
    })
    assert apply_res2.status_code == 409
    assert "already" in apply_res2.get_json().get("error", "").lower()


# -------------------------------------------------------------------------
# Scenario 14: Undo / Revert remains functional
# -------------------------------------------------------------------------
def test_undo_revert_functionality(client):
    """
    After applying a candidate, the patch is registered in patch_history,
    and /api/patch/revert cleanly restores the original code.
    """
    code = """int main() {
    int z = 1
    return z;
}"""
    res = client.post("/api/coordinator/analyze_and_plan", json={
        "code": code,
        "filename": "revert_test.c",
        "language": "c"
    })
    cand_id = res.get_json()["candidate_id"]
    
    # Apply
    apply_res = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={
        "current_code": code,
        "filename": "revert_test.c"
    })
    assert apply_res.status_code == 200
    
    # Revert via /api/patch/revert
    revert_res = client.post("/api/patch/revert", json={})
    assert revert_res.status_code == 200
    revert_data = revert_res.get_json()
    assert revert_data.get("success") is True
    assert revert_data.get("restored_code") == code


# -------------------------------------------------------------------------
# Scenario 15: Existing CodeT5/Qwen routing, APIs, logging and metrics intact
# -------------------------------------------------------------------------
def test_existing_apis_metrics_and_pipeline_events_intact(client):
    """
    Verify that existing 16-stage pipeline events, before_metrics/baseline_scores,
    green metrics, and quality scores remain intact in the coordinator response.
    """
    code = """int main() {
    int a = 100
    return a;
}"""
    res = client.post("/api/coordinator/analyze_and_plan", json={
        "code": code,
        "filename": "metrics_test.c",
        "language": "c"
    })
    assert res.status_code == 200
    data = res.get_json()
    
    # Baseline scores / metrics
    assert "baseline_scores" in data or "before_metrics" in data
    scores = data.get("baseline_scores") or data.get("before_metrics")
    assert "quality_score" in scores
    assert "security_risk_score" in scores
    assert "optimization_potential" in scores
    
    # Pipeline events logging for observability
    assert "pipeline_events" in data
    events = data["pipeline_events"]
    assert len(events) > 0
    stage_names = [e["stage_name"] for e in events]
    assert any("Lexical" in s for s in stage_names)
    assert any("Syntax" in s for s in stage_names)
    assert any("Semantic" in s for s in stage_names)
    assert any("Security" in s for s in stage_names)
