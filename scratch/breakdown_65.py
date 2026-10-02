import glob, os, sys, re
sys.path.insert(0, ".")
from test_parser import parse_source, has_any_errors
from compiler.semantic_checker import SemanticChecker

STD_LIB = {
    "printf", "scanf", "malloc", "free", "strlen", "strcpy", "strncpy",
    "strcmp", "strncmp", "puts", "gets", "putchar", "getchar", "sprintf",
    "snprintf", "exit", "sizeof"
}

c_files = sorted(glob.glob("examples/**/*.c", recursive=True))
main_files = [p for p in c_files if not p.replace("\\", "/").startswith("examples/semantic/")]

cases = []
for p in main_files:
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
        tree, listeners, _ = parse_source(src, p)
        if tree is None or has_any_errors(listeners):
            continue
        sc = SemanticChecker()
        sc.visit(tree)
        lines = src.splitlines()
        for iss in sc.get_issues():
            if iss.get("kind") == "undeclared":
                line_idx = iss.get("line", 1) - 1
                txt = lines[line_idx] if 0 <= line_idx < len(lines) else ""
                cases.append({
                    "file": p,
                    "line": iss.get("line"),
                    "col": iss.get("col"),
                    "name": iss.get("name"),
                    "msg": iss.get("msg"),
                    "text": txt.strip(),
                })
    except Exception as e:
        pass

print(f"Total undeclared cases in 41 clean files: {len(cases)}")

cats = {
    "typo": [],
    "library_function": [],
    "type_inferable_assign": [],
    "genuinely_missing_other": [],
}

for c in cases:
    name = c["name"]
    txt = c["text"]
    if name in {"prinft", "scnaf"}:
        cats["typo"].append(c)
    elif name in STD_LIB:
        cats["library_function"].append(c)
    elif re.match(rf"^\s*{re.escape(name)}\s*=", txt):
        cats["type_inferable_assign"].append(c)
    else:
        cats["genuinely_missing_other"].append(c)

for k, v in cats.items():
    print(f"\n[{k}]: {len(v)} cases")
    for item in v:
        print(f"  {item['file']}:{item['line']} -> {item['name']} | `{item['text']}`")
