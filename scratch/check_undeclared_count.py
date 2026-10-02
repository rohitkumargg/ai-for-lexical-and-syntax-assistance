import glob, os, sys
sys.path.insert(0, os.path.abspath("."))
from test_parser import parse_source
from compiler.gui_bridge import _collect_semantic_issues

all_c_files = sorted(glob.glob("examples/**/*.c", recursive=True))
# The filter that was in semantic_benchmark.py when undeclared was 65:
# [p for p in all_c_files if "semantic" not in p.replace("\\", "/")]
filter1 = [p for p in all_c_files if "semantic" not in p.replace("\\", "/")]
filter2 = [p for p in all_c_files if not p.replace("\\", "/").startswith("examples/semantic/")]

print(f"Files count with filter1 (no 'semantic'): {len(filter1)}")
print(f"Files count with filter2 (not 'examples/semantic/'): {len(filter2)}")

def get_undeclared(file_list):
    res = []
    for p in file_list:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                src = f.read()
            issues = _collect_semantic_issues(src, p)
            for iss in issues:
                if iss.get("kind") == "undeclared":
                    res.append((p, iss))
        except Exception as e:
            pass
    return res

u1 = get_undeclared(filter1)
print(f"Undeclared count with filter1: {len(u1)}")
u2 = get_undeclared(filter2)
print(f"Undeclared count with filter2: {len(u2)}")
