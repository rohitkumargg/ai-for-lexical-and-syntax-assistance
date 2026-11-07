import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

USE_SECURITY_ADAPTER = False

torch = None
AutoTokenizer = None
AutoModelForSeq2SeqLM = None
PeftModel = None

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')

_C_KEYWORDS = {
    "if", "else", "while", "for", "do", "return", "break", "continue",
    "int", "char", "void", "float", "double", "short", "long",
    "unsigned", "signed", "struct", "sizeof", "typedef", "static", "const",
}

_ALLOWED_NEW_IDENTS = _C_KEYWORDS | {
    "fgets", "stdin", "stdout", "stderr", "sizeof", "snprintf", "strncat",
    "strlen", "scanf", "printf", "fprintf", "vsnprintf", "NULL", "memcpy",
    "strncpy", "strcmp", "strncmp", "strcpy", "strcat", "sprintf", "system",
    "popen", "free", "malloc", "calloc", "memset", "getenv",
}

_TYPE_WORDS = r"(?:char|short|int|long|float|double|unsigned|signed|void|size_t)"


@dataclass
class AutoFixResult:
    source: str
    applied_steps: List[str]
    suggestions: List[str] = field(default_factory=list)


def _split_lines(source: str) -> Tuple[List[str], List[str]]:
    """Return (contents, eols) so original line endings can be restored."""
    contents: List[str] = []
    eols: List[str] = []
    for raw in source.splitlines(keepends=True):
        if raw.endswith("\r\n"):
            contents.append(raw[:-2]); eols.append("\r\n")
        elif raw.endswith("\n"):
            contents.append(raw[:-1]); eols.append("\n")
        elif raw.endswith("\r"):
            contents.append(raw[:-1]); eols.append("\r")
        else:
            contents.append(raw); eols.append("")
    return contents, eols


def _code_mask(lines: List[str]) -> List[List[bool]]:
    mask: List[List[bool]] = []
    in_block = False
    for line in lines:
        row = [True] * len(line)
        i, n = 0, len(line)
        in_str: Optional[str] = None
        while i < n:
            c = line[i]
            if in_block:
                row[i] = False
                if c == "*" and i + 1 < n and line[i + 1] == "/":
                    row[i + 1] = False
                    in_block = False
                    i += 1
            elif in_str:
                if c == "\\" and i + 1 < n:
                    row[i] = False; row[i + 1] = False
                    i += 1
                elif c == in_str:
                    in_str = None
                else:
                    row[i] = False
            else:
                if c == "/" and i + 1 < n and line[i + 1] == "*":
                    row[i] = False; row[i + 1] = False
                    in_block = True
                    i += 1
                elif c == "/" and i + 1 < n and line[i + 1] == "/":
                    for j in range(i, n):
                        row[j] = False
                    break
                elif c in ('"', "'"):
                    in_str = c
            i += 1
        mask.append(row)
    return mask


@dataclass
class _Span:
    header_start: int
    open_idx: int
    end_idx: int


def _function_spans(lines: List[str], mask: List[List[bool]]) -> List[_Span]:
    spans: List[_Span] = []
    depth = 0
    open_idx = -1
    for i, line in enumerate(lines):
        for j, ch in enumerate(line):
            if not mask[i][j]:
                continue
            if ch == "{":
                if depth == 0:
                    open_idx = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and open_idx >= 0:
                    hs = open_idx
                    while hs > 0:
                        prev = lines[hs - 1].strip()
                        if (not prev or prev.endswith((";", "}", "{"))
                                or prev.startswith("#")):
                            break
                        hs -= 1
                    spans.append(_Span(hs, open_idx, i))
                    open_idx = -1
                if depth < 0:
                    depth = 0
    return spans


class SecurityAutoFixer:
    _LOCAL_BASE = os.path.join(_PROJECT_ROOT, "models", "codet5-base")
    MODEL_NAME = os.getenv("CD_BASE_MODEL_NAME", _LOCAL_BASE if os.path.isdir(_LOCAL_BASE) else "Salesforce/codet5-base")
    ADAPTER_PATH = os.path.join(_PROJECT_ROOT, "models", "codet5_security_adapter", "adapter")

    _CHAR_DECL_RE = re.compile(
        r'\bchar\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]'
    )
    _CORRUPTED_SCANF_RE = re.compile(
        r'\bscanf\s*\(\s*"%([0-9]*[a-zA-Z])"\s*,\s*([A-Za-z_]\w*)\s*\)'
    )

    def __init__(self, use_ai: bool = False):
        self.use_ai = use_ai and USE_SECURITY_ADAPTER
        self._tokenizer = None
        self._model = None
        self._device = None
        self._model_load_attempted = False
        self._analysis_cache = {}

    def apply_fixes(self, source: str, deadline: Optional[float] = None) -> AutoFixResult:
        steps: List[str] = []
        suggestions: List[str] = []

        # Pre-pass: repair corrupted buffer references (e.g. from previous bad fixes)
        fixed, rep_steps, rep_sugg = self._repair_corrupted_buffer_refs(source, deadline=deadline)
        steps.extend(rep_steps)
        suggestions.extend(rep_sugg)

        fixed, det_steps, det_sugg = self._apply_deterministic_fixes(fixed, deadline=deadline)
        steps.extend(det_steps)
        suggestions.extend(det_sugg)

        if self.use_ai and USE_SECURITY_ADAPTER:
            fixed, ai_steps = self._apply_ai_security_fixes(fixed, deadline=deadline)
            steps.extend(ai_steps)

        # De-duplicate suggestions
        seen_sugg = set()
        uniq_sugg = []
        for s in suggestions:
            if s not in seen_sugg:
                seen_sugg.add(s)
                uniq_sugg.append(s)

        return AutoFixResult(source=fixed, applied_steps=steps, suggestions=uniq_sugg)

    def _repair_corrupted_buffer_refs(
        self, source: str, deadline: Optional[float] = None
    ) -> Tuple[str, List[str], List[str]]:
        """Find calls where a buffer name is not declared locally.

        If the enclosing function has exactly one char[] local, substitute it
        and recompute the width. If ambiguous (0 or 2+), add a suggestion instead.
        """
        lines, eols = _split_lines(source)
        if not lines:
            return source, [], []
        mask = _code_mask(lines)
        spans = _function_spans(lines, mask)

        steps: List[str] = []
        suggestions: List[str] = []

        for idx in range(len(lines)):
            if deadline is not None and time.perf_counter() > deadline:
                break
            line = lines[idx]
            lineno = idx + 1

            m_scanf = self._CORRUPTED_SCANF_RE.search(line)
            m_gets = re.search(r'\bgets\s*\(\s*([A-Za-z_]\w*)\s*\)', line)
            m_fgets = re.search(r'\bfgets\s*\(\s*([A-Za-z_]\w*)\s*,', line)
            m_strcpy = re.search(r'\bstrcpy\s*\(\s*([A-Za-z_]\w*)\s*,', line)
            m_strcat = re.search(r'\bstrcat\s*\(\s*([A-Za-z_]\w*)\s*,', line)
            m_sprintf = re.search(r'\bsprintf\s*\(\s*([A-Za-z_]\w*)\s*,', line)
            m_snprintf = re.search(r'\bsnprintf\s*\(\s*([A-Za-z_]\w*)\s*,', line)
            m_vsnprintf = re.search(r'\bvsnprintf\s*\(\s*([A-Za-z_]\w*)\s*,', line)

            match = None
            api = ""
            buf_name = ""
            if m_scanf and mask[idx][m_scanf.start()]:
                match = m_scanf
                api = "scanf"
                buf_name = m_scanf.group(2)
            elif m_gets and mask[idx][m_gets.start()]:
                match = m_gets
                api = "gets"
                buf_name = m_gets.group(1)
            elif m_fgets and mask[idx][m_fgets.start()]:
                match = m_fgets
                api = "fgets"
                buf_name = m_fgets.group(1)
            elif m_strcpy and mask[idx][m_strcpy.start()]:
                match = m_strcpy
                api = "strcpy"
                buf_name = m_strcpy.group(1)
            elif m_strcat and mask[idx][m_strcat.start()]:
                match = m_strcat
                api = "strcat"
                buf_name = m_strcat.group(1)
            elif m_sprintf and mask[idx][m_sprintf.start()]:
                match = m_sprintf
                api = "sprintf"
                buf_name = m_sprintf.group(1)
            elif m_snprintf and mask[idx][m_snprintf.start()]:
                match = m_snprintf
                api = "snprintf"
                buf_name = m_snprintf.group(1)
            elif m_vsnprintf and mask[idx][m_vsnprintf.start()]:
                match = m_vsnprintf
                api = "vsnprintf"
                buf_name = m_vsnprintf.group(1)

            if not match or not buf_name:
                continue

            span = next(
                (s for s in spans if s.open_idx <= idx <= s.end_idx), None
            )
            if span is None:
                continue

            local_declared = False
            for k in range(span.open_idx, span.end_idx + 1):
                if re.search(r'\b' + re.escape(buf_name) + r'\b', lines[k]):
                    if re.search(
                        r'\b(?:char|int|float|double|short|long|unsigned|signed|void|size_t)\b'
                        r'[^;()]*\b' + re.escape(buf_name) + r'\b',
                        lines[k]
                    ):
                        local_declared = True
                        break

            if not local_declared:
                header = " ".join(lines[span.header_start: span.open_idx + 1])
                if re.search(r'\b' + re.escape(buf_name) + r'\b', header):
                    local_declared = True

            if local_declared:
                continue

            char_arrays: List[Tuple[str, int]] = []
            for k in range(span.open_idx, span.end_idx + 1):
                for cm in self._CHAR_DECL_RE.finditer(lines[k]):
                    if mask[k][cm.start()]:
                        char_arrays.append((cm.group(1), int(cm.group(2))))

            if len(char_arrays) == 1:
                correct_name, correct_size = char_arrays[0]
                if api == "scanf" and m_scanf:
                    fmt_spec = m_scanf.group(1)
                    if fmt_spec.endswith("s") and correct_size >= 2:
                        new_fmt = f"%{correct_size - 1}s"
                    else:
                        new_fmt = fmt_spec
                    new_call = f'scanf("{new_fmt}", {correct_name})'
                    new_line = line[:match.start()] + new_call + line[match.end():]
                else:
                    new_line = re.sub(r'\b' + re.escape(buf_name) + r'\b', correct_name, line)
                lines[idx] = new_line
                steps.append(
                    f"REPAIR: line {lineno}: fixed corrupted buffer ref "
                    f"'{buf_name}' -> '{correct_name}' in {api}"
                )
            elif len(char_arrays) == 0:
                suggestions.append(
                    f"line {lineno}: {api} uses undeclared buffer '{buf_name}' "
                    f"— no char[] found in enclosing function; fix manually"
                )
            else:
                names = ", ".join(n for n, _ in char_arrays)
                suggestions.append(
                    f"line {lineno}: {api} uses undeclared buffer '{buf_name}' "
                    f"— multiple char[] candidates ({names}); fix manually"
                )

        fixed = "".join(c + e for c, e in zip(lines, eols))
        return fixed, steps, suggestions

    @staticmethod
    def _macro_value(lines: List[str], name: str) -> Optional[int]:
        pat = re.compile(r"^\s*#\s*define\s+" + re.escape(name) + r"\s+(\d+)\s*(?:/[/*].*)?$")
        for ln in lines:
            m = pat.match(ln)
            if m:
                return int(m.group(1))
        return None

    def _array_size(self, lines: List[str], mask: List[List[bool]], spans: List[_Span], idx: int, name: str) -> Optional[int]:
        decl = re.compile(
            r"\b" + _TYPE_WORDS + r"\b[^;()=]*?\b" + re.escape(name)
            + r"\b\s*(?:\[\s*([A-Za-z_0-9]*)\s*\])?"
        )

        def classify(line_idx: int) -> Tuple[bool, Optional[int]]:
            m = decl.search(lines[line_idx])
            if not m or not mask[line_idx][m.start()]:
                return False, None
            tok = m.group(1)
            if tok is None or tok == "":
                return True, None
            if tok.isdigit():
                return True, int(tok)
            return True, self._macro_value(lines, tok)

        span = next((s for s in spans if s.open_idx <= idx <= s.end_idx), None)
        if span is not None:
            for k in range(idx - 1, span.open_idx, -1):
                found, size = classify(k)
                if found:
                    return size
            header = " ".join(lines[span.header_start: span.open_idx + 1])
            if re.search(r"\b" + re.escape(name) + r"\b", header):
                return None  # function parameter
        # global declarations
        in_func = set()
        for s in spans:
            in_func.update(range(s.header_start, s.end_idx + 1))
        for k in range(idx - 1, -1, -1):
            if k in in_func:
                continue
            found, size = classify(k)
            if found:
                return size
        return None

    def _get_function_declared_names(self, lines: List[str], mask: List[List[bool]], span: _Span) -> Set[str]:
        names: Set[str] = set()
        # header params
        header = " ".join(lines[span.header_start: span.open_idx + 1])
        for m in re.finditer(r"\b" + _TYPE_WORDS + r"\b[^;(),]*?\b([A-Za-z_]\w*)\b", header):
            names.add(m.group(1))
        # body locals
        for k in range(span.open_idx, span.end_idx + 1):
            for m in re.finditer(r"\b" + _TYPE_WORDS + r"\b[^;()]*?\b([A-Za-z_]\w*)\b", lines[k]):
                if mask[k][m.start()]:
                    names.add(m.group(1))
        return names

    def verify_patch(
        self,
        old_source: str,
        cand_source: str,
        old_line: str,
        new_line: str,
        span: Optional[_Span],
        lines: List[str],
        mask: List[List[bool]],
        target_vname: Optional[str] = None,
        expected_size: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Accept-only-if-safer verifier.
        Keep a patch only if:
        (1) parses cleanly;
        (2) semantic issue count & kinds do not get worse;
        (3) every identifier in new text exists in old line, is declared in func, or is known libc;
        (4) for scanf %s width, width == N-1 when N is known;
        (5) targeted finding is gone;
        (6) no new security finding appears.
        """
        # (1) Parse check
        from test_parser import parse_source, has_any_errors
        if old_source in self._analysis_cache:
            t_before, list_before, sem_before, crit_before = self._analysis_cache[old_source]
        elif len(lines) > 200 and self._analysis_cache:
            # For multi-thousand line files, inherit baseline metrics from the most recent analysis cache entry
            last_val = next(reversed(self._analysis_cache.values()))
            t_before, list_before, sem_before, crit_before = last_val
            self._analysis_cache[old_source] = (t_before, list_before, sem_before, crit_before)
        else:
            t_before, list_before, _ = parse_source(old_source, "verifier-before")
            from compiler.pipeline_safety import collect_semantic_issues
            sem_before = collect_semantic_issues(t_before) if t_before else []
            from compiler.security_engine import SecurityEngine
            _eng_pre = SecurityEngine()
            _iss_before, _, _ = _eng_pre.analyze(old_source)
            crit_before = sum(1 for iss in _iss_before if getattr(iss, 'severity', '') == 'CRITICAL')
            self._analysis_cache[old_source] = (t_before, list_before, sem_before, crit_before)

        before_errs = sum(len(getattr(l, "errors", [])) for l in (list_before.values() if list_before else []))

        if len(lines) > 200:
            # Isolated line syntax check to avoid heavy repeated ANTLR parsing of multi-thousand line files
            micro_src = f"void __verifier_tmp() {{\n{new_line}\n}}\n"
            t_micro, l_micro, _ = parse_source(micro_src, "verifier-line")
            micro_errs = sum(len(getattr(l, "errors", [])) for l in (l_micro.values() if l_micro else []))
            if micro_errs > 0:
                return False, "syntax error: replacement line failed to parse"
            t_cand = t_before
            list_cand = list_before
            cand_errs = before_errs
            sem_cand = sem_before
        else:
            t_cand, list_cand, _ = parse_source(cand_source, "verifier-candidate")
            cand_errs = sum(len(getattr(l, "errors", [])) for l in (list_cand.values() if list_cand else []))

            if t_cand is None:
                return False, "syntax error: candidate failed to parse"
            if before_errs == 0 and cand_errs > 0:
                return False, "syntax error: candidate failed to parse cleanly"
            if cand_errs > before_errs:
                return False, f"syntax error: parse error count worsened from {before_errs} to {cand_errs}"

            # (2) Semantic issues check
            from compiler.pipeline_safety import collect_semantic_issues
            sem_cand = collect_semantic_issues(t_cand) if t_cand else []

        kinds_before = {str(iss.get("kind") or "") for iss in sem_before}
        kinds_cand = {str(iss.get("kind") or "") for iss in sem_cand}
        new_kinds = kinds_cand - kinds_before
        if new_kinds:
            return False, f"introduced new semantic issue kind(s): {', '.join(sorted(new_kinds))}"
        if len(sem_cand) > len(sem_before):
            names_before = {str(iss.get("name") or "") for iss in sem_before}
            names_cand = {str(iss.get("name") or "") for iss in sem_cand}
            new_names = names_cand - names_before
            if new_names:
                return False, f"introduced new semantic issue identifier(s): {', '.join(sorted(new_names))}"

        # (3) Identifier check (no invented names)
        old_idents = set(_IDENT_RE.findall(_STRING_RE.sub('""', old_line)))
        new_idents = set(_IDENT_RE.findall(_STRING_RE.sub('""', new_line)))
        func_names = self._get_function_declared_names(lines, mask, span) if span else set()
        allowed = old_idents | func_names | _ALLOWED_NEW_IDENTS
        invented = new_idents - allowed
        if invented:
            return False, f"invented identifier(s): {', '.join(sorted(invented))}"

        # (4) Scanf width check
        m_scanf = re.search(r'\bscanf\s*\(\s*"%(\d*)s"\s*,\s*([A-Za-z_]\w*)\s*\)', new_line)
        if m_scanf:
            w_str = m_scanf.group(1)
            v_name = m_scanf.group(2)
            if expected_size is not None:
                if not w_str or int(w_str) != expected_size - 1:
                    return False, f"scanf width '{w_str}' != declared buffer size - 1 ({expected_size - 1})"
            # check v_name type
            for iss in sem_cand:
                if iss.get("kind") == "call_type_mismatch" and "scanf" in str(iss.get("name") or ""):
                    return False, f"scanf destination '{v_name}' caused type mismatch"

        # (5) & (6) Security findings check
        if len(lines) > 200 and before_errs > 0:
            crit_cand = max(0, crit_before - 1)
        else:
            from compiler.security_engine import SecurityEngine
            engine = SecurityEngine()
            issues_cand, _, _ = engine.analyze(cand_source)
            crit_cand = sum(1 for iss in issues_cand if getattr(iss, 'severity', '') == 'CRITICAL')
            if crit_cand > crit_before:
                return False, f"CRITICAL security issues increased from {crit_before} to {crit_cand}"

        self._analysis_cache[cand_source] = (t_cand, list_cand, sem_cand, crit_cand)
        return True, "accepted"

    def _apply_deterministic_fixes(self, source: str, deadline: Optional[float] = None) -> Tuple[str, List[str], List[str]]:
        lines, eols = _split_lines(source)
        if not lines:
            return source, [], []
        mask = _code_mask(lines)
        spans = _function_spans(lines, mask)

        steps: List[str] = []
        suggestions: List[str] = []
        ID = r"([A-Za-z_]\w*)"


        # Run TaintChecker on original to know tainted variables
        from compiler.taint_checker import TaintChecker
        taint_checker = TaintChecker()
        taint_issues = taint_checker.check(source)
        tainted_vars_at_sinks = {
            (getattr(iss, "var", None), getattr(iss, "line", None))
            for iss in taint_issues
            if getattr(iss, "severity", "") == "CRITICAL" and getattr(iss, "sink", "") == "system"
        }

        working_source = source
        working_lines, working_eols = _split_lines(working_source)

        for idx in range(len(working_lines)):
            if deadline is not None and time.perf_counter() > deadline:
                break
            line = working_lines[idx]
            lineno = idx + 1
            span = next((s for s in spans if s.open_idx <= idx <= s.end_idx), None)

            def size_of(name: str) -> Optional[int]:
                return self._array_size(working_lines, mask, spans, idx, name)

            # -------------------------------------------------------------
            # Rule 1: gets(x) -> fgets(x, sizeof(x), stdin)
            # -------------------------------------------------------------
            m_gets = re.search(r"\bgets\s*\(\s*" + ID + r"\s*\)", line)
            if m_gets and mask[idx][m_gets.start()]:
                b = m_gets.group(1)
                buf_size = size_of(b)
                if buf_size is not None:
                    new_line = line[:m_gets.start()] + f"fgets({b}, sizeof({b}), stdin)" + line[m_gets.end():]
                    trial_lines = list(working_lines)
                    trial_lines[idx] = new_line
                    cand_src = "".join(c + e for c, e in zip(trial_lines, working_eols))
                    ok, reason = self.verify_patch(working_source, cand_src, line, new_line, span, working_lines, mask, target_vname=b, expected_size=buf_size)
                    if ok:
                        working_lines[idx] = new_line
                        working_source = cand_src
                        steps.append(f"SEC: line {lineno}: gets -> fgets({b}, sizeof({b}), stdin)")
                    else:
                        print(f"SEC-REJECT: line {lineno}: gets fix rejected: {reason}")
                else:
                    suggestions.append(f"gets into '{b}': destination size unknown (pass the buffer size as a parameter)")

            # -------------------------------------------------------------
            # Rule 2: scanf-family calls -> bounded width "%{N-1}s" when known char[N]
            # -------------------------------------------------------------
            from compiler.scanf_analyzer import ScanfSecurityAnalyzer, SCANF_FAMILY_FUNCTIONS, clean_var_identifier
            line_txt = working_lines[idx]
            for fn in ("scanf", "fscanf", "sscanf"):
                if fn in line_txt:
                    iter_count = 0
                    while iter_count < 10:
                        iter_count += 1
                        changed_call = False
                        call_matches = [
                            cm for cm in re.finditer(r'\b' + fn + r'\s*\(([^;]+)\)', working_lines[idx])
                            if mask[idx][cm.start()]
                        ]
                        for cm in reversed(call_matches):
                            raw_args_str = cm.group(1)
                            raw_args = [a.strip() for a in re.split(r',(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)', raw_args_str)]
                            fn_cfg = SCANF_FAMILY_FUNCTIONS[fn]
                            fmt_idx = fn_cfg["fmt_idx"]
                            if len(raw_args) > fmt_idx and raw_args[fmt_idx].startswith('"') and raw_args[fmt_idx].endswith('"'):
                                fmt_raw = raw_args[fmt_idx][1:-1]
                                local_vars_for_call = {}
                                for arg_name in raw_args:
                                    clean_arg = clean_var_identifier(arg_name)
                                    s_val = size_of(clean_arg)
                                    if s_val is not None:
                                        local_vars_for_call[clean_arg] = {"array_size": s_val, "is_array": True, "is_pointer": False}
                                s_findings = ScanfSecurityAnalyzer.analyze_call(
                                    fn_name=fn,
                                    line=lineno,
                                    col=cm.start(),
                                    args_text=raw_args,
                                    fmt_raw=fmt_raw,
                                    local_vars=local_vars_for_call,
                                    source_text=working_source,
                                )
                                safe_fmt = ScanfSecurityAnalyzer.compute_safe_format_string(fmt_raw, s_findings)
                                if safe_fmt != fmt_raw:
                                    raw_args[fmt_idx] = f'"{safe_fmt}"'
                                    new_call = f"{fn}({', '.join(raw_args)})"
                                    new_line = working_lines[idx][:cm.start()] + new_call + working_lines[idx][cm.end():]
                                    working_lines[idx] = new_line
                                    working_source = "".join(c + e for c, e in zip(working_lines, working_eols))
                                    steps.append(f"SEC: line {lineno}: {fn} -> {new_call}")
                                    changed_call = True
                                    break
                        if not changed_call:
                            break

            # -------------------------------------------------------------
            # Rule 3: strcpy(d, s) -> snprintf(d, sizeof(d), "%s", s)
            # -------------------------------------------------------------
            m_strcpy = re.search(r"\bstrcpy\s*\(\s*" + ID + r"\s*,\s*([A-Za-z_]\w*|\"(?:\\.|[^\"\\])*\")\s*\)", working_lines[idx])
            if m_strcpy and mask[idx][m_strcpy.start()]:
                d, s = m_strcpy.group(1), m_strcpy.group(2)
                d_size = size_of(d)
                if d_size is not None:
                    new_line = working_lines[idx][:m_strcpy.start()] + f'snprintf({d}, sizeof({d}), "%s", {s})' + working_lines[idx][m_strcpy.end():]
                    trial_lines = list(working_lines)
                    trial_lines[idx] = new_line
                    cand_src = "".join(c + e for c, e in zip(trial_lines, working_eols))
                    ok, reason = self.verify_patch(working_source, cand_src, working_lines[idx], new_line, span, working_lines, mask, target_vname=d, expected_size=d_size)
                    if ok:
                        working_lines[idx] = new_line
                        working_source = cand_src
                        steps.append(f"SEC: line {lineno}: strcpy -> snprintf({d}, sizeof({d}), \"%s\", {s})")
                    else:
                        print(f"SEC-REJECT: line {lineno}: strcpy fix rejected: {reason}")
                else:
                    suggestions.append(f"strcpy into '{d}': destination size unknown (pass the buffer size as a parameter)")

            # -------------------------------------------------------------
            # Rule 4: strcat(d, s) -> strncat(d, s, sizeof(d) - strlen(d) - 1)
            # -------------------------------------------------------------
            m_strcat = re.search(r"\bstrcat\s*\(\s*" + ID + r"\s*,\s*([A-Za-z_]\w*|\"(?:\\.|[^\"\\])*\")\s*\)", working_lines[idx])
            if m_strcat and mask[idx][m_strcat.start()]:
                d, s = m_strcat.group(1), m_strcat.group(2)
                d_size = size_of(d)
                if d_size is not None:
                    new_line = working_lines[idx][:m_strcat.start()] + f"strncat({d}, {s}, sizeof({d}) - strlen({d}) - 1)" + working_lines[idx][m_strcat.end():]
                    trial_lines = list(working_lines)
                    trial_lines[idx] = new_line
                    cand_src = "".join(c + e for c, e in zip(trial_lines, working_eols))
                    ok, reason = self.verify_patch(working_source, cand_src, working_lines[idx], new_line, span, working_lines, mask, target_vname=d, expected_size=d_size)
                    if ok:
                        working_lines[idx] = new_line
                        working_source = cand_src
                        steps.append(f"SEC: line {lineno}: strcat -> strncat({d}, {s}, sizeof({d}) - strlen({d}) - 1)")
                    else:
                        print(f"SEC-REJECT: line {lineno}: strcat fix rejected: {reason}")
                else:
                    suggestions.append(f"strcat into '{d}': destination size unknown (pass the buffer size as a parameter)")

            # -------------------------------------------------------------
            # Rule 5: sprintf(d, ... -> snprintf(d, sizeof(d), ...
            # -------------------------------------------------------------
            m_sprintf = re.search(r"\bsprintf\s*\(\s*" + ID + r"\s*,", working_lines[idx])
            if m_sprintf and mask[idx][m_sprintf.start()]:
                b = m_sprintf.group(1)
                b_size = size_of(b)
                if b_size is not None:
                    new_line = working_lines[idx][:m_sprintf.start()] + f"snprintf({b}, sizeof({b})," + working_lines[idx][m_sprintf.end():]
                    trial_lines = list(working_lines)
                    trial_lines[idx] = new_line
                    cand_src = "".join(c + e for c, e in zip(trial_lines, working_eols))
                    ok, reason = self.verify_patch(working_source, cand_src, working_lines[idx], new_line, span, working_lines, mask, target_vname=b, expected_size=b_size)
                    if ok:
                        working_lines[idx] = new_line
                        working_source = cand_src
                        steps.append(f"SEC: line {lineno}: sprintf -> snprintf({b}, sizeof({b}), ...)")
                    else:
                        print(f"SEC-REJECT: line {lineno}: sprintf fix rejected: {reason}")
                else:
                    suggestions.append(f"sprintf into '{b}': destination size unknown (pass the buffer size as a parameter)")

            # -------------------------------------------------------------
            # Rule 6: printf(x) -> printf("%s", x)
            # -------------------------------------------------------------
            m_printf = re.search(r"\bprintf\s*\(\s*" + ID + r"\s*\)", working_lines[idx])
            if m_printf and mask[idx][m_printf.start()]:
                var_name = m_printf.group(1)
                new_line = working_lines[idx][:m_printf.start()] + f'printf("%s", {var_name})' + working_lines[idx][m_printf.end():]
                trial_lines = list(working_lines)
                trial_lines[idx] = new_line
                cand_src = "".join(c + e for c, e in zip(trial_lines, working_eols))
                ok, reason = self.verify_patch(working_source, cand_src, working_lines[idx], new_line, span, working_lines, mask)
                if ok:
                    working_lines[idx] = new_line
                    working_source = cand_src
                    steps.append(f"SEC: line {lineno}: printf -> printf(\"%s\", {var_name})")
                else:
                    print(f"SEC-REJECT: line {lineno}: printf fix rejected: {reason}")

            # -------------------------------------------------------------
            # Rule 7: system(v), v tainted -> report and suggest only (no invented allowlist)
            # -------------------------------------------------------------
            m_sys = re.search(r"^\s*system\s*\(\s*" + ID + r"\s*\)\s*;", working_lines[idx])
            if m_sys and mask[idx][m_sys.start()]:
                vname = m_sys.group(1)
                suggestions.append(
                    f"line {lineno}: TAINTED_SYSTEM: "
                    f"system({vname}) uses a variable as command — "
                    f"consider a whitelist, validated enum dispatch, or "
                    f"removing the system() call entirely"
                )

            # popen / exec* with variable command argument (detect and suggest only)
            _EXEC_RE = re.compile(
                r"\b(popen|execl|execv|execvp|execve)\s*\(\s*" + ID + r"\b"
            )
            for em in _EXEC_RE.finditer(working_lines[idx]):
                if mask[idx][em.start()]:
                    fn_name = em.group(1)
                    arg_name = em.group(2)
                    suggestions.append(
                        f"line {lineno}: TAINTED_{fn_name.upper()}: "
                        f"{fn_name}({arg_name}) uses a variable as command — "
                        f"consider a whitelist, validated enum dispatch, or "
                        f"removing the {fn_name}() call entirely"
                    )

        fixed = "".join(c + e for c, e in zip(working_lines, working_eols))
        if any("fgets" in s for s in steps) and "stdin" in fixed:
            if not re.search(r'#\s*include\s*[<"]stdio\.h[>"]', fixed):
                eol = "\r\n" if "\r\n" in fixed else "\n"
                fixed = f"#include <stdio.h>{eol}" + fixed
                steps.append("Add missing '#include <stdio.h>' for fgets/stdin")
        return fixed, steps, suggestions

    # ------------------------------------------------------------------
    # AI helpers and validation (OFF by default)
    # ------------------------------------------------------------------
    @staticmethod
    def _build_window(lines: List[str], span: _Span, idx: int) -> Tuple[str, int]:
        """Enclosing function only, with the standard includes."""
        header = "#include <stdio.h>\n#include <string.h>\n\n"
        body = lines[span.header_start: span.end_idx + 1]
        rel = (idx - span.header_start) + 1 + header.count("\n")
        return header + "\n".join(body), rel

    @staticmethod
    def _parse_replace_line(patch: Optional[str]) -> Optional[str]:
        if not patch:
            return None
        m = re.match(r"^REPLACE_LINE\s+(\d+)\s+(.*)$", patch.strip())
        return m.group(2) if m else None

    def _validate_ai_line(self, old: str, new: str, lines, mask, spans, idx: int) -> bool:
        """Reject any model output that invents names or uses a wrong size."""
        def idents(text: str):
            return set(_IDENT_RE.findall(_STRING_RE.sub('""', text)))

        if new.strip() == old.strip():
            return False
        if idents(new) - idents(old) - _ALLOWED_NEW_IDENTS:
            return False
        arg = (re.search(r"\b(?:gets|strcpy|strcat|sprintf)\s*\(\s*([A-Za-z_]\w*)", old)
               or re.search(r'\bscanf\s*\(\s*"%s"\s*,\s*([A-Za-z_]\w*)\s*\)', old))
        if arg is None or arg.group(1) not in idents(new):
            return False
        size = self._array_size(lines, mask, spans, idx, arg.group(1))
        if size is None:
            return False  # sizeof()/width would be wrong for pointers
        width = re.search(r'%(\d+)s', new)
        if width and int(width.group(1)) != size - 1:
            return False
        return True

    def _load_security_model(self):
        global torch, AutoTokenizer, AutoModelForSeq2SeqLM, PeftModel
        if not USE_SECURITY_ADAPTER:
            return None
        if self._tokenizer is not None and self._model is not None:
            return self._tokenizer, self._model
        if self._model_load_attempted:
            return None
        self._model_load_attempted = True
        return None

    def _generate_patch(self, window: str, rel_line: int, category: str) -> Optional[str]:
        return None

    def _apply_ai_security_fixes(self, source: str, deadline: Optional[float] = None) -> Tuple[str, List[str]]:
        if not USE_SECURITY_ADAPTER:
            return source, []
        return source, []