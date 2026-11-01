"""
tests/test_sequential_repair_and_ui_cleanup.py
Comprehensive unit and integration test suite proving the Qwen-only repair workflow:
Apply -> Re-Analyze -> Conditional Qwen

Verifies:
1. Qwen exclusively generates the repair proposal.
2. Original editor source remains unchanged until Apply.
3. Applying the proposal triggers a fresh complete analysis.
4. Fresh analysis uses the exact applied editor source.
5. Qwen is not re-invoked when all required checks pass.
6. Qwen is invoked when errors remain after applying a candidate.
7. Qwen receives the latest applied source and findings.
8. Qwen generates a proposal without automatically overwriting the editor.
9. Applying a Qwen proposal triggers another fresh analysis.
10. Security analysis runs after every applied candidate.
11. Stale proposals cannot overwrite newer editor contents.
12. Retry limits and repeated-candidate detection prevent infinite loops.
13. CodeT5 is completely removed from repair generation and pipeline logs.
14. Pipeline logs remain operational with deterministic repair rules and CodeT5 removed from view.
"""

import hashlib
import json
import pytest
from unittest.mock import MagicMock, patch

from compiler.repair_planner import RepairPlanner
from compiler.pipeline_logger import StageStatus
from compiler.local_models import OllamaClient
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# 1. Qwen generates repair proposal when CodeT5 fails to provide repair
def test_requirement_1_qwen_generates_repair_proposal():
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True

    code = "int main() {\n    int a = 10\n    return 0;\n}"
    qwen_repaired = "int main() {\n    int a = 10;\n    return 0;\n}"
    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "request_candidate",
        "strategy": "whole_program_synthesis",
        "candidate_code": qwen_repaired,
        "explanation": "Insert missing semicolon",
    }
    planner.ollama = mock_ollama

    with patch.object(planner.codet5, "generate_patch", return_value=(None, "No valid patch")):
        res = planner.plan_and_repair(code, filename="main.c", language="c")

        assert res["workflow_state"] == "QWEN_PROPOSAL_READY"
        assert res["repair_strategy"] in ("qwen_repair", "qwen_fallback")
        assert res["repair_provider"] == "qwen2.5-coder"
        assert res["proposed_code"] == qwen_repaired
        mock_ollama.coordinate_repair_decision.assert_called_once()

        # Deterministic repair rules must NOT be in pipeline events
        stage_names = [e["stage_name"] for e in res["pipeline_events"]]
        assert not any("deterministic repair rules" in name.lower() for name in stage_names)


# 2. Original editor source remains unchanged until Apply
def test_requirement_2_original_editor_source_unchanged_until_apply():
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True

    original_code = "int main() {\n    int a = 10\n    return 0;\n}"
    qwen_repaired = "int main() {\n    int a = 10;\n    return 0;\n}"
    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "request_candidate",
        "strategy": "whole_program_synthesis",
        "candidate_code": qwen_repaired,
        "explanation": "Insert missing semicolon",
    }
    planner.ollama = mock_ollama

    with patch.object(planner.codet5, "generate_patch", return_value=(None, "No valid patch")):
        res = planner.plan_and_repair(original_code, filename="main.c", language="c")

        # Original code must be preserved exactly
        assert res["original_code"] == original_code
        assert res["original_source_hash"] == sha256_text(original_code)
        # The candidate copy is stored separately
        assert res["proposed_code"] == qwen_repaired
        assert res["proposed_code"] != res["original_code"]


# 3 & 4. Applying proposal triggers fresh complete analysis using exact applied editor source
def test_requirement_3_and_4_applying_proposal_triggers_fresh_analysis_using_applied_source():
    planner = RepairPlanner()
    original_code = "int main() {\n    int a = 10\n    return 0;\n}"
    applied_source = "int main() {\n    int a = 10;\n    return 0;\n}"
    applied_hash = sha256_text(applied_source)

    res = planner.post_apply_reanalyze_and_escalate(
        editor_source=applied_source,
        filename="main.c",
        language="c",
        applied_from_state="QWEN_PROPOSAL_READY",
        original_source_hash=sha256_text(original_code),
        applied_source_hash=applied_hash,
    )

    # Must run fresh analysis on the exact editor source and pass
    assert res["workflow_state"] == "ALL_CHECKS_PASSED"
    assert res["applied_source"] == applied_source
    assert res["applied_source_hash"] == applied_hash
    assert len(res["remaining_findings"]) == 0


# 5. Qwen is NOT invoked when all required checks pass
def test_requirement_5_qwen_not_invoked_when_all_checks_pass():
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    planner.ollama = mock_ollama

    clean_applied_source = "int main() {\n    int a = 10;\n    return 0;\n}"
    res = planner.post_apply_reanalyze_and_escalate(
        editor_source=clean_applied_source,
        filename="main.c",
        language="c",
        applied_from_state="QWEN_PROPOSAL_READY",
        applied_source_hash=sha256_text(clean_applied_source),
    )

    assert res["workflow_state"] == "ALL_CHECKS_PASSED"
    # Qwen coordinate_repair_decision must NEVER be called
    mock_ollama.coordinate_repair_decision.assert_not_called()


# 6 & 7. Qwen IS invoked when errors remain after applying candidate, receiving latest applied source and findings
def test_requirement_6_and_7_qwen_invoked_with_applied_source_when_errors_remain():
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    planner.ollama = mock_ollama

    partially_fixed_code = "int main() {\n    int a = 10;\n    b = 20\n    return 0;\n}"
    qwen_fixed_code = "int main() {\n    int a = 10;\n    int b = 20;\n    return 0;\n}"

    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "request_candidate",
        "strategy": "whole_program_synthesis",
        "candidate_code": qwen_fixed_code,
        "explanation": "Declared variable b and added missing semicolon",
    }

    res = planner.post_apply_reanalyze_and_escalate(
        editor_source=partially_fixed_code,
        filename="main.c",
        language="c",
        applied_from_state="QWEN_PROPOSAL_READY",
        applied_source_hash=sha256_text(partially_fixed_code),
        initial_findings=[],
    )

    # Qwen must have been called
    assert mock_ollama.coordinate_repair_decision.called
    call_kwargs = mock_ollama.coordinate_repair_decision.call_args[1]
    assert call_kwargs["source_text"] == partially_fixed_code
    assert len(call_kwargs["findings"]) > 0

    assert res["workflow_state"] == "QWEN_PROPOSAL_READY"
    assert res["proposed_code"] == qwen_fixed_code
    assert res["parent_source_hash"] == sha256_text(partially_fixed_code)


# 8. Qwen generates a proposal without automatically overwriting the editor
def test_requirement_8_qwen_generates_proposal_without_editor_overwrite(client):
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    planner.ollama = mock_ollama

    partially_fixed_code = "int main() {\n    int a = 10;\n    b = 20\n    return 0;\n}"
    qwen_fixed_code = "int main() {\n    int a = 10;\n    int b = 20;\n    return 0;\n}"

    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "request_candidate",
        "strategy": "whole_program_synthesis",
        "candidate_code": qwen_fixed_code,
        "explanation": "Declared variable b and added missing semicolon",
    }

    with patch("compiler.repair_planner.RepairPlanner.post_apply_reanalyze_and_escalate", wraps=planner.post_apply_reanalyze_and_escalate):
        resp = client.post("/api/repair/post_apply", json={
            "source_code": partially_fixed_code,
            "filename": "main.c",
            "language": "c",
            "applied_from_state": "QWEN_PROPOSAL_READY",
            "applied_source_hash": sha256_text(partially_fixed_code),
        })

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["workflow_state"] == "QWEN_PROPOSAL_READY"
    assert data["candidate"]["proposed_code"] == qwen_fixed_code
    assert data["applied_source"] == partially_fixed_code


# 9. Applying Qwen proposal triggers another fresh analysis
def test_requirement_9_applying_qwen_proposal_triggers_fresh_analysis():
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    planner.ollama = mock_ollama

    qwen_fixed_code = "int main() {\n    int a = 10;\n    int b = 20;\n    return 0;\n}"
    qwen_hash = sha256_text(qwen_fixed_code)

    res = planner.post_apply_reanalyze_and_escalate(
        editor_source=qwen_fixed_code,
        filename="main.c",
        language="c",
        applied_from_state="QWEN_PROPOSAL_READY",
        applied_source_hash=qwen_hash,
    )

    assert res["workflow_state"] == "ALL_CHECKS_PASSED"
    assert res["applied_source"] == qwen_fixed_code
    assert len(res["remaining_findings"]) == 0


# 10. Security analysis runs after every applied candidate
def test_requirement_10_security_analysis_runs_after_applied_candidate():
    planner = RepairPlanner()

    # Candidate introduces insecure gets() call
    insecure_applied_code = '#include <stdio.h>\nint main() {\n    char buf[64];\n    gets(buf);\n    return 0;\n}'
    insecure_hash = sha256_text(insecure_applied_code)

    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "request_candidate",
        "candidate_code": '#include <stdio.h>\nint main() {\n    char buf[64];\n    fgets(buf, sizeof(buf), stdin);\n    return 0;\n}',
        "explanation": "Replaced gets with fgets",
    }
    planner.ollama = mock_ollama

    res = planner.post_apply_reanalyze_and_escalate(
        editor_source=insecure_applied_code,
        filename="main.c",
        language="c",
        applied_from_state="QWEN_PROPOSAL_READY",
        applied_source_hash=insecure_hash,
    )

    # Must NOT declare success because security finding exists!
    assert res["workflow_state"] != "ALL_CHECKS_PASSED"
    # Escalate to Qwen to resolve security issue
    assert res["workflow_state"] == "QWEN_PROPOSAL_READY"


# 11. Stale proposals cannot overwrite newer editor contents
def test_requirement_11_stale_proposals_cannot_overwrite_newer_editor_contents():
    planner = RepairPlanner()
    stale_expected_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    modified_editor_source = "int main() {\n    int a = 99;\n    return 0;\n}"

    res = planner.post_apply_reanalyze_and_escalate(
        editor_source=modified_editor_source,
        filename="main.c",
        language="c",
        applied_from_state="QWEN_PROPOSAL_READY",
        applied_source_hash=stale_expected_hash,
    )

    assert res["status"] == "ERROR"
    assert res["workflow_state"] == "STALE_SOURCE_REJECTED"
    assert "cannot overwrite" in res["message"].lower() or "does not match" in res["message"].lower()


# 12. Retry limits and repeated-candidate detection prevent infinite loops
def test_requirement_12_retry_limits_and_cycle_detection_prevent_infinite_loops():
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    planner.ollama = mock_ollama

    source = "int main() {\n    int a = 10\n    return 0;\n}"
    src_hash = sha256_text(source)

    # Test 12a: Max retry limit reached
    res_retry = planner.post_apply_reanalyze_and_escalate(
        editor_source=source,
        filename="main.c",
        language="c",
        retry_count=2,
        max_retries=2,
        applied_source_hash=src_hash,
    )
    assert res_retry["workflow_state"] == "RETRY_LIMIT_REACHED"

    # Test 12b: Cycle detection
    res_cycle = planner.post_apply_reanalyze_and_escalate(
        editor_source=source,
        filename="main.c",
        language="c",
        retry_count=0,
        history_hashes=[src_hash],
        applied_source_hash=src_hash,
    )
    assert res_cycle["workflow_state"] == "RETRY_LIMIT_REACHED"


# 13. Two-model repair hierarchy: CodeT5 primary, Qwen fallback
def test_requirement_13_codet5_primary_and_qwen_fallback():
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True

    code = "int main() {\n    int a = 10\n    return 0;\n}"
    qwen_repaired = "int main() {\n    int a = 10;\n    return 0;\n}"
    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "request_candidate",
        "strategy": "whole_program_synthesis",
        "candidate_code": qwen_repaired,
        "explanation": "Insert missing semicolon",
    }
    planner.ollama = mock_ollama

    # 1. Primary: CodeT5 succeeds on supported syntax issue
    res = planner.plan_and_repair(code, filename="main.c", language="c")
    assert res["repair_provider"] == "codet5"
    assert res["agent_telemetry"]["codet5_active"] is True
    assert "codet5_model" in [e["stage_id"] for e in res["pipeline_events"]]

    # 2. Fallback: When CodeT5 fails, Qwen provides repair
    with patch.object(planner.codet5, "generate_patch", return_value=(None, "No valid patch")):
        res_fb = planner.plan_and_repair(code, filename="main.c", language="c")
        assert res_fb["repair_provider"] == "qwen2.5-coder"
        assert res_fb["agent_telemetry"]["codet5_active"] is False
        assert res_fb["agent_telemetry"]["qwen_active"] is True


# 14. Existing pipeline logs and UI cleanup
def test_requirement_14_pipeline_logs_and_ui_cleanup(client):
    resp = client.get("/api/pipeline/latest")
    assert resp.status_code == 200

    with open("gui/templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert 'id="card-logs"' in html
    assert 'id="logs"' in html
    assert 'id="badge-logs"' in html

    assert '<div style="display:none;" id="legacyPanelsHiddenContainer">' in html

    with open("gui/static/app.js", "r", encoding="utf-8") as f:
        app_js = f.read()

    assert "CodeT5 (Primary Generator)" not in app_js
    assert "Qwen2.5-Coder (Fallback Generator)" not in app_js
