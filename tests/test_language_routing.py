import pytest
from compiler.orchestrator import AgentOrchestrator
from compiler.repair_planner import RepairPlanner
from compiler.patch_validator import PatchValidator, ValidationVerdict
from compiler.languages import detect_language


def test_language_detection():
    """Verify detect_language prioritizes requested language and validates filenames."""
    assert detect_language(requested="python") == "python"
    assert detect_language(requested="c") == "c"
    assert detect_language(filename="script.py") == "python"
    assert detect_language(filename="main.c") == "c"
    # When requested is python but filename is main.c, requested takes precedence if valid
    assert detect_language(filename="main.c", requested="python") == "python"
    assert detect_language(filename="script.py", requested="c") == "c"


def test_valid_python_submission():
    """1. Valid Python code: should pass cleanly through Python pipeline with 0 errors."""
    code = (
        "def compute_sum(a, b):\n"
        "    return a + b\n\n"
        "total = compute_sum(10, 20)\n"
    )
    planner = RepairPlanner()
    res = planner.plan_and_repair(code, filename="main.py", language="python")

    assert res["status"] == "CLEAN"
    assert len(res["findings"]) == 0
    # Verify no C pipeline artifacts
    assert not any("#include" in str(f) for f in res["findings"])


def test_python_with_syntax_error():
    """2. Python with a syntax error: should be identified by Python parser and repaired as Python."""
    code = (
        "def greet(name)\n"  # missing colon
        "    return 'Hello ' + name\n"
    )
    planner = RepairPlanner()
    res = planner.plan_and_repair(code, filename="main.py", language="python")

    # Should find syntax issue
    assert len(res["findings"]) > 0
    # Finding must be from Python syntax analysis, not ANTLR C parser error
    assert any(f["category"] == "SYNTAX" for f in res["findings"])

    # If a candidate was generated, it MUST be valid Python, never C
    if res.get("candidate"):
        cand = res["candidate"]
        cand_code = cand["proposed_code"] if isinstance(cand, dict) else str(cand)
        assert "def greet" in cand_code
        assert "#include" not in cand_code
        assert "int main" not in cand_code
        import ast
        # Candidate must compile as valid Python
        ast.parse(cand_code)


def test_python_with_semantic_or_security_issue():
    """3. Python with semantic/security issue (e.g. eval or insecure deserialization)."""
    code = (
        "def run_untrusted(user_payload):\n"
        "    return eval(user_payload)\n"
    )
    planner = RepairPlanner()
    findings, scores = planner.analyze_program(code, filename="main.py", language="python")

    assert len(findings) > 0
    # Must report security finding for eval
    sec_findings = [f for f in findings if f.category == "SECURITY"]
    assert len(sec_findings) > 0
    assert any("eval" in f.explanation.lower() or "PY-SEC" in f.id or "eval" in f.title.lower() for f in sec_findings)


def test_valid_c_code():
    """4. Valid C code: passes C ANTLR parser and GCC cleanly."""
    code = (
        "int add(int a, int b) {\n"
        "    return a + b;\n"
        "}\n\n"
        "int main() {\n"
        "    return add(5, 10);\n"
        "}\n"
    )
    planner = RepairPlanner()
    res = planner.plan_and_repair(code, filename="main.c", language="c")

    assert res["status"] == "CLEAN"
    assert len(res["findings"]) == 0


def test_c_with_syntax_error():
    """5. C code with syntax error (missing semicolon): identified and repaired as C."""
    code = (
        "int main() {\n"
        "    int x = 42\n"  # missing semicolon
        "    return x;\n"
        "}\n"
    )
    planner = RepairPlanner()
    res = planner.plan_and_repair(code, filename="main.c", language="c")

    assert len(res["findings"]) > 0
    assert any(f["category"] == "SYNTAX" for f in res["findings"])

    if res.get("candidate"):
        cand = res["candidate"]
        cand_code = cand["proposed_code"] if isinstance(cand, dict) else str(cand)
        # Candidate MUST be C code
        assert "int main" in cand_code
        assert "def " not in cand_code


def test_alternating_python_and_c_submissions():
    """6. Python code submitted after C code, and C code submitted after Python code."""
    planner = RepairPlanner()

    c_code = (
        "int main() {\n"
        "    int y = 100;\n"
        "    return y;\n"
        "}\n"
    )
    py_code = (
        "def calculate():\n"
        "    return 42\n"
    )

    # Submission 1: C code
    c_res = planner.plan_and_repair(c_code, filename="main.c", language="c")
    assert c_res["status"] == "CLEAN"

    # Submission 2: Python code immediately after C
    py_res = planner.plan_and_repair(py_code, filename="main.py", language="python")
    assert py_res["status"] == "CLEAN"
    assert not any("int main" in str(f) for f in py_res["findings"])

    # Submission 3: C code immediately after Python
    c_res2 = planner.plan_and_repair(c_code, filename="main.c", language="c")
    assert c_res2["status"] == "CLEAN"

    # Submission 4: Python with syntax error after C
    py_err_code = "if True\n    x = 1\n"
    py_err_res = planner.plan_and_repair(py_err_code, filename="main.py", language="python")
    assert len(py_err_res["findings"]) > 0
    # Must NOT have C compiler error messages like SimpleC lexer/parser error
    for f in py_err_res["findings"]:
        assert "no viable alternative at input" not in f["explanation"].lower() or "line" in f["explanation"].lower()


def test_cross_language_rejection_in_validator():
    """7. Candidate validator rejects proposals written in the wrong language."""
    validator = PatchValidator()

    # Case A: C candidate proposed for Python source
    py_source = "def compute():\n    return 10\n"
    c_candidate = "#include <stdio.h>\nint main() { return 10; }\n"

    report_a = validator.validate_patch(
        original_code=py_source,
        candidate_code=c_candidate,
        filename="main.py",
        language="python",
    )
    assert not report_a.is_valid
    assert report_a.verdict == ValidationVerdict.INVALID_CROSS_LANGUAGE
    assert "c code proposed for python" in report_a.explanation.lower()

    # Case B: Python candidate proposed for C source
    c_source = "int main() { return 10; }\n"
    py_candidate = "def main():\n    return 10\n"

    report_b = validator.validate_patch(
        original_code=c_source,
        candidate_code=py_candidate,
        filename="main.c",
        language="c",
    )
    assert not report_b.is_valid
    assert report_b.verdict == ValidationVerdict.INVALID_CROSS_LANGUAGE
    assert "python code proposed for c" in report_b.explanation.lower()
