import os
import json

base_dir = r"examples/week8_2026"
os.makedirs(base_dir, exist_ok=True)

files = {
"01_integer_overflow_broken.c": """int main() {
    int x = 2147483647 + 1;
    return x > 0;
}
""",
"01_integer_overflow_fixed.c": """int main() {
    long long x = (long long)2147483647 + 1;
    return x > 0;
}
""",
"02_signed_to_unsigned_broken.c": """int main() {
    int x = -1;
    unsigned y = x;
    return y > 0;
}
""",
"02_signed_to_unsigned_suggested.c": """int main() {
    int x = -1;
    unsigned y = 0;
    if (x >= 0) {
        y = (unsigned)x;
    }
    return y > 0;
}
""",
"03_null_dereference_broken.c": """int main() {
    int *p = NULL;
    *p = 10;
    return 0;
}
""",
"03_null_dereference_fixed.c": """int main() {
    int *p = NULL;
    if (p != NULL) {
        *p = 10;
    }
    return 0;
}
""",
"04_uninitialized_variable_broken.c": """int main() {
    int x;
    printf("%d\\n", x);
    return 0;
}
""",
"04_uninitialized_variable_fixed.c": """int main() {
    int x = 0;
    printf("%d\\n", x);
    return 0;
}
""",
"05_array_out_of_bounds_broken.c": """int main() {
    int a[3];
    a[5] = 10;
    return 0;
}
""",
"05_array_out_of_bounds_suggested.c": """int main() {
    int a[3];
    a[2] = 10;
    return 0;
}
""",
"06_off_by_one_broken.c": """int main() {
    int a[10];
    for (int i = 0; i <= 10; i++) {
        a[i] = 0;
    }
    return 0;
}
""",
"06_off_by_one_fixed.c": """int main() {
    int a[10];
    for (int i = 0; i < 10; i++) {
        a[i] = 0;
    }
    return 0;
}
""",
"07_unsafe_memcpy_broken.c": """int main() {
    char src[100];
    char dst[10];
    memcpy(dst, src, 100);
    return 0;
}
""",
"07_unsafe_memcpy_fixed.c": """int main() {
    char src[100];
    char dst[10];
    memcpy(dst, src, sizeof(dst));
    return 0;
}
""",
"08_format_mismatch_broken.c": """int main() {
    printf("%d\\n", "hello");
    return 0;
}
""",
"08_format_mismatch_fixed.c": """int main() {
    printf("%s\\n", "hello");
    return 0;
}
""",
"09_unsafe_scanf_broken.c": """int main() {
    char buf[100];
    scanf("%s", buf);
    return 0;
}
""",
"09_unsafe_scanf_fixed.c": """int main() {
    char buf[100];
    scanf("%99s", buf);
    return 0;
}
""",
"10_uninitialized_pointer_broken.c": """int main() {
    int *p;
    *p = 10;
    return 0;
}
""",
"10_uninitialized_pointer_fixed.c": """int main() {
    int *p = NULL;
    if (p != NULL) {
        *p = 10;
    }
    return 0;
}
""",
"clean_guard.c": """int main() {
    int a[10];
    char buf[100];
    char dst[10];
    int *p = NULL;
    long long big = (long long)2147483647 + 1;
    int n = 0;
    for (int i = 0; i < 10; i++) {
        a[i] = i;
    }
    if (p != NULL) {
        *p = 1;
    }
    scanf("%99s", buf);
    memcpy(dst, buf, sizeof(dst));
    printf("%d %s %lld\\n", a[0], buf, big);
    return n;
}
"""
}

for name, content in files.items():
    with open(os.path.join(base_dir, name), "w", encoding="utf-8") as f:
        f.write(content)

expected = {
  "01_integer_overflow_broken.c":       {"rule": "SEC-01", "finding": "integer_overflow",       "line": 2, "action": "auto_fixed", "fixed_file": "01_integer_overflow_fixed.c"},
  "02_signed_to_unsigned_broken.c":     {"rule": "SEC-02", "finding": "signed_to_unsigned",     "line": 3, "action": "warned",     "fixed_file": None, "suggestion_contains": "x >= 0"},
  "03_null_dereference_broken.c":       {"rule": "SEC-03", "finding": "null_dereference",       "line": 3, "action": "auto_fixed", "fixed_file": "03_null_dereference_fixed.c"},
  "04_uninitialized_variable_broken.c": {"rule": "SEC-04", "finding": "uninitialized_variable", "line": 3, "action": "auto_fixed", "fixed_file": "04_uninitialized_variable_fixed.c"},
  "05_array_out_of_bounds_broken.c":    {"rule": "SEC-05", "finding": "array_out_of_bounds",    "line": 3, "action": "warned",     "fixed_file": None, "suggestion_contains": "0..2"},
  "06_off_by_one_broken.c":             {"rule": "SEC-06", "finding": "off_by_one",             "line": 3, "action": "auto_fixed", "fixed_file": "06_off_by_one_fixed.c"},
  "07_unsafe_memcpy_broken.c":          {"rule": "SEC-07", "finding": "unsafe_memcpy",          "line": 4, "action": "auto_fixed", "fixed_file": "07_unsafe_memcpy_fixed.c"},
  "08_format_mismatch_broken.c":        {"rule": "SEC-08", "finding": "format_type_mismatch",   "line": 2, "action": "auto_fixed", "fixed_file": "08_format_mismatch_fixed.c"},
  "09_unsafe_scanf_broken.c":           {"rule": "SEC-09", "finding": "unsafe_scanf",           "line": 3, "action": "auto_fixed", "fixed_file": "09_unsafe_scanf_fixed.c"},
  "10_uninitialized_pointer_broken.c":  {"rule": "SEC-10", "finding": "uninitialized_pointer",  "line": 3, "action": "auto_fixed", "fixed_file": "10_uninitialized_pointer_fixed.c", "also_reports": ["SEC-03"]},
  "02_signed_to_unsigned_suggested.c":  {"rule": None, "finding": None, "line": None, "action": "unchanged", "fixed_file": None},
  "05_array_out_of_bounds_suggested.c": {"rule": None, "finding": None, "line": None, "action": "unchanged", "fixed_file": None},
  "clean_guard.c":                      {"rule": None, "finding": None, "line": None, "action": "unchanged", "fixed_file": None}
}

with open(os.path.join(base_dir, "expected.json"), "w", encoding="utf-8") as f:
    json.dump(expected, f, indent=2)

print(f"Successfully created {len(files)} files and expected.json in {base_dir}")
