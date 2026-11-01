"""
tests/test_sandbox_interim_guard.py

Tests for the Sandbox Interim Guard:
Until a container sandbox backend (Docker Desktop with WSL2) is verified:
1. /api/program/run must refuse any program with HIGH or CRITICAL findings.
2. /api/program/run must refuse any program with dangerous calls (process, shell, deletion, sockets, dynamic eval).
3. /api/program/run must refuse any program whose classification failed or is missing (unknown = refuse).
4. The refusal reason is presented in the UI/response stderr.
5. Clean programs with zero risk factors are permitted to run.
6. Refused executions strictly spawn 0 host subprocesses.
"""

import pytest
from unittest.mock import patch, MagicMock
from app import app
from compiler.program_executor import ProgramExecutor, ProgramExecutionResult
from compiler.sandbox.interim_guard import (
    evaluate_interim_guard,
    is_sandbox_verified,
    scan_dangerous_calls,
)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def executor():
    return ProgramExecutor()


def test_interim_guard_refuses_c_gets(executor):
    """Programs using gets() have CRITICAL buffer overflow risks and must be refused."""
    code = """
    #include <stdio.h>
    int main() {
        char buf[16];
        gets(buf);
        return 0;
    }
    """
    verdict = evaluate_interim_guard(code, filename="main.c", language="c")
    assert verdict.is_refused is True
    assert "gets" in verdict.reason.lower() or "critical" in verdict.reason.lower()

    res = executor.execute_program(source_code=code, language="c", filename="main.c", gate_already_verified=True)
    assert res.status == "Refused (Sandbox Unverified)"
    assert res.exit_code is None
    assert "[SANDBOX REFUSAL]" in res.stderr


def test_interim_guard_refuses_c_system_call(executor):
    """Programs calling system() or shell execution must be refused."""
    code = """
    #include <stdlib.h>
    int main() {
        system("dir");
        return 0;
    }
    """
    verdict = evaluate_interim_guard(code, filename="main.c", language="c")
    assert verdict.is_refused is True
    assert any("process" in r.lower() or "shell" in r.lower() for r in verdict.risk_factors)

    res = executor.execute_c(source_code=code, filename="main.c", gate_already_verified=True)
    assert res.status == "Refused (Sandbox Unverified)"
    assert res.exit_code is None


def test_interim_guard_refuses_c_network_sockets(executor):
    """Programs creating network sockets must be refused."""
    code = """
    #include <sys/socket.h>
    int main() {
        int s = socket(AF_INET, SOCK_STREAM, 0);
        return 0;
    }
    """
    verdict = evaluate_interim_guard(code, filename="main.c", language="c")
    assert verdict.is_refused is True
    assert any("socket" in r.lower() or "network" in r.lower() for r in verdict.risk_factors)


def test_interim_guard_refuses_c_file_deletion(executor):
    """Programs attempting file deletion / unlink must be refused."""
    code = """
    #include <stdio.h>
    int main() {
        remove("C:\\\\test.txt");
        return 0;
    }
    """
    verdict = evaluate_interim_guard(code, filename="main.c", language="c")
    assert verdict.is_refused is True
    assert any("deletion" in r.lower() or "remove" in r.lower() for r in verdict.risk_factors)


def test_interim_guard_refuses_python_subprocess(executor):
    """Python programs invoking subprocess must be refused on the host."""
    py_code = """
import subprocess
subprocess.call(["dir"], shell=True)
"""
    verdict = evaluate_interim_guard(py_code, filename="script.py", language="python")
    assert verdict.is_refused is True
    assert any("subprocess" in r.lower() or "shell" in r.lower() for r in verdict.risk_factors)

    res = executor.execute_python(source_code=py_code, filename="script.py", gate_already_verified=True)
    assert res.status == "Refused (Sandbox Unverified)"
    assert res.exit_code is None


def test_interim_guard_refuses_python_eval(executor):
    """Python programs performing dynamic code evaluation must be refused."""
    py_code = """
user_input = "__import__('os').system('dir')"
eval(user_input)
"""
    verdict = evaluate_interim_guard(py_code, filename="script.py", language="python")
    assert verdict.is_refused is True
    assert any("dynamic" in r.lower() or "eval" in r.lower() for r in verdict.risk_factors)


def test_interim_guard_refuses_failed_classification(executor):
    """Programs whose security classification fails or is missing must fail closed."""
    code = "int main() { return 0; }"
    with patch("compiler.security_approval_gate.SecurityDecisionGate.evaluate", side_effect=RuntimeError("Classifier crashed")):
        verdict = evaluate_interim_guard(code, filename="main.c", language="c")
        assert verdict.is_refused is True
        assert "classification failed" in verdict.reason.lower()


def test_interim_guard_permits_clean_c(executor):
    """Clean C code with zero dangerous calls and no high/critical findings runs normally."""
    clean_code = """
    #include <stdio.h>
    int main() {
        printf("INTERIM_GUARD_CLEAN_C_OK\\n");
        return 0;
    }
    """
    verdict = evaluate_interim_guard(clean_code, filename="main.c", language="c")
    assert verdict.is_refused is False

    res = executor.execute_c(source_code=clean_code, filename="main.c", gate_already_verified=True)
    assert res.status == "Completed"
    assert res.exit_code == 0
    assert "INTERIM_GUARD_CLEAN_C_OK" in res.stdout


def test_interim_guard_permits_clean_python(executor):
    """Clean Python code with no dangerous calls runs normally."""
    clean_py = "print('INTERIM_GUARD_CLEAN_PY_OK')"
    verdict = evaluate_interim_guard(clean_py, filename="script.py", language="python")
    assert verdict.is_refused is False

    res = executor.execute_python(source_code=clean_py, filename="script.py", gate_already_verified=True)
    assert res.status == "Completed"
    assert res.exit_code == 0
    assert "INTERIM_GUARD_CLEAN_PY_OK" in res.stdout


def test_api_run_endpoint_refuses_risky_program_even_with_token(client):
    """
    Calling /api/program/run on risky code with an approval token returns HTTP 423
    and refuses host execution while the container sandbox is unverified.
    """
    risky_code = """
    #include <stdio.h>
    int main() {
        char buf[8];
        gets(buf);
        return 0;
    }
    """
    # 1. Generate an approval token
    approve_resp = client.post("/api/security/approval/approve", json={
        "code": risky_code,
        "filename": "main.c",
        "operation": "execute",
        "force": True,
    })
    assert approve_resp.status_code == 200
    token = approve_resp.get_json()["approval_token"]

    # 2. Call /api/program/run with token -> Interim guard returns HTTP 423
    with patch("subprocess.Popen") as mock_popen, patch("subprocess.run") as mock_run:
        run_resp = client.post("/api/program/run", json={
            "code": risky_code,
            "filename": "main.c",
            "language": "c",
            "approval_token": token,
        })
        assert run_resp.status_code == 423
        data = run_resp.get_json()
        assert data["refused"] is True
        assert data["status"] == "Refused (Sandbox Unverified)"
        assert "[SANDBOX REFUSAL]" in data["stderr"]
        # Invariance: 0 host subprocesses executed for refused code
        assert mock_popen.call_count == 0
        assert mock_run.call_count == 0


def test_api_run_endpoint_runs_clean_program(client):
    """Calling /api/program/run on clean code returns HTTP 200 and executes cleanly."""
    clean_code = """
    #include <stdio.h>
    int main() {
        printf("API_CLEAN_RUN_PASSED\\n");
        return 0;
    }
    """
    run_resp = client.post("/api/program/run", json={
        "code": clean_code,
        "filename": "main.c",
        "language": "c",
    })
    assert run_resp.status_code == 200
    data = run_resp.get_json()
    assert data["status"] == "Completed"
    assert data["exit_code"] == 0
    assert "API_CLEAN_RUN_PASSED" in data["stdout"]

