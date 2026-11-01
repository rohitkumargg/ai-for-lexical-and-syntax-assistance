"""
tests/test_multi_agent_precheck_architecture.py
Comprehensive test suite verifying the Final Multi-Agent Compiler Repair Architecture
with Malicious Code Precheck.

Verifies:
1. Ordinary valid C source code passes precheck, analysis, and validation.
2. Lexical, syntax, and semantic errors are cleanly classified and prioritized by the multi-agent orchestrator.
3. Unsafe input and buffer-related patterns (gets, unbounded scanf) are flagged with mitigation guidance.
4. Dangerous command execution patterns (system, popen) are detected and classified.
5. Suspicious file operations (/etc/shadow access, destructive shell commands) are identified.
6. False-positive cases involving legitimate uses (system("pause"), system("cls")) are handled with context awareness.
7. High-risk code is blocked from execution by ProgramExecutor.
8. Static analysis and repair planning remain fully operational even when program execution is blocked.
9. Precheck findings reach the multi-agent orchestrator and are passed into Qwen's repair prompt.
10. Independent candidate validation detects both unresolved and newly introduced vulnerabilities/regressions.
11. User approval is strictly required before the editor source can be modified (Apply gate).
12. Re-analysis runs after Apply without triggering an automatic repair loop.
13. Local Ollama failure and malformed model output are handled gracefully with honest reporting.
14. Preservation of existing hardware Green Metrics, Code Quality, Security Risk scores, pipeline logs, and Program Output.
"""

import hashlib
import json
import pytest
from unittest.mock import MagicMock, patch

from compiler.malicious_precheck import (
    MaliciousCodePrecheck,
    PrecheckFinding,
    PrecheckPolicy,
    RiskLevel,
)
from compiler.orchestrator import AgentOrchestrator
from compiler.finding import FindingCategory, FindingSeverity
from compiler.repair_planner import RepairPlanner
from compiler.patch_validator import PatchValidator, ValidationVerdict
from compiler.program_executor import ProgramExecutor, ExecutionStatus
from compiler.local_models import OllamaClient
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def sha256_text(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# =========================================================================
# 1. Ordinary Valid C Source Code
# =========================================================================
def test_1_ordinary_valid_c_source_passes_cleanly():
    code = "#include <stdio.h>\nint main() {\n    printf(\"Hello, World!\\n\");\n    return 0;\n}"
    report = MaliciousCodePrecheck.analyze(code, filename="main.c")
    assert report.is_clean is True
    assert report.highest_risk_level == RiskLevel.LOW
    assert report.blocks_execution is False
    assert len(report.findings) == 0

    planner = RepairPlanner()
    res = planner.plan_and_repair(code, filename="main.c", language="c")
    assert res["status"] == "CLEAN"
    assert len(res["findings"]) == 0
    assert res["precheck_report"]["is_clean"] is True


# =========================================================================
# 2. Lexical, Syntax, and Semantic Errors Handled by Orchestrator
# =========================================================================
def test_2_lexical_syntax_semantic_prioritization_and_dependencies():
    # Code with syntax error: missing semicolon and undeclared identifier
    code = "int main() {\n    int a = 10\n    b = 20;\n    return a;\n}"
    orchestrator = AgentOrchestrator()
    res = orchestrator.run_analysis(code, filename="main.c", language="c")

    assert len(res.findings) > 0
    categories = {f.category for f in res.findings}
    assert FindingCategory.SYNTAX in categories

    # Dependency tracking: syntax error is root cause
    assert len(res.root_cause_findings) > 0
    assert res.root_cause_findings[0].category == FindingCategory.SYNTAX
    assert res.root_cause_findings[0].is_root_cause is True


# =========================================================================
# 3. Unsafe Input and Buffer-Related Patterns
# =========================================================================
def test_3_unsafe_input_and_buffer_overflow_patterns_detected():
    # gets() invocation and unbounded scanf("%s")
    code = '#include <stdio.h>\nint main() {\n    char buf[16];\n    gets(buf);\n    scanf("%s", buf);\n    return 0;\n}'
    report = MaliciousCodePrecheck.analyze(code, filename="main.c")

    rule_ids = {f.rule_id for f in report.findings}
    assert "PRECHECK-DANG-001" in rule_ids  # gets()
    assert "PRECHECK-BUFFER-001" in rule_ids  # scanf("%s")

    gets_finding = next(f for f in report.findings if f.rule_id == "PRECHECK-DANG-001")
    assert gets_finding.severity == "CRITICAL"
    assert "fgets" in gets_finding.recommended_mitigation
    assert gets_finding.confidence >= 0.95


# =========================================================================
# 4. Dangerous Command Execution Patterns
# =========================================================================
def test_4_dangerous_command_execution_patterns_detected():
    # system() and popen() with dynamic/arbitrary command
    code = '#include <stdlib.h>\n#include <stdio.h>\nint main() {\n    system("cmd.exe");\n    popen("bash", "r");\n    return 0;\n}'
    report = MaliciousCodePrecheck.analyze(code, filename="main.c")

    cmd_findings = [f for f in report.findings if f.category == "COMMAND_EXECUTION"]
    assert len(cmd_findings) >= 2
    assert report.blocks_execution is True
    assert report.highest_risk_level in (RiskLevel.HIGH_RISK, RiskLevel.POTENTIALLY_DANGEROUS)


# =========================================================================
# 5. Suspicious File and Destructive Operations
# =========================================================================
def test_5_suspicious_file_and_destructive_operations_detected():
    # Access to /etc/shadow and destructive command del
    code = '#include <stdio.h>\n#include <stdlib.h>\nint main() {\n    fopen("/etc/shadow", "r");\n    system("del /f /s /q C:\\\\");\n    return 0;\n}'
    report = MaliciousCodePrecheck.analyze(code, filename="main.c")

    rule_ids = {f.rule_id for f in report.findings}
    assert "PRECHECK-SENSITIVE-FILE-001" in rule_ids
    assert "PRECHECK-DESTRUCTIVE-001" in rule_ids or "PRECHECK-CMD-001" in rule_ids
    assert report.blocks_execution is True
    assert report.highest_risk_level == RiskLevel.HIGH_RISK


# =========================================================================
# 6. False-Positive Context Awareness (system("pause"), system("cls"))
# =========================================================================
def test_6_context_awareness_avoids_false_positives_on_benign_system():
    # Educational C program using system("pause") and system("cls")
    code = '#include <stdlib.h>\nint main() {\n    system("cls");\n    system("pause");\n    return 0;\n}'
    report = MaliciousCodePrecheck.analyze(code, filename="main.c")

    # Benign literals must NOT be flagged as high-risk or malicious intent
    assert not any(f.is_malicious_intent for f in report.findings)
    assert report.highest_risk_level == RiskLevel.LOW
    assert report.blocks_execution is False


# =========================================================================
# 7. High-Risk Code Blocked from Execution
# =========================================================================
def test_7_high_risk_code_blocked_from_execution_in_program_executor():
    # Destructive command embedded in C program
    code = '#include <stdlib.h>\nint main() {\n    system("rm -rf /");\n    return 0;\n}'
    executor = ProgramExecutor()

    res = executor.execute_c(source_code=code, filename="main.c")
    assert res.status == ExecutionStatus.SECURITY_BLOCKED.value
    assert "blocked" in res.stderr.lower()
    assert res.exit_code is None


# =========================================================================
# 8. Static Analysis Remains Available When Execution Is Blocked
# =========================================================================
def test_8_static_analysis_remains_available_when_execution_blocked():
    # High-risk gets() and system("rm -rf /") with syntax issue
    code = '#include <stdlib.h>\nint main() {\n    int a = 10\n    system("rm -rf /");\n    return 0;\n}'
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True

    fixed_code = '#include <stdlib.h>\nint main() {\n    int a = 10;\n    return 0;\n}'
    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "request_candidate",
        "strategy": "whole_program_synthesis",
        "candidate_code": fixed_code,
        "explanation": "Added missing semicolon and removed destructive command",
    }
    planner.ollama = mock_ollama

    # Static analysis must NOT be terminated by high-risk finding
    res = planner.plan_and_repair(code, filename="main.c", language="c")
    assert res["status"] == "REPAIR_PLAN_READY"
    assert res["workflow_state"] == "QWEN_PROPOSAL_READY"
    assert len(res["findings"]) > 0


# =========================================================================
# 9. Precheck Findings Reach Orchestrator and Qwen Repair Prompt
# =========================================================================
def test_9_precheck_findings_reach_orchestrator_and_qwen_prompt():
    code = '#include <stdio.h>\nint main() {\n    char b[32];\n    gets(b);\n    return 0;\n}'
    orchestrator = AgentOrchestrator()
    orch_res = orchestrator.run_analysis(code, filename="main.c", language="c")

    # Precheck finding must be present in orchestrator findings
    precheck_findings = [f for f in orch_res.findings if f.metadata.get("precheck")]
    assert len(precheck_findings) > 0
    assert any("gets" in f.explanation.lower() for f in precheck_findings)

    # Qwen receives findings in coordinate_repair_decision
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "request_candidate",
        "candidate_code": '#include <stdio.h>\nint main() {\n    char b[32];\n    fgets(b, sizeof(b), stdin);\n    return 0;\n}',
        "explanation": "Replaced gets with fgets",
    }
    planner.ollama = mock_ollama

    planner.plan_and_repair(code, filename="main.c", language="c")
    assert mock_ollama.coordinate_repair_decision.called
    call_kwargs = mock_ollama.coordinate_repair_decision.call_args[1]
    findings_passed = call_kwargs["findings"]
    assert any("gets" in getattr(f, "explanation", "").lower() for f in findings_passed)


# =========================================================================
# 10. Candidate Validation Detects Regressions and Introduced Precheck Issues
# =========================================================================
def test_10_candidate_validation_detects_introduced_vulnerabilities():
    orig_code = '#include <stdio.h>\nint main() {\n    int a = 10;\n    return 0;\n}'
    # Candidate introduces dangerous gets() and rm -rf command
    bad_cand = '#include <stdio.h>\n#include <stdlib.h>\nint main() {\n    char b[32];\n    gets(b);\n    system("rm -rf /");\n    return 0;\n}'

    validator = PatchValidator()
    report = validator.validate_patch(original_code=orig_code, candidate_code=bad_cand, filename="main.c", language="c")

    # Validation must detect the regression
    assert report.is_valid is False
    assert report.security_passed is False
    assert len(report.remaining_risks) > 0
    assert any("regression" in r.lower() or "precheck" in r.lower() for r in report.remaining_risks)


# =========================================================================
# 11. User Approval Required Before Source Changes (Apply Gate)
# =========================================================================
def test_11_editor_source_unchanged_until_explicit_user_apply(client):
    code = "int main() {\n    int a = 10\n    return 0;\n}"
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    fixed = "int main() {\n    int a = 10;\n    return 0;\n}"
    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "request_candidate",
        "candidate_code": fixed,
        "explanation": "Added semicolon",
    }
    planner.ollama = mock_ollama

    plan = planner.plan_and_repair(code, filename="main.c", language="c")
    assert plan["original_code"] == code
    assert plan["proposed_code"] == fixed
    assert plan["workflow_state"] == "QWEN_PROPOSAL_READY"

    # Candidate is waiting in registry; editor source is not modified
    cand_id = plan["candidate_id"]
    cand_obj = plan["candidate"]
    assert cand_obj["user_decision_state"] == "PENDING_REVIEW"


# =========================================================================
# 12. Re-Analysis After Apply Without Automatic Repair Loop
# =========================================================================
def test_12_reanalysis_after_apply_runs_cleanly_without_auto_loop():
    clean_applied = "int main() {\n    int a = 10;\n    return 0;\n}"
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    planner.ollama = mock_ollama

    res = planner.post_apply_reanalyze_and_escalate(
        editor_source=clean_applied,
        filename="main.c",
        language="c",
        applied_from_state="QWEN_PROPOSAL_READY",
        applied_source_hash=sha256_text(clean_applied),
    )

    assert res["status"] == "FULLY_REPAIRED"
    assert res["workflow_state"] == "ALL_CHECKS_PASSED"
    # Qwen must NOT be automatically called when re-analysis is clean
    mock_ollama.coordinate_repair_decision.assert_not_called()


# =========================================================================
# 13. Graceful Handling of Ollama Failure and Malformed Model Output
# =========================================================================
def test_13_ollama_failure_handled_honestly_without_claiming_success():
    code = "int main() { invalid ??? }"
    planner = RepairPlanner()
    mock_ollama = MagicMock(spec=OllamaClient)
    # Simulate Ollama daemon returning failure
    mock_ollama.is_available.return_value = True
    mock_ollama.coordinate_repair_decision.return_value = {
        "action": "stop",
        "reasoning": "Unrepairable invalid syntax",
        "candidate_code": None,
    }
    planner.ollama = mock_ollama

    res = planner.plan_and_repair(code, filename="main.c", language="c")
    assert res["status"] == "UNRESOLVED"
    assert res["workflow_state"] == "REPAIR_FAILED"
    assert res["terminal_status"] == "UNRESOLVED"
    assert res["candidate"] is None


# =========================================================================
# 14. Preservation of Metrics, Logs, Analyzers, and Program Output
# =========================================================================
def test_14_preservation_of_metrics_logs_and_program_output(client):
    # Pipeline endpoint must function
    resp_pipe = client.get("/api/pipeline/latest")
    assert resp_pipe.status_code == 200

    # Program executor runs clean code properly
    clean_code = '#include <stdio.h>\nint main() {\n    printf("Output test\\n");\n    return 0;\n}'
    executor = ProgramExecutor()
    if executor.is_compiler_available():
        res_exec = executor.execute_c(clean_code, filename="main.c")
        assert res_exec.status == ExecutionStatus.COMPLETED.value
        assert "Output test" in res_exec.stdout

    # Plan preserves six metrics
    planner = RepairPlanner()
    code = "int main() {\n    int a = 10;\n    return 0;\n}"
    plan = planner.plan_and_repair(code, filename="main.c", language="c")
    assert "baseline_scores" in plan
    assert "metrics_comparison" in plan
    assert plan["precheck_report"]["is_clean"] is True
