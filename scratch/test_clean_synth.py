import sys, random, re
sys.path.insert(0, ".")
from test_parser import parse_source, has_any_errors
from compiler.semantic_checker import SemanticChecker

def generate_clean_seeds(n_seeds=400):
    seeds = []
    
    # Template 1: Math functions
    for i in range(100):
        code = f"""int calc_math_{i}(int a, int b) {{
    int x = a * 2;
    int y = b + 3;
    int z = x + y;
    if (z > 10) {{
        z = z - 5;
    }} else {{
        z = z + 5;
    }}
    return z;
}}

int main() {{
    int res = calc_math_{i}(3, 4);
    return res;
}}
"""
        seeds.append(code)

    # Template 2: Loops & Arrays
    for i in range(100):
        code = f"""int process_arr_{i}(int start_val) {{
    int arr[5];
    int sum = 0;
    int k = start_val;
    for (int idx = 0; idx < 5; idx++) {{
        arr[idx] = k + idx;
        sum = sum + arr[idx];
    }}
    return sum;
}}

int main() {{
    int total = process_arr_{i}(10);
    return total;
}}
"""
        seeds.append(code)

    # Template 3: Struct operations
    for i in range(100):
        code = f"""struct Point_{i} {{
    int x;
    int y;
    int id;
}};

int calc_point_{i}(int factor) {{
    struct Point_{i} pt;
    pt.x = factor * 2;
    pt.y = factor + 4;
    pt.id = {i};
    return pt.x + pt.y + pt.id;
}}

int main() {{
    int r = calc_point_{i}(5);
    return r;
}}
"""
        seeds.append(code)

    # Template 4: Multi-variable logic
    for i in range(100):
        code = f"""int evaluate_cond_{i}(int u, int v) {{
    int p = u + 1;
    int q = v * 2;
    int count = 0;
    while (p < q) {{
        p = p + 2;
        count = count + 1;
    }}
    return count;
}}

int main() {{
    int c = evaluate_cond_{i}(2, 8);
    return c;
}}
"""
        seeds.append(code)

    return seeds

seeds = generate_clean_seeds()
clean_count = 0
for s in seeds:
    t, l, _ = parse_source(s, "check")
    if t and not has_any_errors(l):
        sc = SemanticChecker()
        sc.visit(t)
        if len(sc.get_issues()) == 0:
            clean_count += 1

print(f"Generated {len(seeds)} seeds, clean count: {clean_count}")
