import re
from dataclasses import dataclass
from typing import Any, List, Optional, Set, Tuple
from compiler.call_extractor import (
    extract_call_sites,
    extract_var_declarations,
    CallSite,
    strip_c_comments_only,
    strip_c_comments_and_strings,
)


DANGEROUS_FUNCTIONS = {
    "system": "Executes shell command",
    "popen": "Opens process pipe",
    "execl": "Exec family process execution",
    "execv": "Exec family process execution",
    "execvp": "Exec family process execution",
    "execve": "Exec family process execution",
    "WinExec": "Windows command execution",
    "ShellExecute": "Windows shell execution",
    "CreateProcess": "Windows process creation",
}


UNSAFE_FUNCTIONS = {
    "gets": "Unsafe input function",
    "strcpy": "Unsafe string copy",
    "strcat": "Unsafe string concatenation",
    "sprintf": "Unsafe string formatting",
    "vsprintf": "Unsafe variadic string formatting",
}


DANGEROUS_COMMAND_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"del\s+/s\s+/q",
    r"rmdir\s+/s\s+/q",
    r"powershell",
    r"cmd\.exe",
    r"wget\s+",
    r"curl\s+",
    r"shutdown\s+",
    r"format\s+[A-Za-z]:",
]


SENSITIVE_PATH_PATTERNS = [
    r"C:\\Windows",
    r"C:\\System32",
    r"/etc/",
    r"/bin/",
    r"/usr/bin/",
]


DANGEROUS_MACRO_PATTERNS = [
    r"#define\s+\w+\s+\".*rm\s+-rf\s+/.*\"",
    r"#define\s+\w+\s+\".*del\s+/s\s+/q.*\"",
    r"#define\s+\w+\s+\".*powershell.*\"",
]


@dataclass
class SecurityIssue:
    severity: str
    message: str
    suggestion: str
    score: int
    line: Optional[int] = None
    col: Optional[int] = None
    fn: Optional[str] = None
    stable_id: Optional[str] = None
    is_confirmed: bool = True
    from_ast: bool = True


class SecurityChecker:

    def check(self, source_text: str, taint_issues: Optional[List[Any]] = None) -> List[SecurityIssue]:

        issues: List[SecurityIssue] = []
        seen_ids: Set[str] = set()

        if taint_issues is None:
            try:
                from compiler.taint_checker import TaintChecker
                taint_issues = TaintChecker().check(source_text)
            except Exception:
                taint_issues = []

        tainted_sinks = {
            (getattr(t, "sink", None), getattr(t, "line", None))
            for t in taint_issues
            if getattr(t, "sink", None) and getattr(t, "line", None)
        }
        tainted_sink_names = {getattr(t, "sink", None) for t in taint_issues if getattr(t, "sink", None)}

        calls = extract_call_sites(source_text)
        decl_vars = extract_var_declarations(source_text)

        # ------------------------------------------------
        # 1. Dangerous APIs
        # ------------------------------------------------
        if calls:
            for call in calls:
                fn = call.fn_name
                if fn in DANGEROUS_FUNCTIONS:
                    line_no = call.line
                    col_no = call.col
                    if (fn, line_no) in tainted_sinks:
                        continue
                    desc = DANGEROUS_FUNCTIONS[fn]
                    # Check command argument (first argument for exec/system/popen)
                    cmd_arg = call.args[0].strip() if getattr(call, "args", None) and len(call.args) > 0 else ""

                    if re.fullmatch(r'"[^"\n]*"', cmd_arg):
                        if fn in ("system", "execv", "execvp", "execl", "execlp"):
                            stable_id = f"dangerous_api_const:{fn}:{line_no}"
                            if stable_id not in seen_ids:
                                seen_ids.add(stable_id)
                                issues.append(
                                    SecurityIssue(
                                        severity="INFO",
                                        message=f"{fn}() runs a fixed command",
                                        suggestion="",
                                        score=0,
                                        line=line_no,
                                        col=col_no,
                                        fn=fn,
                                        stable_id=stable_id,
                                    )
                                )
                        else:
                            stable_id = f"dangerous_api_const:{fn}:{line_no}"
                            if stable_id not in seen_ids:
                                seen_ids.add(stable_id)
                                issues.append(
                                    SecurityIssue(
                                        severity="WARNING",
                                        message=f"Dangerous API used with constant string: {fn} ({desc})",
                                        suggestion="Avoid command execution APIs unless absolutely necessary.",
                                        score=2,
                                        line=line_no,
                                        col=col_no,
                                        fn=fn,
                                        stable_id=stable_id,
                                    )
                                )
                    else:
                        # Non-constant input:
                        # Suppress generic warning if a specific taint-flow finding exists for this sink call
                        is_tainted = (fn, line_no) in tainted_sinks or (fn in tainted_sink_names and not tainted_sinks)
                        if not is_tainted:
                            stable_id = f"dangerous_api_nonconst:{fn}:{line_no}"
                            if stable_id not in seen_ids:
                                seen_ids.add(stable_id)
                                issues.append(
                                    SecurityIssue(
                                        severity="WARNING",
                                        message=f"Dangerous API used with non-constant input: {fn} ({desc})",
                                        suggestion="Sanitize and validate input before passing it to command execution APIs.",
                                        score=3,
                                        line=line_no,
                                        col=col_no,
                                        fn=fn,
                                        stable_id=stable_id,
                                    )
                                )


        # Formatted input buffer overflow and unbounded scanf input checks
        from compiler.scanf_analyzer import ScanfSecurityAnalyzer, SCANF_FAMILY_FUNCTIONS
        if calls:
            for call in calls:
                if call.fn_name in SCANF_FAMILY_FUNCTIONS:
                    fn_cfg = SCANF_FAMILY_FUNCTIONS[call.fn_name]
                    fmt_idx = fn_cfg["fmt_idx"]
                    fmt_raw = None
                    if len(call.args) > fmt_idx:
                        f_arg = call.args[fmt_idx].strip()
                        if f_arg.startswith('"') and f_arg.endswith('"'):
                            fmt_raw = f_arg[1:-1]
                    s_findings = ScanfSecurityAnalyzer.analyze_call(
                        fn_name=call.fn_name,
                        line=call.line,
                        col=call.col,
                        args_text=call.args,
                        fmt_raw=fmt_raw,
                        source_text=source_text,
                    )
                    for sf in s_findings:
                        stable_id = f"unsafe_scanf:{sf.dest_var_name}:{sf.line}:{sf.conversion.conv_index}"
                        if stable_id not in seen_ids:
                            seen_ids.add(stable_id)
                            issues.append(
                                SecurityIssue(
                                    severity=sf.severity,
                                    message=sf.message,
                                    suggestion=sf.suggestion,
                                    score=4 if sf.severity == "HIGH" else 2,
                                    line=sf.line,
                                    col=sf.col,
                                    fn=call.fn_name,
                                    stable_id=stable_id,
                                )
                            )

        # ------------------------------------------------
        # 2. Unsafe C functions (exact function name match on calls only)
        # ------------------------------------------------
        if calls:
            for call in calls:
                fn = call.fn_name
                if fn in UNSAFE_FUNCTIONS:
                    desc = UNSAFE_FUNCTIONS[fn]
                    line_no = call.line
                    col_no = call.col
                    stable_id = f"unsafe_fn:{fn}:{line_no}"
                    if stable_id not in seen_ids:
                        seen_ids.add(stable_id)
                        is_ast = getattr(call, "from_ast", True)
                        if fn == "gets":
                            issues.append(
                                SecurityIssue(
                                    severity="CRITICAL",
                                    message=f"Unsafe function detected: {fn} ({desc})",
                                    suggestion="Replace gets with fgets.",
                                    score=5,
                                    line=line_no,
                                    col=col_no,
                                    fn=fn,
                                    stable_id=stable_id,
                                    is_confirmed=is_ast,
                                    from_ast=is_ast,
                                )
                            )
                        else:
                            msg = f"Unsafe function detected: {fn} ({desc})"
                            if fn in ("strcpy", "strcat", "sprintf", "vsprintf") and call.args:
                                d_m = re.search(r"&?([A-Za-z_]\w*)", call.args[0])
                                if d_m:
                                    d_name = d_m.group(1)
                                    decl = decl_vars.get(d_name)
                                    if not decl or decl.is_pointer or decl.array_size is None:
                                        msg = f"{fn} into '{d_name}': destination size unknown (pass the buffer size as a parameter)"
                            issues.append(
                                SecurityIssue(
                                    severity="WARNING",
                                    message=msg,
                                    suggestion="Use safer alternatives or pass buffer size.",
                                    score=2,
                                    line=line_no,
                                    col=col_no,
                                    fn=fn,
                                    stable_id=stable_id,
                                    is_confirmed=is_ast,
                                    from_ast=is_ast,
                                )
                            )

        # ------------------------------------------------
        # 3. Dangerous command patterns (comments stripped)
        # ------------------------------------------------
        clean_code = strip_c_comments_only(source_text)
        for pattern in DANGEROUS_COMMAND_PATTERNS:
            m = re.search(pattern, clean_code, flags=re.IGNORECASE)
            if m:
                line_no = clean_code.count("\n", 0, m.start()) + 1
                stable_id = f"dangerous_cmd:{pattern}:{line_no}"
                if stable_id not in seen_ids:
                    seen_ids.add(stable_id)
                    issues.append(
                        SecurityIssue(
                            severity="CRITICAL",
                            message=f"Dangerous command pattern detected: {pattern}",
                            suggestion="Remove destructive command usage.",
                            score=5,
                            line=line_no,
                            stable_id=stable_id,
                        )
                    )

        # ------------------------------------------------
        # 4. Sensitive path references (comments stripped)
        # ------------------------------------------------
        for pattern in SENSITIVE_PATH_PATTERNS:
            m = re.search(pattern, clean_code, flags=re.IGNORECASE)
            if m:
                line_no = clean_code.count("\n", 0, m.start()) + 1
                stable_id = f"sensitive_path:{pattern}:{line_no}"
                if stable_id not in seen_ids:
                    seen_ids.add(stable_id)
                    issues.append(
                        SecurityIssue(
                            severity="HIGH",
                            message=f"Sensitive system path referenced: {pattern}",
                            suggestion="Avoid accessing sensitive directories.",
                            score=3,
                            line=line_no,
                            stable_id=stable_id,
                        )
                    )

        # ------------------------------------------------
        # 5. Path traversal (comments stripped)
        # ------------------------------------------------
        m = re.search(r"\.\./", clean_code)
        if m:
            line_no = clean_code.count("\n", 0, m.start()) + 1
            stable_id = f"path_traversal:{line_no}"
            if stable_id not in seen_ids:
                seen_ids.add(stable_id)
                issues.append(
                    SecurityIssue(
                        severity="HIGH",
                        message="Potential path traversal detected (../)",
                        suggestion="Sanitize file paths.",
                        score=3,
                        line=line_no,
                        stable_id=stable_id,
                    )
                )

        # ------------------------------------------------
        # 6. Dangerous macros (comments stripped)
        # ------------------------------------------------
        for pattern in DANGEROUS_MACRO_PATTERNS:
            m = re.search(pattern, clean_code, flags=re.IGNORECASE)
            if m:
                line_no = clean_code.count("\n", 0, m.start()) + 1
                stable_id = f"macro:{pattern}:{line_no}"
                if stable_id not in seen_ids:
                    seen_ids.add(stable_id)
                    issues.append(
                        SecurityIssue(
                            severity="HIGH",
                            message="Dangerous macro detected",
                            suggestion="Avoid embedding commands in macros.",
                            score=4,
                            line=line_no,
                            stable_id=stable_id,
                        )
                    )

        # ------------------------------------------------
        # 7. Hardcoded secrets (comments stripped)
        # ------------------------------------------------
        secret_patterns = [
            r"(password|passwd|pwd)\s*=\s*\".*\"",
            r"(password|passwd|pwd)\s*=\s*\d+",
            r"(api_key|apikey|token|secret)\s*=\s*\".*\"",
            r"(api_key|apikey|token|secret)\s*=\s*\d+",
        ]

        for pattern in secret_patterns:
            m = re.search(pattern, clean_code, flags=re.IGNORECASE)
            if m:
                line_no = clean_code.count("\n", 0, m.start()) + 1
                stable_id = f"secret:{pattern}:{line_no}"
                if stable_id not in seen_ids:
                    seen_ids.add(stable_id)
                    issues.append(
                        SecurityIssue(
                            severity="HIGH",
                            message="Hardcoded secret detected",
                            suggestion="Store secrets securely (env/config).",
                            score=4,
                            line=line_no,
                            stable_id=stable_id,
                        )
                    )

        # ------------------------------------------------
        # 8. Memory allocation tracking (comments and strings stripped)
        # ------------------------------------------------
        clean_code_no_strings = strip_c_comments_and_strings(source_text)
        malloc_vars = re.findall(
            r"\b([A-Za-z_]\w*)\s*=\s*(malloc|calloc|realloc)\s*\(",
            clean_code_no_strings,
        )

        for var, _ in malloc_vars:
            if not re.search(rf"\bfree\s*\(\s*{var}\s*\)", clean_code_no_strings):
                stable_id = f"memleak:{var}"
                if stable_id not in seen_ids:
                    seen_ids.add(stable_id)
                    issues.append(
                        SecurityIssue(
                            severity="WARNING",
                            message=f"Possible memory leak: '{var}' allocated but not freed",
                            suggestion="Ensure free() is called.",
                            score=3,
                            stable_id=stable_id,
                        )
                    )

        # ------------------------------------------------
        # 9. Double free (comments and strings stripped)
        # ------------------------------------------------
        free_matches = re.findall(
            r"\bfree\s*\(\s*([A-Za-z_]\w*)\s*\)",
            clean_code_no_strings,
        )

        for var in set(free_matches):
            if free_matches.count(var) > 1:
                stable_id = f"double_free:{var}"
                if stable_id not in seen_ids:
                    seen_ids.add(stable_id)
                    issues.append(
                        SecurityIssue(
                            severity="CRITICAL",
                            message=f"Double free detected on '{var}'",
                            suggestion="Avoid freeing memory multiple times.",
                            score=5,
                            stable_id=stable_id,
                        )
                    )

        # ------------------------------------------------
        # 10. Use-after-free (heuristic, comments and strings stripped)
        # ------------------------------------------------
        for var in set(free_matches):
            if re.search(rf"\bfree\s*\(\s*{var}\s*\).*{var}", clean_code_no_strings, flags=re.DOTALL):
                stable_id = f"uaf:{var}"
                if stable_id not in seen_ids:
                    seen_ids.add(stable_id)
                    issues.append(
                        SecurityIssue(
                            severity="CRITICAL",
                            message=f"Possible use-after-free of '{var}'",
                            suggestion="Do not use memory after free().",
                            score=5,
                            stable_id=stable_id,
                        )
                    )

        # ------------------------------------------------
        # 11. Format string vulnerability (comments and strings stripped)
        # ------------------------------------------------
        format_string_matches = re.findall(
            r"\bprintf\s*\(\s*([A-Za-z_]\w*)\s*\)",
            clean_code_no_strings,
        )

        for var in format_string_matches:
            stable_id = f"format_string:{var}"
            if stable_id not in seen_ids:
                seen_ids.add(stable_id)
                issues.append(
                    SecurityIssue(
                        severity="WARNING",
                        message=f"Potential format string vulnerability using variable '{var}'",
                        suggestion='Use printf("%s", variable) instead of printf(variable).',
                        score=3,
                        stable_id=stable_id,
                    )
                )
        # Remove duplicate identical findings (Step 3c)
        unique_issues = []
        seen_findings = set()
        for issue in issues:
            key = (issue.severity, issue.message, issue.line)
            if key not in seen_findings:
                seen_findings.add(key)
                unique_issues.append(issue)
        return unique_issues