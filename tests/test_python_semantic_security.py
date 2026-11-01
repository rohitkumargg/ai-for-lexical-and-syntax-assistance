import os
import json
import pytest
from compiler.languages.python_lang import repair_python
from compiler.languages import python_semantic, python_security
from compiler.gui_bridge import repair_source_for_gui

SEM_DIR = os.path.join("examples", "python", "semantic")
SEC_DIR = os.path.join("examples", "python", "security")
EXPECTED_SEM_DIR = os.path.join("examples", "python", "_expected", "semantic")
EXPECTED_SEC_DIR = os.path.join("examples", "python", "_expected", "security")

SEMANTIC_AUTO_PAIRS = [
    "m01_undefined_name_typo.py",
    "m02_true_false_none.py",
    "m03_unused_import.py",
    "m04_unused_variable.py",
    "m05_compare_none.py",
    "m06_missing_self.py",
]

SECURITY_AUTO_PAIRS = [
    "x01_yaml_load.py",
    "x02_weak_hash.py",
    "x03_eval_input.py",
    "x04_shell_true.py",
    "x05_verify_false.py",
    "x06_flask_debug.py",
]

REPORT_ONLY_FILES = [
    ("semantic/m07_call_arity.py", "call_arity_mismatch", 3),
    ("semantic/m08_return_outside.py", "return_outside_function", 2),
    ("security/x07_hardcoded_password.py", "PY-SEC-07", 1),
    ("security/x08_sql_injection.py", "PY-SEC-08", 2),
]

def norm(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").strip().split("\n")]
    return "\n".join(lines)

@pytest.mark.parametrize("filename", SEMANTIC_AUTO_PAIRS)
def test_semantic_auto_fix_pairs(filename):
    broken_path = os.path.join(SEM_DIR, filename)
    expected_path = os.path.join(EXPECTED_SEM_DIR, filename)

    with open(broken_path, "r", encoding="utf-8") as f:
        broken_src = f.read()
    with open(expected_path, "r", encoding="utf-8") as f:
        expected_src = f.read()

    res = repair_python(broken_src, filename)
    assert res["status"] == "SUCCESS"
    assert norm(res["corrected_code"]) == norm(expected_src)

@pytest.mark.parametrize("filename", SECURITY_AUTO_PAIRS)
def test_security_auto_fix_pairs(filename):
    broken_path = os.path.join(SEC_DIR, filename)
    expected_path = os.path.join(EXPECTED_SEC_DIR, filename)

    with open(broken_path, "r", encoding="utf-8") as f:
        broken_src = f.read()
    with open(expected_path, "r", encoding="utf-8") as f:
        expected_src = f.read()

    res = repair_python(broken_src, filename)
    assert res["status"] == "SUCCESS_WITH_WARNINGS"
    assert norm(res["corrected_code"]) == norm(expected_src)

@pytest.mark.parametrize("rel_path, expected_kind, expected_line", REPORT_ONLY_FILES)
def test_report_only_files_byte_identical_and_reported(rel_path, expected_kind, expected_line):
    full_path = os.path.join("examples", "python", rel_path)
    with open(full_path, "rb") as f:
        orig_bytes = f.read()
    orig_src = orig_bytes.decode("utf-8")

    res = repair_python(orig_src, os.path.basename(rel_path))
    assert res["corrected_code"].encode("utf-8") == orig_bytes
    assert len(res["applied_steps"]) == 0

    if expected_kind.startswith("PY-SEC"):
        warnings = res["security_warnings"]
        match = [w for w in warnings if expected_kind in w and f"line {expected_line}:" in w]
        assert len(match) >= 1, f"Missing security warning {expected_kind} on line {expected_line}"
        if expected_kind == "PY-SEC-07":
            assert "os.environ" in match[0]
        elif expected_kind == "PY-SEC-08":
            assert "parameterized" in match[0]
    else:
        issues = res["semantic_issues"]
        match = [i for i in issues if i["kind"] == expected_kind and i["line"] == expected_line]
        assert len(match) >= 1, f"Missing semantic issue {expected_kind} on line {expected_line}"

def test_clean_guard_zero_issues_and_findings():
    path = os.path.join("examples", "python", "clean_guard.py")
    with open(path, "rb") as f:
        orig_bytes = f.read()
    orig_src = orig_bytes.decode("utf-8")

    res = repair_python(orig_src, "clean_guard.py")
    assert res["status"] == "SUCCESS"
    assert res["corrected_code"].encode("utf-8") == orig_bytes
    assert len(res["errors"]) == 0
    assert len(res["semantic_issues"]) == 0
    assert len(res["security_warnings"]) == 0
    assert len(res["applied_steps"]) == 0

@pytest.mark.parametrize("filename", SEMANTIC_AUTO_PAIRS + SECURITY_AUTO_PAIRS)
def test_idempotence(filename):
    if filename.startswith("m"):
        broken_path = os.path.join(SEM_DIR, filename)
    else:
        broken_path = os.path.join(SEC_DIR, filename)

    with open(broken_path, "r", encoding="utf-8") as f:
        src = f.read()

    res1 = repair_python(src, filename)
    fixed1 = res1["corrected_code"]

    res2 = repair_python(fixed1, filename)
    assert res2["corrected_code"] == fixed1
    assert len(res2["applied_steps"]) == 0

# Must-not-fire negative cases for EVERY rule:
def test_must_not_fire_cases():
    # 1. os is used via os.path.sep -> no unused_import
    src1 = "import os\nprint(os.path.sep)\n"
    sem1 = python_semantic.analyze(src1)
    assert not any(i["kind"] == "unused_import" for i in sem1)

    # 2. variable used inside nested function is NOT unused
    src2 = "def outer():\n    x = 10\n    def inner():\n        return x\n    return inner()\n"
    sem2 = python_semantic.analyze(src2)
    assert not any(i["kind"] == "unused_variable" for i in sem2)

    # 3. 'x = \"a == None\"' must not report comparison_to_none
    src3 = 'x = "a == None"\n'
    sem3 = python_semantic.analyze(src3)
    assert not any(i["kind"] == "comparison_to_none" for i in sem3)

    # 4. yaml.load(f, Loader=yaml.SafeLoader) must not trigger PY-SEC-01
    src4 = "import yaml\nyaml.load(f, Loader=yaml.SafeLoader)\n"
    sec4 = python_security.analyze(src4)
    assert not any(f["rule"] == "PY-SEC-01" for f in sec4)

    # 5. hashlib.md5(b"x", usedforsecurity=False) must not trigger PY-SEC-02
    src5 = "import hashlib\nhashlib.md5(b'x', usedforsecurity=False)\n"
    sec5 = python_security.analyze(src5)
    assert not any(f["rule"] == "PY-SEC-02" for f in sec5)

    # 6. subprocess.call(["ls"]) must not trigger PY-SEC-04
    src6 = "import subprocess\nsubprocess.call(['ls'])\n"
    sec6 = python_security.analyze(src6)
    assert not any(f["rule"] == "PY-SEC-04" for f in sec6)

    # 7. add(1, 2) matching arity must not report call_arity_mismatch
    src7 = "def add(a, b):\n    return a + b\nadd(1, 2)\n"
    sem7 = python_semantic.analyze(src7)
    assert not any(i["kind"] == "call_arity_mismatch" for i in sem7)

    # 8. Name defined later at module level but used inside a function must not be undefined_name
    src8 = "def get_val():\n    return global_val\nglobal_val = 42\n"
    sem8 = python_semantic.analyze(src8)
    assert not any(i["kind"] == "undefined_name" for i in sem8)

    # 9. @staticmethod must not report method_missing_self
    src9 = "class C:\n    @staticmethod\n    def helper():\n        return 1\n"
    sem9 = python_semantic.analyze(src9)
    assert not any(i["kind"] == "method_missing_self" for i in sem9)

    # 10. verify=True must not trigger PY-SEC-05
    src10 = "import requests\nrequests.get('https://example.com', verify=True)\n"
    sec10 = python_security.analyze(src10)
    assert not any(f["rule"] == "PY-SEC-05" for f in sec10)

    # 11. debug=False must not trigger PY-SEC-06
    src11 = "from flask import Flask\napp = Flask(__name__)\napp.run(debug=False)\n"
    sec11 = python_security.analyze(src11)
    assert not any(f["rule"] == "PY-SEC-06" for f in sec11)

    # 12. Empty string password must not trigger PY-SEC-07
    src12 = "password = ''\n"
    sec12 = python_security.analyze(src12)
    assert not any(f["rule"] == "PY-SEC-07" for f in sec12)

    # 13. Parameterized query must not trigger PY-SEC-08
    src13 = "cursor.execute('SELECT * FROM users WHERE id = %s', (uid,))\n"
    sec13 = python_security.analyze(src13)
    assert not any(f["rule"] == "PY-SEC-08" for f in sec13)

def test_revert_unsafe_fix_when_syntax_broken(monkeypatch):
    # A fix that produces invalid syntax must be rejected
    orig_get_fix = python_semantic.get_fix_candidate
    def broken_fixer(src, issues):
        cand = orig_get_fix(src, issues)
        if cand:
            return cand[0] + "\ndef :", cand[1], cand[2]
        return None

    monkeypatch.setattr(python_semantic, "get_fix_candidate", broken_fixer)
    src = "done = true\nprint(done)\n"
    res = repair_python(src, "test_revert.py")
    # Because broken fix was rejected, original code was not corrupted
    assert "def :" not in res["corrected_code"]

def test_python_and_c_results_have_same_keys():
    py_res = repair_python("x = 1\n", "test.py")
    c_res = repair_source_for_gui("int main() { return 0; }", "main.c")

    expected_keys = {
        "success",
        "status",
        "filename",
        "corrected_code",
        "applied_steps",
        "logs",
        "errors",
        "semantic_issues",
        "security_warnings",
        "changed_lines",
        "security_changed_lines",
        "stats",
        "green_report",
        "total_applied_steps",
        "language",
    }

    assert expected_keys.issubset(set(py_res.keys())), f"Python missing keys: {expected_keys - set(py_res.keys())}"
    assert expected_keys.issubset(set(c_res.keys())), f"C missing keys: {expected_keys - set(c_res.keys())}"
