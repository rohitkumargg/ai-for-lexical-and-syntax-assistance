import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath("."))

from test_parser import parse_source, has_any_errors, get_all_error_strings
from compiler.semantic_checker import SemanticChecker

def main():
    out_file = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "examples/baseline_before_week8.json"
    files = sorted(glob.glob("examples/**/*.c", recursive=True))
    if "week8" in out_file:
        files = [f for f in files if "week8_2026" not in f.replace("\\", "/")]
    else:
        files = [f for f in files if "week5_" not in f and "week6_" not in f and "week7_" not in f]
    
    print(f"Collecting baseline for {len(files)} existing example files into {out_file}...")
    baseline = {}
    
    clean_count = 0
    error_count = 0

    for idx, filepath in enumerate(files, 1):
        rel_path = filepath.replace("\\", "/")
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            print(f"[{idx}/{len(files)}] Failed to read {rel_path}: {e}")
            continue

        t0 = time.perf_counter()
        tree, listeners, parser = parse_source(content, rel_path)
        is_clean = (tree is not None) and (not has_any_errors(listeners))
        errs = get_all_error_strings(listeners) if tree is not None else ["Tree is None"]
        
        sem_issues = []
        if is_clean and tree is not None:
            checker = SemanticChecker()
            try:
                checker.visit(tree)
                sem_issues = checker.get_issues()
            except Exception as e:
                sem_issues = [{"kind": "exception", "msg": str(e)}]

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        
        if is_clean:
            clean_count += 1
        else:
            error_count += 1

        baseline[rel_path] = {
            "initial_clean": is_clean,
            "error_count": len(errs) if not is_clean else 0,
            "errors": errs if not is_clean else [],
            "semantic_issue_count": len(sem_issues),
            "semantic_issues": sem_issues,
            "elapsed_ms": elapsed_ms,
        }
        print(f"[{idx}/{len(files)}] {rel_path}: clean={is_clean}, errors={len(errs) if not is_clean else 0}, sem_issues={len(sem_issues)} ({elapsed_ms}ms)")

    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)
    print(f"\nBaseline saved to {out_file}: {clean_count} clean, {error_count} with errors out of {len(files)} files.")

if __name__ == "__main__":
    main()
