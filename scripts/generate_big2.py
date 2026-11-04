import os

def generate_big2():
    lines = [
        "/* Generated 2000-line comprehensive benchmark file: big2.c */",
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <string.h>",
        "",
        "/* Global structures and definitions */",
        "struct Point {",
        "    int x;",
        "    int y;",
        "};",
        "",
        "struct DataRecord {",
        "    int id;",
        "    char name[64];",
        "    double val;",
        "};",
        "",
        "int helper_add(int a, int b) {",
        "    return a + b;",
        "}",
        "",
        "int helper_sub(int a, int b) {",
        "    return a - b;",
        "}",
        "",
        "int helper_mul(int a, int b) {",
        "    return a * b;",
        "}",
        "",
    ]

    fn_count = 300  # ~7 lines per function -> ~2035 lines

    for i in range(1, fn_count + 1):
        mode = i % 8
        if mode == 1:
            # Lexical error: bad operator or token (e.g. === or @ or bad escape)
            lines.extend([
                f"int test_lex_{i}(void) {{",
                f"    int a = {i};",
                f"    int b = {i * 2};",
                f"    int res = 0;",
                f"    if (a === b) {{",
                f"        res = 1;",
                f"    }}",
                f"    return res;",
                f"}}",
                "",
            ])
        elif mode == 2:
            # Syntax error 1: missing semicolon
            lines.extend([
                f"int test_syn_semi_{i}(void) {{",
                f"    int x = {i}",
                f"    int y = x + 10;",
                f"    return y;",
                f"}}",
                "",
            ])
        elif mode == 3:
            # Syntax error 2: array bracket missing closing bracket: int arr[5;
            lines.extend([
                f"int test_syn_bracket_{i}(void) {{",
                f"    int arr[5;",
                f"    arr[0] = {i};",
                f"    return arr[0];",
                f"}}",
                "",
            ])
        elif mode == 4:
            # Syntax error 3: missing comma in argument list: helper_add(10 20);
            lines.extend([
                f"int test_syn_comma_{i}(void) {{",
                f"    int sum = helper_add(10 20);",
                f"    return sum + {i};",
                f"}}",
                "",
            ])
        elif mode == 5:
            # Semantic error: dot on pointer struct
            lines.extend([
                f"int test_sem_dot_{i}(void) {{",
                f"    struct Point p;",
                f"    struct Point *ptr = &p;",
                f"    ptr.x = {i};",
                f"    ptr.y = {i + 1};",
                f"    return ptr.x + ptr.y;",
                f"}}",
                "",
            ])
        elif mode == 6:
            # Security error 1: gets(buf) with declared buffer
            lines.extend([
                f"int test_sec_gets_{i}(void) {{",
                f"    char buf[64];",
                f"    gets(buf);",
                f"    return buf[0] == 'A' ? 1 : 0;",
                f"}}",
                "",
            ])
        elif mode == 7:
            # Security error 2: unbounded scanf with declared buffer
            lines.extend([
                f"int test_sec_scanf_{i}(void) {{",
                f"    char name[32];",
                f"    scanf(\"%s\", name);",
                f"    return name[0] ? {i} : 0;",
                f"}}",
                "",
            ])
        else:
            # Security error 3: sprintf into buffer
            lines.extend([
                f"int test_sec_sprintf_{i}(void) {{",
                f"    char msg[128];",
                f"    sprintf(msg, \"Record ID: %d\", {i});",
                f"    return msg[0] ? 1 : 0;",
                f"}}",
                "",
            ])

    # Add main function
    lines.extend([
        "int main(void) {",
        "    int total = 0;",
        "    total += test_lex_1();",
        "    total += test_syn_semi_2();",
        "    total += test_syn_bracket_3();",
        "    total += test_syn_comma_4();",
        "    total += test_sem_dot_5();",
        "    total += test_sec_gets_6();",
        "    total += test_sec_scanf_7();",
        "    total += test_sec_sprintf_8();",
        "    printf(\"Total: %d\\n\", total);",
        "    return 0;",
        "}",
        "",
    ])

    content = "\n".join(lines)
    with open("examples/big2.c", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Generated examples/big2.c: {len(content.splitlines())} lines, {len(content)} bytes.")

if __name__ == "__main__":
    generate_big2()
