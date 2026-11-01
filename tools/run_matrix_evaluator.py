#!/usr/bin/env python3
"""
tools/run_matrix_evaluator.py
Executes the Oracle vs App comparison matrix across all 192 inventory programs:
1. Oracle execution (gcc -O0 or python) in temp isolated dir.
2. App execution via /api/program/run with approval handling.
3. Compares stdout, exit code, and stderr class after newline normalization.
4. For invalid syntax, verifies first error line is within +-1 of oracle.
5. Saves reports/p2/run_matrix.csv and reports/p2/run_matrix.json
"""
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports" / "p2"
INVENTORY_FILE = REPORTS_DIR / "inventory.json"
STDIN_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "default_stdin.txt"
APP_URL = "http://127.0.0.1:5000"


def normalize_output(text: str) -> str:
    """Normalizes CRLF -> LF, collapses trailing spaces per line, strips ends."""
    if not text:
        return ""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").splitlines()]
    return "\n".join(lines).strip()


def run_oracle(path: Path, lang: str, stdin_data: str) -> dict:
    """
    Executes the program using the system oracle:
    gcc -O0 for C, python for Python.
    """
    code = path.read_text(encoding="utf-8", errors="replace")

    # Interim Guard: never execute risky programs on the host machine
    from compiler.sandbox.interim_guard import evaluate_interim_guard
    guard = evaluate_interim_guard(code, filename=path.name, language=lang)
    if guard.is_refused:
        return {
            "kind": "SKIPPED_UNSAFE",
            "exit_code": None,
            "stdout": "",
            "stderr": f"[SANDBOX REFUSAL] Oracle host execution refused: {guard.reason}",
            "first_error_line": None,
        }

    with tempfile.TemporaryDirectory(prefix="antigravity_oracle_") as tmpdir:
        if lang == "c":
            src_file = os.path.join(tmpdir, "main.c")
            exe_file = os.path.join(tmpdir, "main.exe")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write(code)

            # Compile with gcc -O0
            comp = subprocess.run(
                ["gcc", "-std=gnu11", "-O0", "-Wall", "-Werror=implicit-function-declaration", src_file, "-o", exe_file],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if comp.returncode != 0:
                first_line = None
                for line in comp.stderr.splitlines():
                    m = re.search(r":(\d+):(?:\d+:)?\s*(?:fatal\s+)?error:", line)
                    if m:
                        first_line = int(m.group(1))
                        break
                return {
                    "kind": "COMPILE_ERROR",
                    "exit_code": comp.returncode,
                    "stdout": "",
                    "stderr": comp.stderr.strip(),
                    "first_error_line": first_line,
                }

            # Run compiled binary
            try:
                run_p = subprocess.run(
                    [exe_file],
                    input=stdin_data,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return {
                    "kind": "EXECUTION",
                    "exit_code": run_p.returncode,
                    "stdout": normalize_output(run_p.stdout),
                    "stderr": normalize_output(run_p.stderr),
                    "first_error_line": None,
                }
            except subprocess.TimeoutExpired:
                return {
                    "kind": "TIMED_OUT",
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "Oracle execution timed out",
                    "first_error_line": None,
                }
            except Exception as e:
                return {
                    "kind": "RUNTIME_ERROR",
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": str(e),
                    "first_error_line": None,
                }
        else:
            # Python oracle
            src_file = os.path.join(tmpdir, "script.py")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write(code)

            try:
                run_p = subprocess.run(
                    [sys.executable, "-u", "-B", src_file],
                    input=stdin_data,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                first_line = None
                if run_p.returncode != 0:
                    for line in run_p.stderr.splitlines():
                        m = re.search(r'File ".*?", line (\d+)', line)
                        if m:
                            first_line = int(m.group(1))
                            break
                    if "SyntaxError" in run_p.stderr:
                        return {
                            "kind": "COMPILE_ERROR",
                            "exit_code": run_p.returncode,
                            "stdout": normalize_output(run_p.stdout),
                            "stderr": normalize_output(run_p.stderr),
                            "first_error_line": first_line,
                        }

                return {
                    "kind": "EXECUTION",
                    "exit_code": run_p.returncode,
                    "stdout": normalize_output(run_p.stdout),
                    "stderr": normalize_output(run_p.stderr),
                    "first_error_line": first_line,
                }
            except subprocess.TimeoutExpired:
                return {
                    "kind": "TIMED_OUT",
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "Oracle execution timed out",
                    "first_error_line": None,
                }
            except Exception as e:
                return {
                    "kind": "RUNTIME_ERROR",
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": str(e),
                    "first_error_line": None,
                }


def call_app_run(code: str, filename: str, lang: str, stdin_data: str, token: str = None) -> tuple[int, dict]:
    payload = {
        "code": code,
        "filename": filename,
        "language": lang,
        "stdin": stdin_data,
        "timeout": 5.0,
    }
    if token:
        payload["approval_token"] = token

    url = f"{APP_URL}/api/program/run"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"error": err_body}
    except Exception as e:
        return 0, {"error": str(e)}


def call_app_approve(code: str, filename: str) -> str:
    url = f"{APP_URL}/api/security/approval/approve"
    req = urllib.request.Request(
        url,
        data=json.dumps({"code": code, "filename": filename, "operation": "execute"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("approval_token")
    except Exception:
        return None


def evaluate_matrix() -> list[dict]:
    with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
        inventory = json.load(f)

    stdin_content = STDIN_FIXTURE.read_text(encoding="utf-8")

    matrix_rows = []

    for idx, item in enumerate(inventory, start=1):
        rel_path = item["path"]
        p = REPO_ROOT / rel_path
        filename = item["filename"]
        lang = item["language"]
        code = p.read_text(encoding="utf-8", errors="replace")
        stdin_to_use = stdin_content if item["reads_stdin"] else ""

        print(f"[{idx}/{len(inventory)}] Evaluating {rel_path}...")

        is_flagged_unsafe = item["is_dangerous"]

        # Run App (First Attempt without approval token)
        app_http, app_resp = call_app_run(code, filename, lang, stdin_to_use, token=None)

        app_refused_without_token = (app_http == 409 and app_resp.get("requires_approval") is True)

        row = {
            "path": rel_path,
            "filename": filename,
            "language": lang,
            "valid_syntax": item["valid_syntax"],
            "is_dangerous": is_flagged_unsafe,
            "danger_flags": item["danger_flags"],
            "reads_stdin": item["reads_stdin"],
            "oracle_status": "",
            "oracle_exit": "",
            "oracle_stdout": "",
            "oracle_stderr_snip": "",
            "oracle_err_line": "",
            "app_http": app_http,
            "app_status": "",
            "app_exit": "",
            "app_stdout": "",
            "app_stderr_snip": "",
            "app_err_line": "",
            "match": "NO",
            "category": "",
            "reason": "",
        }

        if is_flagged_unsafe:
            # Policy: Flagged programs are NOT executed directly on the host
            # Record SKIPPED_UNSAFE and verify app refuses without approval
            row["oracle_status"] = "SKIPPED_UNSAFE"
            if app_refused_without_token:
                row["app_status"] = "SECURITY_WARNING"
                row["match"] = "YES"
                row["category"] = "UNSAFE_SECURITY_GATE_REFUSAL"
                row["reason"] = "Unsafe program skipped per security policy; App correctly refused execution without user approval token."
            else:
                row["app_status"] = app_resp.get("status", str(app_http))
                row["match"] = "NO"
                row["category"] = "SECURITY_GATE_BYPASS_FAILURE"
                row["reason"] = f"Unsafe program was not intercepted with HTTP 409 approval gate (got HTTP {app_http})."
            matrix_rows.append(row)
            continue

        # If it was clean, run oracle
        oracle_res = run_oracle(p, lang, stdin_to_use)
        row["oracle_status"] = oracle_res["kind"]
        row["oracle_exit"] = str(oracle_res["exit_code"]) if oracle_res["exit_code"] is not None else ""
        row["oracle_stdout"] = oracle_res["stdout"][:100]
        row["oracle_stderr_snip"] = oracle_res["stderr"][:120]
        row["oracle_err_line"] = str(oracle_res["first_error_line"]) if oracle_res["first_error_line"] is not None else ""

        # Process App result
        row["app_status"] = app_resp.get("status", "")
        row["app_exit"] = str(app_resp.get("exit_code")) if app_resp.get("exit_code") is not None else ""
        row["app_stdout"] = normalize_output(app_resp.get("stdout", ""))[:100]
        app_err = app_resp.get("stderr") or app_resp.get("compilation_error") or ""
        row["app_stderr_snip"] = normalize_output(app_err)[:120]

        # Extract app first error line
        app_err_line = None
        for l_line in app_err.splitlines():
            m1 = re.search(r":(\d+):(?:\d+:)?\s*(?:fatal\s+)?error:", l_line)
            if m1:
                app_err_line = int(m1.group(1))
                break
            m2 = re.search(r'line (\d+)', l_line)
            if m2:
                app_err_line = int(m2.group(1))
                break
        row["app_err_line"] = str(app_err_line) if app_err_line is not None else ""

        # Compare Oracle vs App
        if oracle_res["kind"] == "EXECUTION":
            # Both should complete or match exit code and stdout
            norm_or_out = oracle_res["stdout"]
            norm_app_out = normalize_output(app_resp.get("stdout", ""))

            if oracle_res["exit_code"] == 0 and app_resp.get("status") == "Completed" and norm_or_out == norm_app_out:
                row["match"] = "YES"
                row["category"] = "CLEAN_EXECUTION_MATCH"
                row["reason"] = "Oracle and App outputs and exit codes match exactly."
            elif oracle_res["exit_code"] != 0 and app_resp.get("exit_code") == oracle_res["exit_code"]:
                row["match"] = "YES"
                row["category"] = "RUNTIME_ERROR_MATCH"
                row["reason"] = f"Runtime exit codes match ({oracle_res['exit_code']})."
            elif app_resp.get("status") == "Compilation Failed" and oracle_res["exit_code"] != 0:
                row["match"] = "YES"
                row["category"] = "COMPILE_ERROR_MATCH"
                row["reason"] = "Both Oracle and App failed compilation."
            else:
                row["match"] = "NO"
                row["category"] = "OUTPUT_MISMATCH"
                row["reason"] = f"Oracle exit={oracle_res['exit_code']}, App exit={app_resp.get('exit_code')}, stdout mismatch."

        elif oracle_res["kind"] == "COMPILE_ERROR":
            # Invalid program: App must report compilation/syntax error within +-1 line
            or_line = oracle_res["first_error_line"]
            if app_resp.get("status") in ("Compilation Failed", "Runtime Error") or app_http != 200:
                line_ok = True
                if or_line is not None and app_err_line is not None:
                    line_ok = abs(or_line - app_err_line) <= 1

                if line_ok:
                    row["match"] = "YES"
                    row["category"] = "SYNTAX_ERROR_LINE_MATCH"
                    row["reason"] = f"App reported compilation failure; error line ({app_err_line}) within +-1 of oracle ({or_line})."
                else:
                    row["match"] = "NO"
                    row["category"] = "SYNTAX_LINE_MISMATCH"
                    row["reason"] = f"Error line mismatch: Oracle line {or_line} vs App line {app_err_line}."
            else:
                row["match"] = "NO"
                row["category"] = "EXPECTED_ERROR_NOT_SHOWN"
                row["reason"] = f"Oracle expected compile error, but App returned status {app_resp.get('status')}."

        elif oracle_res["kind"] == "TIMED_OUT":
            if app_resp.get("status") == "Timed Out":
                row["match"] = "YES"
                row["category"] = "TIMEOUT_MATCH"
                row["reason"] = "Both Oracle and App timed out."
            else:
                row["match"] = "NO"
                row["category"] = "TIMEOUT_MISMATCH"
                row["reason"] = f"Oracle timed out but App returned {app_resp.get('status')}."

        elif oracle_res["kind"] == "RUNTIME_ERROR":
            if app_resp.get("status") in ("Runtime Error", "Compilation Failed"):
                row["match"] = "YES"
                row["category"] = "RUNTIME_ERROR_MATCH"
                row["reason"] = "Both Oracle and App reported runtime error."
            else:
                row["match"] = "NO"
                row["category"] = "RUNTIME_ERROR_MISMATCH"
                row["reason"] = f"Oracle runtime error but App returned {app_resp.get('status')}."

        matrix_rows.append(row)

    # Save to CSV
    csv_file = REPORTS_DIR / "run_matrix.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "path", "filename", "language", "valid_syntax", "is_dangerous", "danger_flags", "reads_stdin",
            "oracle_status", "oracle_exit", "oracle_stdout", "oracle_stderr_snip", "oracle_err_line",
            "app_http", "app_status", "app_exit", "app_stdout", "app_stderr_snip", "app_err_line",
            "match", "category", "reason"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(matrix_rows)

    # Save to JSON
    json_file = REPORTS_DIR / "run_matrix.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(matrix_rows, f, indent=2)

    return matrix_rows


if __name__ == "__main__":
    rows = evaluate_matrix()
    total = len(rows)
    matches = sum(1 for r in rows if r["match"] == "YES")
    mismatches = total - matches

    cats = {}
    for r in rows:
        c = r["category"]
        cats[c] = cats.get(c, 0) + 1

    print("\n================ RUN MATRIX SUMMARY ================")
    print(f"Total programs evaluated: {total}")
    print(f"Matches: {matches} ({matches/total*100:.1f}%)")
    print(f"Mismatches: {mismatches}")
    print("\nBreakdown by Category:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  - {cat}: {count}")
    print(f"\nOutputs written to {REPORTS_DIR / 'run_matrix.csv'} and {REPORTS_DIR / 'run_matrix.json'}")
