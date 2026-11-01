import os
import sys
import json

sys.path.insert(0, os.path.abspath("."))
from compiler.languages.python_lang import repair_python

def norm(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").strip().split("\n")]
    return "\n".join(lines)

def main():
    base_dir = os.path.join("examples", "python")
    expected_dir = os.path.join(base_dir, "_expected")
    expected_json_path = os.path.join(expected_dir, "expected.json")

    expected_metadata = {}
    if os.path.exists(expected_json_path):
        try:
            with open(expected_json_path, "r", encoding="utf-8") as f:
                expected_metadata = json.load(f)
        except Exception:
            expected_metadata = {}

    results = []
    failures = 0

    for root, dirs, files in os.walk(base_dir):
        # Skip folders starting with "_" or "."
        dirs[:] = [d for d in dirs if not d.startswith(("_", ".")) and d != "__pycache__"]
        for file in sorted(files):
            if not file.endswith(".py") or file.startswith(("_", ".")):
                continue

            full_path = os.path.join(root, file)
            rel_to_python = os.path.relpath(full_path, base_dir).replace("\\", "/")

            with open(full_path, "r", encoding="utf-8") as f:
                original_source = f.read()

            res = repair_python(original_source, filename=rel_to_python)
            corrected = res.get("corrected_code", "")
            status = res.get("status", "")
            fixes_count = len(res.get("applied_steps", []))

            passed = True
            fail_reason = ""

            # Check if report-only / metadata expected
            if rel_to_python in expected_metadata:
                meta = expected_metadata[rel_to_python]
                action = meta.get("action")
                if action == "reported":
                    if norm(corrected) != norm(original_source):
                        passed = False
                        fail_reason = "Report-only file was modified"
                    target_kind = meta.get("kind")
                    target_rule = meta.get("rule")
                    target_line = meta.get("line")
                    target_sug = meta.get("suggestion_contains")

                    if target_kind:
                        issues = res.get("semantic_issues", [])
                        match = [i for i in issues if i.get("kind") == target_kind]
                        if not match:
                            passed = False
                            fail_reason = f"Missing semantic issue {target_kind}"
                        elif target_line and match[0].get("line") != target_line:
                            passed = False
                            fail_reason = f"Issue line mismatch: expected {target_line}, got {match[0].get('line')}"
                    elif target_rule:
                        warnings = res.get("security_warnings", [])
                        match = [w for w in warnings if target_rule in w]
                        if not match:
                            passed = False
                            fail_reason = f"Missing security warning {target_rule}"
                        else:
                            if target_line and f"line {target_line}:" not in match[0]:
                                passed = False
                                fail_reason = f"Warning line mismatch: expected {target_line}"
                            if target_sug and target_sug not in match[0]:
                                passed = False
                                fail_reason = f"Warning suggestion missing {target_sug}"
            else:
                expected_twin = os.path.join(expected_dir, rel_to_python)
                if not os.path.exists(expected_twin):
                    passed = False
                    fail_reason = f"Missing expected twin: {expected_twin}"
                else:
                    with open(expected_twin, "r", encoding="utf-8") as f:
                        expected_source = f.read()
                    if norm(corrected) != norm(expected_source):
                        passed = False
                        fail_reason = "Corrected code does not match expected twin"

            if not passed:
                failures += 1

            results.append({
                "file": rel_to_python,
                "status": status,
                "fixes": fixes_count,
                "pass": passed,
                "reason": fail_reason,
            })

    # Print table
    print(f"\n{'File':<45} | {'Status':<22} | {'Fixes':<5} | {'Result':<6}")
    print("-" * 85)
    for r in results:
        res_str = "PASS" if r["pass"] else f"FAIL ({r['reason']})"
        print(f"{r['file']:<45} | {r['status']:<22} | {r['fixes']:<5} | {res_str}")
    print("-" * 85)
    print(f"Total: {len(results)} files, {failures} failures.")

    # Write RESULTS.md
    md_lines = [
        "# Python Examples Repair Results",
        "",
        f"**Total files checked:** {len(results)}",
        f"**Passed:** {len(results) - failures}",
        f"**Failed:** {failures}",
        "",
        "| File | Status | Fixes | Result |",
        "| --- | --- | --- | --- |",
    ]
    for r in results:
        res_str = "PASS" if r["pass"] else f"FAIL: {r['reason']}"
        md_lines.append(f"| `{r['file']}` | `{r['status']}` | {r['fixes']} | {res_str} |")

    with open(os.path.join(base_dir, "RESULTS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    sys.exit(0 if failures == 0 else 1)

if __name__ == "__main__":
    main()
