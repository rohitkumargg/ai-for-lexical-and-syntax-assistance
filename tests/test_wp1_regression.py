# tests/test_wp1_regression.py
import pytest
from unittest.mock import patch, MagicMock
from compiler.repair_planner import RepairPlanner

@pytest.fixture
def planner():
    return RepairPlanner()

def test_c_no_repair_needed_clean(planner):
    code = """#include <stdio.h>
int main(void) {
    printf("Clean program\\n");
    return 0;
}
"""
    res = planner.plan_and_repair(code, filename="clean.c", language="c")
    assert res["status"] == "CLEAN"
    assert len(res["findings"]) == 0
    assert res.get("candidate") is None

def test_python_no_repair_needed_clean(planner):
    code = """def main():
    print("Clean Python")

if __name__ == "__main__":
    main()
"""
    res = planner.plan_and_repair(code, filename="clean.py", language="python")
    assert res["status"] in ("CLEAN", "ANALYSIS_ONLY", "REPAIR_PLAN_READY")
    assert len([f for f in res["findings"] if getattr(f, "severity", "") in ("CRITICAL", "HIGH")]) == 0

def test_c_resolved_attempt_0_deterministic(planner):
    # Missing semicolon: deterministic repair resolves at attempt 0
    code = """int main() {
    int x = 10
    return 0;
}
"""
    res = planner.plan_and_repair(code, filename="missing_semi.c", language="c")
    assert res["status"] == "REPAIR_PLAN_READY"
    cand = res.get("candidate")
    assert cand is not None
    assert "int x = 10;" in cand["proposed_code"]
    assert cand.get("repair_provider") in ("deterministic", "deterministic_rules")

def test_python_resolved_attempt_0(planner):
    # Python syntax missing colon: deterministic rule resolves at attempt 0
    code = """def test_func()
    return 42
"""
    res = planner.plan_and_repair(code, filename="syntax_err.py", language="python")
    assert res["status"] == "REPAIR_PLAN_READY"
    cand = res.get("candidate")
    assert cand is not None
    assert "def test_func():" in cand["proposed_code"]

def test_c_needing_retry_feedback(planner):
    # Mock Ollama coordinate_repair_decision to simulate retry 0 failing validation then retry 1 passing
    attempt = 0
    def mock_coordinate(*args, **kwargs):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            return {
                "action": "request_candidate",
                "candidate_code": "int main() { int bad = ; return 0; }", # Invalid syntax
                "reasoning": "Attempt 1 with syntax error",
                "strategy": "qwen_repair",
                "assumptions": [],
                "expected_effects": []
            }
        else:
            return {
                "action": "request_candidate",
                "candidate_code": "int main() { int fixed = 1; return 0; }",
                "reasoning": "Attempt 2 fixed",
                "strategy": "qwen_repair",
                "assumptions": [],
                "expected_effects": []
            }

    with patch.object(planner.ollama, "coordinate_repair_decision", side_effect=mock_coordinate):
        code = "int main() { int val = ; return 0; }"
        res = planner.plan_and_repair(code, filename="test_retry.c", language="c")
        assert res["status"] == "REPAIR_PLAN_READY"
        assert attempt >= 2 # Proves retry mechanism was triggered and succeeded

def test_python_needing_retry_feedback(planner):
    attempt = 0
    def mock_coordinate(*args, **kwargs):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            return {
                "action": "request_candidate",
                "candidate_code": "def foo(\n   bad_syntax",
                "reasoning": "Attempt 1",
                "strategy": "qwen_repair",
                "assumptions": [],
                "expected_effects": []
            }
        else:
            return {
                "action": "request_candidate",
                "candidate_code": "def foo():\n    return 1\n",
                "reasoning": "Attempt 2",
                "strategy": "qwen_repair",
                "assumptions": [],
                "expected_effects": []
            }

    with patch.object(planner.ollama, "coordinate_repair_decision", side_effect=mock_coordinate):
        code = "def foo(\n"
        res = planner.plan_and_repair(code, filename="test_retry.py", language="python")
        assert res["status"] in ("REPAIR_PLAN_READY", "UNRESOLVED", "PARTIALLY_REPAIRED")
        assert attempt >= 2

def test_never_lose_analysis_results_on_repair_exception(planner):
    # Simulate an unexpected exception during repair candidate generation
    from compiler.repair_planner import reset_internal_repair_exceptions_count, get_internal_repair_exceptions_count
    reset_internal_repair_exceptions_count()
    code = """int main() {
    int x = ;
    return 0;
}
"""
    with patch.object(planner, "_apply_deterministic_rules", side_effect=RuntimeError("Simulated repair crash")):
        res = planner.plan_and_repair(code, filename="crash_repair.c", language="c")
        # Must return ANALYSIS_ONLY instead of crashing or returning 500
        assert res["status"] == "ANALYSIS_ONLY"
        assert len(res["findings"]) > 0
        assert "Simulated repair crash" in res.get("repair_unavailable_reason", "")
        # Must carry structured repair_error metadata
        assert "repair_error" in res
        rep_err = res["repair_error"]
        assert rep_err["stage"] == "repair_synthesis"
        assert rep_err["exception_type"] == "RuntimeError"
        assert "Simulated repair crash" in rep_err["error_message"]
        assert get_internal_repair_exceptions_count() >= 1


def test_header_invariant_validated_equals_applied(planner):
    """
    Ensure ensure_c_libc_headers runs before the candidate is hashed, diffed,
    shown to the user, stored, and applied, so the validated text is byte-identical
    to the applied text.
    """
    import hashlib
    # Program with gets() missing <stdio.h>
    code = """int main(void) {
    char buf[32];
    gets(buf);
    return 0;
}
"""
    res = planner.plan_and_repair(code, filename="unsafe.c", language="c")
    assert res["status"] == "REPAIR_PLAN_READY"
    cand = res.get("candidate")
    assert cand is not None
    proposed = cand["proposed_code"]

    # Invariant 1: proposed_code contains the required header
    assert "#include <stdio.h>" in proposed
    assert "fgets(" in proposed

    # Invariant 2: Candidate source hash matches the proposed_code exactly
    expected_hash = hashlib.sha256(proposed.encode("utf-8")).hexdigest()
    assert cand["candidate_source_hash"] == expected_hash
    assert res["candidate_source_hash"] == expected_hash

    # Invariant 3: The unified diff reflects the added header line
    assert "+#include <stdio.h>" in cand["diff"]

    # Invariant 4: Candidate validation passed cleanly under -Werror=implicit-function-declaration
    assert cand["is_valid"] is True
    assert cand["validation"]["compilation_passed"] is True
    assert cand["validation"]["verdict"] == "VALIDATED"

    # Invariant 5: Code inside string literals or comments does not trigger false includes
    no_libc_code = """int main(void) {
    // #include <stdio.h>
    char *msg = "calling fgets or snprintf in string";
    return 0;
}
"""
    res_clean = planner.plan_and_repair(no_libc_code, filename="clean_str.c", language="c")
    cand_clean = res_clean.get("candidate")
    if cand_clean:
        # Should not inject stdio or string headers if no actual libc function was called
        assert "#include <string.h>" not in cand_clean["proposed_code"]


def test_sec01_token_based_detection():
    """
    Test SEC-01 token-based detection:
    1. Overflowing constant into int -> flags
    2. Overflowing constant into long long -> flags
    3. With LL suffix -> clean
    4. With explicit cast -> clean
    5. With identifiers containing 'll' -> no false flag or suppression
    6. Ordinary constants -> clean
    """
    from compiler.security_rules import parse_source, SecurityRulesCollector

    def get_findings_for_stmt(stmt: str):
        full_code = f"int main(void) {{\n    {stmt}\n    return 0;\n}}\n"
        tree, _, _ = parse_source(full_code)
        collector = SecurityRulesCollector(full_code)
        collector.visit(tree)
        return [f for f in collector.findings if f.rule == "SEC-01"]

    # 1. Overflowing constant into int -> flags
    f1 = get_findings_for_stmt("int x = 2147483647 + 1;")
    assert len(f1) == 1
    assert "integer_overflow" in f1[0].kind

    # 2. Overflowing constant into long long (without 64-bit suffix/cast) -> flags
    f2 = get_findings_for_stmt("long long x = 2147483647 + 1;")
    assert len(f2) == 1
    assert "integer_overflow" in f2[0].kind

    # 3. With LL suffix -> clean (64-bit promoted)
    f3 = get_findings_for_stmt("long long x = 2147483647LL + 1;")
    assert len(f3) == 0

    # 4. With explicit cast to (long long) -> clean
    f4 = get_findings_for_stmt("long long x = (long long)2147483647 + 1;")
    assert len(f4) == 0

    # 5. Identifiers containing 'll' -> no false trigger
    f5 = get_findings_for_stmt("int call = 5; int x = call + 1;")
    assert len(f5) == 0

    f6 = get_findings_for_stmt("int small = 2; long long x = small + 10;")
    assert len(f6) == 0

    # 6. Ordinary constant -> clean
    f7 = get_findings_for_stmt("int x = 100 + 200;")
    assert len(f7) == 0


def test_ruff_and_pyflakes_clean():
    """Verify that ruff and pyflakes find no undefined variables or uninitialized locals."""
    import subprocess
    # Run ruff check on scoping error codes
    ruff_res = subprocess.run(
        ["ruff", "check", "--select", "F821,F822,F823", "compiler/"],
        capture_output=True,
        text=True,
    )
    assert ruff_res.returncode == 0, f"Ruff scoping check failed:\n{ruff_res.stdout}"

    # Run pyflakes check
    pyflakes_res = subprocess.run(
        ["pyflakes", "compiler/"],
        capture_output=True,
        text=True,
    )
    output = pyflakes_res.stdout + pyflakes_res.stderr
    assert "undefined name" not in output, f"Pyflakes found undefined name:\n{output}"
    assert "before assignment" not in output, f"Pyflakes found uninitialized local:\n{output}"

