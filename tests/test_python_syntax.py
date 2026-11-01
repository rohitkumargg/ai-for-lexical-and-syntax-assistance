import os
import time
import pytest
from compiler.languages.python_lang import repair_python

SYNTAX_DIR = os.path.join("examples", "python", "syntax")
EXPECTED_DIR = os.path.join("examples", "python", "_expected", "syntax")

PAIRS = [
    "s01_missing_colon.py",
    "s02_unclosed_paren.py",
    "s03_assign_in_condition.py",
    "s04_missing_indent.py",
    "s05_unexpected_indent.py",
    "s06_unterminated_string.py",
    "s07_python2_print.py",
    "s08_else_if.py",
    "s09_keyword_typo.py",
    "s10_c_style_operators.py",
]

@pytest.mark.parametrize("filename", PAIRS)
def test_syntax_pairs_match_expected(filename):
    broken_path = os.path.join(SYNTAX_DIR, filename)
    expected_path = os.path.join(EXPECTED_DIR, filename)

    with open(broken_path, "r", encoding="utf-8") as f:
        broken_src = f.read()
    with open(expected_path, "r", encoding="utf-8") as f:
        expected_src = f.read()

    res = repair_python(broken_src, filename)
    assert res["status"] in ("SUCCESS", "SUCCESS_WITH_WARNINGS")
    # Normalize line endings and trailing whitespace
    norm_corrected = "\n".join(line.rstrip() for line in res["corrected_code"].replace("\r\n", "\n").strip().split("\n"))
    norm_expected = "\n".join(line.rstrip() for line in expected_src.replace("\r\n", "\n").strip().split("\n"))
    assert norm_corrected == norm_expected

@pytest.mark.parametrize("filename", PAIRS)
def test_syntax_idempotence(filename):
    broken_path = os.path.join(SYNTAX_DIR, filename)
    with open(broken_path, "r", encoding="utf-8") as f:
        broken_src = f.read()

    res1 = repair_python(broken_src, filename)
    fixed1 = res1["corrected_code"]

    res2 = repair_python(fixed1, filename)
    assert res2["corrected_code"] == fixed1
    assert len(res2["applied_steps"]) == 0

def test_clean_guard_unchanged():
    path = os.path.join("examples", "python", "clean_guard.py")
    with open(path, "rb") as f:
        raw_bytes = f.read()
    src = raw_bytes.decode("utf-8")

    res = repair_python(src, "clean_guard.py")
    assert res["status"] == "SUCCESS"
    assert res["corrected_code"] == src
    assert len(res["errors"]) == 0
    assert len(res["semantic_issues"]) == 0
    assert len(res["security_warnings"]) == 0
    assert len(res["applied_steps"]) == 0
    assert res["corrected_code"].encode("utf-8") == raw_bytes

def test_valid_code_never_touched():
    valid_snippets = [
        "x = 1\ny = 2\nz = x + y\n",
        "def greet(name):\n    return f'Hello, {name}'\n",
        "class A:\n    def __init__(self):\n        self.v = 1\n",
    ]
    for snip in valid_snippets:
        res = repair_python(snip, "valid.py")
        assert res["status"] == "SUCCESS"
        assert res["corrected_code"] == snip
        assert len(res["applied_steps"]) == 0

@pytest.mark.parametrize("garbage, expected_status", [
    ("", "SUCCESS"),  # empty string is valid python ast
    ("\x00", ("UNFIXABLE", "STOPPED")),
    ("def :", ("UNFIXABLE", "STOPPED")),
    ("'''unclosed triple quote", ("UNFIXABLE", "STOPPED")),
    ("a = 1\n" * 5000 + "def :", ("UNFIXABLE", "STOPPED")),
], ids=["empty", "null_byte", "def_colon", "unclosed_triple", "5000_lines"])
def test_garbage_input_safe_and_fast(garbage, expected_status):
    t0 = time.perf_counter()
    res = repair_python(garbage, "garbage.py")
    elapsed = time.perf_counter() - t0

    assert elapsed < 5.0, f"Garbage test took {elapsed:.2f}s, expected < 5s"
    if isinstance(expected_status, tuple):
        assert res["status"] in expected_status
    else:
        assert res["status"] == expected_status

def test_stats_counters_correct():
    with open(os.path.join(SYNTAX_DIR, "s07_python2_print.py"), "r", encoding="utf-8") as f:
        s07_src = f.read()
    res07 = repair_python(s07_src, "s07_python2_print.py")
    assert res07["stats"]["lex_fixes"] == 1
    assert any("LEX:" in s for s in res07["applied_steps"])

    with open(os.path.join(SYNTAX_DIR, "s01_missing_colon.py"), "r", encoding="utf-8") as f:
        s01_src = f.read()
    res01 = repair_python(s01_src, "s01_missing_colon.py")
    assert res01["stats"]["rule_fixes"] == 1
    assert any("RULE:" in s for s in res01["applied_steps"])
