"""Tests for SecurityAutoFixer v2.  Run:  python -m unittest tests.security.test_security_autofix -v
(also collected by pytest).  No model / ANTLR needed."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from compiler.security_auto_fixer import SecurityAutoFixer, _split_lines, _code_mask, _function_spans

KEYWORDS_AND_LIBC = {
    "int", "char", "void", "return", "if", "else", "while", "for", "sizeof", "stdin",
    "fgets", "gets", "scanf", "printf", "snprintf", "sprintf", "strcpy", "strcat",
    "strncat", "strlen", "main", "NULL", "unsigned", "long", "short", "float", "double",
}


def fix(src):
    return SecurityAutoFixer().apply_fixes(src)


def idents(src):
    src = re.sub(r'"(?:\\.|[^"\\])*"', '""', src)
    return set(re.findall(r"[A-Za-z_]\w*", src))


class TestGets(unittest.TestCase):
    def test_gets_local_array(self):   # mixed_errors_1.c shape
        r = fix("int main() {\n    int a = 5;\n    char buf[100];\n    gets(buf);\n    return a;\n}\n")
        self.assertIn("fgets(buf, sizeof(buf), stdin);", r.source)
        self.assertNotIn("str", idents(r.source))

    def test_gets_global_array(self):
        r = fix("char g[16];\nint main() {\n    gets(g);\n    return 0;\n}\n")
        self.assertIn("fgets(g, sizeof(g), stdin)", r.source)

    def test_gets_macro_size(self):
        r = fix("#define N 32\nint main() {\n    char b[N];\n    gets(b);\n    return 0;\n}\n")
        self.assertIn("fgets(b, sizeof(b), stdin)", r.source)

    def test_gets_pointer_param_not_fixed_but_suggested(self):
        src = "void f(char *p) {\n    gets(p);\n}\n"
        r = fix(src)
        self.assertEqual(r.source, src)
        self.assertTrue(r.suggestions)

    def test_gets_array_param_not_fixed(self):   # char p[] decays to pointer
        src = "void f(char p[100]) {\n    gets(p);\n}\n"
        self.assertEqual(fix(src).source, src)

    def test_gets_pointer_local_not_fixed(self):
        src = "int main() {\n    char *p;\n    gets(p);\n    return 0;\n}\n"
        self.assertEqual(fix(src).source, src)

    def test_gets_undeclared_not_fixed(self):
        src = "int main() {\n    gets(zzz);\n    return 0;\n}\n"
        self.assertEqual(fix(src).source, src)


class TestScanf(unittest.TestCase):
    def test_width_is_size_minus_one(self):
        r = fix('int main() {\n    char name[32];\n    scanf("%s", name);\n    return 0;\n}\n')
        self.assertIn('scanf("%31s", name);', r.source)

    def test_width_not_hardcoded_99(self):
        r = fix('int main() {\n    char cmd[50];\n    scanf("%s", cmd);\n    return 0;\n}\n')
        self.assertIn('"%49s"', r.source)
        self.assertNotIn("%99s", r.source)

    def test_never_uses_other_functions_variable(self):   # the arr / %11s bug
        src = ("int sum(int arr[], int n) {\n    return arr[0] + n;\n}\n\n"
               "int vuln() {\n    char cmd[100];\n    scanf(\"%s\", cmd);\n    return 0;\n}\n")
        r = fix(src)
        self.assertIn('scanf("%99s", cmd);', r.source)
        self.assertNotIn("%11s", r.source)

    def test_scanf_pointer_not_fixed(self):
        src = 'void f(char *p) {\n    scanf("%s", p);\n}\n'
        self.assertEqual(fix(src).source, src)

    def test_scanf_already_bounded_untouched(self):
        src = 'int main() {\n    char b[8];\n    scanf("%7s", b);\n    return 0;\n}\n'
        self.assertEqual(fix(src).source, src)


class TestCopyFormat(unittest.TestCase):
    def test_strcpy(self):
        r = fix('int main() {\n    char d[10];\n    char s[20] = "x";\n    strcpy(d, s);\n    return 0;\n}\n')
        self.assertIn('snprintf(d, sizeof(d), "%s", s);', r.source)

    def test_strcpy_does_not_invent_a(self):   # snprintf(a, sizeof(a), "%s", a) bug
        src = ("int add(int a, int b) {\n    return a + b;\n}\n\n"
               "int f() {\n    char buf[8];\n    char src[16] = \"hi\";\n    strcpy(buf, src);\n    return 0;\n}\n")
        out = fix(src).source
        self.assertIn('snprintf(buf, sizeof(buf), "%s", src);', out)
        self.assertNotIn("snprintf(a", out)

    def test_strcpy_pointer_dst_not_fixed(self):
        src = "void f(char *d, char *s) {\n    strcpy(d, s);\n}\n"
        self.assertEqual(fix(src).source, src)

    def test_strcat(self):
        r = fix('int main() {\n    char d[20];\n    char s[5] = "a";\n    strcat(d, s);\n    return 0;\n}\n')
        self.assertIn("strncat(d, s, sizeof(d) - strlen(d) - 1);", r.source)

    def test_sprintf(self):
        r = fix('int main() {\n    char b[16];\n    sprintf(b, "%d", 5);\n    return 0;\n}\n')
        self.assertIn('snprintf(b, sizeof(b), "%d", 5);', r.source)

    def test_printf_var(self):
        r = fix("int main() {\n    char u[8];\n    printf(u);\n    return 0;\n}\n")
        self.assertIn('printf("%s", u);', r.source)

    def test_printf_literal_untouched(self):
        src = 'int main() {\n    printf("hello\\n");\n    return 0;\n}\n'
        self.assertEqual(fix(src).source, src)


class TestRobustness(unittest.TestCase):
    def test_comments_and_strings_untouched(self):
        src = ('int main() {\n    char b[8];\n    // gets(b);\n'
               '    /* strcpy(b, b); */\n    printf("gets(b)\\n");\n    return 0;\n}\n')
        self.assertEqual(fix(src).source, src)

    def test_crlf_preserved(self):
        src = "int main() {\r\n    char b[8];\r\n    gets(b);\r\n    return 0;\r\n}\r\n"
        out = fix(src).source
        self.assertIn("fgets(b, sizeof(b), stdin);\r\n", out)
        self.assertNotIn("\n", out.replace("\r\n", ""))

    def test_no_trailing_newline_preserved(self):
        src = "int main() {\n    char b[8];\n    gets(b);\n}"
        self.assertFalse(fix(src).source.endswith("\n"))

    def test_idempotent(self):
        src = ('int main() {\n    char b[16];\n    char c[16];\n    gets(b);\n    strcpy(c, b);\n'
               '    strcat(c, b);\n    sprintf(b, "%s", c);\n    scanf("%s", c);\n    printf(b);\n    return 0;\n}\n')
        once = fix(src).source
        self.assertEqual(fix(once).source, once)

    def test_shadowing_uses_nearest_declaration(self):
        src = ("char b[4];\nint f() {\n    char b[64];\n    scanf(\"%s\", b);\n    return 0;\n}\n")
        self.assertIn('"%63s"', fix(src).source)

    def test_other_function_array_not_visible(self):
        src = ("int f() {\n    char only_here[32];\n    return 0;\n}\n"
               "int g() {\n    gets(only_here);\n    return 0;\n}\n")
        self.assertEqual(fix(src).source, src)

    def test_no_new_identifiers_on_realistic_file(self):
        src = ("int helper_sum_array(int arr[], int n) {\n    int s = 0;\n    return s + arr[0] + n;\n}\n\n"
               "int vuln_system_1() {\n    char cmd[100];\n    gets(cmd);\n    return 0;\n}\n\n"
               "int vuln_mixed() {\n    char buf[32];\n    char src[64] = \"x\";\n    strcpy(buf, src);\n    return 0;\n}\n")
        before, after = idents(src), idents(fix(src).source)
        self.assertEqual(after - before - KEYWORDS_AND_LIBC, set())

    def test_system_taint_never_autofixed(self):   # mixed_errors_2.c
        src = 'int main() {\n    char cmd[50];\n    system(cmd);\n}\n'
        self.assertEqual(fix(src).source, src)

    def test_empty_source(self):
        self.assertEqual(fix("").source, "")


class TestAiValidator(unittest.TestCase):
    """Model output is never trusted; these are the exact bad outputs seen."""
    def setUp(self):
        self.f = SecurityAutoFixer()
        self.src = ("int sum(int arr[], int n) {\n    return arr[0];\n}\n\n"
                    "int vuln() {\n    char cmd[12];\n    scanf(\"%s\", cmd);\n    return 0;\n}\n")
        self.lines, _ = _split_lines(self.src)
        self.mask = _code_mask(self.lines)
        self.spans = _function_spans(self.lines, self.mask)
        self.idx = 6

    def check(self, new):
        return self.f._validate_ai_line(self.lines[self.idx], new, self.lines, self.mask, self.spans, self.idx)

    def test_rejects_hallucinated_arr(self):
        self.assertFalse(self.check('    scanf("%11s", arr);'))

    def test_rejects_wrong_width(self):
        self.assertFalse(self.check('    scanf("%5s", cmd);'))

    def test_accepts_correct_line(self):
        self.assertTrue(self.check('    scanf("%11s", cmd);'))

    def test_window_contains_only_enclosing_function(self):
        span = next(s for s in self.spans if s.open_idx <= self.idx <= s.end_idx)
        window, rel = self.f._build_window(self.lines, span, self.idx)
        self.assertNotIn("arr", window)
        self.assertEqual(window.splitlines()[rel - 1].strip(), 'scanf("%s", cmd);')

    def test_ai_off_by_default_never_loads_model(self):
        f = SecurityAutoFixer()
        f.apply_fixes(self.src)
        self.assertFalse(f._model_load_attempted)


class TestCorruptionRepair(unittest.TestCase):
    """The old fixer produced scanf("%11s", arr) where arr belongs to another
    function.  The repair pre-pass should fix these when the function has
    exactly one char[] local."""

    def test_unique_char_array_substituted(self):
        src = ("int helper(int arr[], int n) {\n    return arr[0];\n}\n\n"
               "int vuln() {\n    char cmd[100];\n    scanf(\"%11s\", arr);\n    return 0;\n}\n")
        r = fix(src)
        self.assertIn('scanf("%99s", cmd)', r.source)
        self.assertNotIn("arr", r.source.split("int vuln")[1])  # no arr in vuln()

    def test_already_correct_buffer_untouched(self):
        src = "int f() {\n    char buf[32];\n    scanf(\"%31s\", buf);\n    return 0;\n}\n"
        r = fix(src)
        self.assertEqual(r.source, src)

    def test_multiple_char_arrays_suggested_not_fixed(self):
        src = ("int f() {\n    char a[10];\n    char b[20];\n"
               "    scanf(\"%11s\", arr);\n    return 0;\n}\n")
        r = fix(src)
        self.assertIn("arr", r.source)  # not auto-fixed
        self.assertTrue(any("multiple" in s.lower() for s in r.suggestions))

    def test_no_char_array_suggested(self):
        src = "int f() {\n    int x = 5;\n    scanf(\"%11s\", arr);\n    return 0;\n}\n"
        r = fix(src)
        self.assertIn("arr", r.source)  # not auto-fixed
        self.assertTrue(any("no char[]" in s.lower() for s in r.suggestions))

    def test_idempotent_after_repair(self):
        src = ("int helper(int arr[], int n) {\n    return arr[0];\n}\n\n"
               "int vuln() {\n    char cmd[100];\n    scanf(\"%11s\", arr);\n    return 0;\n}\n")
        once = fix(src).source
        self.assertEqual(fix(once).source, once)

    def test_snprintf_corrupted_self_copy_repaired(self):
        # ademo3mix.c shape: syntax20() has int a; sec1() only has char buf[32];
        src = ("int syntax20() {\n"
               "    int a = 0;\n"
               "    return a;\n"
               "}\n"
               "int sec1() {\n"
               "    char buf[32];\n"
               "    snprintf(a, sizeof(a), \"%s\", a);\n"
               "    return 0;\n"
               "}\n")
        r = fix(src)
        self.assertIn('snprintf(buf, sizeof(buf), "%s", buf);', r.source)
        self.assertNotIn('snprintf(a', r.source)
        self.assertNotIn('sizeof(a)', r.source)

    def test_fgets_corrupted_str_in_sizeof_repaired(self):
        src = ("int main() {\n"
               "    char buf[64];\n"
               "    fgets(str, sizeof(str), stdin);\n"
               "    return 0;\n"
               "}\n")
        r = fix(src)
        self.assertIn("fgets(buf, sizeof(buf), stdin);", r.source)
        self.assertNotIn("str", r.source)


class TestSystemSuggestion(unittest.TestCase):
    def test_system_variable_suggested(self):
        src = "int main() {\n    char cmd[50];\n    system(cmd);\n    return 0;\n}\n"
        r = fix(src)
        self.assertEqual(r.source, src)  # not auto-fixed
        self.assertTrue(any("TAINTED_SYSTEM" in s for s in r.suggestions))

    def test_system_literal_not_suggested(self):
        # system("ls") with a string literal won't match our variable pattern
        src = 'int main() {\n    system("ls");\n    return 0;\n}\n'
        r = fix(src)
        self.assertFalse(any("TAINTED" in s for s in r.suggestions))

    def test_popen_suggested(self):
        src = "int f() {\n    char cmd[100];\n    popen(cmd);\n    return 0;\n}\n"
        r = fix(src)
        self.assertTrue(any("TAINTED_POPEN" in s for s in r.suggestions))


    def test_unique_char_array_substituted_gets(self):
        src = ("int helper(int arr[], int n) {\n    return arr[0];\n}\n\n"
               "int vuln() {\n    char cmd[100];\n    gets(arr);\n    return 0;\n}\n")
        r = fix(src)
        self.assertIn("cmd", r.source)
        self.assertNotIn("arr", r.source.split("int vuln")[1])

    def test_unique_char_array_substituted_strcpy(self):
        src = ("int helper(int arr[], int n) {\n    return arr[0];\n}\n\n"
               "int vuln() {\n    char cmd[100];\n    strcpy(arr, \"test\");\n    return 0;\n}\n")
        r = fix(src)
        self.assertNotIn("arr", r.source.split("int vuln")[1])
        self.assertIn("cmd", r.source)


class TestSemanticUndeclaredBufferRule(unittest.TestCase):
    """Semantic repair rule for undeclared buffer arguments."""

    def test_two_char_arrays_suggested(self):
        from compiler.semantic_auto_fixer import fix_semantic_issue
        src = ("int main() {\n"
               "    char a[10];\n"
               "    char b[20];\n"
               "    gets(unknown_buf);\n"
               "    return 0;\n"
               "}\n")
        issue = {"kind": "undeclared", "name": "unknown_buf", "line": 4, "col": 10}
        new_src, msg = fix_semantic_issue(src, issue)
        self.assertEqual(new_src, src)
        self.assertIsNone(msg)
        self.assertIn("suggestion", issue)
        self.assertIn("multiple", issue["suggestion"])

    def test_typo_wins_over_buffer_fallback(self):
        from compiler.semantic_auto_fixer import fix_semantic_issue
        src = ("int main() {\n"
               "    char buffer[32];\n"
               "    gets(buffr);\n"
               "    return 0;\n"
               "}\n")
        issue = {"kind": "undeclared", "name": "buffr", "line": 3, "col": 10}
        new_src, msg = fix_semantic_issue(src, issue)
        self.assertIn("gets(buffer);", new_src)
        self.assertIn("typo", msg.lower())

    def test_single_char_array_replaced(self):
        from compiler.semantic_auto_fixer import fix_semantic_issue
        src = ("int main() {\n"
               "    char local_buf[64];\n"
               "    gets(unknown_buf);\n"
               "    return 0;\n"
               "}\n")
        issue = {"kind": "undeclared", "name": "unknown_buf", "line": 3, "col": 10}
        new_src, msg = fix_semantic_issue(src, issue)
        self.assertIn("gets(local_buf);", new_src)
        self.assertIn("replaced undeclared buffer", msg)

    def test_snprintf_undeclared_repaired_all_occurrences(self):
        from compiler.semantic_auto_fixer import fix_semantic_issue
        src = ("int sec1() {\n"
               "    char buf[32];\n"
               "    snprintf(a, sizeof(a), \"%s\", a);\n"
               "    return 0;\n"
               "}\n")
        issue = {"kind": "undeclared", "name": "a", "line": 3, "col": 13}
        new_src, msg = fix_semantic_issue(src, issue)
        self.assertIn('snprintf(buf, sizeof(buf), "%s", buf);', new_src)
        self.assertIn("replaced undeclared buffer 'a' with local array 'buf'", msg)

    def test_snprintf_undeclared_no_char_array_auto_declared(self):
        from compiler.semantic_auto_fixer import fix_semantic_issue
        src = ("int sec1() {\n"
               "    snprintf(a, sizeof(a), \"%s\", a);\n"
               "    return 0;\n"
               "}\n")
        issue = {"kind": "undeclared", "name": "a", "line": 2, "col": 13}
        new_src, msg = fix_semantic_issue(src, issue)
        self.assertIn("char a[40];", new_src)
        self.assertIn("declared character buffer 'char a[40]'", msg)
        expected = ("int sec1() {\n"
                    "    char a[40];\n"
                    "    snprintf(a, sizeof(a), \"%s\", a);\n"
                    "    return 0;\n"
                    "}\n")
        self.assertEqual(new_src, expected)


class TestPipelineSafetyGuard(unittest.TestCase):
    """Pipeline safety guard: accept only if clean parse & no new semantic issues."""

    def test_accepts_safe_fix(self):
        from compiler.pipeline_safety import apply_security_fixes_with_safety_guard
        src = ("int main() {\n"
               "    char buf[32];\n"
               "    gets(buf);\n"
               "    return 0;\n"
               "}\n")
        res = apply_security_fixes_with_safety_guard(src)
        self.assertIn("fgets(buf, sizeof(buf), stdin);", res.source)
        self.assertEqual(len(res.applied_steps), 1)

    def test_rolls_back_if_undeclared_introduced(self):
        from compiler.pipeline_safety import apply_security_fixes_with_safety_guard
        from compiler.security_auto_fixer import AutoFixResult
        # Create a mock fixer that attempts to inject an undeclared identifier
        class CorruptingFixer:
            def apply_fixes(self, s):
                bad_src = s.replace("gets(buf);", 'snprintf(ghost_var, sizeof(ghost_var), "%s", ghost_var);')
                return AutoFixResult(
                    source=bad_src,
                    applied_steps=["AISEC: line 3: corrupt fix"],
                    suggestions=[]
                )

        src = ("int main() {\n"
               "    char buf[32];\n"
               "    gets(buf);\n"
               "    return 0;\n"
               "}\n")
        res = apply_security_fixes_with_safety_guard(src, auto_fixer=CorruptingFixer())
        # The safety guard must reject the fix and roll back to original line!
        self.assertEqual(res.source, src)
        self.assertEqual(len(res.applied_steps), 0)
        self.assertTrue(any("rejected" in s and "ghost_var" in s for s in res.suggestions))


if __name__ == "__main__":
    unittest.main()