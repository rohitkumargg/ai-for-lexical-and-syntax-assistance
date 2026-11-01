import pytest
from unittest.mock import MagicMock, patch

from compiler.agents import SecurityAgent, PythonSecurityAgent
from compiler.finding import FindingCategory, FindingSeverity, FindingStatus
from compiler.local_models import OllamaClient
from compiler.repair_planner import RepairPlanner


def test_security_agent_uses_qwen_for_repairs():
    """Verify SecurityAgent uses Qwen to generate repairs / possible fix code to the user."""
    code = """#include <stdio.h>
int main() {
    char buf[100];
    gets(buf);
    return 0;
}
"""
    repaired_code = """#include <stdio.h>
int main() {
    char buf[100];
    fgets(buf, sizeof(buf), stdin);
    return 0;
}
"""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "request_candidate",
        "strategy": "security_repair",
        "candidate_code": repaired_code,
        "explanation": "Replaced unsafe gets() with bounded fgets()",
    }

    agent = SecurityAgent(ollama=mock_ollama, enable_qwen=True)
    findings = agent.analyze(code, filename="sec_test.c")

    # Assert findings were produced
    sec_findings = [f for f in findings if f.category == FindingCategory.SECURITY]
    assert len(sec_findings) >= 1

    # Assert Qwen was invoked to coordinate and generate repair
    mock_ollama.coordinate_repair_decision.assert_called_once()

    # Assert the Qwen repair candidate is provided in suggested_corrections
    finding = sec_findings[0]
    qwen_suggestions = [
        s for s in finding.suggested_corrections
        if not s.is_deterministic and s.replacement_text == repaired_code
    ]
    assert len(qwen_suggestions) >= 1
    assert "Qwen AI security repair" in qwen_suggestions[0].description
    assert "fgets" in qwen_suggestions[0].replacement_text


def test_security_agent_generate_qwen_repair_direct():
    """Verify SecurityAgent.generate_qwen_repair() method produces the candidate code."""
    code = "int main() { char b[10]; gets(b); return 0; }"
    fixed = "int main() { char b[10]; fgets(b, sizeof(b), stdin); return 0; }"

    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.coordinate_repair_decision.return_value = {
        "candidate_code": fixed,
        "explanation": "Safe fgets repair",
    }

    agent = SecurityAgent(ollama=mock_ollama)
    cand, expl = agent.generate_qwen_repair(code, findings=[{"category": "SECURITY", "line": 1}], filename="main.c")

    assert cand == fixed
    assert "Safe fgets repair" in expl


def test_python_security_agent_uses_qwen_for_repairs():
    """Verify PythonSecurityAgent uses Qwen to generate repairs / possible fix code to the user."""
    code = """import os
def run_user_cmd(cmd):
    eval(cmd)
"""
    fixed = """import ast
def run_user_cmd(cmd):
    ast.literal_eval(cmd)
"""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "request_candidate",
        "strategy": "python_security_repair",
        "candidate_code": fixed,
        "explanation": "Replaced dangerous eval with ast.literal_eval",
    }

    agent = PythonSecurityAgent(ollama=mock_ollama, enable_qwen=True)
    findings = agent.analyze(code, filename="sec_test.py")

    sec_findings = [f for f in findings if f.category == FindingCategory.SECURITY]
    assert len(sec_findings) >= 1

    # Verify Qwen was invoked
    mock_ollama.coordinate_repair_decision.assert_called_once()

    # Verify Qwen repair code is attached to suggested corrections
    finding = sec_findings[0]
    qwen_suggestions = [
        s for s in finding.suggested_corrections
        if s.replacement_text == fixed
    ]
    assert len(qwen_suggestions) >= 1
    assert "Qwen AI security repair" in qwen_suggestions[0].description


def test_repair_planner_routes_security_findings_directly_to_qwen():
    """Verify RepairPlanner routes SecurityAgent findings directly to Qwen, skipping CodeT5."""
    code = """#include <stdio.h>
int main() {
    char buf[100];
    gets(buf);
    return 0;
}
"""
    fixed_code = """#include <stdio.h>
int main() {
    char buf[100];
    fgets(buf, sizeof(buf), stdin);
    return 0;
}
"""
    mock_decision = {
        "reasoning": "Unsafe gets() API detected; replace with fgets()",
        "strategy": "security_repair",
        "action": "request_candidate",
        "explanation": "Replaced gets with fgets to eliminate buffer overflow",
        "candidate_code": fixed_code,
    }

    planner = RepairPlanner()

    with patch.object(planner.ollama, "is_available", return_value=True):
        with patch.object(planner.remediation_engine, "generate_recommendations", return_value=[]):
            with patch.object(planner, "_try_deterministic_fix", return_value=(None, None)):
                with patch.object(planner.ollama, "coordinate_repair_decision", return_value=mock_decision) as mock_qwen:
                    with patch.object(planner.codet5, "generate_patch") as mock_codet5:
                        plan = planner.plan_and_repair(
                            source_code=code,
                            filename="sec_test.c",
                            language="c",
                        )

                # CodeT5 must NOT be invoked for security defects
                mock_codet5.assert_not_called()

                # Qwen MUST be invoked as the repair generator
                mock_qwen.assert_called_once()
                assert plan.get("repair_strategy") in ("qwen_repair", "qwen_fallback")
                assert plan.get("repair_provider") == "qwen2.5-coder"
                assert "fgets" in plan.get("proposed_code", "")
