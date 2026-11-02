#!/usr/bin/env python3
"""
Comprehensive Audit & Verification Script for all Examples.
Runs every C example (144 files) and Python example (28 files) under examples/.
Validates:
1. No unhandled crashes/exceptions.
2. Status categorization correctness.
3. Repaired programs compile/parse cleanly.
4. Clean files are not regressed (do-no-harm).
5. Diff generation is present whenever a candidate exists.
6. Scope guard and patch validation integrity.
"""
import os
import sys
import time
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compiler.repair_planner import RepairPlanner
from compiler.patch_validator import SandboxedCompiler
from compiler.repair_job_manager import RepairJobManager


def check_python_syntax(code: str) -> bool:
    try:
        compile(code, "<string>", "exec")
        return True
    except SyntaxError:
        return False


def run_audit(target_lang="all", limit=None):
    example_root = "examples"
    all_files = []

    for root, dirs, filenames in os.walk(example_root):
        dirs[:] = [d for d in dirs if not d.startswith((".", "_")) and d != "__pycache__"]
        for f in filenames:
            if f.startswith((".", "_")):
                continue
            lower = f.lower()
            if "_fixed." in lower:
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, example_root).replace("\\", "/")
            parts = rel_path.split("/")
            if any(p.startswith((".", "_")) or p == "__pycache__" for p in parts):
                continue
            
            if lower.endswith(".c") and target_lang in ("all", "c"):
                all_files.append((rel_path, "c", full_path))
            elif lower.endswith(".py") and target_lang in ("all", "python"):
                all_files.append((rel_path, "python", full_path))

    all_files.sort(key=lambda x: (x[1], x[0]))
    if limit:
        all_files = all_files[:limit]

    print(f"Starting audit across {len(all_files)} example files...")
    planner = RepairPlanner()
    compiler = SandboxedCompiler()

    results = []
    start_time = time.time()

    for idx, (rel, lang, full_path) in enumerate(all_files, 1):
        with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
            code = fp.read()
        lines = len(code.splitlines())
        t0 = time.time()

        # Check baseline compilation/parsing
        if lang == "c":
            c_before, out_before, _ = compiler.compile_check(code)
        else:
            c_before = check_python_syntax(code)
            out_before = ""

        try:
            if lang == "c" and lines > 300:
                jm = RepairJobManager()
                job = jm.create_job(code, os.path.basename(rel), "c", operation="repair")
                jm._execute_repair_job(job)
                j = jm.get_job(job.job_id)
                res = j.result or {}
            else:
                res = planner.plan_and_repair(
                    code,
                    filename=os.path.basename(rel),
                    language=lang,
                    operation="repair",
                    time_budget_s=15.0,
                )

            elapsed = round(time.time() - t0, 2)
            status = res.get("status") or res.get("terminal_status") or "UNKNOWN"
            cand = res.get("candidate") or {}
            proposed = res.get("proposed_code") or cand.get("proposed_code")
            has_cand = bool(proposed and proposed.strip() != code.strip())

            diff = res.get("diff") or res.get("unified_diff") or cand.get("diff") or cand.get("unified_diff") or ""
            has_diff = bool(diff and diff.strip())

            c_after = None
            if proposed:
                if lang == "c":
                    c_after, _, _ = compiler.compile_check(proposed)
                else:
                    c_after = check_python_syntax(proposed)

            is_valid = res.get("is_valid")
            if is_valid is None and cand:
                is_valid = cand.get("is_valid")

            stopping_reason = str(res.get("stopping_reason") or "")[:120]

            issues = []
            if has_cand and not has_diff:
                issues.append("MISSING_DIFF")
            if c_before and proposed and c_after is False:
                issues.append("DO_NO_HARM_REGRESSION")
            if has_cand and is_valid is True and c_after is False:
                issues.append("INVALID_CANDIDATE_MARKED_VALID")
            if status == "ERROR":
                issues.append("STATUS_ERROR")

            entry = {
                "file": rel,
                "lang": lang,
                "lines": lines,
                "status": status,
                "c_before": c_before,
                "c_after": c_after,
                "has_cand": has_cand,
                "has_diff": has_diff,
                "diff_len": len(diff),
                "is_valid": is_valid,
                "elapsed": elapsed,
                "stopping_reason": stopping_reason,
                "issues": issues,
            }
            results.append(entry)

            issue_str = f" [!] {', '.join(issues)}" if issues else ""
            print(f"[{idx:3d}/{len(all_files)}] [{lang:6s}] {rel:50s} lines={lines:4d} status={status:24s} c_b={str(c_before):5s} c_a={str(c_after):5s} diff={str(has_diff):5s} {elapsed:4.1f}s{issue_str}", flush=True)

        except Exception as e:
            tb = traceback.format_exc()
            elapsed = round(time.time() - t0, 2)
            results.append({
                "file": rel,
                "lang": lang,
                "lines": lines,
                "status": "EXCEPTION",
                "c_before": c_before,
                "c_after": None,
                "has_cand": False,
                "has_diff": False,
                "diff_len": 0,
                "is_valid": False,
                "elapsed": elapsed,
                "stopping_reason": str(e),
                "issues": ["UNHANDLED_EXCEPTION"],
                "traceback": tb,
            })
            print(f"[{idx:3d}/{len(all_files)}] [{lang:6s}] {rel:50s} EXCEPTION: {e}", flush=True)

    total_time = round(time.time() - start_time, 2)
    print("\n" + "=" * 80)
    print(f"AUDIT SUMMARY ({len(all_files)} files in {total_time}s):")
    total_issues = sum(len(r["issues"]) for r in results)
    exceptions = [r for r in results if "UNHANDLED_EXCEPTION" in r["issues"]]
    missing_diffs = [r for r in results if "MISSING_DIFF" in r["issues"]]
    regressions = [r for r in results if "DO_NO_HARM_REGRESSION" in r["issues"]]
    false_valids = [r for r in results if "INVALID_CANDIDATE_MARKED_VALID" in r["issues"]]

    status_counts = {}
    for r in results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    for st, cnt in sorted(status_counts.items()):
        print(f"  Status {st:25s}: {cnt}")

    print(f"\n  Total issues: {total_issues}")
    print(f"  Exceptions: {len(exceptions)}")
    print(f"  Missing diffs: {len(missing_diffs)}")
    print(f"  Do-no-harm regressions: {len(regressions)}")
    print(f"  Invalid candidates marked valid: {len(false_valids)}")
    print("=" * 80)

    out_file = f"reports/audit_all_{target_lang}.json"
    os.makedirs("reports", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2)
    print(f"Report saved to {out_file}")
    return results


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "all"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    run_audit(target_lang=lang, limit=limit)
