"""Tests for dedicated Program Output Panel and Execution Engine.

Covers the 11 testing requirements:
1. A valid C program that prints output.
2. A program that reads stdin.
3. A compilation failure.
4. A runtime error or nonzero exit status.
5. An infinite loop that must be stopped by the timeout.
6. Excessive output being limited safely.
7. Repeated runs using the latest editor source.
8. Run Program not invoking CodeT5 or Qwen.
9. Run Program not modifying the editor or repair metrics.
10. Execution failures being displayed honestly.
11. Security isolation and resource limits.
"""
import pytest
from unittest.mock import patch, MagicMock
from app import app
from compiler.program_executor import ProgramExecutor, ExecutionStatus


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def executor():
    return ProgramExecutor()


# 1. Valid C program that prints output
def test_valid_c_program_execution(executor):
    code = """#include <stdio.h>
int main() {
    printf("Hello Antigravity Compiler!\\n");
    return 0;
}
"""
    res = executor.execute_c(code)
    assert res.status == ExecutionStatus.COMPLETED.value
    assert "Hello Antigravity Compiler!" in res.stdout
    assert res.exit_code == 0
    assert res.execution_time_ms >= 0


# 2. Program that reads stdin
def test_program_with_stdin(executor):
    code = """#include <stdio.h>
int main() {
    int val = 0;
    if (scanf("%d", &val) == 1) {
        printf("Doubled: %d\\n", val * 2);
    }
    return 0;
}
"""
    res = executor.execute_c(code, stdin_input="21\n")
    assert res.status == ExecutionStatus.COMPLETED.value
    assert "Doubled: 42" in res.stdout
    assert res.stdin_used is True
    assert res.exit_code == 0


# 3. Compilation failure
def test_compilation_failure_detected(executor):
    code = """#include <stdio.h>
int main() {
    this_is_invalid_syntax_error here;;;
    return 0;
}
"""
    res = executor.execute_c(code)
    assert res.status == ExecutionStatus.COMPILATION_FAILED.value
    assert res.exit_code != 0
    assert res.compilation_error is not None
    assert len(res.stderr) > 0


# 4. Runtime error or nonzero exit status
def test_runtime_error_nonzero_exit_status(executor):
    code = """#include <stdio.h>
int main() {
    fprintf(stderr, "Fatal runtime diagnostic\\n");
    return 7;
}
"""
    res = executor.execute_c(code)
    assert res.status == ExecutionStatus.RUNTIME_ERROR.value
    assert res.exit_code == 7
    assert "Fatal runtime diagnostic" in res.stderr


# 5. Infinite loop that must be stopped by the timeout
def test_infinite_loop_timeout_enforced(executor):
    code = """#include <stdio.h>
int main() {
    while (1) {
        // loop indefinitely
    }
    return 0;
}
"""
    # Use a short timeout of 1.0s for testing
    res = executor.execute_c(code, timeout_sec=1.0)
    assert res.status == ExecutionStatus.TIMED_OUT.value
    assert "timed out" in res.stderr.lower()
    assert res.exit_code is None


# 6. Excessive output being limited safely
def test_excessive_output_truncated(executor):
    # Outputting 100,000 characters
    code = """#include <stdio.h>
int main() {
    for (int i = 0; i < 8000; i++) {
        printf("1234567890ABCDEF\\n");
    }
    return 0;
}
"""
    res = executor.execute_c(code)
    assert res.status == ExecutionStatus.COMPLETED.value
    # Maximum output buffer is capped
    assert len(res.stdout) <= executor.MAX_OUTPUT_BYTES + 256
    assert "truncated" in res.stdout.lower()


# 7. Repeated runs using latest source via API
def test_repeated_runs_use_latest_source(client):
    code1 = """#include <stdio.h>
int main() { printf("Run 1 Output\\n"); return 0; }
"""
    resp1 = client.post("/api/program/run", json={"code": code1, "language": "c"})
    data1 = resp1.get_json()
    assert data1["status"] == "Completed"
    assert "Run 1 Output" in data1["stdout"]

    code2 = """#include <stdio.h>
int main() { printf("Run 2 Output with Updates\\n"); return 0; }
"""
    resp2 = client.post("/api/program/run", json={"code": code2, "language": "c"})
    data2 = resp2.get_json()
    assert data2["status"] == "Completed"
    assert "Run 2 Output with Updates" in data2["stdout"]
    assert "Run 1 Output" not in data2["stdout"]


# 8. Run Program does NOT invoke CodeT5 or Qwen or repair pipeline
@patch("compiler.gui_bridge.repair_source_for_gui")
def test_run_program_does_not_invoke_models(mock_repair_fn, client):
    code = """#include <stdio.h>
int main() { printf("Pure Execution\\n"); return 0; }
"""
    resp = client.post("/api/program/run", json={"code": code, "language": "c"})
    assert resp.status_code == 200
    # Repair pipeline must not be touched at all
    mock_repair_fn.assert_not_called()


# 9. Run Program does NOT modify editor or repair metrics
def test_run_program_does_not_mutate_repair_metrics_or_proposals(client):
    code = """#include <stdio.h>
int main() { printf("Testing isolation\\n"); return 0; }
"""
    resp = client.post("/api/program/run", json={"code": code, "language": "c"})
    data = resp.get_json()
    # Response contains only execution fields, no repair planner metrics
    assert "before_metrics" not in data
    assert "after_metrics" not in data
    assert "candidate_id" not in data
    assert "repair_plan" not in data


# 10. Execution failures displayed honestly
def test_execution_failure_displayed_honestly(client):
    code = """#include <stdio.h>
int main() {
    fprintf(stderr, "Unrecoverable runtime abort\\n");
    return 139; // Nonzero error status
}
"""
    resp = client.post("/api/program/run", json={"code": code, "language": "c"})
    data = resp.get_json()
    assert data["status"] == "Runtime Error"
    assert data["success"] is False
    assert data["exit_code"] == 139
    assert "Unrecoverable runtime abort" in data["stderr"]


# 11. Security isolation and resource limits (dangerous calls blocked)
def test_security_isolation_blocks_system_calls(executor):
    malicious_code = """#include <stdio.h>
#include <stdlib.h>
int main() {
    system("calc.exe");
    return 0;
}
"""
    res = executor.execute_c(malicious_code)
    assert res.status == ExecutionStatus.SECURITY_BLOCKED.value
    assert res.exit_code is None
    assert "system()" in res.stderr or "security" in res.stderr.lower()
