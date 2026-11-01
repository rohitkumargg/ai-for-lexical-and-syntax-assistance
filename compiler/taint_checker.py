import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from compiler.call_extractor import strip_c_comments_and_strings
from compiler.cwe_catalog import CWE_CATALOG, get_cwe_details


DANGEROUS_SINKS = [
    "system",
    "popen",
    "execl",
    "execv",
    "execvp",
    "execve",
    "execlp",
    "execle",
    "execvpe",
    "WinExec",
    "ShellExecute",
    "CreateProcess",
]

INPUT_APIS = ["scanf", "gets", "fgets", "read", "recv", "recvfrom", "getenv"]


@dataclass
class TaintIssue:
    severity: str
    message: str
    suggestion: str
    score: int
    line: Optional[int] = None
    col: Optional[int] = None
    sink: Optional[str] = None
    var: Optional[str] = None
    source: Optional[str] = None
    source_line: Optional[int] = None
    sink_line: Optional[int] = None
    cwe: str = "CWE-78"
    stable_id: Optional[str] = None


def _build_code_mask(text: str) -> List[bool]:
    """Return a boolean mask where True means code (not comment or string literal content)."""
    n = len(text)
    mask = [True] * n
    i = 0
    in_line_comment = False
    in_block_comment = False
    in_string = False
    in_char = False

    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_line_comment:
            mask[i] = False
            if c == "\n":
                in_line_comment = False
            i += 1
        elif in_block_comment:
            mask[i] = False
            if c == "*" and nxt == "/":
                mask[i + 1] = False
                in_block_comment = False
                i += 2
            else:
                i += 1
        elif in_string:
            if c == "\\":
                mask[i] = False
                if i + 1 < n:
                    mask[i + 1] = False
                    i += 2
                else:
                    i += 1
            elif c == '"':
                in_string = False
                i += 1
            else:
                mask[i] = False
                i += 1
        elif in_char:
            if c == "\\":
                mask[i] = False
                if i + 1 < n:
                    mask[i + 1] = False
                    i += 2
                else:
                    i += 1
            elif c == "'":
                in_char = False
                i += 1
            else:
                mask[i] = False
                i += 1
        else:
            if c == "/" and nxt == "/":
                mask[i] = False
                mask[i + 1] = False
                in_line_comment = True
                i += 2
            elif c == "/" and nxt == "*":
                mask[i] = False
                mask[i + 1] = False
                in_block_comment = True
                i += 2
            elif c == '"':
                in_string = True
                i += 1
            elif c == "'":
                in_char = True
                i += 1
            else:
                i += 1

    return mask


@dataclass
class _FuncDef:
    name: str
    header_start: int
    open_brace: int
    close_brace: int
    body: str


def _extract_functions(source_text: str) -> List[_FuncDef]:
    """Find all top-level functions using brace matching."""
    mask = _build_code_mask(source_text)
    funcs: List[_FuncDef] = []
    n = len(source_text)
    i = 0
    depth = 0
    func_start = 0
    open_idx = -1

    while i < n:
        if not mask[i]:
            i += 1
            continue

        ch = source_text[i]
        if ch == "{":
            if depth == 0:
                open_idx = i
                # Look backwards for function signature
                hdr_start = i
                while hdr_start > 0:
                    prev_char = source_text[hdr_start - 1]
                    if prev_char in (";", "}", "{") and mask[hdr_start - 1]:
                        break
                    hdr_start -= 1
                func_start = hdr_start
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and open_idx != -1:
                close_idx = i
                header = source_text[func_start:open_idx]
                m_fn = re.search(r"\b([A-Za-z_]\w*)\s*\([^;]*\)\s*$", header.strip())
                fn_name = m_fn.group(1) if m_fn else "func"
                funcs.append(_FuncDef(
                    name=fn_name,
                    header_start=func_start,
                    open_brace=open_idx,
                    close_brace=close_idx,
                    body=source_text[open_idx:close_idx + 1]
                ))
                open_idx = -1
            elif depth < 0:
                depth = 0
        i += 1

    return funcs


class TaintChecker:
    def check(self, source_text: str) -> List[TaintIssue]:
        issues: List[TaintIssue] = []
        seen_ids: Set[str] = set()

        funcs = _extract_functions(source_text)
        if not funcs:
            funcs = [_FuncDef(
                name="global",
                header_start=0,
                open_brace=0,
                close_brace=len(source_text) - 1,
                body=source_text
            )]

        # Discover local wrapper functions that invoke command execution sinks
        wrapper_sinks = self._discover_wrapper_sinks(source_text, funcs)

        for func in funcs:
            func_issues = self._analyze_function(source_text, func, wrapper_sinks=wrapper_sinks)
            for iss in func_issues:
                if iss.stable_id and iss.stable_id not in seen_ids:
                    seen_ids.add(iss.stable_id)
                    issues.append(iss)
                elif not iss.stable_id:
                    issues.append(iss)

        return issues

    def _discover_wrapper_sinks(self, full_source: str, funcs: List[_FuncDef]) -> Dict[str, Dict[str, Any]]:
        """Identify local functions that act as wrappers for command execution sinks."""
        wrapper_sinks: Dict[str, Dict[str, Any]] = {}
        for func in funcs:
            if func.name in ("main", "global"):
                continue
            hdr = full_source[func.header_start:func.open_brace]
            # Extract formal parameter names
            params: List[str] = []
            for p_m in re.finditer(r"\b(?:const\s+)?(?:char|int|void)\b\s*\*+\s*([A-Za-z_]\w*)", hdr):
                params.append(p_m.group(1))
            if not params:
                for p_m in re.finditer(r"\b(?:const\s+)?char\s+([A-Za-z_]\w*)\s*\[", hdr):
                    params.append(p_m.group(1))

            body_clean = strip_c_comments_and_strings(func.body)
            for idx, p_name in enumerate(params):
                for sink in DANGEROUS_SINKS:
                    # Direct sink call or call via variable assigned from p_name
                    if re.search(rf"\b{re.escape(sink)}\s*\([^;)]*\b{re.escape(p_name)}\b", body_clean):
                        m_sink = re.search(rf"\b{re.escape(sink)}\s*\(", func.body)
                        sink_pos = func.open_brace + (m_sink.start() if m_sink else 0)
                        sink_l = full_source.count("\n", 0, sink_pos) + 1
                        wrapper_sinks[func.name] = {
                            "param_idx": idx,
                            "sink": sink,
                            "sink_line": sink_l,
                            "wrapper_fn": func.name,
                        }
                        break
                if func.name in wrapper_sinks:
                    break
        return wrapper_sinks

    def _analyze_function(
        self,
        full_source: str,
        func: _FuncDef,
        wrapper_sinks: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[TaintIssue]:
        body = func.body
        body_start = func.open_brace
        header = full_source[func.header_start:func.open_brace]
        issues: List[TaintIssue] = []
        wrappers = wrapper_sinks or {}

        # Tainted variables: name -> {"source": source_str, "line": int}
        tainted: Dict[str, Dict[str, Any]] = {}

        # 1. Check if argv is present in function signature or body
        if "argv" in header or re.search(r"\bargv\b", body):
            hdr_line = full_source.count("\n", 0, func.header_start) + 1
            tainted["argv"] = {"source": "argv", "line": hdr_line}

        clean_body = strip_c_comments_and_strings(body)

        # 2. Extract input sources
        # (a) scanf calls - includes %s, %49s, %[^...], %49[^...]
        for m in re.finditer(r'\bscanf\s*\(\s*"([^"]*)"\s*,\s*([^;)]+)\)', body):
            fmt_str = m.group(1)
            raw_args = m.group(2)
            call_pos = body_start + m.start()
            line_no = full_source.count("\n", 0, call_pos) + 1

            args = [a.strip() for a in raw_args.split(",")]
            specs = list(re.finditer(r"%(\*?)([0-9]*)(?:hh|h|ll|l|j|z|t|L)?([%diuoxXfFeEgGaAcspn\[])", fmt_str))

            for idx, spec_m in enumerate(specs):
                conv = spec_m.group(3)
                if idx < len(args):
                    arg = args[idx]
                    var_m = re.search(r"&?([A-Za-z_]\w*)", arg)
                    if var_m:
                        vname = var_m.group(1)
                        # String conversions taint the buffer regardless of width limits (e.g. %49s limits overflow, not injection)
                        if conv in ("s", "["):
                            tainted[vname] = {"source": "scanf", "line": line_no}
                        elif conv in ("d", "i", "u", "x", "X", "f", "e", "g", "c", "p"):
                            if vname in tainted and tainted[vname].get("source") == "scanf":
                                del tainted[vname]

        # (b) gets(var)
        for m in re.finditer(r'\bgets\s*\(\s*([A-Za-z_]\w*)\s*\)', clean_body):
            vname = m.group(1)
            call_pos = body_start + m.start()
            line_no = full_source.count("\n", 0, call_pos) + 1
            tainted[vname] = {"source": "gets", "line": line_no}

        # (c) fgets(var, ...)
        for m in re.finditer(r'\bfgets\s*\(\s*([A-Za-z_]\w*)\s*,', clean_body):
            vname = m.group(1)
            call_pos = body_start + m.start()
            line_no = full_source.count("\n", 0, call_pos) + 1
            tainted[vname] = {"source": "fgets", "line": line_no}

        # (d) read(fd, var, ...)
        for m in re.finditer(r'\bread\s*\(\s*[^,]+\s*,\s*&?([A-Za-z_]\w*)', clean_body):
            vname = m.group(1)
            call_pos = body_start + m.start()
            line_no = full_source.count("\n", 0, call_pos) + 1
            tainted[vname] = {"source": "read", "line": line_no}

        # (e) v = getenv(...)
        for m in re.finditer(r'\b([A-Za-z_]\w*)\s*=\s*getenv\s*\(', clean_body):
            vname = m.group(1)
            call_pos = body_start + m.start()
            line_no = full_source.count("\n", 0, call_pos) + 1
            tainted[vname] = {"source": "getenv", "line": line_no}

        # (f) strcpy(v, getenv(...))
        for m in re.finditer(r'\b(?:strcpy|strncpy)\s*\(\s*([A-Za-z_]\w*)\s*,\s*getenv\s*\(', clean_body):
            vname = m.group(1)
            call_pos = body_start + m.start()
            line_no = full_source.count("\n", 0, call_pos) + 1
            tainted[vname] = {"source": "getenv", "line": line_no}

        # 3. Intra-function propagation (loop until fixed point)
        changed = True
        iterations = 0
        while changed and iterations < 12:
            changed = False
            iterations += 1

            # (i) Variable assignments: lhs = rhs; (covers renaming, pointers)
            for m in re.finditer(r'\b([A-Za-z_]\w*)\s*=\s*([^;]+);', body):
                lhs = m.group(1)
                rhs = m.group(2)
                if lhs not in tainted:
                    for t_var, t_info in list(tainted.items()):
                        if re.search(rf'\b{re.escape(t_var)}\b', rhs):
                            tainted[lhs] = {"source": t_info["source"], "line": t_info["line"]}
                            changed = True
                            break

            # (ii) String copy / concat: strcpy, strncpy, strcat, strncat, memcpy
            for m in re.finditer(r'\b(strcpy|strncpy|strcat|strncat|memcpy)\s*\(\s*([A-Za-z_]\w*)\s*,\s*([^,;)]+)', body):
                dst = m.group(2)
                src_expr = m.group(3)
                if dst not in tainted:
                    for t_var, t_info in list(tainted.items()):
                        if re.search(rf'\b{re.escape(t_var)}\b', src_expr):
                            tainted[dst] = {"source": t_info["source"], "line": t_info["line"]}
                            changed = True
                            break

            # (iii) String formatting: snprintf, sprintf from tainted buffer (parenthesis-aware)
            for m in re.finditer(r'\b(snprintf|sprintf)\s*\(\s*([A-Za-z_]\w*)\s*,', body):
                dst = m.group(2)
                start_p = m.end()
                d_p = 1
                curr_p = start_p
                while curr_p < len(body) and d_p > 0:
                    if body[curr_p] == '(':
                        d_p += 1
                    elif body[curr_p] == ')':
                        d_p -= 1
                    curr_p += 1
                rest = body[start_p:max(start_p, curr_p - 1)]
                if dst not in tainted:
                    for t_var, t_info in list(tainted.items()):
                        if re.search(rf'\b{re.escape(t_var)}\b', rest):
                            tainted[dst] = {"source": t_info["source"], "line": t_info["line"]}
                            changed = True
                            break

        # 4. Check command execution sinks (built-ins + local wrapper functions)
        all_sink_names = list(DANGEROUS_SINKS) + list(wrappers.keys())
        sink_regex = re.compile(
            r'\b(' + '|'.join(re.escape(s) for s in all_sink_names) + r')\s*\(([^;)]*)\)'
        )

        cwe78_meta = CWE_CATALOG.get("CWE-78", get_cwe_details("CWE-78"))

        for m in sink_regex.finditer(body):
            sink_called = m.group(1)
            raw_args = m.group(2).strip()
            call_start = body_start + m.start()

            # Skip function declarations / prototypes
            prefix = body[:m.start()].rstrip()
            if prefix.endswith(("int", "void", "char", "short", "long", "float", "double", "size_t")):
                continue

            call_line_no = full_source.count("\n", 0, call_start) + 1
            col_no = call_start - full_source.rfind("\n", 0, call_start)

            # Determine actual underlying sink and target argument index
            if sink_called in wrappers:
                target_sink = wrappers[sink_called]["sink"]
                target_arg_idx = wrappers[sink_called]["param_idx"]
                sink_line_no = call_line_no
            else:
                target_sink = sink_called
                target_arg_idx = 0
                sink_line_no = call_line_no

            args = [a.strip() for a in raw_args.split(",")]
            if target_arg_idx < len(args):
                arg_expr = args[target_arg_idx]
            else:
                arg_expr = raw_args

            # Check if argument is a constant string literal (e.g. system("ls"))
            if re.fullmatch(r'"(?:\\.|[^"\\])*"', arg_expr):
                stable_id = f"cmd_const:{target_sink}:{sink_line_no}"
                issues.append(TaintIssue(
                    severity="LOW",
                    message=f"Shell call with constant command: {target_sink}() called with constant string literal",
                    suggestion=cwe78_meta["mitigation"],
                    score=2,
                    line=sink_line_no,
                    col=col_no,
                    sink=target_sink,
                    sink_line=sink_line_no,
                    cwe="CWE-78",
                    stable_id=stable_id,
                ))
                continue

            # Extract variable identifier from argument expression
            v_match = re.search(r"&?([A-Za-z_]\w*)", arg_expr)
            var_name = v_match.group(1) if v_match else None

            # Check taint flow
            is_tainted = False
            src_info = None
            if var_name and var_name in tainted:
                is_tainted = True
                src_info = tainted[var_name]
            elif "argv" in arg_expr and "argv" in tainted:
                is_tainted = True
                src_info = tainted["argv"]
                var_name = "argv"

            if is_tainted and src_info:
                src_name = src_info.get("source", "input")
                src_line = src_info.get("line", call_line_no)
                stable_id = f"taint:{var_name}:{target_sink}:{sink_line_no}"
                msg = f"CWE-78 OS command injection: input flows from line {src_line} to {target_sink}() at line {sink_line_no} (source line {src_line} -> sink line {sink_line_no})"
                issues.append(TaintIssue(
                    severity="CRITICAL",
                    message=msg,
                    suggestion=cwe78_meta["mitigation"],
                    score=5,
                    line=sink_line_no,
                    col=col_no,
                    sink=target_sink,
                    var=var_name,
                    source=src_name,
                    source_line=src_line,
                    sink_line=sink_line_no,
                    cwe="CWE-78",
                    stable_id=stable_id,
                ))
            else:
                # Variable argument without confirmed taint path
                stable_id = f"cmd_var:{target_sink}:{sink_line_no}"
                issues.append(TaintIssue(
                    severity="WARNING",
                    message=f"Command execution sink '{target_sink}()' called with variable argument at line {sink_line_no}",
                    suggestion=cwe78_meta["mitigation"],
                    score=3,
                    line=sink_line_no,
                    col=col_no,
                    sink=target_sink,
                    var=var_name,
                    sink_line=sink_line_no,
                    cwe="CWE-78",
                    stable_id=stable_id,
                ))

        return issues
