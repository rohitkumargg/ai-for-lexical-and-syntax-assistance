# tests/test_runtime_architecture_integration.py
import os
import json
import hashlib
import pytest
from unittest.mock import patch, MagicMock

from app import app
from compiler.finding import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)
from compiler.local_models import (
    OllamaClient,
    CodeT5Manager,
    LocalModelPipeline,
    EscalationTier,
)
from compiler.repair_planner import RepairPlanner
from compiler.improvement_advisor import candidate_registry
from compiler.pipeline_logger import StageStatus, get_pipeline_run


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_runtime_e2e_active_application_path(client):
    """
    End-to-end active application path:
    1. User submits code via /api/coordinator/analyze_and_plan
    2. Multi-agent analyzers produce findings in shared Finding format
    3. Deterministic fixes are attempted first
    4. Whole-program validation ensures candidate correctness
    5. Candidate registered awaiting explicit user approval
    6. Rejecting candidate leaves source unchanged
    7. Stale modification check blocks out-of-sync application (409)
    8. Valid user approval applies patch and re-analyzes updated source
    """
    broken_code = """int main() {
    int x = 10
    return 0;
}"""
    
    # 1. Analyze and Plan via active backend route
    res = client.post("/api/coordinator/analyze_and_plan", json={
        "code": broken_code,
        "filename": "test_e2e.c",
        "language": "c",
    })
    assert res.status_code == 200
    data = res.get_json()

    assert data["status"] == "REPAIR_PLAN_READY"
    assert "candidate" in data and data["candidate"] is not None
    cand = data["candidate"]
    cand_id = cand["id"]
    proposed_code = cand["proposed_code"]
    assert "int x = 10;" in proposed_code or ";return 0;" in proposed_code

    # 2. Check Candidate Registry lifecycle
    reg_cand = candidate_registry.get(cand_id)
    assert reg_cand is not None
    assert reg_cand.user_decision_state == "AWAITING_USER_DECISION"
    assert reg_cand.validation_passed is True

    # 3. Check Truthful Observability & Metrics
    assert "pipeline_events" in data
    events = data["pipeline_events"]
    stage_ids = [e["stage_id"] for e in events]
    assert "source_received" in stage_ids
    assert "deterministic_rules" in stage_ids
    assert "candidate_generation" in stage_ids
    assert "patch_validation" in stage_ids
    assert "user_approval_apply" in stage_ids

    # Baseline percentage metrics exist and truthful
    before_m = data["baseline_scores"]
    assert "overall_code_quality" in before_m
    assert "optimal_code" in before_m
    assert "poor_code" in before_m
    assert "vulnerability_risk" in before_m
    assert "green_metrics" in before_m

    # 4. Enforce Safety: Stale baseline check blocks out-of-sync application
    stale_editor_code = "int main() {\n    int x = 999; /* modified */\n    return 0;\n}"
    stale_res = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={
        "current_code": stale_editor_code,
    })
    assert stale_res.status_code == 409
    stale_data = stale_res.get_json()
    assert stale_data["success"] is False
    assert "stale" in stale_data["error"].lower()

    # 5. Explicit User Approval: Valid baseline source applies cleanly
    apply_res = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={
        "current_code": broken_code,
    })
    assert apply_res.status_code == 200
    apply_data = apply_res.get_json()
    assert apply_data["success"] is True
    assert apply_data["applied_code"] == proposed_code

    # Candidate marked as APPLIED
    assert candidate_registry.get(cand_id).user_decision_state == "APPLIED"

    # Cannot re-apply already applied candidate (Conflict / Unprocessable)
    reapply_res = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={
        "current_code": broken_code,
    })
    assert reapply_res.status_code in [409, 422]


def test_rejection_leaves_source_code_untouched(client):
    """Verify that explicitly rejecting a candidate does not apply changes."""
    code = "int main() {\n    int a = 5\n    return 0;\n}"
    res = client.post("/api/coordinator/analyze_and_plan", json={
        "code": code,
        "filename": "reject_test.c",
        "language": "c",
    })
    assert res.status_code == 200
    data = res.get_json()
    cand_id = data["candidate"]["id"]

    # Reject
    rej_res = client.post(f"/api/improvement/candidate/{cand_id}/reject", json={})
    assert rej_res.status_code == 200
    rej_data = rej_res.get_json()
    assert rej_data["success"] is True
    assert rej_data["user_decision"] == "USER_REJECTED"

    # Trying to apply rejected candidate is blocked
    apply_res = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={
        "current_code": code,
    })
    assert apply_res.status_code in [400, 422]


def test_qwen_coordinator_structured_decision_and_fallback():
    """Verify Qwen acts as structured model-backed coordinator when deterministic and CodeT5 fail."""
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.base_url = "http://127.0.0.1:11434"
    mock_ollama.default_model = "qwen2.5-coder:3b"
    mock_ollama.timeout = 5.0

    repaired_c = "int main() {\n    int a = 10;\n    return 0;\n}"
    
    # Qwen returns structured coordinator decision
    mock_ollama.coordinate_repair_decision.return_value = {
        "reasoning": "Identified syntax omission at statement boundary",
        "strategy": "whole_program_synthesis",
        "action": "request_candidate",
        "explanation": "Supplied missing semicolon terminating variable declaration.",
        "assumptions": ["Declaration belongs to enclosing main scope"],
        "expected_effects": ["Eliminates ANTLR parse error at line 2"],
        "candidate_code": repaired_c,
    }
    planner.ollama = mock_ollama

    code = "int main() {\n    int a = 10\n    return 0;\n}"

    # Force deterministic & CodeT5 to fail to trigger Qwen coordinator
    with patch("compiler.gui_bridge.repair_source_for_gui", return_value={"corrected_code": code, "steps": []}):
        with patch("compiler.local_models.CodeT5Manager.generate_patch", return_value=(None, "CodeT5 token filter failed")):
            res = planner.plan_and_repair(code, filename="test_qwen_coord.c", language="c")

    assert res["status"] == "REPAIR_PLAN_READY"
    events = res["pipeline_events"]
    qwen_ev = next((e for e in events if e["stage_id"] == "qwen_ollama"), None)
    assert qwen_ev is not None
    assert qwen_ev["status"] == StageStatus.PASSED.value
    assert qwen_ev["diagnostics"]["strategy"] in ("qwen_fallback", "whole_program_synthesis")
    assert qwen_ev["diagnostics"]["validation_passed"] is True
    assert "int a = 10;" in res["candidate"]["proposed_code"]


def test_qwen_coordinator_bounded_retry_on_validation_failure():
    """Verify Qwen coordinator receives compiler validation feedback and retries up to bound."""
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.base_url = "http://127.0.0.1:11434"
    mock_ollama.default_model = "qwen2.5-coder:3b"
    mock_ollama.timeout = 5.0

    call_records = []

    def mock_coord_call(*args, **kwargs):
        call_records.append(kwargs)
        if len(call_records) == 1:
            # First attempt returns invalid syntax
            return {
                "reasoning": "Attempt 1 with bad syntax",
                "strategy": "targeted_security_fix",
                "action": "request_candidate",
                "candidate_code": "int main() { int bad syntax here return 0; }",
            }
        else:
            # Second attempt receives compiler feedback and fixes it
            return {
                "reasoning": "Attempt 2 corrected with feedback",
                "strategy": "whole_program_synthesis",
                "action": "retry_with_feedback",
                "candidate_code": "int main() {\n    int a = 10;\n    return 0;\n}",
            }

    mock_ollama.coordinate_repair_decision.side_effect = mock_coord_call
    planner.ollama = mock_ollama

    code = "int main() {\n    int a = 10\n    return 0;\n}"

    with patch("compiler.gui_bridge.repair_source_for_gui", return_value={"corrected_code": code, "steps": []}):
        with patch("compiler.local_models.CodeT5Manager.generate_patch", return_value=(None, "CodeT5 skipped")):
            res = planner.plan_and_repair(code, filename="test_retry.c", language="c")

    # Assert 2 attempts occurred
    assert len(call_records) == 2
    # Second attempt received feedback from first attempt's validation failure
    assert call_records[1]["previous_feedback"] is not None
    assert "Validation failed" in call_records[1]["previous_feedback"]

    # Ultimately passed on attempt 2
    assert res["status"] == "REPAIR_PLAN_READY"
    assert "int a = 10;" in res["candidate"]["proposed_code"]
    qwen_ev = next((e for e in res["pipeline_events"] if e["stage_id"] == "qwen_ollama"), None)
    assert qwen_ev["diagnostics"]["attempts"] == 2


def test_cross_language_integrity_enforced_in_application_code():
    """Verify application code rejects cross-language conversions (e.g. converting Python to C)."""
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.base_url = "http://127.0.0.1:11434"
    mock_ollama.default_model = "qwen2.5-coder:3b"
    mock_ollama.timeout = 5.0

    # Model attempts to illicitly convert Python code to C
    mock_ollama.coordinate_repair_decision.return_value = {
        "reasoning": "Converting to C",
        "strategy": "invalid_convert",
        "action": "request_candidate",
        "candidate_code": "#include <stdio.h>\nint main() { printf(\"hi\"); return 0; }",
    }
    planner.ollama = mock_ollama

    python_code = "def foo():\n    x = 10\n    return x +\n"

    with patch("compiler.languages.python_lang.repair_python", return_value={"corrected_code": python_code, "steps": []}):
        res = planner.plan_and_repair(python_code, filename="test_lang.py", language="python")

    # Cross-language candidate must be rejected by application guard
    qwen_ev = next((e for e in res["pipeline_events"] if e["stage_id"] == "qwen_ollama"), None)
    assert qwen_ev["status"] == StageStatus.FAILED.value


def test_real_qwen_coordinator_live_invocation():
    """Verify genuine execution of local Qwen coordinator via Ollama if daemon is running."""
    ollama = OllamaClient()
    if not ollama.is_available():
        pytest.skip("Local Ollama daemon offline at http://127.0.0.1:11434")

    code = "int main() {\n    int a = 10\n    return 0;\n}"
    finding = Finding.create(
        category=FindingCategory.SYNTAX,
        line=2,
        col=14,
        explanation="Missing semicolon after declaration",
        evidence="int a = 10",
        file_path="main.c",
    )
    decision = ollama.coordinate_repair_decision(
        source_text=code,
        findings=[finding],
        filename="main.c",
        language="c",
    )

    assert isinstance(decision, dict)
    assert "action" in decision
    assert decision["action"] in ["request_candidate", "retry_with_feedback", "stop"]
    if decision.get("candidate_code"):
        cand = decision["candidate_code"]
        assert "int a = 10;" in cand
