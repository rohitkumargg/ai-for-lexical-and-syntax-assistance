"""
Regression tests for Antigravity Security Repair Generation and Validation Pipeline.
Verifies:
1. An undefined popen2() candidate is rejected by SandboxedCompiler and PatchValidator.
2. A candidate that compiles but retains shell-execution risk (swapping system for popen) is not marked repaired.
3. A valid candidate using direct process execution or allowlist passes validation.
4. Failed retries in RepairWorkflowEngine do not overwrite a previously validated candidate.
5. Unvalidated candidates cannot be applied through /api/security/apply.
6. WorkflowStatus accurately distinguishes Completed, Partially Repaired, Failed, and Timed Out.
"""

import pytest
from unittest.mock import patch, MagicMock

from compiler.patch_validator import PatchValidator, SandboxedCompiler, ValidationVerdict
from compiler.repair_workflow import RepairWorkflowEngine, WorkflowConfig, WorkflowStatus
from compiler.finding import Finding, FindingCategory, FindingSeverity, SourceLocation
from compiler.orchestrator import DecisionState
from app import app


def test_security_only_overflow_repair_does_not_apply_syntax_guessing():
    """A security finding must not trigger unrelated syntax-token heuristics."""
    from compiler.repair_planner import RepairPlanner

    source = """int main() {
    int x = 2147483647 + 1;
    return x > 0;
}
"""
    planner = RepairPlanner()
    findings, _ = planner.analyze_program(
        source, filename="overflow.c", language="c"
    )
    assert any(
        getattr(getattr(f, "category", ""), "value", getattr(f, "category", "")).upper() == "SECURITY"
        for f in findings
    )

    candidate, applied = planner._apply_deterministic_rules(
        source, filename="overflow.c", language="c", findings=findings
    )

    assert "long long x = (long long)2147483647 + 1;" in candidate
    assert "return x > 0;" in candidate
    assert ", x" not in candidate
    assert "SEC-01" in " ".join(applied)


def test_undefined_popen2_candidate_rejected():
    """An undefined popen2() candidate must fail compilation/semantic validation and be rejected."""
    original_code = """#include <stdio.h>
#include <stdlib.h>

int main() {
    char cmd[128];
    if (fgets(cmd, sizeof(cmd), stdin) != NULL) {
        system(cmd);
    }
    return 0;
}
"""
    # Candidate invents popen2 which is not standard or declared
    popen2_candidate = """#include <stdio.h>
#include <stdlib.h>

int main() {
    char cmd[128];
    if (fgets(cmd, sizeof(cmd), stdin) != NULL) {
        popen2(cmd, "r");
    }
    return 0;
}
"""
    validator = PatchValidator()
    report = validator.validate_patch(
        original_code=original_code,
        candidate_code=popen2_candidate,
        filename="main.c",
        language="c",
    )

    assert report.is_valid is False
    assert report.verdict in (
        ValidationVerdict.FAILED_COMPILATION,
        ValidationVerdict.FAILED_SEMANTIC,
        ValidationVerdict.FAILED_SECURITY,
    )
    # Compiler or semantic validator must have flagged popen2
    remaining_text = " ".join(report.remaining_risks).lower() + " " + (report.compiler_output or "").lower()
    assert "popen2" in remaining_text or "undeclared" in remaining_text or "implicit" in remaining_text


def test_popen_retaining_shell_risk_fails_security_validation():
    """
    Replacing system() with popen() alone does NOT eliminate shell execution risks (CWE-78).
    Candidate must be rejected with FAILED_SECURITY and is_valid == False.
    """
    original_code = """#include <stdio.h>
#include <stdlib.h>

int main() {
    char cmd[128];
    if (fgets(cmd, sizeof(cmd), stdin) != NULL) {
        system(cmd);
    }
    return 0;
}
"""
    # Merely swapping system() for popen() retains shell injection risk
    popen_candidate = """#include <stdio.h>
#include <stdlib.h>

int main() {
    char cmd[128];
    if (fgets(cmd, sizeof(cmd), stdin) != NULL) {
        popen(cmd, "r");
    }
    return 0;
}
"""
    validator = PatchValidator()
    report = validator.validate_patch(
        original_code=original_code,
        candidate_code=popen_candidate,
        filename="main.c",
        language="c",
    )

    assert report.is_valid is False
    assert report.verdict == ValidationVerdict.FAILED_SECURITY
    assert any("shell-related security risks" in r or "SEC-" in r for r in report.remaining_risks)


def test_valid_direct_process_execution_passes_validation():
    """A valid candidate using direct process execution with argument arrays passes validation."""
    original_code = """#include <stdio.h>
#include <stdlib.h>

int main() {
    char cmd[128];
    if (fgets(cmd, sizeof(cmd), stdin) != NULL) {
        system(cmd);
    }
    return 0;
}
"""
    # Valid direct execution using standard execv without shell invocation
    direct_exec_candidate = """#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <process.h>

int main() {
    char cmd[128];
    if (fgets(cmd, sizeof(cmd), stdin) != NULL) {
        if (strcmp(cmd, "ls") == 0) {
            execv("ls", 0);
        }
    }
    return 0;
}
"""
    validator = PatchValidator()
    report = validator.validate_patch(
        original_code=original_code,
        candidate_code=direct_exec_candidate,
        filename="main.c",
        language="c",
    )

    assert report.syntax_passed is True
    assert report.semantic_passed is True
    assert report.security_passed is True
    assert report.is_valid is True
    assert report.verdict == ValidationVerdict.VALIDATED


def test_valid_allowlist_command_execution_passes_validation():
    """A candidate validating the command against an allowlist before execution passes validation."""
    original_code = """#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main() {
    char cmd[128];
    if (fgets(cmd, sizeof(cmd), stdin) != NULL) {
        system(cmd);
    }
    return 0;
}
"""
    allowlist_candidate = """#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main() {
    char cmd[128];
    if (fgets(cmd, sizeof(cmd), stdin) != NULL) {
        if (strcmp(cmd, "status") == 0) {
            system("status");
        } else if (strcmp(cmd, "ping") == 0) {
            system("ping");
        } else {
            printf("command not allowed\\n");
        }
    }
    return 0;
}
"""
    validator = PatchValidator()
    report = validator.validate_patch(
        original_code=original_code,
        candidate_code=allowlist_candidate,
        filename="main.c",
        language="c",
    )

    assert report.is_valid is True
    assert report.verdict == ValidationVerdict.VALIDATED


def test_failed_retries_do_not_overwrite_previously_validated_candidate():
    """In RepairWorkflowEngine, if an attempt was validated, failed retries must not overwrite it."""
    engine = RepairWorkflowEngine(config=WorkflowConfig(max_retries=2))

    finding = Finding.create(
        category=FindingCategory.SYNTAX,
        line=4,
        col=5,
        explanation="missing semicolon",
        evidence="int x = 5",
        severity=FindingSeverity.CRITICAL,
    )

    validated_code = """#include <stdio.h>
int main() {
    int x = 5;
    return 0;
}
"""
    failing_code = """#include <stdio.h>
int main() {
    popen2("bad", "r");
    return 0;
}
"""
    responses = [
        # Attempt 0: returns validated code
        f'```c\n{validated_code}\n```\nEXPLANATION: Added semicolon.',
        # Attempt 1: returns failing code
        f'```c\n{failing_code}\n```\nEXPLANATION: Bad candidate.',
    ]

    with patch.object(engine, "_call_qwen", side_effect=responses):
        res, patches = engine._run_qwen_bounded_retry_loop(
            source_text="int main() { int x = 5 return 0; }",
            finding=finding,
            filename="main.c",
            patches_accumulator=[],
            telemetry={"tier_counts": {"qwen2.5_coder": 0}},
            errors_before=1,
            language="c",
        )

        assert res.strip() == validated_code.strip()
        assert len(patches) >= 1
        assert patches[0].validation_passed is True


def test_workflow_status_distinctions():
    """WorkflowStatus distinguishes canonical states and maintains legacy equivalence."""
    status_completed = WorkflowStatus("Completed")
    status_part = WorkflowStatus("Partially Repaired")
    status_failed = WorkflowStatus("Failed")
    status_timed = WorkflowStatus("Timed Out")

    # Canonical equality
    assert status_completed == "Completed"
    assert status_part == "Partially Repaired"
    assert status_failed == "Failed"
    assert status_timed == "Timed Out"

    # Backwards compatibility equality
    assert status_completed == "REPAIRED"
    assert status_part == "PARTIALLY_REPAIRED"
    assert status_failed == "UNRESOLVED"
    assert status_timed == "TIMED_OUT"


def test_security_apply_endpoint_rejects_unvalidated_patch():
    """Calling /api/security/apply with a patch that fails validation returns HTTP 400."""
    client = app.test_client()

    original_code = "int main() { return 0; }"
    invalid_patch = "int main() { popen2('invalid'); return 0; }"

    resp = client.post(
        "/api/security/apply",
        json={
            "original_code": original_code,
            "proposed_code": invalid_patch,
            "filename": "main.c",
            "language": "c",
        },
    )

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "validation failed" in data["error"].lower()
    assert data["is_valid"] is False
