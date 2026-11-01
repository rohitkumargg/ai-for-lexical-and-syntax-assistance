# tests/test_local_models.py
import pytest
from unittest.mock import patch, MagicMock

from compiler.finding import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    CorrectionSuggestion,
)
from compiler.local_models import (
    EscalationTier,
    ModelInfo,
    RepairAttemptResult,
    CodeT5Manager,
    OllamaClient,
    LocalModelPipeline,
    _assert_local_url,
)
from app import app


def test_security_assert_local_url_blocks_external():
    """Verify security guard strictly rejects external APIs (OpenAI, Anthropic, cloud endpoints)."""
    # Allowed local hosts
    _assert_local_url("http://127.0.0.1:11434")
    _assert_local_url("http://localhost:11434")
    _assert_local_url("http://0.0.0.0:11434")

    # Disallowed external endpoints
    with pytest.raises(ValueError, match="SECURITY VIOLATION"):
        _assert_local_url("https://api.openai.com/v1/chat/completions")

    with pytest.raises(ValueError, match="SECURITY VIOLATION"):
        _assert_local_url("https://api.anthropic.com/v1/messages")

    with pytest.raises(ValueError, match="SECURITY VIOLATION"):
        _assert_local_url("http://192.168.1.50:11434")


def test_codet5_manager_adapter_status():
    """Verify CodeT5Manager accurately inspects adapter directories on disk."""
    manager = CodeT5Manager()
    status = manager.get_adapter_status()

    assert "patch_adapter" in status
    assert "security_adapter" in status
    assert "semantic_adapter" in status

    # Patch adapter was found during audit
    assert status["patch_adapter"]["exists"] is True
    assert status["patch_adapter"]["size_mb"] > 0
    assert manager.is_available() is True


def test_codet5_unload():
    """Verify unload releases model and calls garbage collection without crashing."""
    manager = CodeT5Manager()
    manager.unload()
    assert manager._is_loaded is False


def test_ollama_client_offline_detection():
    """Verify OllamaClient detects offline status gracefully without throwing unhandled exceptions."""
    client = OllamaClient(base_url="http://127.0.0.1:19999", timeout_seconds=0.5)
    assert client.is_available() is False
    assert client.list_models() == []
    assert client.is_model_pulled("qwen2.5-coder:3b") is False


def test_ollama_client_code_extraction():
    """Verify code extraction from markdown code fences or raw C snippets."""
    client = OllamaClient()

    # Markdown with ```c
    raw1 = "Here is the fix:\n```c\nint main() {\n    return 0;\n}\n```\nHope this helps!"
    assert client._extract_code(raw1) == "int main() {\n    return 0;\n}"

    # Markdown with ```
    raw2 = "```\n#include <stdio.h>\nint main() { return 0; }\n```"
    assert client._extract_code(raw2) == "#include <stdio.h>\nint main() { return 0; }"

    # Fallback C code without fences
    raw3 = "int main() {\n    int a = 10;\n    return a;\n}"
    assert client._extract_code(raw3) == raw3


def test_escalation_ladder_and_category_routing():
    """Verify pipeline routes categories appropriately (CodeT5 primary, Qwen fallback, no deterministic rules)."""
    pipeline = LocalModelPipeline()

    # Syntax missing semicolon finding -> CodeT5 first, Qwen fallback
    fnd_syntax = Finding.create(
        category=FindingCategory.SYNTAX,
        line=2,
        col=10,
        explanation="missing ';'",
        metadata={"reason": "missing_semicolon"},
    )
    ladder_syntax = pipeline.route_category(fnd_syntax)
    assert ladder_syntax == [EscalationTier.CODET5, EscalationTier.QWEN_CODER]
    assert EscalationTier.DETERMINISTIC not in ladder_syntax

    # Complex logic finding -> Qwen preferred directly, bypassing CodeT5
    fnd_logic = Finding.create(
        category=FindingCategory.SEMANTIC,
        line=5,
        col=4,
        explanation="Complex expression mismatch",
        metadata={"reason": "complex_logic"},
    )
    ladder_logic = pipeline.route_category(fnd_logic)
    assert ladder_logic == [EscalationTier.QWEN_CODER]
    assert EscalationTier.DETERMINISTIC not in ladder_logic


def test_pipeline_codet5_primary_repair_success():
    """Verify pipeline successfully applies CodeT5 fix as primary tier without deterministic rules."""
    pipeline = LocalModelPipeline()
    code = """int main() {
    int x = 10
    return x;
}
"""
    fnd = Finding.create(
        category=FindingCategory.SYNTAX,
        line=2,
        col=15,
        explanation="missing ';'",
        metadata={"reason": "missing_semicolon", "raw_msg": "missing ';' at 'return'"},
    )

    repaired, attempts = pipeline.repair(code, fnd)
    assert ";" in repaired
    assert len(attempts) >= 1
    assert attempts[0].tier == EscalationTier.CODET5
    assert attempts[0].validation_passed is True


def test_pipeline_qwen_mock_repair():
    """Verify fallback to Qwen via mock when earlier tiers cannot resolve the finding."""
    pipeline = LocalModelPipeline()
    
    # Mock OllamaClient to simulate Qwen repair
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.generate_repair.return_value = (
        "int main() {\n    int x = 10;\n    return x;\n}\n",
        "Repaired by qwen2.5-coder:3b (local Ollama)",
    )
    pipeline.ollama = mock_ollama

    # Create finding where CodeT5 returns nothing
    code = "int main() { int x = ; return 0; }"
    fnd = Finding.create(
        category=FindingCategory.SYNTAX,
        line=1,
        col=21,
        explanation="unknown syntax construct",
        metadata={"reason": "unknown_reason"},
    )

    with patch.object(pipeline.codet5, "generate_patch", return_value=(None, "No valid patch")):
        repaired, attempts = pipeline.repair(code, fnd)
        assert mock_ollama.generate_repair.called
        qwen_attempts = [a for a in attempts if a.tier == EscalationTier.QWEN_CODER]
        assert len(qwen_attempts) == 1
        assert qwen_attempts[0].validation_passed is True


def test_api_models_status_and_unload_endpoints():
    """Verify Flask backend exposes /api/models/status and /api/models/unload cleanly."""
    client = app.test_client()

    # 1. GET /api/models/status
    res_status = client.get("/api/models/status")
    assert res_status.status_code == 200
    data = res_status.get_json()
    assert data["offline_enforced"] is True
    assert data["external_apis_allowed"] is False
    assert "codet5" in data
    assert "ollama" in data
    assert "escalation_ladder" in data
    assert data["escalation_ladder"] == [EscalationTier.CODET5.value, EscalationTier.QWEN_CODER.value]

    # 2. POST /api/models/unload
    res_unload = client.post("/api/models/unload")
    assert res_unload.status_code == 200
    unload_data = res_unload.get_json()
    assert unload_data["success"] is True
    assert unload_data["codet5_unloaded"] is True


def test_local_codet5_loading_and_base_model_path():
    """Verify CodeT5Manager points to local directory models/codet5-base and loads natively."""
    import os
    manager = CodeT5Manager()
    base_path = manager.get_base_model_path()
    assert os.path.isdir(base_path)
    assert base_path.endswith(os.path.join("models", "codet5-base"))

    status = manager.get_adapter_status()
    assert "base_model" in status
    assert status["base_model"]["exists"] is True


def test_codet5_real_candidate_generation_and_validation():
    """Verify CodeT5+LoRA generates and validates a real patch candidate on a broken C program."""
    manager = CodeT5Manager()
    code = "int main() {\n    int a = 10\n    return 0;\n}"
    cand, desc = manager.generate_patch(code, reason="missing_semicolon", line=2, col=14)

    assert cand is not None, f"Expected patch candidate from CodeT5, got error: {desc}"
    assert "int a = 10;" in cand
    assert desc is not None
    assert "INS_LC" in desc
    manager.unload()


def test_codet5_invalid_or_malformed_output_rejected():
    """Verify parse_patch_command and safety checks reject invalid or malformed outputs."""
    from compiler.ai_error_corrector import parse_patch_command, _is_safe_patch

    # Malformed command strings
    assert parse_patch_command("") is None
    assert parse_patch_command("INVALID_COMMAND") is None
    assert parse_patch_command("INS_LC 1") is None
    assert parse_patch_command("INS_LC one two ;") is None
    assert parse_patch_command("DEL 10 5") is None  # end < start
    assert parse_patch_command("REP 10 5 ;") is None  # end < start

    # Positional safety rejection: command position not in allowed error positions
    parsed_valid = parse_patch_command("INS_LC 1 10 ;")
    assert not _is_safe_patch(parsed_valid, allowed_positions=[0], source_text="int main() {}")

    # Family compatibility rejection: inserting non-semicolon payload for missing_semicolon
    from compiler.ai_error_corrector import _family_compatible
    bad_payload = parse_patch_command("INS_LC 1 10 system(\"rm -rf\");")
    assert not _family_compatible(
        family="missing_semicolon",
        source_before="int main() {}",
        source_after="int main() system(\"rm -rf\"); {}",
        patch=bad_payload,
        error_line=1,
        error_col=10,
    )


def test_orchestration_codet5_success_skips_qwen():
    """Verify CodeT5 primary succeeds on supported finding and Qwen is NOT called."""
    from compiler.repair_planner import RepairPlanner
    from compiler.pipeline_logger import StageStatus

    planner = RepairPlanner()

    # Mock OllamaClient as available
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.base_url = "http://127.0.0.1:11434"
    mock_ollama.default_model = "qwen2.5-coder:3b"
    mock_ollama.timeout = 5.0
    planner.ollama = mock_ollama
    # Isolate ML stage testing by setting deterministic rules to return no matches
    planner._apply_deterministic_rules = MagicMock(side_effect=lambda *a, **kw: (kw.get("source_code", a[0] if a else ""), []))

    # C code with syntax error: missing semicolon (supported by CodeT5)
    code = "int main() {\n    int a = 10\n    return 0;\n}"
    res = planner.plan_and_repair(code, filename="test_syntax.c", language="c")

    events = res.get("pipeline_events", [])
    det_ev = next((e for e in events if e["stage_id"] == "deterministic_rules"), None)
    c5_ev = next((e for e in events if e["stage_id"] == "codet5_model"), None)
    qwen_ev = next((e for e in events if e["stage_id"] == "qwen_ollama"), None)

    # Deterministic rules stage must be SKIPPED
    assert det_ev is not None
    assert det_ev["status"] == StageStatus.SKIPPED.value

    # CodeT5 must have run and passed
    assert c5_ev is not None
    assert c5_ev["status"] == StageStatus.PASSED.value

    # Qwen must NOT have been called (held in reserve / skipped)
    mock_ollama.coordinate_repair_decision.assert_not_called()
    assert qwen_ev is not None
    assert qwen_ev["status"] == StageStatus.SKIPPED.value

    # Candidate and strategy reporting
    assert res.get("candidate") is not None
    cand = res["candidate"]
    assert "int a = 10;" in cand["proposed_code"] or ";return 0;" in cand["proposed_code"]
    assert cand["repair_provider"] == "codet5"
    assert cand["repair_strategy"] == "codet5_primary"
    assert "CodeT5 Primary" in cand["title"]
    assert res["agent_telemetry"]["repair_provider"] == "codet5"
    assert res["agent_telemetry"]["repair_strategy"] == "codet5_primary"


def test_orchestration_codet5_generation_failure_qwen_fallback():
    """Verify safe fallback to Qwen when CodeT5 fails to generate a candidate."""
    from compiler.repair_planner import RepairPlanner
    from compiler.pipeline_logger import StageStatus

    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.base_url = "http://127.0.0.1:11434"
    mock_ollama.default_model = "qwen2.5-coder:3b"
    mock_ollama.timeout = 5.0

    qwen_repaired = "int main() {\n    int a = 10;\n    return 0;\n}"
    mock_ollama.coordinate_repair_decision.return_value = {
        "reasoning": "Synthesized declaration semicolon repair",
        "strategy": "whole_program_synthesis",
        "action": "request_candidate",
        "explanation": "Qwen2.5-Coder coordinated fallback repair",
        "candidate_code": qwen_repaired,
    }
    planner.ollama = mock_ollama
    planner._apply_deterministic_rules = MagicMock(side_effect=lambda *a, **kw: (kw.get("source_code", a[0] if a else ""), []))

    # Mock CodeT5 returning None (generation failure)
    with patch("compiler.local_models.CodeT5Manager.generate_patch", return_value=(None, "No valid patch")):
        code = "int main() {\n    int a = 10\n    return 0;\n}"
        res = planner.plan_and_repair(code, filename="test_escalate.c", language="c")

        events = res.get("pipeline_events", [])
        c5_ev = next((e for e in events if e["stage_id"] == "codet5_model"), None)
        qwen_ev = next((e for e in events if e["stage_id"] == "qwen_ollama"), None)

        assert c5_ev is not None
        assert c5_ev["status"] == StageStatus.FAILED.value

        assert qwen_ev is not None
        assert qwen_ev["status"] == StageStatus.PASSED.value
        assert mock_ollama.coordinate_repair_decision.called

        # Candidate and strategy reporting
        assert res.get("candidate") is not None
        cand = res["candidate"]
        assert cand["repair_provider"] == "qwen2.5-coder"
        assert cand["repair_strategy"] == "qwen_fallback"
        assert cand["fallback_reason"] == "codet5_generation_failed"
        assert "Qwen Fallback" in cand["title"]


def test_orchestration_codet5_malformed_output_qwen_fallback():
    """Verify fallback to Qwen when CodeT5 generates malformed output that fails candidate validation."""
    from compiler.repair_planner import RepairPlanner
    from compiler.pipeline_logger import StageStatus

    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.base_url = "http://127.0.0.1:11434"
    mock_ollama.default_model = "qwen2.5-coder:3b"
    mock_ollama.timeout = 5.0

    qwen_repaired = "int main() {\n    int a = 10;\n    return 0;\n}"
    mock_ollama.coordinate_repair_decision.return_value = {
        "reasoning": "Synthesized declaration repair",
        "strategy": "whole_program_synthesis",
        "action": "request_candidate",
        "explanation": "Qwen2.5-Coder fallback repair",
        "candidate_code": qwen_repaired,
    }
    planner.ollama = mock_ollama
    planner._apply_deterministic_rules = MagicMock(side_effect=lambda *a, **kw: (kw.get("source_code", a[0] if a else ""), []))

    # Mock CodeT5 returning broken/invalid C code
    malformed_c5_code = "int main() { INVALID C SYNTAX HERE }"
    with patch("compiler.local_models.CodeT5Manager.generate_patch", return_value=(malformed_c5_code, "malformed patch")):
        code = "int main() {\n    int a = 10\n    return 0;\n}"
        res = planner.plan_and_repair(code, filename="test_malformed.c", language="c")

        events = res.get("pipeline_events", [])
        c5_ev = next((e for e in events if e["stage_id"] == "codet5_model"), None)
        qwen_ev = next((e for e in events if e["stage_id"] == "qwen_ollama"), None)

        assert c5_ev is not None
        assert c5_ev["status"] == StageStatus.FAILED.value
        assert "validation" in c5_ev["description"].lower()

        assert qwen_ev is not None
        assert qwen_ev["status"] == StageStatus.PASSED.value

        cand = res["candidate"]
        assert cand["repair_provider"] == "qwen2.5-coder"
        assert cand["repair_strategy"] == "qwen_fallback"
        assert cand["fallback_reason"] == "codet5_validation_failed"


def test_orchestration_unsupported_codet5_finding_routes_to_qwen():
    """Verify findings outside CodeT5 domain (e.g. Python code) route directly to Qwen fallback."""
    from compiler.repair_planner import RepairPlanner
    from compiler.pipeline_logger import StageStatus

    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.base_url = "http://127.0.0.1:11434"
    mock_ollama.default_model = "qwen2.5-coder:3b"
    mock_ollama.timeout = 5.0

    py_repaired = "def calculate():\n    return 42\n"
    mock_ollama.coordinate_repair_decision.return_value = {
        "reasoning": "Fixed Python syntax",
        "strategy": "whole_program_synthesis",
        "action": "request_candidate",
        "explanation": "Qwen2.5-Coder fallback repair for Python",
        "candidate_code": py_repaired,
    }
    planner.ollama = mock_ollama

    # Python code with syntax error (missing colon)
    py_code = "def calculate()\n    return 42\n"
    res = planner.plan_and_repair(py_code, filename="test.py", language="python")

    events = res.get("pipeline_events", [])
    c5_ev = next((e for e in events if e["stage_id"] == "codet5_model"), None)
    qwen_ev = next((e for e in events if e["stage_id"] == "qwen_ollama"), None)

    # CodeT5 skipped for Python
    assert c5_ev is not None
    assert c5_ev["status"] == StageStatus.SKIPPED.value

    # Qwen handled fallback
    assert qwen_ev is not None
    assert qwen_ev["status"] == StageStatus.PASSED.value
    assert res.get("candidate") is not None
    assert res["candidate"]["repair_provider"] == "qwen2.5-coder"
    assert res["candidate"]["repair_strategy"] == "qwen_fallback"


def test_orchestration_qwen_failure_returns_unresolved_no_deterministic_fallback():
    """Verify that when CodeT5 and Qwen both fail, system returns UNRESOLVED with zero deterministic fallback."""
    from compiler.repair_planner import RepairPlanner
    from compiler.pipeline_logger import StageStatus

    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.base_url = "http://127.0.0.1:11434"
    mock_ollama.default_model = "qwen2.5-coder:3b"
    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "stop",
        "candidate_code": None,
        "explanation": "Cannot repair safely",
    }
    planner.ollama = mock_ollama
    planner._apply_deterministic_rules = MagicMock(side_effect=lambda *a, **kw: (kw.get("source_code", a[0] if a else ""), []))

    # Force CodeT5 to fail
    with patch("compiler.local_models.CodeT5Manager.generate_patch", return_value=(None, "No valid patch")):
        code = "int main() {\n    int a = 10\n    return 0;\n}"
        res = planner.plan_and_repair(code, filename="test_unresolved.c", language="c")

        assert res["status"] == "UNRESOLVED"
        assert res["candidate"] is None
        assert res["agent_telemetry"]["repair_provider"] is None
        assert res["agent_telemetry"]["repair_strategy"] is None

        events = res.get("pipeline_events", [])
        c5_ev = next((e for e in events if e["stage_id"] == "codet5_model"), None)
        qwen_ev = next((e for e in events if e["stage_id"] == "qwen_ollama"), None)
        assert c5_ev["status"] == StageStatus.FAILED.value
        assert qwen_ev["status"] == StageStatus.FAILED.value


def test_no_deterministic_ast_rules_tool_or_strategy():
    """Verify deterministic_ast_rules is removed from available tools and never selected as a strategy."""
    client = OllamaClient()
    # Mocking call to coordinate_repair_decision to inspect formatted prompt
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        import json
        mock_resp.read.return_value = json.dumps({"response": "{\"action\": \"stop\"}"}).encode("utf-8")
        mock_url.return_value.__enter__.return_value = mock_resp

        client.coordinate_repair_decision(
            source_text="int main() { return 0; }",
            findings=[],
            filename="main.c",
            language="c",
        )

        # Inspect the request payload sent to Ollama
        assert mock_url.called
        req = mock_url.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        prompt_text = payload.get("prompt", "")
        assert "deterministic_ast_rules" not in prompt_text

