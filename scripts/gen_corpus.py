#!/usr/bin/env python3
"""Deterministic Corpus Generator for Antigravity Repair Pipeline.

Generates 320+ test programs (C, Python, and Cross-cutting) across:
- C: Syntax (~50), Semantic (~30), Security (~35), Structure/Size/Format (~35)
- Python: Syntax (~40), Semantic (~20), Security (~30), Structure/Size (~20)
- Cross-cutting: Regression, Agent-security, Clean, Warnings-only, Metrics, API negatives, UI flows (~60)

Outputs:
  tests/corpus/<id>.<ext>
  tests/corpus/oracles/<id>_oracle.<ext>
  tests/corpus/manifest.csv

Deterministic seed: 20261114.
Split: 70% dev / 30% held_out via sha256(id) % 100 < 70.
"""

import ast
import csv
import hashlib
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SEED = 20261114
random.seed(SEED)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "tests" / "corpus"
ORACLES_DIR = CORPUS_DIR / "oracles"
MANIFEST_PATH = CORPUS_DIR / "manifest.csv"
MOCK_HEADERS_DIR = PROJECT_ROOT / "data" / "mock_headers"


def get_split(case_id: str) -> str:
    """Deterministic 70/30 split based on SHA256 hash."""
    h = int(hashlib.sha256(case_id.encode("utf-8")).hexdigest(), 16)
    return "dev" if (h % 100) < 70 else "held_out"


def compile_c_code(source: str) -> Tuple[int, str, str]:
    """Compile C code with gcc -Wall -Wextra -std=c11 -c."""
    with tempfile.NamedTemporaryFile(suffix=".c", delete=False, mode="w", encoding="utf-8") as f:
        f.write(source)
        src_path = f.name
    obj_path = src_path + ".o"
    try:
        cmd = ["gcc", "-Wall", "-Wextra", "-std=c11", "-c"]
        if MOCK_HEADERS_DIR.is_dir():
            cmd.extend(["-I", str(MOCK_HEADERS_DIR)])
        cmd.extend([src_path, "-o", obj_path])
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.returncode, res.stdout, res.stderr
    except Exception as ex:
        return -1, "", str(ex)
    finally:
        for p in (src_path, obj_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def compile_py_code(source: str) -> Tuple[int, str, str]:
    """Compile Python code with py_compile and ast.parse."""
    try:
        ast.parse(source)
    except SyntaxError as e:
        return 1, "", f"SyntaxError: {e}"
    except Exception as e:
        return 1, "", str(e)

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
        f.write(source)
        src_path = f.name
    try:
        res = subprocess.run([sys.executable, "-m", "py_compile", src_path], capture_output=True, text=True, timeout=15)
        return res.returncode, res.stdout, res.stderr
    except Exception as ex:
        return -1, "", str(ex)
    finally:
        if os.path.exists(src_path):
            try:
                os.remove(src_path)
            except OSError:
                pass


class CorpusCase:
    def __init__(
        self,
        case_id: str,
        language: str,
        category: str,
        subcat: str,
        expected_class: str,
        valid_base: str,
        mutated_code: str,
        mutation_desc: str,
    ):
        self.id = case_id
        self.language = language
        self.category = category
        self.subcat = subcat
        self.expected_class = expected_class
        self.valid_base = valid_base
        self.mutated_code = mutated_code
        self.mutation_desc = mutation_desc
        self.split = get_split(case_id)
        self.lines = len(mutated_code.splitlines())
        ext = ".c" if language == "c" else ".py"
        self.filename = f"{case_id}{ext}"
        self.oracle_name = f"{case_id}_oracle{ext}"


def generate_all_cases() -> List[CorpusCase]:
    cases: List[CorpusCase] = []

    # =========================================================================
    # 1. C CASES (~150)
    # =========================================================================

    # --- 1.1 C SYNTAX (~50) ---
    c_syntax_specs = [
        ("missing_semicolon_assign", "int main(void) {\n    int a = 10;\n    int b = 20;\n    int c = a + b;\n    return c;\n}\n", "int main(void) {\n    int a = 10\n    int b = 20;\n    int c = a + b;\n    return c;\n}\n", "missing ';' on assign"),
        ("missing_semicolon_decl", "int main(void) {\n    int x = 5;\n    int y = 10;\n    return x + y;\n}\n", "int main(void) {\n    int x\n    int y = 10;\n    return x + y;\n}\n", "missing ';' on decl"),
        ("missing_semicolon_return", "int calc(int a) {\n    return a * 2;\n}\nint main(void) {\n    return calc(5);\n}\n", "int calc(int a) {\n    return a * 2\n}\nint main(void) {\n    return calc(5);\n}\n", "missing ';' on return"),
        ("missing_semicolon_call", "#include <stdio.h>\nint main(void) {\n    printf(\"Hello\\n\");\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    printf(\"Hello\\n\")\n    return 0;\n}\n", "missing ';' on function call"),
        ("missing_semicolon_multi", "int main(void) {\n    int a = 1;\n    int b = 2;\n    int c = 3;\n    return a + b + c;\n}\n", "int main(void) {\n    int a = 1\n    int b = 2\n    int c = 3;\n    return a + b + c;\n}\n", "multiple missing ';' in single function"),
        ("missing_right_paren_if", "int main(void) {\n    int x = 10;\n    if (x > 5) {\n        return 1;\n    }\n    return 0;\n}\n", "int main(void) {\n    int x = 10;\n    if (x > 5 {\n        return 1;\n    }\n    return 0;\n}\n", "missing ')' in if statement"),
        ("missing_right_paren_while", "int main(void) {\n    int i = 0;\n    while (i < 10) {\n        i++;\n    }\n    return i;\n}\n", "int main(void) {\n    int i = 0;\n    while (i < 10 {\n        i++;\n    }\n    return i;\n}\n", "missing ')' in while loop"),
        ("missing_right_paren_for", "int main(void) {\n    int s = 0;\n    for (int i = 0; i < 5; i++) {\n        s += i;\n    }\n    return s;\n}\n", "int main(void) {\n    int s = 0;\n    for (int i = 0; i < 5; i++ {\n        s += i;\n    }\n    return s;\n}\n", "missing ')' in for loop"),
        ("missing_right_paren_call", "#include <stdio.h>\nint main(void) {\n    int v = 42;\n    printf(\"Value: %d\\n\", v);\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    int v = 42;\n    printf(\"Value: %d\\n\", v;\n    return 0;\n}\n", "missing ')' in call args"),
        ("missing_right_bracket_decl", "int main(void) {\n    int arr[10];\n    arr[0] = 1;\n    return arr[0];\n}\n", "int main(void) {\n    int arr[10;\n    arr[0] = 1;\n    return arr[0];\n}\n", "missing ']' in array declaration"),
        ("missing_right_bracket_idx", "int main(void) {\n    int arr[5] = {1, 2, 3, 4, 5};\n    return arr[2];\n}\n", "int main(void) {\n    int arr[5] = {1, 2, 3, 4, 5};\n    return arr[2;\n}\n", "missing ']' in array subscript"),
        ("missing_right_brace_func", "int square(int x) {\n    return x * x;\n}\nint main(void) {\n    return square(4);\n}\n", "int square(int x) {\n    return x * x;\n\nint main(void) {\n    return square(4);\n}\n", "unbalanced missing '}' in function body"),
        ("missing_right_brace_if", "int main(void) {\n    int x = 3;\n    if (x > 0) {\n        x = x * 2;\n    }\n    return x;\n}\n", "int main(void) {\n    int x = 3;\n    if (x > 0) {\n        x = x * 2;\n    \n    return x;\n}\n", "unclosed block missing '}' in if"),
        ("missing_comma_args", "int add(int a, int b) {\n    return a + b;\n}\nint main(void) {\n    return add(10, 20);\n}\n", "int add(int a, int b) {\n    return a + b;\n}\nint main(void) {\n    return add(10 20);\n}\n", "missing ',' between call arguments"),
        ("missing_comma_params", "int sub(int a, int b) {\n    return a - b;\n}\nint main(void) {\n    return sub(5, 2);\n}\n", "int sub(int a int b) {\n    return a - b;\n}\nint main(void) {\n    return sub(5, 2);\n}\n", "missing ',' in parameter declaration"),
        ("missing_comma_array", "int main(void) {\n    int nums[] = {1, 2, 3, 4};\n    return nums[0];\n}\n", "int main(void) {\n    int nums[] = {1, 2 3, 4};\n    return nums[0];\n}\n", "missing ',' in array initializer"),
        ("extra_token_stray_semis", "int main(void) {\n    int x = 10;\n    return x;\n}\n", "int main(void) {\n    int x = 10 %% 2;\n    return x;\n}\n", "extra stray token '%%'"),
        ("extra_token_stray_char", "int main(void) {\n    int total = 100;\n    return total;\n}\n", "int main(void) {\n    int total = 100;\n    @\n    return total;\n}\n", "stray '@' token"),
        ("typo_keyword_viod", "void process(void) {\n    int a = 1;\n    (void)a;\n}\nint main(void) {\n    process();\n    return 0;\n}\n", "viod process(void) {\n    int a = 1;\n    (void)a;\n}\nint main(void) {\n    process();\n    return 0;\n}\n", "keyword typo 'viod'"),
        ("typo_keyword_cahr", "int main(void) {\n    char c = 'A';\n    return (int)c;\n}\n", "int main(void) {\n    cahr c = 'A';\n    return (int)c;\n}\n", "keyword typo 'cahr'"),
        ("typo_keyword_retrun", "int compute(void) {\n    return 42;\n}\nint main(void) {\n    return compute();\n}\n", "int compute(void) {\n    retrun 42;\n}\nint main(void) {\n    return compute();\n}\n", "keyword typo 'retrun'"),
        ("typo_keyword_whiel", "int main(void) {\n    int n = 3;\n    while (n > 0) {\n        n--;\n    }\n    return n;\n}\n", "int main(void) {\n    int n = 3;\n    whiel (n > 0) {\n        n--;\n    }\n    return n;\n}\n", "keyword typo 'whiel'"),
        ("typo_keyword_itn", "int main(void) {\n    int val = 99;\n    return val;\n}\n", "int main(void) {\n    itn val = 99;\n    return val;\n}\n", "keyword typo 'itn'"),
        ("typo_keyword_doubel", "int main(void) {\n    double pi = 3.14;\n    return (int)pi;\n}\n", "int main(void) {\n    doubel pi = 3.14;\n    return (int)pi;\n}\n", "keyword typo 'doubel'"),
        ("typo_keyword_flota", "int main(void) {\n    float rate = 1.5f;\n    return (int)rate;\n}\n", "int main(void) {\n    flota rate = 1.5f;\n    return (int)rate;\n}\n", "keyword typo 'flota'"),
        ("missing_paren_if_cond", "int main(void) {\n    int k = 10;\n    if (k > 0) {\n        return 1;\n    }\n    return 0;\n}\n", "int main(void) {\n    int k = 10;\n    if k > 0 {\n        return 1;\n    }\n    return 0;\n}\n", "missing enclosing '(' and ')' in if statement"),
        ("missing_paren_while_cond", "int main(void) {\n    int cnt = 5;\n    while (cnt > 0) {\n        cnt--;\n    }\n    return cnt;\n}\n", "int main(void) {\n    int cnt = 5;\n    while cnt > 0 {\n        cnt--;\n    }\n    return cnt;\n}\n", "missing enclosing '(' and ')' in while statement"),
        ("missing_paren_for_cond", "int main(void) {\n    int s = 0;\n    for (int i = 0; i < 3; i++) {\n        s += i;\n    }\n    return s;\n}\n", "int main(void) {\n    int s = 0;\n    for int i = 0; i < 3; i++ {\n        s += i;\n    }\n    return s;\n}\n", "missing enclosing '(' and ')' in for loop"),
        ("bad_decl_missing_type", "int main(void) {\n    int z = 42;\n    return z;\n}\n", "int main(void) {\n    z = 42;\n    return z;\n}\n", "variable assigned without type declaration"),
        ("bad_decl_inverted_order", "int main(void) {\n    int score = 100;\n    return score;\n}\n", "int main(void) {\n    score int = 100;\n    return score;\n}\n", "inverted type declaration (identifier before type)"),
        ("unterminated_string", "#include <stdio.h>\nint main(void) {\n    printf(\"hello world\\n\");\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    printf(\"hello world\\n);\n    return 0;\n}\n", "unterminated string literal"),
        ("unterminated_comment", "/* Valid banner comment */\nint main(void) {\n    return 0;\n}\n", "/* Unclosed banner comment\nint main(void) {\n    return 0;\n}\n", "unterminated /* comment"),
        ("missing_binary_operator", "int main(void) {\n    int a = 10;\n    int b = 20;\n    int c = a + b;\n    return c;\n}\n", "int main(void) {\n    int a = 10;\n    int b = 20;\n    int c = a b;\n    return c;\n}\n", "missing operator between operands 'a b'"),
        ("missing_colon_switch_case", "int main(void) {\n    int x = 1;\n    switch (x) {\n        case 1:\n            return 10;\n        default:\n            return 0;\n    }\n}\n", "int main(void) {\n    int x = 1;\n    switch (x) {\n        case 1\n            return 10;\n        default:\n            return 0;\n    }\n}\n", "missing ':' after case label"),
        ("missing_semicolon_struct_def", "struct Point {\n    int x;\n    int y;\n};\nint main(void) {\n    struct Point p = {1, 2};\n    return p.x + p.y;\n}\n", "struct Point {\n    int x;\n    int y;\n}\nint main(void) {\n    struct Point p = {1, 2};\n    return p.x + p.y;\n}\n", "missing ';' after struct closing brace"),
        ("missing_semicolon_enum_def", "enum Mode {\n    IDLE,\n    ACTIVE\n};\nint main(void) {\n    enum Mode m = ACTIVE;\n    return (int)m;\n}\n", "enum Mode {\n    IDLE,\n    ACTIVE\n}\nint main(void) {\n    enum Mode m = ACTIVE;\n    return (int)m;\n}\n", "missing ';' after enum definition"),
        ("missing_semicolon_do_while", "int main(void) {\n    int i = 0;\n    do {\n        i++;\n    } while (i < 5);\n    return i;\n}\n", "int main(void) {\n    int i = 0;\n    do {\n        i++;\n    } while (i < 5)\n    return i;\n}\n", "missing ';' after do-while condition"),
        ("missing_left_brace_func", "int run(void) {\n    return 42;\n}\nint main(void) {\n    return run();\n}\n", "int run(void)\n    return 42;\n}\nint main(void) {\n    return run();\n}\n", "missing opening '{' for function body"),
        ("missing_right_paren_switch", "int main(void) {\n    int opt = 2;\n    switch (opt) {\n        case 2: return 0;\n        default: return 1;\n    }\n}\n", "int main(void) {\n    int opt = 2;\n    switch (opt {\n        case 2: return 0;\n        default: return 1;\n    }\n}\n", "missing ')' in switch condition"),
        ("stray_hash_token", "int main(void) {\n    int v = 1;\n    return v;\n}\n", "int main(void) {\n    int v = 1;\n    # bad\n    return v;\n}\n", "stray '#' preprocessor token in function"),
        ("multiple_errors_3funcs", "int f1(void) {\n    return 1;\n}\nint f2(void) {\n    return 2;\n}\nint f3(void) {\n    return 3;\n}\nint main(void) {\n    return f1() + f2() + f3();\n}\n", "int f1(void) {\n    return 1\n}\nint f2(void) {\n    return 2\n}\nint f3(void) {\n    return 3\n}\nint main(void) {\n    return f1() + f2() + f3();\n}\n", "errors spread across 3 functions (missing ;)"),
        ("multiple_errors_5funcs", "int a(void) { return 1; }\nint b(void) { return 2; }\nint c(void) { return 3; }\nint d(void) { return 4; }\nint e(void) { return 5; }\nint main(void) { return a()+b()+c()+d()+e(); }\n", "int a(void) { return 1 }\nint b(void) { return 2 }\nint c(void) { return 3 }\nint d(void) { return 4 }\nint e(void) { return 5 }\nint main(void) { return a()+b()+c()+d()+e(); }\n", "errors spread across 5 functions"),
        ("semicolon_and_paren_mix", "int check(int val) {\n    if (val > 10) {\n        return val;\n    }\n    return 0;\n}\nint main(void) {\n    return check(20);\n}\n", "int check(int val) {\n    if (val > 10 {\n        return val\n    }\n    return 0;\n}\nint main(void) {\n    return check(20);\n}\n", "mixed missing ')' and missing ';' in same function"),
        ("missing_type_in_param", "int mult(int x, int y) {\n    return x * y;\n}\nint main(void) {\n    return mult(4, 5);\n}\n", "int mult(int x, y) {\n    return x * y;\n}\nint main(void) {\n    return mult(4, 5);\n}\n", "missing type in parameter 'y'"),
        ("bad_struct_field_decl", "struct Config {\n    int timeout;\n    int retries;\n};\nint main(void) {\n    struct Config c = {10, 3};\n    return c.retries;\n}\n", "struct Config {\n    int timeout\n    int retries;\n};\nint main(void) {\n    struct Config c = {10, 3};\n    return c.retries;\n}\n", "missing ';' on struct field declaration"),
        ("missing_return_semicolon_nested", "int eval(int x) {\n    if (x > 0) {\n        if (x > 10) {\n            return 100;\n        }\n    }\n    return 0;\n}\nint main(void) {\n    return eval(15);\n}\n", "int eval(int x) {\n    if (x > 0) {\n        if (x > 10) {\n            return 100\n        }\n    }\n    return 0;\n}\n", "missing ';' in deeply nested return"),
        ("broken_for_loop_semicolons", "int main(void) {\n    int sum = 0;\n    for (int i = 0; i < 5; i++) {\n        sum += i;\n    }\n    return sum;\n}\n", "int main(void) {\n    int sum = 0;\n    for (int i = 0, i < 5, i++) {\n        sum += i;\n    }\n    return sum;\n}\n", "commas instead of semicolons in for header"),
        ("missing_right_bracket_matrix", "int main(void) {\n    int mat[2][2] = {{1, 2}, {3, 4}};\n    return mat[0][1];\n}\n", "int main(void) {\n    int mat[2][2 = {{1, 2}, {3, 4}};\n    return mat[0][1];\n}\n", "missing ']' in 2D array declaration"),
        ("double_type_specifier", "int main(void) {\n    int count = 5;\n    return count;\n}\n", "int main(void) {\n    int float count = 5;\n    return count;\n}\n", "conflicting double type specifier 'int float'"),
        ("unterminated_char_literal", "int main(void) {\n    char ch = 'A';\n    return (int)ch;\n}\n", "int main(void) {\n    char ch = 'A;\n    return (int)ch;\n}\n", "unterminated character literal"),
    ]

    for idx, (subcat, base, mut, desc) in enumerate(c_syntax_specs, start=1):
        cases.append(CorpusCase(
            case_id=f"c_syn_{idx:03d}",
            language="c",
            category="syntax",
            subcat=subcat,
            expected_class="broken",
            valid_base=base,
            mutated_code=mut,
            mutation_desc=desc,
        ))

    # --- 1.2 C SEMANTIC (~30) ---
    c_semantic_specs = [
        ("undeclared_var", "int main(void) {\n    int val = 42;\n    return val;\n}\n", "int main(void) {\n    return val;\n}\n", "broken", "undeclared variable 'val'"),
        ("undeclared_func", "struct Point { int x; };\nstruct Point helper(void) { struct Point p = {1}; return p; }\nint main(void) {\n    struct Point res = helper();\n    return res.x;\n}\n", "struct Point { int x; };\nint main(void) {\n    struct Point res = helper();\n    return res.x;\n}\n", "broken", "calling undeclared function returning struct (hard error)"),
        ("wrong_arg_count_few", "int calc(int a, int b) {\n    return a + b;\n}\nint main(void) {\n    return calc(10, 20);\n}\n", "int calc(int a, int b) {\n    return a + b;\n}\nint main(void) {\n    return calc(10);\n}\n", "broken", "too few arguments to function 'calc'"),
        ("wrong_arg_count_many", "int inc(int a) {\n    return a + 1;\n}\nint main(void) {\n    return inc(5);\n}\n", "int inc(int a) {\n    return a + 1;\n}\nint main(void) {\n    return inc(5, 10);\n}\n", "broken", "too many arguments to function 'inc'"),
        ("type_mismatch_ptr_to_int", "struct Point { int x; };\nint main(void) {\n    struct Point pt = {1};\n    int a = pt.x;\n    return a;\n}\n", "struct Point { int x; };\nint main(void) {\n    struct Point pt = {1};\n    int *p = pt;\n    return (p != 0);\n}\n", "broken", "incompatible struct to pointer assignment"),
        ("type_mismatch_int_to_ptr", "struct Point { int x; };\nint main(void) {\n    struct Point pt = {1};\n    return pt.x;\n}\n", "struct Point { int x; };\nint main(void) {\n    struct Point pt = {1};\n    int x = pt;\n    return x;\n}\n", "broken", "incompatible struct to int initialization"),
        ("missing_return_nonvoid", "int get_status(void) {\n    int ok = 1;\n    return ok;\n}\n", "int get_status(void) {\n    int ok = 1;\n    (void)ok;\n}\n", "compiles-with-warnings", "missing return statement in non-void function"),
        ("missing_include_stdio", "#include <stdio.h>\nint main(void) {\n    puts(\"test\");\n    return 0;\n}\n", "int main(void) {\n    puts(\"test\");\n    return 0;\n}\n", "compiles-with-warnings", "missing #include <stdio.h> (implicit declaration warning)"),
        ("missing_include_stdlib", "#include <stdlib.h>\nint main(void) {\n    void *p = malloc(16);\n    free(p);\n    return 0;\n}\n", "int main(void) {\n    void *p = malloc(16);\n    free(p);\n    return 0;\n}\n", "compiles-with-warnings", "missing #include <stdlib.h> for malloc/free"),
        ("redefinition_var", "int main(void) {\n    int total = 10;\n    total += 5;\n    return total;\n}\n", "int main(void) {\n    int total = 10;\n    int total = 20;\n    return total;\n}\n", "broken", "redefinition of variable 'total'"),
        ("redefinition_func", "int get_val(void) {\n    return 1;\n}\nint main(void) {\n    return get_val();\n}\n", "int get_val(void) {\n    return 1;\n}\nint get_val(void) {\n    return 2;\n}\nint main(void) {\n    return get_val();\n}\n", "broken", "redefinition of function 'get_val'"),
        ("void_func_returns_val", "void do_work(void) {\n    int a = 1;\n    (void)a;\n    return;\n}\nint main(void) {\n    do_work();\n    return 0;\n}\n", "void do_work(void) {\n    return 42;\n}\nint main(void) {\n    do_work();\n    return 0;\n}\n", "broken", "return with value in void function"),
        ("access_nonexistent_struct_member", "struct User {\n    int id;\n    int age;\n};\nint main(void) {\n    struct User u = {1, 30};\n    return u.age;\n}\n", "struct User {\n    int id;\n    int age;\n};\nint main(void) {\n    struct User u = {1, 30};\n    return u.score;\n}\n", "broken", "access member 'score' not in struct User"),
        ("dereference_non_pointer", "int main(void) {\n    int a = 10;\n    int b = a;\n    return b;\n}\n", "int main(void) {\n    int a = 10;\n    int b = *a;\n    return b;\n}\n", "broken", "invalid indirection / dereferencing non-pointer"),
        ("subscript_non_array", "int main(void) {\n    int arr[2] = {1, 2};\n    return arr[0];\n}\n", "int main(void) {\n    int val = 5;\n    return val[0];\n}\n", "broken", "subscripted value is neither array nor pointer"),
        ("call_non_function", "int main(void) {\n    int x = 42;\n    return x;\n}\n", "int main(void) {\n    int x = 42;\n    return x();\n}\n", "broken", "called object 'x' is not a function"),
        ("case_label_not_in_switch", "int main(void) {\n    int x = 1;\n    switch (x) {\n        case 1: return 0;\n        default: return 1;\n    }\n}\n", "int main(void) {\n    int x = 1;\n    case 1: return 0;\n    return x;\n}\n", "broken", "case label not within a switch statement"),
        ("break_not_in_loop", "int main(void) {\n    int sum = 0;\n    for (int i = 0; i < 5; i++) {\n        if (i == 3) break;\n        sum += i;\n    }\n    return sum;\n}\n", "int main(void) {\n    int sum = 0;\n    break;\n    return sum;\n}\n", "broken", "break statement not within loop or switch"),
        ("continue_not_in_loop", "int main(void) {\n    int sum = 0;\n    for (int i = 0; i < 5; i++) {\n        if (i == 2) continue;\n        sum += i;\n    }\n    return sum;\n}\n", "int main(void) {\n    int sum = 0;\n    continue;\n    return sum;\n}\n", "broken", "continue statement not within a loop"),
        ("uninitialized_var_warning", "int main(void) {\n    int x = 0;\n    return x;\n}\n", "int main(void) {\n    int x;\n    return x;\n}\n", "compiles-with-warnings", "uninitialized variable use (warning with -Wall)"),
        ("format_specifier_mismatch", "#include <stdio.h>\nint main(void) {\n    int count = 5;\n    printf(\"%d\\n\", count);\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    int count = 5;\n    printf(\"%s\\n\", count);\n    return 0;\n}\n", "compiles-with-warnings", "format specifier '%s' expects char* but arg has type int"),
        ("unused_variable_warning", "int main(void) {\n    int a = 10;\n    return a;\n}\n", "int main(void) {\n    int a = 10;\n    int b = 20;\n    return a;\n}\n", "compiles-with-warnings", "unused variable 'b' warning with -Wall"),
        ("comparison_pointer_integer", "struct Point { int x; };\nint main(void) {\n    struct Point pt = {1};\n    int a = pt.x;\n    return a;\n}\n", "struct Point { int x; };\nint main(void) {\n    struct Point pt = {1};\n    int *p = 0;\n    return (p == pt);\n}\n", "broken", "comparison between pointer and struct (hard error)"),
        ("array_size_negative", "int main(void) {\n    int arr[5];\n    arr[0] = 1;\n    return arr[0];\n}\n", "int main(void) {\n    int arr[-5];\n    arr[0] = 1;\n    return arr[0];\n}\n", "broken", "size of array is negative"),
        ("invalid_operands_binary_modulo", "int main(void) {\n    int a = 10;\n    int b = 3;\n    return a % b;\n}\n", "int main(void) {\n    double a = 10.5;\n    double b = 3.2;\n    return (int)(a % b);\n}\n", "broken", "invalid operands to binary % (have double and double)"),
        ("lvalue_required_assign", "int main(void) {\n    int a = 5;\n    a = 10;\n    return a;\n}\n", "int main(void) {\n    int a = 5;\n    a + 1 = 10;\n    return a;\n}\n", "broken", "lvalue required as left operand of assignment"),
        ("void_variable_declaration", "int main(void) {\n    int val = 0;\n    return val;\n}\n", "int main(void) {\n    void val;\n    return 0;\n}\n", "broken", "variable 'val' declared void"),
        ("duplicate_case_value", "int main(void) {\n    int x = 1;\n    switch (x) {\n        case 1: return 10;\n        case 2: return 20;\n        default: return 0;\n    }\n}\n", "int main(void) {\n    int x = 1;\n    switch (x) {\n        case 1: return 10;\n        case 1: return 20;\n        default: return 0;\n    }\n}\n", "broken", "duplicate case value '1' in switch"),
        ("conflicting_types_for_func", "int test(int x);\nint test(int x) {\n    return x * 2;\n}\nint main(void) {\n    return test(4);\n}\n", "int test(int x);\nvoid test(int x) {\n    (void)x;\n}\nint main(void) {\n    test(4);\n    return 0;\n}\n", "broken", "conflicting return types for 'test'"),
        ("missing_include_string", "#include <string.h>\nint main(void) {\n    const char *s = \"abc\";\n    return (int)strlen(s);\n}\n", "int main(void) {\n    const char *s = \"abc\";\n    return (int)strlen(s);\n}\n", "compiles-with-warnings", "implicit declaration of strlen without <string.h>"),
    ]

    for idx, (subcat, base, mut, exp_cls, desc) in enumerate(c_semantic_specs, start=1):
        cases.append(CorpusCase(
            case_id=f"c_sem_{idx:03d}",
            language="c",
            category="semantic",
            subcat=subcat,
            expected_class=exp_cls,
            valid_base=base,
            mutated_code=mut,
            mutation_desc=desc,
        ))

    # --- 1.3 C SECURITY (~35, vulnerable patterns only, fake dummy secrets, NO attack payloads) ---
    c_sec_specs = [
        ("unsafe_gets", "#include <stdio.h>\nint main(void) {\n    char buf[64];\n    if (fgets(buf, sizeof(buf), stdin)) {\n        puts(buf);\n    }\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    char buf[64];\n    gets(buf);\n    return 0;\n}\n", "CWE-242: gets() function is obsolete and inherently unsafe"),
        ("unsafe_strcpy", "#include <string.h>\nint main(void) {\n    char src[] = \"test\";\n    char dst[16];\n    strncpy(dst, src, sizeof(dst) - 1);\n    dst[sizeof(dst) - 1] = '\\0';\n    return 0;\n}\n", "#include <string.h>\nint main(void) {\n    char src[] = \"test\";\n    char dst[16];\n    strcpy(dst, src);\n    return 0;\n}\n", "CWE-120: strcpy() without bounds check"),
        ("unsafe_strcat", "#include <string.h>\nint main(void) {\n    char dst[32] = \"hello\";\n    strncat(dst, \" world\", sizeof(dst) - strlen(dst) - 1);\n    return 0;\n}\n", "#include <string.h>\nint main(void) {\n    char dst[32] = \"hello\";\n    strcat(dst, \" world\");\n    return 0;\n}\n", "CWE-120: strcat() buffer overflow risk"),
        ("unsafe_sprintf", "#include <stdio.h>\nint main(void) {\n    char buf[32];\n    snprintf(buf, sizeof(buf), \"%s\", \"safe\");\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    char buf[32];\n    sprintf(buf, \"%s\", \"vulnerable\");\n    return 0;\n}\n", "CWE-134/120: sprintf() unbounded write into buffer"),
        ("unsafe_scanf_unbounded", "#include <stdio.h>\nint main(void) {\n    char name[32];\n    if (scanf(\"%31s\", name) == 1) {\n        puts(name);\n    }\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    char name[32];\n    scanf(\"%s\", name);\n    return 0;\n}\n", "CWE-120: scanf without maximum field width"),
        ("format_string_misuse", "#include <stdio.h>\nint main(void) {\n    char msg[] = \"notice\";\n    printf(\"%s\\n\", msg);\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    char msg[] = \"notice\";\n    printf(msg);\n    return 0;\n}\n", "CWE-134: uncontrolled format string in printf"),
        ("unchecked_malloc", "#include <stdlib.h>\nint main(void) {\n    int *ptr = (int *)malloc(sizeof(int));\n    if (ptr == NULL) return 1;\n    *ptr = 10;\n    free(ptr);\n    return 0;\n}\n", "#include <stdlib.h>\nint main(void) {\n    int *ptr = (int *)malloc(sizeof(int));\n    *ptr = 10;\n    free(ptr);\n    return 0;\n}\n", "CWE-252: unchecked malloc return value before dereference"),
        ("use_after_free", "#include <stdlib.h>\nint main(void) {\n    int *p = (int *)malloc(sizeof(int));\n    if (!p) return 1;\n    *p = 42;\n    free(p);\n    p = NULL;\n    return 0;\n}\n", "#include <stdlib.h>\nint main(void) {\n    int *p = (int *)malloc(sizeof(int));\n    if (!p) return 1;\n    *p = 42;\n    free(p);\n    *p = 99;\n    return 0;\n}\n", "CWE-416: use-after-free pointer dereference"),
        ("double_free", "#include <stdlib.h>\nint main(void) {\n    void *p = malloc(16);\n    if (!p) return 1;\n    free(p);\n    p = NULL;\n    return 0;\n}\n", "#include <stdlib.h>\nint main(void) {\n    void *p = malloc(16);\n    if (!p) return 1;\n    free(p);\n    free(p);\n    return 0;\n}\n", "CWE-415: double free on dynamic memory buffer"),
        ("buffer_index_overflow", "int main(void) {\n    int arr[5] = {1, 2, 3, 4, 5};\n    int idx = 2;\n    if (idx < 5) arr[idx] = 10;\n    return arr[0];\n}\n", "int main(void) {\n    int arr[5] = {1, 2, 3, 4, 5};\n    arr[10] = 99;\n    return arr[0];\n}\n", "CWE-119: out of bounds array access arr[10]"),
        ("integer_overflow_alloc", "#include <stdlib.h>\nint main(void) {\n    size_t count = 100;\n    if (count > 1000) return 1;\n    int *buf = (int *)malloc(count * sizeof(int));\n    if (buf) free(buf);\n    return 0;\n}\n", "#include <stdlib.h>\nint main(void) {\n    int count = 100;\n    int *buf = (int *)malloc(count * sizeof(int));\n    if (buf) free(buf);\n    return 0;\n}\n", "CWE-190: unchecked integer multiplication in size calculation"),
        ("command_injection_system", "#include <stdlib.h>\n#include <stdio.h>\nint main(void) {\n    system(\"echo SafeListing\");\n    return 0;\n}\n", "#include <stdlib.h>\n#include <stdio.h>\nint main(void) {\n    char cmd[128];\n    sprintf(cmd, \"echo %s\", \"input\");\n    system(cmd);\n    return 0;\n}\n", "CWE-78: command injection via constructed shell string"),
        ("hardcoded_credential_password", "#include <stdlib.h>\n#include <stdio.h>\nint main(void) {\n    const char *pwd = getenv(\"APP_PASS\");\n    if (pwd) puts(\"Logged in\");\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    const char *pwd = \"EXAMPLE_NOT_A_REAL_KEY_0001\";\n    if (pwd) puts(\"Logged in\");\n    return 0;\n}\n", "CWE-798: hardcoded secret key credential"),
        ("sql_injection_sprintf", "#include <stdio.h>\nint main(void) {\n    char query[128] = \"SELECT * FROM users WHERE id = ?\";\n    puts(query);\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    char query[128];\n    sprintf(query, \"SELECT * FROM users WHERE name = '%s'\", \"admin\");\n    puts(query);\n    return 0;\n}\n", "CWE-89: SQL query constructed via raw string formatting"),
        ("weak_random_number", "#include <stdlib.h>\nint main(void) {\n    int r = 0;\n    return r;\n}\n", "#include <stdlib.h>\nint main(void) {\n    int secret_token = rand() % 10000;\n    return secret_token;\n}\n", "CWE-338: use of cryptographically weak PRNG rand() for token"),
        ("temp_file_race_tmpnam", "#include <stdio.h>\nint main(void) {\n    FILE *f = fopen(\"safe_temp.txt\", \"w\");\n    if (f) { fputs(\"data\", f); fclose(f); }\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    char buf[L_tmpnam];\n    tmpnam(buf);\n    return 0;\n}\n", "CWE-377: insecure temporary file creation using tmpnam()"),
        ("unchecked_fopen_return", "#include <stdio.h>\nint main(void) {\n    FILE *f = fopen(\"log.txt\", \"r\");\n    if (f == NULL) return 1;\n    fclose(f);\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    FILE *f = fopen(\"log.txt\", \"r\");\n    fclose(f);\n    return 0;\n}\n", "CWE-252: unchecked return value from fopen before fclose"),
        ("off_by_one_null_term", "int main(void) {\n    char buf[10];\n    buf[9] = '\\0';\n    return 0;\n}\n", "int main(void) {\n    char buf[10];\n    buf[10] = '\\0';\n    return 0;\n}\n", "CWE-193: off-by-one error assigning null terminator at buf[10]"),
        ("unbounded_sscanf", "#include <stdio.h>\nint main(void) {\n    const char *in = \"alice 100\";\n    char name[32];\n    int val = 0;\n    if (sscanf(in, \"%31s %d\", name, &val) == 2) puts(name);\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    const char *in = \"alice 100\";\n    char name[32];\n    int val = 0;\n    sscanf(in, \"%s %d\", name, &val);\n    return 0;\n}\n", "CWE-120: unbounded %s in sscanf call"),
        ("hardcoded_api_token", "#include <stdlib.h>\n#include <stdio.h>\nint main(void) {\n    const char *tok = getenv(\"API_TOKEN\");\n    if (tok) puts(\"Token loaded\");\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    const char *tok = \"EXAMPLE_NOT_A_REAL_KEY_0002\";\n    if (tok) puts(\"Token loaded\");\n    return 0;\n}\n", "CWE-798: hardcoded API token credential"),
        ("hardcoded_db_conn", "#include <stdlib.h>\n#include <stdio.h>\nint main(void) {\n    const char *cs = getenv(\"DB_URI\");\n    if (cs) puts(\"Connected\");\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    const char *cs = \"Server=sql.internal;User Id=dbuser;Password=EXAMPLE_NOT_A_REAL_KEY_0003;\";\n    if (cs) puts(\"Connected\");\n    return 0;\n}\n", "CWE-798: hardcoded connection string with password"),
        ("unchecked_write_return", "#include <stdio.h>\nint main(void) {\n    FILE *f = fopen(\"out.txt\", \"w\");\n    if (!f) return 1;\n    if (fputs(\"hello\\n\", f) == EOF) { fclose(f); return 1; }\n    fclose(f);\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    FILE *f = fopen(\"out.txt\", \"w\");\n    if (!f) return 1;\n    fputs(\"hello\\n\", f);\n    fclose(f);\n    return 0;\n}\n", "CWE-252: unchecked return value on fputs"),
        ("unsafe_temp_mktemp", "#include <stdlib.h>\n#include <stdio.h>\nint main(void) {\n    return 0;\n}\n", "#include <stdlib.h>\n#include <stdio.h>\nint main(void) {\n    char templ[] = \"/tmp/testXXXXXX\";\n    mktemp(templ);\n    return 0;\n}\n", "CWE-377: use of obsolete and insecure mktemp function"),
        ("unvalidated_loop_bound_copy", "#include <string.h>\nint main(void) {\n    char src[20] = \"hello\";\n    char dst[10];\n    size_t len = strlen(src);\n    if (len >= sizeof(dst)) len = sizeof(dst) - 1;\n    for (size_t i = 0; i < len; i++) dst[i] = src[i];\n    dst[len] = '\\0';\n    return 0;\n}\n", "#include <string.h>\nint main(void) {\n    char src[20] = \"hello\";\n    char dst[10];\n    for (size_t i = 0; i < strlen(src); i++) dst[i] = src[i];\n    return 0;\n}\n", "CWE-120: loop copy without destination length bound check"),
        ("stack_buffer_overread", "#include <stdio.h>\nint main(void) {\n    char buf[10] = \"abcdef\";\n    for (int i = 0; i < 6; i++) {\n        putchar(buf[i]);\n    }\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    char buf[10] = \"abcdef\";\n    for (int i = 0; i < 50; i++) {\n        putchar(buf[i]);\n    }\n    return 0;\n}\n", "CWE-125: out-of-bounds read past end of stack buffer"),
        ("unchecked_realloc", "#include <stdlib.h>\nint main(void) {\n    int *p = (int *)malloc(10 * sizeof(int));\n    if (!p) return 1;\n    int *tmp = (int *)realloc(p, 20 * sizeof(int));\n    if (tmp) p = tmp;\n    free(p);\n    return 0;\n}\n", "#include <stdlib.h>\nint main(void) {\n    int *p = (int *)malloc(10 * sizeof(int));\n    if (!p) return 1;\n    p = (int *)realloc(p, 20 * sizeof(int));\n    free(p);\n    return 0;\n}\n", "CWE-401: memory leak on realloc failure if ptr overwritten"),
        ("signed_int_overflow_calc", "int main(void) {\n    int x = 100;\n    int y = 200;\n    int z = x + y;\n    return z;\n}\n", "int main(void) {\n    int max = 2147483647;\n    int z = max + 1;\n    return z;\n}\n", "CWE-190: intentional signed integer overflow at compile time"),
        ("pointer_arithmetic_overflow", "#include <stdlib.h>\nint main(void) {\n    int arr[10];\n    int *p = arr + 5;\n    return (p != NULL);\n}\n", "#include <stdlib.h>\nint main(void) {\n    int arr[10];\n    int *p = arr + 500;\n    return (p != NULL);\n}\n", "CWE-119: pointer arithmetic way beyond array allocation"),
        ("hardcoded_private_key", "#include <stdlib.h>\n#include <stdio.h>\nint main(void) {\n    const char *key = getenv(\"PRIV_KEY\");\n    if (key) puts(\"Key present\");\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    const char *key = \"-----BEGIN PRIVATE KEY-----\\nEXAMPLE_NOT_A_REAL_KEY_0004\\n-----END PRIVATE KEY-----\";\n    if (key) puts(\"Key present\");\n    return 0;\n}\n", "CWE-798: embedded private key block"),
        ("unbounded_vsnprintf", "#include <stdio.h>\n#include <stdarg.h>\nvoid log_msg(const char *fmt, ...) {\n    char buf[128];\n    va_list ap;\n    va_start(ap, fmt);\n    vsnprintf(buf, sizeof(buf), fmt, ap);\n    va_end(ap);\n    puts(buf);\n}\nint main(void) {\n    log_msg(\"Hello %d\", 123);\n    return 0;\n}\n", "#include <stdio.h>\n#include <stdarg.h>\nvoid log_msg(const char *fmt, ...) {\n    char buf[128];\n    va_list ap;\n    va_start(ap, fmt);\n    vsprintf(buf, fmt, ap);\n    va_end(ap);\n    puts(buf);\n}\nint main(void) {\n    log_msg(\"Hello %d\", 123);\n    return 0;\n}\n", "CWE-120: unsafe vsprintf with unbounded destination"),
        ("unrestricted_file_permission", "#include <stdio.h>\nint main(void) {\n    FILE *f = fopen(\"secure.dat\", \"w\");\n    if (f) { fputs(\"data\", f); fclose(f); }\n    return 0;\n}\n", "#include <fcntl.h>\n#include <unistd.h>\nint main(void) {\n    int fd = open(\"secure.dat\", O_CREAT | O_WRONLY, 0777);\n    if (fd >= 0) close(fd);\n    return 0;\n}\n", "CWE-732: file created with 0777 overly permissive permissions"),
        ("free_non_heap_pointer", "#include <stdlib.h>\nint main(void) {\n    int *p = (int *)malloc(sizeof(int));\n    if (p) free(p);\n    return 0;\n}\n", "#include <stdlib.h>\nint main(void) {\n    int a = 10;\n    int *p = &a;\n    free(p);\n    return 0;\n}\n", "CWE-590: free of pointer not pointing to heap memory"),
        ("missing_boundary_check_strncat", "#include <string.h>\nint main(void) {\n    char dest[20] = \"prefix_\";\n    char src[] = \"longer_than_dest_buffer\";\n    strncat(dest, src, sizeof(dest) - strlen(dest) - 1);\n    return 0;\n}\n", "#include <string.h>\nint main(void) {\n    char dest[20] = \"prefix_\";\n    char src[] = \"longer_than_dest_buffer\";\n    strncat(dest, src, sizeof(dest));\n    return 0;\n}\n", "CWE-120: strncat with n=sizeof(dest) exceeding remaining buffer"),
        ("scanf_missing_ampersand", "#include <stdio.h>\nint main(void) {\n    int val = 0;\n    if (scanf(\"%d\", &val) == 1) printf(\"%d\\n\", val);\n    return 0;\n}\n", "#include <stdio.h>\nint main(void) {\n    int val = 0;\n    scanf(\"%d\", val);\n    return 0;\n}\n", "CWE-119: scanf passing integer directly instead of pointer &val"),
        ("unsafe_memcpy_unbounded", "#include <string.h>\nint main(void) {\n    char src[20] = \"1234567890123456789\";\n    char dst[10];\n    memcpy(dst, src, sizeof(dst));\n    return 0;\n}\n", "#include <string.h>\nint main(void) {\n    char src[20] = \"1234567890123456789\";\n    char dst[10];\n    memcpy(dst, src, sizeof(src));\n    return 0;\n}\n", "CWE-120: memcpy copying 20 bytes into 10-byte destination buffer"),
    ]

    for idx, (subcat, base, mut, desc) in enumerate(c_sec_specs, start=1):
        cases.append(CorpusCase(
            case_id=f"c_sec_{idx:03d}",
            language="c",
            category="security",
            subcat=subcat,
            expected_class="security-issue",
            valid_base=base,
            mutated_code=mut,
            mutation_desc=desc,
        ))

    # --- 1.4 C STRUCTURE, SIZE & FORMATTING (~35) ---
    # Helper to generate N-line C program
    def gen_c_prog(num_lines: int, inject_err: bool = False) -> Tuple[str, str]:
        lines_base = ["#include <stdio.h>", ""]
        lines_mut = ["#include <stdio.h>", ""]
        fn_count = max(1, (num_lines - 10) // 10)
        for i in range(fn_count):
            lines_base.append(f"int compute_step_{i}(int x) {{")
            lines_base.append(f"    int temp = x + {i};")
            lines_base.append("    int res = temp * 2;")
            lines_base.append("    return res;")
            lines_base.append("}")
            lines_base.append("")

            lines_mut.append(f"int compute_step_{i}(int x) {{")
            lines_mut.append(f"    int temp = x + {i};")
            if inject_err and i == fn_count // 2:
                lines_mut.append("    int res = temp * 2")  # Missing semicolon
            else:
                lines_mut.append("    int res = temp * 2;")
            lines_mut.append("    return res;")
            lines_mut.append("}")
            lines_mut.append("")

        lines_base.append("int main(void) {")
        lines_base.append("    int total = 0;")
        for i in range(min(5, fn_count)):
            lines_base.append(f"    total += compute_step_{i}({i});")
        lines_base.append("    return total;")
        lines_base.append("}")

        lines_mut.append("int main(void) {")
        lines_mut.append("    int total = 0;")
        for i in range(min(5, fn_count)):
            lines_mut.append(f"    total += compute_step_{i}({i});")
        lines_mut.append("    return total;")
        lines_mut.append("}")

        return "\n".join(lines_base) + "\n", "\n".join(lines_mut) + "\n"

    c_struct_specs = [
        ("struct_nested", "struct Point { int x; int y; };\nstruct Rect { struct Point tl; struct Point br; };\nint main(void) {\n    struct Rect r = {{0, 0}, {10, 10}};\n    return r.br.x;\n}\n", "struct Point { int x; int y; };\nstruct Rect { struct Point tl; struct Point br; };\nint main(void) {\n    struct Rect r = {{0, 0}, {10, 10}}\n    return r.br.x;\n}\n", "broken", "nested structs missing semicolon"),
        ("union_demo", "union Data { int i; float f; };\nint main(void) {\n    union Data d;\n    d.i = 42;\n    return d.i;\n}\n", "union Data { int i; float f; };\nint main(void) {\n    union Data d;\n    d.i = 42\n    return d.i;\n}\n", "broken", "union access missing semicolon"),
        ("enum_typedef", "typedef enum { RED = 1, GREEN = 2, BLUE = 3 } Color;\nint main(void) {\n    Color c = GREEN;\n    return (int)c;\n}\n", "typedef enum { RED = 1, GREEN = 2, BLUE = 3 } Color\nint main(void) {\n    Color c = GREEN;\n    return (int)c;\n}\n", "broken", "typedef enum missing semicolon"),
        ("function_pointer", "int add(int a, int b) { return a + b; }\nint main(void) {\n    int (*fn)(int, int) = add;\n    return fn(2, 3);\n}\n", "int add(int a, int b) { return a + b; }\nint main(void) {\n    int (*fn)(int, int) = add\n    return fn(2, 3);\n}\n", "broken", "function pointer assignment missing semicolon"),
        ("const_volatile_qualifiers", "int main(void) {\n    const volatile int sensor = 100;\n    int val = sensor;\n    return val;\n}\n", "int main(void) {\n    const volatile int sensor = 100\n    int val = sensor;\n    return val;\n}\n", "broken", "const volatile variable missing semicolon"),
        ("static_func_and_var", "static int counter(void) {\n    static int count = 0;\n    return ++count;\n}\nint main(void) {\n    return counter();\n}\n", "static int counter(void) {\n    static int count = 0\n    return ++count;\n}\nint main(void) {\n    return counter();\n}\n", "broken", "static local var missing semicolon"),
        ("preprocessor_macros", "#define SQUARE(x) ((x) * (x))\n#define ADD(a, b) ((a) + (b))\nint main(void) {\n    int r = SQUARE(4) + ADD(2, 3);\n    return r;\n}\n", "#define SQUARE(x) ((x) * (x))\n#define ADD(a, b) ((a) + (b))\nint main(void) {\n    int r = SQUARE(4) + ADD(2, 3)\n    return r;\n}\n", "broken", "macro expansion expression missing semicolon"),
        ("nested_loops_switch", "int main(void) {\n    int sum = 0;\n    for (int i = 0; i < 3; i++) {\n        for (int j = 0; j < 3; j++) {\n            switch (i + j) {\n                case 0: sum += 1; break;\n                case 2: sum += 2; break;\n                default: sum += 3; break;\n            }\n        }\n    }\n    return sum;\n}\n", "int main(void) {\n    int sum = 0;\n    for (int i = 0; i < 3; i++) {\n        for (int j = 0; j < 3; j++) {\n            switch (i + j) {\n                case 0: sum += 1; break\n                case 2: sum += 2; break;\n                default: sum += 3; break;\n            }\n        }\n    }\n    return sum;\n}\n", "broken", "nested loops & switch case break missing semicolon"),
        ("recursion_fibonacci", "int fib(int n) {\n    if (n <= 1) return n;\n    return fib(n - 1) + fib(n - 2);\n}\nint main(void) {\n    return fib(6);\n}\n", "int fib(int n) {\n    if (n <= 1) return n;\n    return fib(n - 1) + fib(n - 2)\n}\nint main(void) {\n    return fib(6);\n}\n", "broken", "recursive function return missing semicolon"),
        ("crlf_line_endings", "int main(void) {\r\n    int val = 42;\r\n    return val;\r\n}\r\n", "int main(void) {\r\n    int val = 42\r\n    return val;\r\n}\r\n", "broken", "CRLF line endings with missing semicolon"),
        ("tab_indentation", "int main(void) {\n\tint a = 10;\n\tint b = 20;\n\treturn a + b;\n}\n", "int main(void) {\n\tint a = 10\n\tint b = 20;\n\treturn a + b;\n}\n", "broken", "tab-indented code missing semicolon"),
        ("no_trailing_newline", "int main(void) {\n    int status = 0;\n    return status;\n}", "int main(void) {\n    int status = 0\n    return status;\n}", "broken", "no trailing newline missing semicolon"),
        ("very_long_line", "int main(void) {\n    int very_long_variable_name_for_testing_length_limits_and_diagnostics_buffer_allocation_alpha = 10, very_long_variable_name_for_testing_length_limits_and_diagnostics_buffer_allocation_beta = 20;\n    return very_long_variable_name_for_testing_length_limits_and_diagnostics_buffer_allocation_alpha + very_long_variable_name_for_testing_length_limits_and_diagnostics_buffer_allocation_beta;\n}\n", "int main(void) {\n    int very_long_variable_name_for_testing_length_limits_and_diagnostics_buffer_allocation_alpha = 10, very_long_variable_name_for_testing_length_limits_and_diagnostics_buffer_allocation_beta = 20\n    return very_long_variable_name_for_testing_length_limits_and_diagnostics_buffer_allocation_alpha + very_long_variable_name_for_testing_length_limits_and_diagnostics_buffer_allocation_beta;\n}\n", "broken", "line > 200 chars missing semicolon"),
        ("unicode_in_comments", "// UTF-8 comments: ★ 🚀 Résumé ñ å\nint main(void) {\n    int code = 100;\n    return code;\n}\n", "// UTF-8 comments: ★ 🚀 Résumé ñ å\nint main(void) {\n    int code = 100\n    return code;\n}\n", "broken", "unicode characters in header comment with syntax defect"),
        ("empty_file", "", "", "clean", "completely empty C source file"),
        ("only_comments", "/* Header comment */\n// Secondary comment\n/* Block comment describing nothing */\n", "/* Header comment */\n// Secondary comment\n/* Block comment describing nothing */\n", "clean", "source file containing only comments"),
    ]

    # Add size tiers (~5, ~50, ~200, ~500, ~1000 lines)
    size_tiers = [
        ("size_5_lines", 5, True, "broken"),
        ("size_5_lines_clean", 5, False, "clean"),
        ("size_50_lines", 50, True, "broken"),
        ("size_50_lines_clean", 50, False, "clean"),
        ("size_200_lines", 200, True, "broken"),
        ("size_200_lines_clean", 200, False, "clean"),
        ("size_500_lines", 500, True, "broken"),
        ("size_500_lines_clean", 500, False, "clean"),
        ("size_1000_lines", 1000, True, "broken"),
        ("size_1000_lines_clean", 1000, False, "clean"),
    ]

    for name, lines, inject, exp_cls in size_tiers:
        b, m = gen_c_prog(lines, inject)
        c_struct_specs.append((name, b, m, exp_cls, f"{lines}-line C program ({exp_cls})"))

    # Also add some structural varieties
    more_struct_specs = [
        ("typedef_func_pointer", "typedef int (*OpFunc)(int, int);\nint do_op(int a, int b, OpFunc f) { return f(a, b); }\nint sub(int a, int b) { return a - b; }\nint main(void) { return do_op(10, 4, sub); }\n", "typedef int (*OpFunc)(int, int);\nint do_op(int a, int b, OpFunc f) { return f(a, b); }\nint sub(int a, int b) { return a - b; }\nint main(void) { return do_op(10, 4, sub) }\n", "broken", "typedef func pointer return missing semicolon"),
        ("macro_multiline", "#define SWAP(a, b) do { \\\n    int _tmp = (a); \\\n    (a) = (b); \\\n    (b) = _tmp; \\\n} while(0)\nint main(void) {\n    int x = 1, y = 2;\n    SWAP(x, y);\n    return x;\n}\n", "#define SWAP(a, b) do { \\\n    int _tmp = (a); \\\n    (a) = (b); \\\n    (b) = _tmp; \\\n} while(0)\nint main(void) {\n    int x = 1, y = 2\n    SWAP(x, y);\n    return x;\n}\n", "broken", "multi-line macro call missing semicolon"),
        ("deep_nested_ifs", "int test_depth(int a, int b, int c, int d, int e) {\n    if (a) if (b) if (c) if (d) if (e) return 1;\n    return 0;\n}\nint main(void) { return test_depth(1,1,1,1,1); }\n", "int test_depth(int a, int b, int c, int d, int e) {\n    if (a) if (b) if (c) if (d) if (e) return 1\n    return 0;\n}\nint main(void) { return test_depth(1,1,1,1,1); }\n", "broken", "5-level nested if statement missing semicolon"),
        ("goto_label_statement", "int main(void) {\n    int x = 0;\n    goto end;\n    x = 10;\nend:\n    return x;\n}\n", "int main(void) {\n    int x = 0;\n    goto end\n    x = 10;\nend:\n    return x;\n}\n", "broken", "goto statement missing semicolon"),
        ("ternary_operator_assign", "int main(void) {\n    int a = 5;\n    int b = (a > 0) ? 10 : 20;\n    return b;\n}\n", "int main(void) {\n    int a = 5;\n    int b = (a > 0) ? 10 : 20\n    return b;\n}\n", "broken", "ternary operator assign missing semicolon"),
        ("multiple_declarations_comma", "int main(void) {\n    int a = 1, b = 2, c = 3, d = 4;\n    return a + b + c + d;\n}\n", "int main(void) {\n    int a = 1, b = 2, c = 3, d = 4\n    return a + b + c + d;\n}\n", "broken", "multi-variable single declaration missing semicolon"),
        ("anonymous_struct", "struct { int id; const char *name; } item = {10, \"test\"};\nint main(void) {\n    return item.id;\n}\n", "struct { int id; const char *name; } item = {10, \"test\"}\nint main(void) {\n    return item.id;\n}\n", "broken", "anonymous struct instance missing semicolon"),
        ("complex_initializers", "int main(void) {\n    int matrix[2][2] = {{1, 2}, {3, 4}};\n    int sum = matrix[0][0] + matrix[1][1];\n    return sum;\n}\n", "int main(void) {\n    int matrix[2][2] = {{1, 2}, {3, 4}};\n    int sum = matrix[0][0] + matrix[1][1]\n    return sum;\n}\n", "broken", "2D matrix calculation missing semicolon"),
        ("enum_bitmasks", "enum Flags { F_READ = 1 << 0, F_WRITE = 1 << 1, F_EXEC = 1 << 2 };\nint main(void) {\n    int mask = F_READ | F_WRITE;\n    return mask;\n}\n", "enum Flags { F_READ = 1 << 0, F_WRITE = 1 << 1, F_EXEC = 1 << 2 };\nint main(void) {\n    int mask = F_READ | F_WRITE\n    return mask;\n}\n", "broken", "enum bitmask expression missing semicolon"),
    ]
    c_struct_specs.extend(more_struct_specs)

    for idx, (subcat, base, mut, exp_cls, desc) in enumerate(c_struct_specs, start=1):
        cases.append(CorpusCase(
            case_id=f"c_str_{idx:03d}",
            language="c",
            category="structure",
            subcat=subcat,
            expected_class=exp_cls,
            valid_base=base,
            mutated_code=mut,
            mutation_desc=desc,
        ))

    # =========================================================================
    # 2. PYTHON CASES (~110)
    # =========================================================================

    # --- 2.1 PYTHON SYNTAX (~40) ---
    py_syntax_specs = [
        ("missing_colon_def", "def add(a, b):\n    return a + b\n\nres = add(1, 2)\n", "def add(a, b)\n    return a + b\n\nres = add(1, 2)\n", "missing colon after def"),
        ("missing_colon_if", "x = 10\nif x > 5:\n    status = 'high'\n", "x = 10\nif x > 5\n    status = 'high'\n", "missing colon after if"),
        ("missing_colon_else", "x = 3\nif x > 5:\n    val = 1\nelse:\n    val = 0\n", "x = 3\nif x > 5:\n    val = 1\nelse\n    val = 0\n", "missing colon after else"),
        ("missing_colon_elif", "x = 2\nif x == 1:\n    a = 10\nelif x == 2:\n    a = 20\n", "x = 2\nif x == 1:\n    a = 10\nelif x == 2\n    a = 20\n", "missing colon after elif"),
        ("missing_colon_for", "total = 0\nfor i in range(5):\n    total += i\n", "total = 0\nfor i in range(5)\n    total += i\n", "missing colon after for"),
        ("missing_colon_while", "n = 5\nwhile n > 0:\n    n -= 1\n", "n = 5\nwhile n > 0\n    n -= 1\n", "missing colon after while"),
        ("missing_colon_class", "class Service:\n    def run(self):\n        return True\n", "class Service\n    def run(self):\n        return True\n", "missing colon after class"),
        ("missing_colon_with", "import io\nwith io.StringIO() as f:\n    f.write('data')\n", "import io\nwith io.StringIO() as f\n    f.write('data')\n", "missing colon after with"),
        ("missing_colon_try", "try:\n    x = 1 / 1\nexcept ZeroDivisionError:\n    x = 0\n", "try\n    x = 1 / 1\nexcept ZeroDivisionError:\n    x = 0\n", "missing colon after try"),
        ("missing_colon_except", "try:\n    x = 1 / 1\nexcept ZeroDivisionError:\n    x = 0\n", "try:\n    x = 1 / 1\nexcept ZeroDivisionError\n    x = 0\n", "missing colon after except"),
        ("missing_colon_finally", "try:\n    x = 10\nfinally:\n    x = 0\n", "try:\n    x = 10\nfinally\n    x = 0\n", "missing colon after finally"),
        ("indent_unexpected", "def compute():\n    a = 1\n    b = 2\n    return a + b\n", "def compute():\n    a = 1\n      b = 2\n    return a + b\n", "unexpected indentation increase"),
        ("indent_unindent_mismatch", "def evaluate(val):\n    if val > 0:\n        x = 1\n    else:\n        x = -1\n    return x\n", "def evaluate(val):\n    if val > 0:\n        x = 1\n    else:\n        x = -1\n   return x\n", "unindent does not match any outer indentation level"),
        ("indent_mixed_tabs_spaces", "def process():\n    step1 = 10\n    step2 = 20\n    return step1 + step2\n", "def process():\n\tstep1 = 10\n    step2 = 20\n    return step1 + step2\n", "inconsistent use of tabs and spaces in indentation"),
        ("missing_indent_def_body", "def empty_func():\n    pass\n", "def empty_func():\n", "expected an indented block after function def"),
        ("missing_indent_if_body", "x = 1\nif x == 1:\n    pass\n", "x = 1\nif x == 1:\n", "expected an indented block after if"),
        ("unclosed_bracket_call", "def square(x):\n    return x * x\n\nval = square(10)\n", "def square(x):\n    return x * x\n\nval = square(10\n", "unclosed '(' in function call"),
        ("unclosed_bracket_list", "items = [1, 2, 3, 4]\n", "items = [1, 2, 3, 4\n", "unclosed '[' in list literal"),
        ("unclosed_bracket_dict", "config = {'host': 'localhost', 'port': 8080}\n", "config = {'host': 'localhost', 'port': 8080\n", "unclosed '{' in dict literal"),
        ("unclosed_bracket_tuple", "coords = (10, 20)\n", "coords = (10, 20\n", "unclosed '(' in tuple literal"),
        ("unclosed_quote_single", "message = 'hello world'\n", "message = 'hello world\n", "unterminated string literal (single quote)"),
        ("unclosed_quote_double", "greeting = \"welcome home\"\n", "greeting = \"welcome home\n", "unterminated string literal (double quote)"),
        ("unclosed_triple_quote", "doc = '''multi\nline\nstring'''\n", "doc = '''multi\nline\nstring\n", "unterminated triple-quoted string"),
        ("unclosed_fstring_brace", "name = 'Ada'\ntext = f'User: {name}'\n", "name = 'Ada'\ntext = f'User: {name'\n", "f-string: expecting '}' in expression"),
        ("break_outside_loop", "for i in range(5):\n    if i == 2:\n        break\n", "x = 10\nbreak\n", "'break' outside loop"),
        ("continue_outside_loop", "for i in range(5):\n    if i == 2:\n        continue\n", "y = 20\ncontinue\n", "'continue' not properly in loop"),
        ("return_outside_func", "def get_val():\n    return 42\n", "x = 100\nreturn x\n", "'return' outside function"),
        ("stray_character_dollar", "value = 50\n", "value = $50\n", "invalid syntax: stray '$' character"),
        ("missing_comma_in_list", "nums = [1, 2, 3, 4]\n", "nums = [1 2, 3, 4]\n", "missing comma in list literal"),
        ("missing_comma_in_dict", "d = {'a': 1, 'b': 2}\n", "d = {'a': 1 'b': 2}\n", "missing comma in dict literal"),
        ("missing_comma_in_args", "def calc(a, b):\n    return a * b\n\nres = calc(3, 4)\n", "def calc(a, b):\n    return a * b\n\nres = calc(3 4)\n", "missing comma in call arguments"),
        ("bad_assignment_operator", "x = 10\n", "10 = x\n", "cannot assign to literal (SyntaxError)"),
        ("keyword_used_as_ident", "def run():\n    my_pass = True\n    return my_pass\n", "def run():\n    pass = True\n    return pass\n", "cannot assign to keyword 'pass'"),
        ("missing_operator_expr", "x = 10 + 20\n", "x = 10 20\n", "invalid syntax missing operator between literals"),
        ("multi_funcs_missing_colons", "def f1():\n    return 1\n\ndef f2():\n    return 2\n", "def f1()\n    return 1\n\ndef f2()\n    return 2\n", "missing colons across multiple functions"),
        ("multi_errors_same_func", "def parse(x):\n    if x > 0:\n        return x\n    return 0\n", "def parse(x)\n    if x > 0\n        return x\n    return 0\n", "multiple missing colons in single function"),
        ("missing_colon_lambda", "sq = lambda x: x * x\n", "sq = lambda x x * x\n", "missing colon in lambda expression"),
        ("extra_closing_paren", "x = (1 + 2)\n", "x = (1 + 2))\n", "unmatched ')' closing parenthesis"),
        ("extra_closing_bracket", "arr = [1, 2, 3]\n", "arr = [1, 2, 3]]\n", "unmatched ']' closing bracket"),
        ("extra_closing_brace", "d = {'key': 'val'}\n", "d = {'key': 'val'}}\n", "unmatched '}' closing brace"),
    ]

    for idx, (subcat, base, mut, desc) in enumerate(py_syntax_specs, start=1):
        cases.append(CorpusCase(
            case_id=f"py_syn_{idx:03d}",
            language="python",
            category="syntax",
            subcat=subcat,
            expected_class="broken",
            valid_base=base,
            mutated_code=mut,
            mutation_desc=desc,
        ))

    # --- 2.2 PYTHON SEMANTIC (~20) ---
    py_sem_specs = [
        ("undefined_name_var", "def calculate():\n    total = 100\n    return total\n", "def calculate():\n    return total_missing\n", "compiles-with-warnings", "name 'total_missing' is not defined"),
        ("undefined_name_call", "def helper():\n    return 1\ndef run():\n    return helper()\n", "def run():\n    return nonexistent_func()\n", "compiles-with-warnings", "calling undefined function"),
        ("shadowed_builtin_list", "def get_items():\n    my_list = [1, 2, 3]\n    return list(my_list)\n", "def get_items():\n    list = [1, 2, 3]\n    return list([4, 5])\n", "compiles-with-warnings", "shadowing built-in 'list' causing callable type error"),
        ("unreachable_code_after_return", "def compute(x):\n    return x * 2\n", "def compute(x):\n    return x * 2\n    y = x + 10\n", "compiles-with-warnings", "unreachable statement after return"),
        ("unused_import_module", "import math\n\ndef calc(r):\n    return math.pi * r * r\n", "import math\nimport os\n\ndef calc(r):\n    return math.pi * r * r\n", "compiles-with-warnings", "unused import 'os'"),
        ("wrong_args_too_many", "def greet(name):\n    return f'Hello {name}'\n\nmsg = greet('World')\n", "def greet(name):\n    return f'Hello {name}'\n\nmsg = greet('World', 'Extra')\n", "compiles-with-warnings", "greet() takes 1 positional argument but 2 were given"),
        ("wrong_args_too_few", "def multiply(a, b):\n    return a * b\n\nval = multiply(3, 4)\n", "def multiply(a, b):\n    return a * b\n\nval = multiply(3)\n", "compiles-with-warnings", "multiply() missing 1 required positional argument: 'b'"),
        ("unbound_local_var", "def counter():\n    c = 0\n    c += 1\n    return c\n", "c = 10\ndef counter():\n    c += 1\n    return c\n", "compiles-with-warnings", "local variable 'c' referenced before assignment"),
        ("none_comparison_equality", "def check(val):\n    return val is None\n", "def check(val):\n    return val == None\n", "compiles-with-warnings", "comparison to None should be 'if cond is None:'"),
        ("type_error_concat_str_int", "def format_id(n):\n    return 'ID_' + str(n)\n", "def format_id(n):\n    return 'ID_' + n\n", "compiles-with-warnings", "can only concatenate str (not 'int') to str"),
        ("duplicate_dict_key", "d = {'key': 1, 'other': 2}\n", "d = {'key': 1, 'key': 2}\n", "compiles-with-warnings", "duplicate dictionary key 'key'"),
        ("attribute_error_call", "s = 'hello'\nl = s.lower()\n", "s = 'hello'\nl = s.to_lower()\n", "compiles-with-warnings", "'str' object has no attribute 'to_lower'"),
        ("import_nonexistent_attr", "from math import sqrt\n", "from math import nonexistent_method\n", "compiles-with-warnings", "cannot import name 'nonexistent_method' from 'math'"),
        ("zero_division_literal", "def divide(a, b):\n    if b == 0: return 0\n    return a / b\n", "def divide(a):\n    return a / 0\n", "compiles-with-warnings", "division by zero literal"),
        ("assert_always_true_tuple", "def validate(x):\n    assert x > 0\n", "def validate(x):\n    assert (x > 0, 'error')\n", "compiles-with-warnings", "asserting non-empty tuple is always True"),
        ("mutable_default_arg", "def append_item(x, lst=None):\n    if lst is None: lst = []\n    lst.append(x)\n    return lst\n", "def append_item(x, lst=[]):\n    lst.append(x)\n    return lst\n", "compiles-with-warnings", "default argument value is mutable (list)"),
        ("unused_variable_func", "def process():\n    used = 10\n    return used\n", "def process():\n    used = 10\n    unused_var = 20\n    return used\n", "compiles-with-warnings", "local variable 'unused_var' is assigned to but never used"),
        ("pointless_statement_expr", "def run():\n    x = 10\n    return x\n", "def run():\n    x = 10\n    x + 1\n    return x\n", "compiles-with-warnings", "statement has no effect (x + 1)"),
        ("is_literal_comparison", "def is_ten(x):\n    return x == 10\n", "def is_ten(x):\n    return x is 10\n", "compiles-with-warnings", "'is' with a literal (did you mean '=='?)"),
        ("bare_except_clause", "try:\n    x = 1\nexcept Exception:\n    x = 0\n", "try:\n    x = 1\nexcept:\n    x = 0\n", "compiles-with-warnings", "bare 'except:' catches all exceptions including KeyboardInterrupt"),
    ]

    for idx, (subcat, base, mut, exp_cls, desc) in enumerate(py_sem_specs, start=1):
        cases.append(CorpusCase(
            case_id=f"py_sem_{idx:03d}",
            language="python",
            category="semantic",
            subcat=subcat,
            expected_class=exp_cls,
            valid_base=base,
            mutated_code=mut,
            mutation_desc=desc,
        ))

    # --- 2.3 PYTHON SECURITY (~30, vulnerable patterns only, fake dummy secrets, NO attack payloads) ---
    py_sec_specs = [
        ("unsafe_eval_call", "import ast\ndef run_calc(expr):\n    return ast.literal_eval(expr)\n", "def run_calc(expr):\n    return eval(expr)\n", "CWE-95: eval() on arbitrary input"),
        ("unsafe_exec_call", "def run_task(cmd):\n    if cmd == 'start':\n        return True\n    return False\n", "def run_task(code_str):\n    exec(code_str)\n", "CWE-95: exec() on untrusted code string"),
        ("shell_true_subprocess", "import subprocess\ndef ping_host(host):\n    return subprocess.run(['ping', '-c', '1', host], capture_output=True)\n", "import subprocess\ndef ping_host(host):\n    return subprocess.run(f'ping -c 1 {host}', shell=True, capture_output=True)\n", "CWE-78: subprocess with shell=True command injection"),
        ("insecure_pickle_load", "import json\ndef parse_data(raw):\n    return json.loads(raw)\n", "import pickle\ndef parse_data(raw):\n    return pickle.loads(raw)\n", "CWE-502: deserialization of untrusted data via pickle.loads"),
        ("unsafe_yaml_load", "import yaml\ndef load_config(s):\n    return yaml.safe_load(s)\n", "import yaml\ndef load_config(s):\n    return yaml.load(s, Loader=yaml.Loader)\n", "CWE-502: unsafe yaml.load without SafeLoader"),
        ("weak_hash_md5_pwd", "import hashlib\ndef hash_token(data):\n    return hashlib.sha256(data.encode()).hexdigest()\n", "import hashlib\ndef hash_password(pwd):\n    return hashlib.md5(pwd.encode()).hexdigest()\n", "CWE-328: use of weak cryptographic hash MD5 for password"),
        ("weak_hash_sha1", "import hashlib\ndef hash_token(data):\n    return hashlib.sha256(data.encode()).hexdigest()\n", "import hashlib\ndef hash_token(data):\n    return hashlib.sha1(data.encode()).hexdigest()\n", "CWE-328: use of deprecated hash SHA1"),
        ("sql_injection_fstring", "def fetch_user(cursor, username):\n    cursor.execute('SELECT * FROM users WHERE name = %s', (username,))\n", "def fetch_user(cursor, username):\n    cursor.execute(f'SELECT * FROM users WHERE name = \"{username}\"')\n", "CWE-89: SQL query constructed via f-string formatting"),
        ("insecure_temp_mktemp", "import tempfile\ndef create_temp():\n    return tempfile.NamedTemporaryFile(delete=False)\n", "import tempfile\ndef create_temp():\n    return tempfile.mktemp()\n", "CWE-377: insecure temp file creation with tempfile.mktemp()"),
        ("disabled_cert_verify_requests", "import requests\ndef fetch(url):\n    return requests.get(url, timeout=10, verify=True)\n", "import requests\ndef fetch(url):\n    return requests.get(url, timeout=10, verify=False)\n", "CWE-295: disabled SSL certificate verification in requests"),
        ("hardcoded_secret_token", "import os\ndef get_key():\n    return os.environ.get('API_KEY', '')\n", "def get_key():\n    return 'EXAMPLE_NOT_A_REAL_KEY_0001'\n", "CWE-798: hardcoded API token secret"),
        ("hardcoded_db_password", "import os\ndef get_db_pwd():\n    return os.environ.get('DB_PASS', '')\n", "def get_db_pwd():\n    return 'EXAMPLE_NOT_A_REAL_KEY_0002'\n", "CWE-798: hardcoded database password"),
        ("assert_used_for_auth", "def admin_action(user):\n    if not user.get('is_admin'):\n        raise PermissionError('Unauthorized')\n    return 'done'\n", "def admin_action(user):\n    assert user.get('is_admin'), 'Unauthorized'\n    return 'done'\n", "CWE-617: assert statement used for security/authorization check"),
        ("unverified_ssl_context", "import ssl\ndef get_ssl_ctx():\n    return ssl.create_default_context()\n", "import ssl\ndef get_ssl_ctx():\n    return ssl._create_unverified_context()\n", "CWE-295: unverified SSL context bypassing certificate checks"),
        ("weak_random_secrets", "import secrets\ndef make_token():\n    return secrets.token_hex(16)\n", "import random\ndef make_token():\n    return str(random.randint(100000, 999999))\n", "CWE-338: use of random module instead of secrets for token generation"),
        ("shell_true_popen", "import subprocess\ndef run_cmd(arg):\n    return subprocess.Popen(['ls', arg], stdout=subprocess.PIPE)\n", "import subprocess\ndef run_cmd(arg):\n    return subprocess.Popen(f'ls {arg}', shell=True, stdout=subprocess.PIPE)\n", "CWE-78: subprocess.Popen with shell=True command injection"),
        ("hardcoded_jwt_secret", "import os\ndef get_jwt_secret():\n    return os.environ.get('JWT_SECRET', '')\n", "def get_jwt_secret():\n    return 'EXAMPLE_NOT_A_REAL_KEY_0003'\n", "CWE-798: hardcoded JWT signing secret"),
        ("tarfile_unsafe_extract", "import tarfile\ndef extract_safe(tf, path):\n    # Extract with member filter\n    tf.extractall(path=path, filter='data')\n", "import tarfile\ndef extract_archive(tf, path):\n    tf.extractall(path=path)\n", "CWE-22: tarfile.extractall without path traversal prevention"),
        ("xml_entity_expansion", "import defusedxml.ElementTree as ET\ndef parse_xml(s):\n    return ET.fromstring(s)\n", "import xml.etree.ElementTree as ET\ndef parse_xml(s):\n    return ET.fromstring(s)\n", "CWE-611: standard xml.etree is vulnerable to XML entity expansion"),
        ("insecure_deserialization_shelve", "import json\ndef load_records(fp):\n    return json.load(fp)\n", "import shelve\ndef load_records(filename):\n    return shelve.open(filename)\n", "CWE-502: shelve module uses pickle under the hood"),
        ("hardcoded_aws_secret", "import os\ndef get_aws_keys():\n    return os.environ.get('AWS_SECRET_ACCESS_KEY', '')\n", "def get_aws_keys():\n    return 'EXAMPLE_NOT_A_REAL_KEY_0004'\n", "CWE-798: hardcoded AWS credentials"),
        ("flask_debug_true_production", "from flask import Flask\napp = Flask(__name__)\ndef start():\n    app.run(debug=False)\n", "from flask import Flask\napp = Flask(__name__)\ndef start():\n    app.run(debug=True)\n", "CWE-489: Flask running with debug=True in production code"),
        ("insecure_cipher_des", "from cryptography.hazmat.primitives.ciphers import algorithms\ndef get_algo():\n    return algorithms.AES(b'0' * 32)\n", "from cryptography.hazmat.primitives.ciphers import algorithms\ndef get_algo():\n    return algorithms.TripleDES(b'0' * 24)\n", "CWE-327: use of weak/broken encryption algorithm (TripleDES)"),
        ("open_redirect_url", "from urllib.parse import urlparse\ndef safe_redirect(target):\n    parsed = urlparse(target)\n    if parsed.netloc in ('example.com', ''):\n        return target\n    return '/'\n", "def redirect_user(target):\n    return target\n", "CWE-601: URL redirection to untrusted site without validation"),
        ("regex_dos_catastrophic", "import re\ndef check_pattern(s):\n    # Safe bounded regex\n    return re.match(r'^[a-z]{1,20}$', s)\n", "import re\ndef check_pattern(s):\n    # Catastrophic backtracking regex\n    return re.match(r'^(a+)+$', s)\n", "CWE-1333: exponential ReDoS pattern (a+)+"),
        ("sql_format_concatenation", "def query_by_id(cursor, user_id):\n    cursor.execute('SELECT * FROM accounts WHERE id = ?', (user_id,))\n", "def query_by_id(cursor, user_id):\n    cursor.execute('SELECT * FROM accounts WHERE id = ' + str(user_id))\n", "CWE-89: raw string concatenation in SQL execution"),
        ("hardcoded_private_rsa_key", "import os\ndef get_priv_key():\n    return os.environ.get('RSA_KEY', '')\n", "def get_priv_key():\n    return '-----BEGIN PRIVATE KEY-----\\nEXAMPLE_NOT_A_REAL_KEY_0005\\n-----END PRIVATE KEY-----'\n", "CWE-798: hardcoded RSA private key"),
        ("unsafe_chmod_world_writable", "import os\ndef make_file(p):\n    with open(p, 'w') as f: f.write('ok')\n    os.chmod(p, 0o600)\n", "import os\ndef make_file(p):\n    with open(p, 'w') as f: f.write('ok')\n    os.chmod(p, 0o777)\n", "CWE-732: file created with 0o777 world-writable permissions"),
        ("logging_sensitive_credential", "import logging\ndef authenticate(user, password):\n    logging.info('Login attempt for user: %s', user)\n    return True\n", "import logging\ndef authenticate(user, password):\n    logging.info('User: %s Password: %s', user, password)\n    return True\n", "CWE-532: logging sensitive authentication credentials in plain text"),
        ("insecure_ssl_protocol", "import ssl\ndef get_context():\n    return ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)\n", "import ssl\ndef get_context():\n    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)\n    ctx.options &= ~ssl.OP_NO_SSLv3\n    return ctx\n", "CWE-326: permitting obsolete SSLv3 protocol"),
    ]

    for idx, (subcat, base, mut, desc) in enumerate(py_sec_specs, start=1):
        cases.append(CorpusCase(
            case_id=f"py_sec_{idx:03d}",
            language="python",
            category="security",
            subcat=subcat,
            expected_class="security-issue",
            valid_base=base,
            mutated_code=mut,
            mutation_desc=desc,
        ))

    # --- 2.4 PYTHON STRUCTURE AND SIZE (~20) ---
    def gen_py_prog(num_lines: int, inject_err: bool = False) -> Tuple[str, str]:
        lines_base = ["# Python multi-line module", ""]
        lines_mut = ["# Python multi-line module", ""]
        fn_count = max(1, (num_lines - 10) // 8)
        for i in range(fn_count):
            lines_base.append(f"def process_block_{i}(val: int) -> int:")
            lines_base.append(f"    offset = {i}")
            lines_base.append("    result = (val + offset) * 2")
            lines_base.append("    return result")
            lines_base.append("")

            if inject_err and i == fn_count // 2:
                lines_mut.append(f"def process_block_{i}(val: int) -> int")  # Missing colon
            else:
                lines_mut.append(f"def process_block_{i}(val: int) -> int:")
            lines_mut.append(f"    offset = {i}")
            lines_mut.append("    result = (val + offset) * 2")
            lines_mut.append("    return result")
            lines_mut.append("")

        lines_base.append("def main():")
        lines_base.append("    total = 0")
        for i in range(min(5, fn_count)):
            lines_base.append(f"    total += process_block_{i}({i})")
        lines_base.append("    return total")
        lines_base.append("")
        lines_base.append("if __name__ == '__main__':")
        lines_base.append("    main()")

        lines_mut.append("def main():")
        lines_mut.append("    total = 0")
        for i in range(min(5, fn_count)):
            lines_mut.append(f"    total += process_block_{i}({i})")
        lines_mut.append("    return total")
        lines_mut.append("")
        lines_mut.append("if __name__ == '__main__':")
        lines_mut.append("    main()")

        return "\n".join(lines_base) + "\n", "\n".join(lines_mut) + "\n"

    py_struct_specs = [
        ("class_and_methods", "class MathHelper:\n    def __init__(self, factor: int):\n        self.factor = factor\n    def multiply(self, x: int) -> int:\n        return x * self.factor\n", "class MathHelper:\n    def __init__(self, factor: int):\n        self.factor = factor\n    def multiply(self, x: int) -> int\n        return x * self.factor\n", "broken", "method declaration missing colon"),
        ("decorator_usage", "def repeat(fn):\n    def wrapper(*args, **kwargs):\n        return fn(*args, **kwargs)\n    return wrapper\n\n@repeat\ndef do_action():\n    return 'ok'\n", "def repeat(fn):\n    def wrapper(*args, **kwargs):\n        return fn(*args, **kwargs)\n    return wrapper\n\n@repeat\ndef do_action()\n    return 'ok'\n", "broken", "decorated function missing colon"),
        ("list_comprehensions", "squares = [x * x for x in range(10) if x % 2 == 0]\n", "squares = [x * x for x in range(10 if x % 2 == 0]\n", "broken", "unclosed parenthesis in comprehension"),
        ("generator_expression", "def count_up(limit):\n    for i in range(limit):\n        yield i\n", "def count_up(limit)\n    for i in range(limit):\n        yield i\n", "broken", "generator function missing colon"),
        ("async_await_funcs", "import asyncio\nasync def fetch_data():\n    await asyncio.sleep(0.01)\n    return {'status': 'done'}\n", "import asyncio\nasync def fetch_data()\n    await asyncio.sleep(0.01)\n    return {'status': 'done'}\n", "broken", "async def missing colon"),
        ("dataclass_definition", "from dataclasses import dataclass\n@dataclass\nclass Config:\n    host: str\n    port: int\n", "from dataclasses import dataclass\n@dataclass\nclass Config\n    host: str\n    port: int\n", "broken", "dataclass declaration missing colon"),
        ("type_hints_annotations", "from typing import List, Dict, Optional\ndef summarize(items: List[int]) -> Optional[int]:\n    if not items: return None\n    return sum(items)\n", "from typing import List, Dict, Optional\ndef summarize(items: List[int]) -> Optional[int]\n    if not items: return None\n    return sum(items)\n", "broken", "annotated function def missing colon"),
        ("match_case_statements", "def inspect(val):\n    match val:\n        case 1:\n            return 'one'\n        case _:\n            return 'other'\n", "def inspect(val):\n    match val\n        case 1:\n            return 'one'\n        case _:\n            return 'other'\n", "broken", "match statement missing colon"),
        ("walrus_operator", "data = [1, 2, 3, 4, 5]\nif (n := len(data)) > 3:\n    total = n * 10\n", "data = [1, 2, 3, 4, 5]\nif (n := len(data) > 3:\n    total = n * 10\n", "broken", "unclosed parenthesis around walrus assignment"),
        ("crlf_endings_py", "def check():\r\n    return True\r\n", "def check()\r\n    return True\r\n", "broken", "Python with CRLF line endings missing colon"),
        ("tabs_indentation_py", "def check():\n\tval = 10\n\treturn val\n", "def check()\n\tval = 10\n\treturn val\n", "broken", "Python tab indented missing colon"),
        ("unicode_identifiers_comments", "# Unicode comments: ⚡ 🚀 π ≈ 3.14159\ndef compute():\n    return 42\n", "# Unicode comments: ⚡ 🚀 π ≈ 3.14159\ndef compute()\n    return 42\n", "broken", "Python with unicode comment missing colon"),
        ("empty_file_py", "", "", "clean", "completely empty Python file"),
    ]

    # Add size tiers (~5, ~50, ~200, ~500 lines)
    py_size_tiers = [
        ("size_5_lines_py", 5, True, "broken"),
        ("size_5_lines_clean_py", 5, False, "clean"),
        ("size_50_lines_py", 50, True, "broken"),
        ("size_50_lines_clean_py", 50, False, "clean"),
        ("size_200_lines_py", 200, True, "broken"),
        ("size_200_lines_clean_py", 200, False, "clean"),
        ("size_500_lines_py", 500, True, "broken"),
        ("size_500_lines_clean_py", 500, False, "clean"),
    ]

    for name, lines, inject, exp_cls in py_size_tiers:
        b, m = gen_py_prog(lines, inject)
        py_struct_specs.append((name, b, m, exp_cls, f"{lines}-line Python program ({exp_cls})"))

    for idx, (subcat, base, mut, exp_cls, desc) in enumerate(py_struct_specs, start=1):
        cases.append(CorpusCase(
            case_id=f"py_str_{idx:03d}",
            language="python",
            category="structure",
            subcat=subcat,
            expected_class=exp_cls,
            valid_base=base,
            mutated_code=mut,
            mutation_desc=desc,
        ))

    # =========================================================================
    # 3. CROSS-CUTTING CASES (~60)
    # =========================================================================

    cross_specs: List[Tuple[str, str, str, str, str, str]] = []

    # --- 3.1 Regression Cases for bugs seen before (15) ---
    cross_specs.extend([
        ("reg_rename_variable_guard", "c", "int main(void) {\n    int threshold_limit = 100;\n    int current_val = 50;\n    if (current_val < threshold_limit) {\n        return 0;\n    }\n    return 1;\n}\n", "int main(void) {\n    int threshold_limit = 100\n    int current_val = 50;\n    if (current_val < threshold_limit) {\n        return 0;\n    }\n    return 1;\n}\n", "broken", "rule must not rename threshold_limit variable while fixing ;"),
        ("reg_comma_after_if_keyword", "c", "int main(void) {\n    int x = 10;\n    if (x > 0) {\n        return x;\n    }\n    return 0;\n}\n", "int main(void) {\n    int x = 10;\n    if (x > 0) {\n        return x\n    }\n    return 0;\n}\n", "broken", "rule must never insert comma after if/for/while/return"),
        ("reg_semicolon_at_end_of_line", "c", "int main(void) {\n    int a = 1;\n    int b = 2;\n    return a + b;\n}\n", "int main(void) {\n    int a = 1\n    int b = 2;\n    return a + b;\n}\n", "broken", "; must be placed at end of line 2, not beginning of line 3"),
        ("reg_same_error_10_funcs", "c", "\n".join([f"int fn_{i}(void) {{ return {i}; }}" for i in range(10)]) + "\nint main(void) { return 0; }\n", "\n".join([f"int fn_{i}(void) {{ return {i} }}" for i in range(10)]) + "\nint main(void) { return 0; }\n", "broken", "same missing ';' error repeated across 10 functions"),
        ("reg_high_error_count_dense", "c", "int main(void) {\n" + "\n".join([f"    int v_{i} = {i};" for i in range(25)]) + "\n    return 0;\n}\n", "int main(void) {\n" + "\n".join([f"    int v_{i} = {i}" for i in range(25)]) + "\n    return 0;\n}\n", "broken", "dense 25-line missing semicolon block"),
        ("reg_py_indent_normalize", "python", "def check(x):\n    if x > 0:\n        return 'pos'\n    else:\n        return 'zero_or_neg'\n", "def check(x):\nif x > 0:\n    return 'pos'\n    else:\n        return 'zero_or_neg'\n", "broken", "indentation error: unindented block after def"),
        ("reg_py_no_delete_statements", "python", "def calc(a, b):\n    step1 = a * 2\n    step2 = b * 3\n    return step1 + step2\n", "def calc(a, b):\n    step1 = a * 2\n    step2 = b * 3\n    return step1 + step2\n", "clean", "clean python must never delete statements"),
        ("reg_c_clean_preserves_macros", "c", "#define MAX(a, b) ((a) > (b) ? (a) : (b))\nint main(void) {\n    int m = MAX(10, 20);\n    return m;\n}\n", "#define MAX(a, b) ((a) > (b) ? (a) : (b))\nint main(void) {\n    int m = MAX(10, 20);\n    return m;\n}\n", "clean", "clean C with macros must be 100% byte-identical"),
        ("reg_c_for_comma_no_insert", "c", "int main(void) {\n    for (int i = 0; i < 10; i++) {\n        int x = i;\n        (void)x;\n    }\n    return 0;\n}\n", "int main(void) {\n    for (int i = 0; i < 10; i++) {\n        int x = i\n        (void)x;\n    }\n    return 0;\n}\n", "broken", "missing semicolon inside loop body without touching for()"),
        ("reg_py_def_colon_at_end", "python", "def compute_value(x, y):\n    return x + y\n", "def compute_value(x, y)\n    return x + y\n", "broken", "colon must go strictly at the end of def line"),
        ("reg_c_switch_case_break", "c", "int main(void) {\n    int code = 2;\n    switch (code) {\n        case 1: return 10;\n        case 2: return 20;\n        default: return 0;\n    }\n}\n", "int main(void) {\n    int code = 2;\n    switch (code) {\n        case 1: return 10;\n        case 2: return 20\n        default: return 0;\n    }\n}\n", "broken", "missing semicolon on return inside switch case"),
        ("reg_py_elif_colon_at_end", "python", "val = 15\nif val < 10:\n    res = 'small'\nelif val < 20:\n    res = 'medium'\nelse:\n    res = 'large'\n", "val = 15\nif val < 10:\n    res = 'small'\nelif val < 20\n    res = 'medium'\nelse:\n    res = 'large'\n", "broken", "colon must go strictly at end of elif line"),
        ("reg_c_return_expression_paren", "c", "int main(void) {\n    int a = 5;\n    int b = 6;\n    return (a * b) + 2;\n}\n", "int main(void) {\n    int a = 5;\n    int b = 6;\n    return (a * b) + 2\n}\n", "broken", "missing semicolon after parenthesized return expression"),
        ("reg_c_struct_ptr_deref", "c", "struct Node { int val; struct Node *next; };\nint main(void) {\n    struct Node n = {42, 0};\n    struct Node *p = &n;\n    return p->val;\n}\n", "struct Node { int val; struct Node *next; };\nint main(void) {\n    struct Node n = {42, 0};\n    struct Node *p = &n;\n    return p->val\n}\n", "broken", "missing semicolon after arrow operator expression"),
        ("reg_py_try_except_clause", "python", "def safe_int(s):\n    try:\n        return int(s)\n    except ValueError:\n        return 0\n", "def safe_int(s):\n    try\n        return int(s)\n    except ValueError:\n        return 0\n", "broken", "missing colon after try statement"),
    ])

    # --- 3.2 Existing Agent-Security Fixtures (15) ---
    agent_sec_files = [
        ("c", "c_api_key.c", "security-issue", "C API key redaction"),
        ("c", "c_comment_secret.c", "clean", "C secret in benign comment"),
        ("c", "c_conn_str.c", "security-issue", "C DB connection string"),
        ("c", "c_neg_ctrl_var.c", "clean", "C negative control variable"),
        ("c", "c_password.c", "security-issue", "C hardcoded password"),
        ("c", "c_private_key.c", "security-issue", "C private key PEM"),
        ("c", "c_prompt_injection.c", "clean", "C prompt injection in comment benign"),
        ("c", "c_syntax_err_secret.c", "broken", "C syntax error with secret"),
        ("python", "py_api_key.py", "security-issue", "Py API key secret"),
        ("python", "py_comment_secret.py", "clean", "Py comment secret benign"),
        ("python", "py_conn_str.py", "security-issue", "Py connection string"),
        ("python", "py_neg_ctrl_var.py", "clean", "Py negative control variable"),
        ("python", "py_password.py", "security-issue", "Py hardcoded password"),
        ("python", "py_prompt_injection.py", "clean", "Py prompt injection in comment"),
        ("python", "py_syntax_err_secret.py", "broken", "Py syntax error with secret"),
    ]

    for lang, fname, exp_cls, desc in agent_sec_files:
        p = PROJECT_ROOT / "examples" / "agent_security" / fname
        if p.exists():
            code = p.read_text(encoding="utf-8", errors="replace")
            cross_specs.append((f"agent_sec_{Path(fname).stem}", lang, code, code, exp_cls, desc))

    # --- 3.3 Already-Clean Programs of Every Size (10) ---
    clean_specs = [
        ("clean_c_tiny", "c", "int main(void) { return 0; }\n"),
        ("clean_py_tiny", "python", "x = 0\n"),
        ("clean_c_medium", "c", "#include <stdio.h>\nint compute(int x) { return x * 2; }\nint main(void) {\n    int a = 10;\n    int b = compute(a);\n    return b == 20 ? 0 : 1;\n}\n"),
        ("clean_py_medium", "python", "def compute(x: int) -> int:\n    return x * 2\n\nif __name__ == '__main__':\n    res = compute(10)\n"),
        ("clean_c_large", "c", gen_c_prog(100, False)[0]),
        ("clean_py_large", "python", gen_py_prog(100, False)[0]),
        ("clean_c_xlarge", "c", gen_c_prog(250, False)[0]),
        ("clean_py_xlarge", "python", gen_py_prog(250, False)[0]),
        ("clean_c_xxlarge", "c", gen_c_prog(400, False)[0]),
        ("clean_py_xxlarge", "python", gen_py_prog(400, False)[0]),
    ]
    for name, lang, code in clean_specs:
        cross_specs.append((name, lang, code, code, "clean", f"Already-clean {lang} program"))

    # --- 3.4 Warnings-only programs (6) ---
    cross_specs.extend([
        ("warn_c_missing_include", "c", "#include <stdio.h>\nint main(void) { puts(\"hi\"); return 0; }\n", "int main(void) { puts(\"hi\"); return 0; }\n", "compiles-with-warnings", "missing #include <stdio.h> warning"),
        ("warn_c_unused_var", "c", "int main(void) { int a = 1; return a; }\n", "int main(void) { int a = 1; int b = 2; return a; }\n", "compiles-with-warnings", "unused variable 'b' warning"),
        ("warn_c_format_specifier", "c", "#include <stdio.h>\nint main(void) { int x = 5; printf(\"%d\\n\", x); return 0; }\n", "#include <stdio.h>\nint main(void) { int x = 5; printf(\"%s\\n\", x); return 0; }\n", "compiles-with-warnings", "format specifier mismatch warning"),
        ("warn_py_unused_import", "python", "import math\ndef get_pi(): return math.pi\n", "import math\nimport sys\ndef get_pi(): return math.pi\n", "compiles-with-warnings", "unused import sys warning"),
        ("warn_py_none_equality", "python", "def is_none(v): return v is None\n", "def is_none(v): return v == None\n", "compiles-with-warnings", "comparison to None warning"),
        ("warn_py_unreachable", "python", "def f(): return 1\n", "def f(): return 1\n    x = 2\n", "compiles-with-warnings", "unreachable code after return warning"),
    ])

    # --- 3.5 Metric variety (6) ---
    cross_specs.extend([
        ("metric_c_1line", "c", "int main(void){return 0;}", "int main(void){return 0;}", "clean", "1-line tiny C program"),
        ("metric_py_1line", "python", "pass", "pass", "clean", "1-line tiny Python program"),
        ("metric_c_deeply_nested", "c", "int main(void) {\n    int x = 0;\n    if (1) if (1) if (1) if (1) if (1) if (1) if (1) if (1) x = 1;\n    return x;\n}\n", "int main(void) {\n    int x = 0;\n    if (1) if (1) if (1) if (1) if (1) if (1) if (1) if (1) x = 1;\n    return x;\n}\n", "clean", "deeply nested if structures"),
        ("metric_c_no_functions", "c", "int g_val = 100;\nconst char *g_banner = \"Active\";\n", "int g_val = 100;\nconst char *g_banner = \"Active\";\n", "clean", "file with globals/macros and no functions"),
        ("metric_py_only_comments", "python", "# Line 1 comment\n# Line 2 comment\n# Line 3 comment\n", "# Line 1 comment\n# Line 2 comment\n# Line 3 comment\n", "clean", "Python file with only comments"),
        ("metric_c_uncompilable", "c", "int main(void) {\n    return 0;\n}\n", "int main(void) {\n    %!@#$ invalid tokens\n    return 0;\n}\n", "broken", "uncompilable code showing estimated metrics"),
    ])

    # --- 3.6 API negatives (5) ---
    cross_specs.extend([
        ("api_neg_malformed_json", "c", "int main(void) { return 0; }\n", "int main(void) { return 0; }\n", "clean", "API negative: test with malformed payload"),
        ("api_neg_empty_body", "c", "int main(void) { return 0; }\n", "int main(void) { return 0; }\n", "clean", "API negative: test with empty request body"),
        ("api_neg_oversize_body", "c", "int main(void) { return 0; }\n", "int main(void) { return 0; }\n", "clean", "API negative: test with oversized body"),
        ("api_neg_wrong_language", "c", "int main(void) { return 0; }\n", "int main(void) { return 0; }\n", "clean", "API negative: mismatched language parameter"),
        ("api_neg_cancelled_job", "c", "int main(void) { return 0; }\n", "int main(void) { return 0; }\n", "clean", "API negative: job cancellation workflow"),
    ])

    # --- 3.7 UI flows (5) ---
    cross_specs.extend([
        ("ui_flow_approval_accept", "c", "#include <stdlib.h>\nint main(void) { const char *k = getenv(\"KEY\"); return (k != 0); }\n", "#include <stdio.h>\nint main(void) { const char *k = \"EXAMPLE_NOT_A_REAL_KEY_0009\"; return (k != 0); }\n", "security-issue", "UI flow: security gate modal approved"),
        ("ui_flow_approval_decline", "c", "#include <stdio.h>\nint main(void) { const char *k = \"EXAMPLE_NOT_A_REAL_KEY_0010\"; return 0; }\n", "#include <stdio.h>\nint main(void) { const char *k = \"EXAMPLE_NOT_A_REAL_KEY_0010\"; return 0; }\n", "security-issue", "UI flow: security gate modal cancelled"),
        ("ui_flow_apply_patch", "c", "int main(void) { return 0; }\n", "int main(void) { return 0\n}\n", "broken", "UI flow: apply patch verification"),
        ("ui_flow_reject_patch", "c", "int main(void) { return 0; }\n", "int main(void) { return 0\n}\n", "broken", "UI flow: reject patch verification"),
        ("ui_flow_results_close_reopen", "c", "int main(void) { return 0; }\n", "int main(void) { return 0; }\n", "clean", "UI flow: results screen close with Esc and reopen"),
    ])

    for idx, (subcat, lang, base, mut, exp_cls, desc) in enumerate(cross_specs, start=1):
        cases.append(CorpusCase(
            case_id=f"cross_{idx:03d}",
            language=lang,
            category="cross_cutting",
            subcat=subcat,
            expected_class=exp_cls,
            valid_base=base,
            mutated_code=mut,
            mutation_desc=desc,
        ))

    return cases


def validate_case_oracle(case: CorpusCase) -> Tuple[bool, str]:
    """Validate independently that base program compiles and mutant matches expected class."""
    # 1. Base validation
    if case.valid_base.strip():
        if case.language == "c":
            rc, out, err = compile_c_code(case.valid_base)
            if rc != 0:
                return False, f"Valid base failed C compilation (rc={rc}): {err[:150]}"
        else:
            rc, out, err = compile_py_code(case.valid_base)
            if rc != 0:
                return False, f"Valid base failed Python compilation (rc={rc}): {err[:150]}"

    # 2. Mutant behavior check
    if case.expected_class == "clean":
        if case.mutated_code.strip():
            if case.language == "c":
                rc, out, err = compile_c_code(case.mutated_code)
                if rc != 0:
                    return False, f"Clean mutant failed C compilation: {err[:150]}"
            else:
                rc, out, err = compile_py_code(case.mutated_code)
                if rc != 0:
                    return False, f"Clean mutant failed Python compilation: {err[:150]}"
    elif case.expected_class == "broken":
        if case.language == "c":
            rc, out, err = compile_c_code(case.mutated_code)
            if rc == 0:
                return False, "Broken C mutant compiled without errors (expected failure)"
        else:
            rc, out, err = compile_py_code(case.mutated_code)
            if rc == 0:
                return False, "Broken Python mutant compiled without errors (expected failure)"

    return True, "OK"


def write_corpus(cases: List[CorpusCase]) -> Dict[str, Any]:
    """Write all corpus files, oracles, and manifest.csv."""
    os.makedirs(CORPUS_DIR, exist_ok=True)
    os.makedirs(ORACLES_DIR, exist_ok=True)

    manifest_rows = []
    counts_by_cat: Dict[str, int] = {}
    counts_by_class: Dict[str, int] = {}
    counts_by_split: Dict[str, int] = {}

    for c in cases:
        # Write mutant source
        file_path = CORPUS_DIR / c.filename
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(c.mutated_code)

        # Write oracle
        oracle_path = ORACLES_DIR / c.oracle_name
        with open(oracle_path, "w", encoding="utf-8", newline="") as f:
            f.write(c.valid_base)

        rel_oracle_path = f"tests/corpus/oracles/{c.oracle_name}"
        manifest_rows.append({
            "id": c.id,
            "language": c.language,
            "category": c.category,
            "subcat": c.subcat,
            "lines": c.lines,
            "mutation": c.mutation_desc,
            "expected_class": c.expected_class,
            "oracle_path": rel_oracle_path,
            "split": c.split,
        })

        counts_by_cat[c.category] = counts_by_cat.get(c.category, 0) + 1
        counts_by_class[c.expected_class] = counts_by_class.get(c.expected_class, 0) + 1
        counts_by_split[c.split] = counts_by_split.get(c.split, 0) + 1

    # Write manifest.csv
    fieldnames = ["id", "language", "category", "subcat", "lines", "mutation", "expected_class", "oracle_path", "split"]
    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    return {
        "total": len(cases),
        "by_category": counts_by_cat,
        "by_class": counts_by_class,
        "by_split": counts_by_split,
        "manifest": str(MANIFEST_PATH),
    }


def main():
    print(f"=== Antigravity Deterministic Corpus Generator (Seed: {SEED}) ===")
    cases = generate_all_cases()
    print(f"Generated {len(cases)} case candidates.")

    # Validate oracles and mutants
    print("\n--- Validating Oracles & Expected Classes (Step 2) ---")
    valid_cases: List[CorpusCase] = []
    dropped: List[Tuple[str, str]] = []

    for c in cases:
        ok, msg = validate_case_oracle(c)
        if ok:
            valid_cases.append(c)
        else:
            dropped.append((c.id, msg))

    if dropped:
        print(f"WARNING: Dropped {len(dropped)} cases that did not behave as labelled:")
        for cid, reason in dropped[:10]:
            print(f"  - {cid}: {reason}")
    else:
        print(f"All {len(valid_cases)} cases validated independently!")

    res = write_corpus(valid_cases)
    print("\n=== Corpus Generation Complete ===")
    print(f"Total Cases Written: {res['total']}")
    print(f"By Category: {res['by_category']}")
    print(f"By Expected Class: {res['by_class']}")
    print(f"By Split: {res['by_split']} (dev: {res['by_split'].get('dev', 0) / res['total'] * 100:.1f}%, held_out: {res['by_split'].get('held_out', 0) / res['total'] * 100:.1f}%)")
    print(f"Manifest: {res['manifest']}")


if __name__ == "__main__":
    main()
