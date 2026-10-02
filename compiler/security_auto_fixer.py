"""
SecurityAutoFixer (v2)

Why this was rewritten
----------------------
The previous version asked the CodeT5 security adapter to rewrite the line
FIRST, sending the WHOLE file truncated to 256 tokens.  The adapter was
trained on 13-15 line programs, so on real files it never saw the unsafe
line and copied names from unrelated code, producing things like
    scanf("%11s", arr);                  (arr belongs to another function)
    snprintf(a, sizeof(a), "%s", a);     (a belongs to another function)
    fgets(str, sizeof(str), stdin);      (str does not exist)
and the pipeline applied them with no validation.

New design (deterministic first, ML only as a validated, optional fallback):
  1. Every fix is symbol-aware: the buffer must be a real ARRAY declared in
     the enclosing function (or a global), so sizeof()/widths are correct.
     Function parameters (pointers) and unknown sizes are NEVER auto-fixed;
     they are reported as suggestions instead.
  2. The ML adapter is OFF by default (use_ai=False).  When enabled it only
     sees the enclosing function (like its training data) and its output is
     rejected unless it introduces no identifier absent from the original
     line and uses the declared buffer size.
  3. Output keeps the file's original line endings (CRLF stays CRLF).
  4. Fixes are idempotent.

Never auto-fixed (detect/suggest only): tainted system()/exec flows,
hardcoded secrets, path traversal, ownership/lifetime issues.
"""
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    from peft import PeftModel
except Exception:  # model stack is optional
    torch = None
    AutoTokenizer = None
    AutoModelForSeq2SeqLM = None
    PeftModel = None


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')

# Identifiers an AI-produced replacement line is allowed to introduce.
_ALLOWED_NEW_IDENTS = {
    "fgets", "stdin", "stdout", "stderr", "sizeof", "snprintf", "strncat",
    "strlen", "scanf", "printf", "fprintf", "vsnprintf", "NULL", "memcpy",
    "strncpy",
}

_TYPE_WORDS = r"(?:char|short|int|long|float|double|unsigned|signed|void|size_t)"


@dataclass
class AutoFixResult:
    source: str
    applied_steps: List[str]
    suggestions: List[str] = field(default_factory=list)


# ----------------------------------------------------------------------
# Source structure helpers (comments/strings mask, function spans)
# ----------------------------------------------------------------------
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
    """mask[i][j] is True when char j of line i is real code (not inside a
    comment or the CONTENT of a string/char literal; quote chars are code)."""
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
    MODEL_NAME = "Salesforce/codet5-base"
    ADAPTER_PATH = os.path.join(_PROJECT_ROOT, "models", "codet5_security_adapter", "adapter")

    def __init__(self, use_ai: bool = False):
        self.use_ai = use_ai
        self._tokenizer = None
        self._model = None
        self._device = None
        self._model_load_attempted = False

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------
    def apply_fixes(self, source: str) -> AutoFixResult:
        steps: List[str] = []
        suggestions: List[str] = []

        # Pre-pass: repair already-corrupted lines from the old fixer
        fixed, corr_steps, corr_sugg = self._repair_corrupted_buffer_refs(source)
        steps.extend(corr_steps)
        suggestions.extend(corr_sugg)

        fixed, det_steps, det_sugg = self._apply_deterministic_fixes(fixed)
        steps.extend(det_steps)
        suggestions.extend(det_sugg)

        if self.use_ai:
            fixed, ai_steps = self._apply_ai_security_fixes(fixed)
            steps.extend(ai_steps)

        return AutoFixResult(source=fixed, applied_steps=steps, suggestions=suggestions)

    # ------------------------------------------------------------------
    # Symbol lookup: is `name` a real array here, and how big?
    # ------------------------------------------------------------------
    @staticmethod
    def _macro_value(lines: List[str], name: str) -> Optional[int]:
        pat = re.compile(r"^\s*#\s*define\s+" + re.escape(name) + r"\s+(\d+)\s*(?:/[/*].*)?$")
        for ln in lines:
            m = pat.match(ln)
            if m:
                return int(m.group(1))
        return None

    def _array_size(self, lines, mask, spans, idx: int, name: str) -> Optional[int]:
        """Size of char array `name` visible at line idx, or None when it is
        not an array / is a parameter / the size cannot be determined."""
        decl = re.compile(
            r"\b" + _TYPE_WORDS + r"\b[^;()=]*?\b" + re.escape(name)
            + r"\b\s*(?:\[\s*([A-Za-z_0-9]*)\s*\])?"
        )

        def classify(line_idx: int) -> Tuple[bool, Optional[int]]:
            m = decl.search(lines[line_idx])
            if not m or not mask[line_idx][m.start()]:
                return False, None
            if "char" not in lines[line_idx][: m.end()]:
                return True, None  # declared, but not a char buffer
            tok = m.group(1)
            if tok is None or tok == "":
                return True, None  # pointer, or unsized array
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
                return None  # function parameter: decays to a pointer
        # global declarations (outside every function)
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

    # ------------------------------------------------------------------
    # Pre-pass: repair corruption left by the old (v1) fixer
    # ------------------------------------------------------------------
    # The old fixer would copy identifiers from unrelated functions,
    # producing lines like  scanf("%11s", arr)  where arr belongs to a
    # different function.  This pass detects such lines and substitutes
    # the correct local buffer when unambiguous.
    _CORRUPTED_SCANF_RE = re.compile(
        r'\bscanf\s*\(\s*"(%\d*[dsx])"\s*,\s*([A-Za-z_]\w*)\s*\)'
    )
    _CHAR_DECL_RE = re.compile(
        r'\b(?:char)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]'
    )

    def _repair_corrupted_buffer_refs(
        self, source: str
    ) -> Tuple[str, List[str], List[str]]:
        """Find scanf(..., NAME) where NAME is not declared locally.

        If the enclosing function has exactly one char[] local, substitute
        it and recompute the width.  If ambiguous (0 or 2+), add a
        suggestion instead.
        """
        lines, eols = _split_lines(source)
        if not lines:
            return source, [], []
        mask = _code_mask(lines)
        spans = _function_spans(lines, mask)

        steps: List[str] = []
        suggestions: List[str] = []

        for idx in range(len(lines)):
            line = lines[idx]
            lineno = idx + 1
            m = self._CORRUPTED_SCANF_RE.search(line)
            if m is None or not mask[idx][m.start()]:
                continue

            buf_name = m.group(2)
            # Is buf_name declared in this function?
            span = next(
                (s for s in spans if s.open_idx <= idx <= s.end_idx), None
            )
            if span is None:
                continue  # not inside a function

            # Check local declarations in this function body
            local_declared = False
            for k in range(span.open_idx, span.end_idx + 1):
                if re.search(r'\b' + re.escape(buf_name) + r'\b', lines[k]):
                    # Is it a declaration (not just a use)?
                    if re.search(
                        r'\b(?:char|int|float|double|short|long|unsigned|signed|void|size_t)\b'
                        r'[^;()]*\b' + re.escape(buf_name) + r'\b',
                        lines[k]
                    ):
                        local_declared = True
                        break

            # Also check function parameters
            if not local_declared:
                header = " ".join(lines[span.header_start: span.open_idx + 1])
                if re.search(r'\b' + re.escape(buf_name) + r'\b', header):
                    local_declared = True

            if local_declared:
                continue  # buf_name is a real local, nothing to fix

            # Find all char[] locals in this function
            char_arrays: List[Tuple[str, int]] = []
            for k in range(span.open_idx, span.end_idx + 1):
                for cm in self._CHAR_DECL_RE.finditer(lines[k]):
                    if mask[k][cm.start()]:
                        char_arrays.append((cm.group(1), int(cm.group(2))))

            if len(char_arrays) == 1:
                correct_name, correct_size = char_arrays[0]
                fmt_spec = m.group(1)
                # Rewrite the format spec width to match the correct buffer
                if fmt_spec.endswith("s") and correct_size >= 2:
                    new_fmt = f"%{correct_size - 1}s"
                else:
                    new_fmt = fmt_spec
                new_call = f'scanf("{new_fmt}", {correct_name})'
                new_line = line[:m.start()] + new_call + line[m.end():]
                lines[idx] = new_line
                steps.append(
                    f"REPAIR: line {lineno}: fixed corrupted buffer ref "
                    f"'{buf_name}' -> '{correct_name}' in scanf"
                )
            elif len(char_arrays) == 0:
                suggestions.append(
                    f"line {lineno}: scanf uses undeclared buffer '{buf_name}' "
                    f"— no char[] found in enclosing function; fix manually"
                )
            else:
                names = ", ".join(n for n, _ in char_arrays)
                suggestions.append(
                    f"line {lineno}: scanf uses undeclared buffer '{buf_name}' "
                    f"— multiple char[] candidates ({names}); fix manually"
                )

        fixed = "".join(c + e for c, e in zip(lines, eols))
        return fixed, steps, suggestions

    # ------------------------------------------------------------------
    # Deterministic fixes
    # ------------------------------------------------------------------
    def _apply_deterministic_fixes(self, source: str) -> Tuple[str, List[str], List[str]]:
        lines, eols = _split_lines(source)
        if not lines:
            return source, [], []
        mask = _code_mask(lines)
        spans = _function_spans(lines, mask)

        steps: List[str] = []
        suggestions: List[str] = []
        ID = r"([A-Za-z_]\w*)"

        for idx in range(len(lines)):
            line = lines[idx]
            lineno = idx + 1

            def size_of(name: str) -> Optional[int]:
                return self._array_size(lines, mask, spans, idx, name)

            def sub_call(pattern: str, make, label: str, line_text: str) -> str:
                rx = re.compile(pattern)
                out, pos = [], 0
                for m in rx.finditer(line_text):
                    if not mask[idx][m.start()]:
                        continue
                    repl = make(m)
                    if repl is None:
                        suggestions.append(
                            f"line {lineno}: {label}: buffer size unknown "
                            f"(pointer/parameter or unsized array) - fix manually"
                        )
                        continue
                    out.append(line_text[pos:m.start()])
                    out.append(repl)
                    pos = m.end()
                    steps.append(f"AUTOSEC: line {lineno}: {label}")
                out.append(line_text[pos:])
                return "".join(out)

            # gets(buf) -> fgets(buf, sizeof(buf), stdin)
            def mk_gets(m):
                b = m.group(1)
                return f"fgets({b}, sizeof({b}), stdin)" if size_of(b) else None
            line = sub_call(r"\bgets\s*\(\s*" + ID + r"\s*\)", mk_gets,
                            "gets -> fgets(buf, sizeof(buf), stdin)", line)

            # strcpy(dst, src) -> snprintf(dst, sizeof(dst), "%s", src)
            def mk_strcpy(m):
                d, s = m.group(1), m.group(2)
                return f'snprintf({d}, sizeof({d}), "%s", {s})' if size_of(d) else None
            line = sub_call(
                r"\bstrcpy\s*\(\s*" + ID + r"\s*,\s*([A-Za-z_]\w*|\"(?:\\.|[^\"\\])*\")\s*\)",
                mk_strcpy, 'strcpy -> snprintf(dst, sizeof(dst), "%s", src)', line)

            # strcat(dst, src) -> strncat(dst, src, sizeof(dst) - strlen(dst) - 1)
            def mk_strcat(m):
                d, s = m.group(1), m.group(2)
                return (f"strncat({d}, {s}, sizeof({d}) - strlen({d}) - 1)"
                        if size_of(d) else None)
            line = sub_call(
                r"\bstrcat\s*\(\s*" + ID + r"\s*,\s*([A-Za-z_]\w*|\"(?:\\.|[^\"\\])*\")\s*\)",
                mk_strcat, "strcat -> strncat(dst, src, sizeof(dst) - strlen(dst) - 1)", line)

            # sprintf(buf, ...) -> snprintf(buf, sizeof(buf), ...)
            def mk_sprintf(m):
                b = m.group(1)
                return f"snprintf({b}, sizeof({b})," if size_of(b) else None
            line = sub_call(r"\bsprintf\s*\(\s*" + ID + r"\s*,", mk_sprintf,
                            "sprintf -> snprintf(buf, sizeof(buf), ...)", line)

            # vsprintf(buf, ...) -> vsnprintf(buf, sizeof(buf), ...)
            def mk_vsprintf(m):
                b = m.group(1)
                return f"vsnprintf({b}, sizeof({b})," if size_of(b) else None
            line = sub_call(r"\bvsprintf\s*\(\s*" + ID + r"\s*,", mk_vsprintf,
                            "vsprintf -> vsnprintf(buf, sizeof(buf), ...)", line)

            # scanf("%s", buf) -> scanf("%<N-1>s", buf)
            def mk_scanf(m):
                n = size_of(m.group(1))
                return f'scanf("%{n - 1}s", {m.group(1)})' if n and n >= 2 else None
            line = sub_call(r'\bscanf\s*\(\s*"%s"\s*,\s*' + ID + r"\s*\)", mk_scanf,
                            'scanf("%s", buf) -> scanf("%<size-1>s", buf)', line)

            # printf(var) -> printf("%s", var)   (format-string injection)
            line = sub_call(r"\bprintf\s*\(\s*" + ID + r"\s*\)",
                            lambda m: f'printf("%s", {m.group(1)})',
                            'printf(var) -> printf("%s", var)', line)

            # system/popen/exec with variable argument: detect-only, never auto-fixed
            _EXEC_RE = re.compile(
                r"\b(system|popen|execl|execv|execvp|execve)\s*\(\s*" + ID + r"\b"
            )
            for em in _EXEC_RE.finditer(line):
                if mask[idx][em.start()]:
                    fn_name = em.group(1)
                    arg_name = em.group(2)
                    suggestions.append(
                        f"line {lineno}: TAINTED_{fn_name.upper()}: "
                        f"{fn_name}({arg_name}) uses a variable as command — "
                        f"consider a whitelist, validated enum dispatch, or "
                        f"removing the {fn_name}() call entirely"
                    )

            lines[idx] = line

        fixed = "".join(c + e for c, e in zip(lines, eols))
        # de-duplicate suggestions (a line may be re-scanned by several rules)
        seen, uniq = set(), []
        for s in suggestions:
            if s not in seen:
                seen.add(s); uniq.append(s)
        return fixed, steps, uniq

    # ------------------------------------------------------------------
    # Optional AI fallback (OFF by default) - windowed + validated
    # ------------------------------------------------------------------
    _AI_PATTERNS = [
        (re.compile(r"\bgets\s*\(\s*[A-Za-z_]\w*\s*\)"), "UNSAFE_INPUT"),
        (re.compile(r"\bstrcpy\s*\(\s*[A-Za-z_]\w*\s*,\s*[A-Za-z_]\w*\s*\)"), "UNBOUNDED_COPY"),
        (re.compile(r"\bstrcat\s*\(\s*[A-Za-z_]\w*\s*,\s*[A-Za-z_]\w*\s*\)"), "UNBOUNDED_CONCAT"),
        (re.compile(r"\bsprintf\s*\(\s*[A-Za-z_]\w*\s*,"), "UNBOUNDED_FORMAT"),
        (re.compile(r'\bscanf\s*\(\s*"%s"\s*,\s*[A-Za-z_]\w*\s*\)'), "UNBOUNDED_INPUT"),
    ]

    def _apply_ai_security_fixes(self, source: str) -> Tuple[str, List[str]]:
        if self._load_security_model() is None:
            return source, []
        lines, eols = _split_lines(source)
        mask = _code_mask(lines)
        spans = _function_spans(lines, mask)
        steps: List[str] = []

        for idx in range(len(lines)):
            old = lines[idx]
            category = next((c for rx, c in self._AI_PATTERNS
                             if (m := rx.search(old)) and mask[idx][m.start()]), None)
            if category is None:
                continue
            span = next((s for s in spans if s.header_start <= idx <= s.end_idx), None)
            if span is None:
                continue
            window, rel_line = self._build_window(lines, span, idx)
            patch = self._generate_patch(window, rel_line, category)
            new_line = self._parse_replace_line(patch)
            if new_line is None:
                continue
            new_line = re.match(r"^\s*", old).group(0) + new_line.strip()
            if not self._validate_ai_line(old, new_line, lines, mask, spans, idx):
                continue
            lines[idx] = new_line
            steps.append(f"AISEC: {category} at line {idx + 1} -> {new_line.strip()}")
        return "".join(c + e for c, e in zip(lines, eols)), steps

    @staticmethod
    def _build_window(lines: List[str], span: _Span, idx: int) -> Tuple[str, int]:
        """Enclosing function only, with the includes the training data had."""
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
        # The buffer being protected: first arg of gets/strcpy/strcat/sprintf,
        # or the destination (last arg) of scanf("%s", buf).
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
        if self._tokenizer is not None and self._model is not None:
            return self._tokenizer, self._model
        if self._model_load_attempted:
            return None
        self._model_load_attempted = True
        if (torch is None or AutoTokenizer is None or AutoModelForSeq2SeqLM is None
                or PeftModel is None or not os.path.isdir(self.ADAPTER_PATH)):
            return None
        try:
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self._tokenizer = AutoTokenizer.from_pretrained(self.ADAPTER_PATH)
            base = AutoModelForSeq2SeqLM.from_pretrained(self.MODEL_NAME)
            model = PeftModel.from_pretrained(base, self.ADAPTER_PATH)
            try:
                model = model.merge_and_unload()  # faster inference
            except Exception:
                pass
            self._model = model.to(self._device).eval()
            return self._tokenizer, self._model
        except Exception:
            self._tokenizer = None
            self._model = None
            return None

    def _generate_patch(self, window: str, rel_line: int, category: str) -> Optional[str]:
        bundle = self._load_security_model()
        if bundle is None:
            return None
        tokenizer, model = bundle
        prompt = (f"SECURITY_FIX\nCATEGORY {category}\nLINE {rel_line}\n\n"
                  f"<CODE>\n{window}\n</CODE>")
        try:
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
            with torch.no_grad():
                out = model.generate(**inputs, max_length=64, num_beams=1)
            pred = tokenizer.decode(out[0], skip_special_tokens=True).strip()
            return pred if pred.startswith("REPLACE_LINE") else None
        except Exception:
            return None