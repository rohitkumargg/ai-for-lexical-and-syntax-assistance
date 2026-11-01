# scripts/generate_1000_line_test.py
"""
Generates a ~1000-line C file by concatenating typo-injected clean functions
(strictly NOT ademo2.c). Used for testing background repair jobs, function splitting,
progress estimation, and mid-run cancellation.
"""
import os

TEMPLATES = [
    """
int compute_sum_{idx}(int n) {{
    int total = 0;
    for (int i = 0; i < n; i++) {{
        total += i * 2;
    }}
    return total;
}}
""",
    """
void process_array_{idx}(int arr[], int size) {{
    for (int i = 0; i < size - 1; i++) {{
        for (int j = 0; j < size - i - 1; j++) {{
            if (arr[j] > arr[j + 1]) {{
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }}
        }}
    }}
}}
""",
    """
int binary_search_{idx}(int arr[], int l, int r, int x) {{
    while (l <= r) {{
        int m = l + (r - l) / 2;
        if (arr[m] == x)
            return m;
        if (arr[m] < x)
            l = m + 1;
        else
            r = m - 1;
    }}
    return -1;
}}
""",
    """
long long factorial_{idx}(int n) {{
    if (n <= 1)
        return 1;
    long long res = 1;
    for (int i = 2; i <= n; i++) {{
        res *= i;
    }}
    return res;
}}
""",
    """
int count_matches_{idx}(const char *str, char target) {{
    int count = 0;
    while (*str) {{
        if (*str == target)
            count++;
        str++;
    }}
    return count;
}}
""",
    """
void matrix_add_{idx}(int a[4][4], int b[4][4], int res[4][4]) {{
    for (int i = 0; i < 4; i++) {{
        for (int j = 0; j < 4; j++) {{
            res[i][j] = a[i][j] + b[i][j];
        }}
    }}
}}
"""
]

# Injected typo versions for some functions
TYPO_VARIANTS = [
    # Typo 1: 'viod' instead of 'void'
    """
viod display_status_{idx}(int code) {{
    printf("Status code: %d\\n", code);
}}
""",
    # Typo 2: Missing semicolon
    """
int calculate_offset_{idx}(int base, int step) {{
    int factor = step * 4
    return base + factor;
}}
""",
    # Typo 3: 'cahr' instead of 'char'
    """
cahr get_grade_{idx}(int score) {{
    if (score >= 90) return 'A';
    if (score >= 80) return 'B';
    return 'C';
}}
""",
    # Typo 4: missing semicolon after variable declaration
    """
int find_peak_{idx}(int data[], int len) {{
    int peak = data[0]
    for (int i = 1; i < len; i++) {{
        if (data[i] > peak) {{
            peak = data[i];
        }}
    }}
    return peak;
}}
"""
]


def generate_1000_line_file(output_path: str = "examples/generated_1000_lines.c") -> str:
    lines = [
        "/* Generated 1000-line multi-function test file */",
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <string.h>",
        "",
        "/* Global structures and definitions */",
        "typedef struct {",
        "    int id;",
        "    char name[64];",
        "    double val;",
        "} RecordItem;",
        "",
    ]

    fn_count = 0
    typo_count = 0
    idx = 0

    # We concatenate until we exceed ~1000 lines
    while len(lines) < 980:
        idx += 1
        # Alternate between clean templates and typo-injected templates
        if idx % 4 == 0 and typo_count < 8:
            t = TYPO_VARIANTS[typo_count % len(TYPO_VARIANTS)]
            rendered = t.format(idx=idx).strip().splitlines()
            typo_count += 1
        else:
            t = TEMPLATES[(idx - 1) % len(TEMPLATES)]
            rendered = t.format(idx=idx).strip().splitlines()

        lines.extend(rendered)
        lines.append("") # blank line between functions
        fn_count += 1

    # Add a main function at the end
    lines.extend([
        "int main(void) {",
        "    printf(\"Generated multi-function benchmark initialized.\\n\");",
        "    int sum = compute_sum_1(10);",
        "    printf(\"Sum: %d\\n\", sum);",
        "    return 0;",
        "}",
        ""
    ])

    code = "\n".join(lines)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"Generated {output_path} with {len(lines)} lines and {fn_count} functions ({typo_count} typo defects).")
    return output_path


if __name__ == "__main__":
    generate_1000_line_file()

