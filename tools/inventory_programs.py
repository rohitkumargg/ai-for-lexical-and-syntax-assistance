#!/usr/bin/env python3
"""
tools/inventory_programs.py
Inventories all C and Python files in examples/ for P2:
- language (c / python)
- size in bytes
- whether gcc (-std=gnu17 with -std=gnu11 fallback -Wall -fsyntax-only) or ast.parse accepts it
- first syntax error line if invalid
- whether it reads stdin
- whether a dangerous-call scan flags it (system, popen, exec*, fork, rm/delete, sockets, eval/exec, subprocess, os.system, infinite loops)
Outputs to reports/p2/inventory.csv and reports/p2/inventory.json
"""
import ast
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
REPORTS_DIR = REPO_ROOT / "reports" / "p2"

# Dangerous patterns: (name, regex)
C_DANGEROUS_PATTERNS = [
    ("system", re.compile(r"\bsystem\s*\(")),
    ("popen", re.compile(r"\bpopen\s*\(")),
    ("exec", re.compile(r"\bexec[lvpe]*\s*\(")),
    ("fork", re.compile(r"\bfork\s*\(")),
    ("socket", re.compile(r"\bsocket\s*\(")),
    ("connect", re.compile(r"\bconnect\s*\(")),
    ("bind", re.compile(r"\bbind\s*\(")),
    ("listen", re.compile(r"\blisten\s*\(")),
    ("remove", re.compile(r"\bremove\s*\(")),
    ("unlink", re.compile(r"\bunlink\s*\(")),
    ("rmdir", re.compile(r"\brmdir\s*\(")),
    ("rm_rf", re.compile(r"\brm\s+-rf\b")),
    ("del_f", re.compile(r"\bdel\s+/[fF]\b")),
]

PY_DANGEROUS_PATTERNS = [
    ("eval", re.compile(r"\beval\s*\(")),
    ("exec", re.compile(r"\bexec\s*\(")),
    ("os_system", re.compile(r"\bos\.system\s*\(")),
    ("os_popen", re.compile(r"\bos\.popen\s*\(")),
    ("os_spawn", re.compile(r"\bos\.spawn[a-z]*\s*\(")),
    ("subprocess", re.compile(r"\bsubprocess\b")),
    ("socket", re.compile(r"\bsocket\b")),
    ("os_remove", re.compile(r"\bos\.(?:remove|unlink)\s*\(")),
    ("shutil_rmtree", re.compile(r"\bshutil\.rmtree\s*\(")),
    ("server_run", re.compile(r"\bapp\.run\s*\([^)]*debug\s*=\s*True|\bserve_forever\s*\(")),
    ("yaml_unsafe", re.compile(r"\byaml\.load\s*\(")),
    ("pickle", re.compile(r"\bpickle\.loads?\s*\(")),
    ("verify_false", re.compile(r"\bverify\s*=\s*False\b")),
    ("weak_hash", re.compile(r"\bhashlib\.(?:md5|sha1)\s*\(")),
]

# Stdin patterns
C_STDIN_PATTERNS = [
    re.compile(r"\bscanf\s*\("),
    re.compile(r"\bfscanf\s*\(\s*stdin\b"),
    re.compile(r"\bfgets\s*\([^,]+,\s*[^,]+,\s*stdin\b"),
    re.compile(r"\bgetchar\s*\("),
    re.compile(r"\bgetc\s*\(\s*stdin\b"),
    re.compile(r"\bfgetc\s*\(\s*stdin\b"),
    re.compile(r"\bgets\s*\("),
    re.compile(r"\bread\s*\(\s*(?:0|STDIN_FILENO)\b"),
]

PY_STDIN_PATTERNS = [
    re.compile(r"\binput\s*\("),
    re.compile(r"\bsys\.stdin\.read"),
    re.compile(r"\bsys\.stdin\.readline"),
    re.compile(r"\bsys\.stdin\.readlines"),
]


def check_infinite_loop(content: str, language: str) -> bool:
    """Heuristic for unconditional infinite loops."""
    if language == "c":
        m = re.search(r"while\s*\(\s*(?:1|true)\s*\)\s*\{([^}]*)\}", content, re.DOTALL | re.IGNORECASE)
        if m:
            body = m.group(1)
            if not re.search(r"\b(break|return|exit|goto)\b", body):
                return True
        m_for = re.search(r"for\s*\(\s*;\s*;\s*\)\s*\{([^}]*)\}", content, re.DOTALL)
        if m_for:
            body = m_for.group(1)
            if not re.search(r"\b(break|return|exit|goto)\b", body):
                return True
    else:
        m = re.search(r"while\s+(?:True|1)\s*:(.*?)(?=\n\S|\Z)", content, re.DOTALL)
        if m:
            body = m.group(1)
            if not re.search(r"\b(break|return|sys\.exit|exit|raise)\b", body):
                return True
    return False


def scan_dangerous(content: str, language: str) -> list[str]:
    flags = []
    pats = C_DANGEROUS_PATTERNS if language == "c" else PY_DANGEROUS_PATTERNS
    for name, pat in pats:
        if pat.search(content):
            if name == "system":
                # If only a prototype declaration without any actual call statements
                if re.search(r"\b(?:int|void|extern)\s+system\s*\([^)]*\)\s*;", content):
                    if not re.search(r"[=;{]\s*system\s*\(|\bif\s*\([^)]*system\s*\(", content):
                        continue
            flags.append(name)

    if check_infinite_loop(content, language):
        flags.append("infinite_loop_heuristic")

    try:
        from compiler.security_approval_gate import SecurityDecisionGate
        gate = SecurityDecisionGate()
        v = gate.evaluate(content, "file.c" if language == "c" else "file.py", language)
        if v.findings:
            for f in v.findings:
                flags.append(f"{f.category}:{f.rule_id}")
    except Exception as e:
        pass

    return list(dict.fromkeys(flags))


def check_reads_stdin(content: str, language: str) -> bool:
    pats = C_STDIN_PATTERNS if language == "c" else PY_STDIN_PATTERNS
    for pat in pats:
        if pat.search(content):
            return True
    return False


def check_c_syntax(file_path: Path) -> tuple[bool, str, int | None]:
    """Runs gcc -std=gnu17 (or -std=gnu11 fallback if gnu17 unrecognized) -Wall -fsyntax-only."""
    for std_flag in ["-std=gnu17", "-std=gnu11"]:
        try:
            cmd = ["gcc", std_flag, "-Wall", "-fsyntax-only", str(file_path)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if "unrecognized command line option" in proc.stderr and std_flag == "-std=gnu17":
                continue
            if proc.returncode == 0:
                return True, "", None
            # Extract first error line
            first_line = None
            err_msg = proc.stderr.strip()
            for line in err_msg.splitlines():
                m = re.search(r":(\d+):(?:\d+:)?\s*(?:fatal\s+)?error:", line)
                if m:
                    first_line = int(m.group(1))
                    break
            first_err_str = ""
            for line in err_msg.splitlines():
                if "error:" in line:
                    first_err_str = line
                    break
            return False, first_err_str or (err_msg.splitlines()[0] if err_msg else "Syntax error"), first_line
        except Exception as e:
            return False, f"gcc check failed: {e}", None
    return False, "gcc execution failed", None


def check_python_syntax(content: str) -> tuple[bool, str, int | None]:
    """Checks Python syntax with ast.parse."""
    try:
        ast.parse(content)
        return True, "", None
    except SyntaxError as e:
        return False, str(e), e.lineno
    except Exception as e:
        return False, str(e), None


def inventory_all() -> list[dict]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    records = []

    c_files = sorted(list(EXAMPLES_DIR.rglob("*.c")))
    py_files = sorted(list(EXAMPLES_DIR.rglob("*.py")))

    all_files = sorted(c_files + py_files)

    for p in all_files:
        rel_path = p.relative_to(REPO_ROOT).as_posix()
        lang = "c" if p.suffix == ".c" else "python"
        size = p.stat().st_size
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            content = ""

        # Syntax check
        if lang == "c":
            valid_syntax, err_msg, err_line = check_c_syntax(p)
        else:
            valid_syntax, err_msg, err_line = check_python_syntax(content)

        reads_stdin = check_reads_stdin(content, lang)
        danger_flags = scan_dangerous(content, lang)
        
        # A program is dangerous if:
        # 1. It contains host-damaging patterns (infinite loops, destructive file ops)
        # 2. Or the compiler security gate flagged security findings requiring approval
        has_host_risk = any(
            flag in danger_flags
            for flag in ("infinite_loop_heuristic", "infinite_loop", "rm_rf", "del_f", "os_remove", "shutil_rmtree")
        )
        has_gate_finding = any(":" in flag for flag in danger_flags)
        is_dangerous = has_host_risk or has_gate_finding

        rec = {
            "path": rel_path,
            "filename": p.name,
            "language": lang,
            "size_bytes": size,
            "valid_syntax": valid_syntax,
            "first_error_line": err_line if err_line is not None else "",
            "syntax_message": err_msg[:160] if err_msg else "",
            "reads_stdin": reads_stdin,
            "is_dangerous": is_dangerous,
            "danger_flags": ";".join(danger_flags) if danger_flags else "",
        }
        records.append(rec)

    # Save to CSV
    csv_file = REPORTS_DIR / "inventory.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "path", "filename", "language", "size_bytes", "valid_syntax",
            "first_error_line", "syntax_message", "reads_stdin", "is_dangerous", "danger_flags"
        ])
        writer.writeheader()
        writer.writerows(records)

    # Save to JSON
    json_file = REPORTS_DIR / "inventory.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    return records


if __name__ == "__main__":
    records = inventory_all()
    print(f"Inventory complete: {len(records)} files examined.")
    c_count = sum(1 for r in records if r["language"] == "c")
    py_count = sum(1 for r in records if r["language"] == "python")
    valid_count = sum(1 for r in records if r["valid_syntax"])
    dang_count = sum(1 for r in records if r["is_dangerous"])
    stdin_count = sum(1 for r in records if r["reads_stdin"])
    print(f"C files: {c_count}, Python files: {py_count}")
    print(f"Valid syntax: {valid_count}, Invalid: {len(records) - valid_count}")
    print(f"Dangerous/unsafe calls: {dang_count}, Reads stdin: {stdin_count}")
    print(f"Outputs written to {REPORTS_DIR / 'inventory.csv'} and {REPORTS_DIR / 'inventory.json'}")
