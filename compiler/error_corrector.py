import re
from typing import Optional, Tuple, List

from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener
try:
    from generated.SimpleCLexer import SimpleCLexer
    from generated.SimpleCParser import SimpleCParser
except Exception:
    SimpleCLexer = None
    SimpleCParser = None

from .error_classifier import ErrorClassification


class _SilentParseCollector(ErrorListener):
    def __init__(self):
        self.errors = []
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append((line, column, msg))


def _count_parse_errors(code: str) -> Tuple[int, Optional[Tuple[int, int]]]:
    if SimpleCLexer is None or SimpleCParser is None:
        return 9999, None
    try:
        lexer = SimpleCLexer(InputStream(code))
        collector = _SilentParseCollector()
        lexer.removeErrorListeners()
        lexer.addErrorListener(collector)
        parser = SimpleCParser(CommonTokenStream(lexer))
        parser.removeErrorListeners()
        parser.addErrorListener(collector)
        parser.program()
        if not collector.errors:
            return 0, None
        earliest = min((e[0], e[1]) for e in collector.errors)
        return len(collector.errors), earliest
    except Exception:
        return 9999, (0, 0)


def _validate_fix(orig_src: str, candidate_src: str, fix_msg: str) -> Tuple[str, Optional[str]]:
    if candidate_src == orig_src or not fix_msg:
        return orig_src, None

    orig_count, orig_earliest = _count_parse_errors(orig_src)
    if orig_count == 0:
        # Do not touch code that parses cleanly
        return orig_src, None

    cand_count, cand_earliest = _count_parse_errors(candidate_src)

    # Only accept it if the error count goes down and no new error appears earlier in the file
    if cand_count < orig_count:
        if cand_count == 0 or (cand_earliest is not None and orig_earliest is not None and cand_earliest >= orig_earliest):
            return candidate_src, fix_msg

    # Otherwise ambiguous or invalid -> leave for AI fallback
    return orig_src, None


def apply_correction(
    source_text: str,
    error_line: int,
    error_column: int,
    classification: ErrorClassification,
) -> Tuple[str, Optional[str]]:
    """
    Deterministic correction dispatcher.
    Returns: (new_source, applied_fix_message_or_None)
    """

    new_src, msg = repair_missing_rhs(source_text, error_line)

    if msg:
        return new_src, msg

    # ANTLR may report a missing do-while terminator at the next token rather
    # than including `do` in its message.  The source shape is unambiguous.
    new_src, msg = _fix_missing_semicolon_after_do_while(source_text, error_line)
    if msg:
        return new_src, msg
    new_src, msg = _fix_missing_rparen_cast_or_sizeof(source_text, error_line)
    if msg:
        return new_src, msg
    if not classification.fixable:
        return source_text, None

    reason = classification.reason

    if reason == "missing_semicolon_after_prototype":
        return _fix_missing_semicolon_after_prototype(source_text, error_line, error_column)

    if reason == "missing_comma_params":
        return _fix_missing_comma_params(source_text, error_line, error_column)

    if reason == "missing_rparen_params":
        return _fix_missing_rparen_params(source_text, error_line, error_column)

    if reason == "missing_semicolon_after_global":
        return _fix_missing_semicolon_after_global(source_text, error_line, error_column)

    if reason == "missing_semicolon_after_do_while":
        return _fix_missing_semicolon_after_do_while(source_text, error_line)

    if reason == "missing_rparen_cast_or_sizeof":
        return _fix_missing_rparen_cast_or_sizeof(source_text, error_line)

    if reason == "missing_semicolon":
        return _insert_semicolon_near_line(source_text, error_line)

    if reason == "missing_rbrace":
        return _append_missing_rbrace(source_text)

    if reason == "missing_lbrace":
        return _insert_missing_lbrace(source_text, error_line)

    if reason == "missing_lparen":
        new_src, msg = _fix_main_parentheses(source_text)
        if msg:
            return new_src, msg
        return _insert_missing_lparen(source_text, error_line)

    if reason == "missing_rparen":
        return _insert_missing_rparen(source_text, error_line)

    if reason == "extraneous_token":
        return _delete_extraneous_token_at(source_text, error_line, error_column)

    if reason == "main_lparen_expected":
        return _fix_main_parentheses(source_text)
    
    if reason == "missing_rhs":
        return _repair_missing_rhs(source_text, error_line)

    # New deterministic rescue for incomplete declarations like:
    #   int
    #   return 0;
    if reason == "mismatched_token":
        new_src, msg = _remove_dangling_type_line(source_text, error_line)
        if msg:
            return new_src, msg

    return source_text, None


# -----------------------------
# Semicolon insertion
# -----------------------------
_CONTROL_KEYWORDS = ("if", "while", "for", "switch")


def _looks_like_control_header(code: str) -> bool:
    s = code.strip()
    return any(s.startswith(k + " ") or s.startswith(k + "(") for k in _CONTROL_KEYWORDS)


def _strip_line_comment(s: str) -> str:
    return s.split("//", 1)[0].rstrip()


def _line_ends_like_complete_statement(code_part: str) -> bool:
    return code_part.rstrip().endswith((";", "{", "}", ":", ","))


def _insert_semicolon_near_line(source_text: str, error_line: int) -> Tuple[str, Optional[str]]:
    lines = source_text.splitlines(keepends=True)
    idx = error_line - 1
    if idx < 0 or idx >= len(lines):
        return source_text, None

    def prev_code_line(start: int) -> Optional[int]:
        j = start
        while j >= 0:
            s = lines[j].strip()
            if not s:
                j -= 1
                continue
            if s.startswith("#"):
                j -= 1
                continue
            return j
        return None

    target = idx

    cur = lines[target]
    cur_no_nl = cur.rstrip("\r\n")
    cur_code = _strip_line_comment(cur_no_nl)

    if cur_code.endswith("{") or _looks_like_control_header(cur_code):
        p = prev_code_line(target - 1)
        if p is not None:
            target = p
            return _insert_semicolon_at_line_index(lines, target)

    if _line_ends_like_complete_statement(cur_code):
        p = prev_code_line(target - 1)
        if p is not None:
            target = p

    return _insert_semicolon_at_line_index(lines, target)


def _insert_semicolon_at_line_index(lines: List[str], idx: int) -> Tuple[str, Optional[str]]:
    if idx < 0 or idx >= len(lines):
        return "".join(lines), None

    original = lines[idx]
    nl = "\n"
    if original.endswith("\r\n"):
        nl = "\r\n"
    elif original.endswith("\n"):
        nl = "\n"
    elif original.endswith("\r"):
        nl = "\r"
    else:
        nl = ""

    no_nl = original.rstrip("\r\n")

    stripped = no_nl.strip()
    if not stripped or stripped.startswith("#"):
        return "".join(lines), None

    code_part = _strip_line_comment(no_nl)

    if _line_ends_like_complete_statement(code_part):
        return "".join(lines), None

    if _looks_like_control_header(code_part):
        return "".join(lines), None

    if "//" in no_nl:
        code, sep, comment = no_nl.partition("//")
        updated = code.rstrip() + ";" + " " + sep + comment
    else:
        updated = no_nl.rstrip() + ";"

    lines[idx] = updated + nl
    return "".join(lines), "inserted missing ';'"


# -----------------------------
# Brace fixes
# -----------------------------
def _append_missing_rbrace(source_text: str) -> Tuple[str, Optional[str]]:
    stripped = source_text.rstrip()
    if stripped.endswith("}"):
        return source_text, None
    return stripped + "\n}", "inserted missing '}' at end"


def _insert_missing_lbrace(source_text: str, error_line: int) -> Tuple[str, Optional[str]]:
    lines = source_text.splitlines(keepends=True)
    idx = max(0, min(len(lines) - 1, error_line - 1))

    func_re = re.compile(r"^\s*(?:int|void|char|float|double)\s+[A-Za-z_]\w*\s*\([^;]*\)\s*$")

    candidates = [idx, idx - 1]
    for c in candidates:
        if c < 0 or c >= len(lines):
            continue
        line_no_nl = lines[c].rstrip("\r\n")
        code = _strip_line_comment(line_no_nl)
        if func_re.match(code):
            insert_at = c + 1
            j = insert_at
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].lstrip().startswith("{"):
                return source_text, None

            nl = "\n"
            if lines[c].endswith("\r\n"):
                nl = "\r\n"
            elif lines[c].endswith("\n"):
                nl = "\n"
            elif lines[c].endswith("\r"):
                nl = "\r"
            else:
                nl = "\n"

            lines.insert(insert_at, "{" + nl)
            return "".join(lines), "inserted missing '{' after function header"

    return source_text, None


# -----------------------------
# Parenthesis fixes
# -----------------------------
def _insert_missing_lparen(source_text: str, error_line: int) -> Tuple[str, Optional[str]]:
    lines = source_text.splitlines(keepends=True)
    idx = error_line - 1
    if idx < 0 or idx >= len(lines):
        return source_text, None

    line = lines[idx]
    line_no_nl = line.rstrip("\r\n")
    nl = line[len(line_no_nl):]

    m = re.search(r"\b(if|while|for)\s+([^\(].*\))", line_no_nl)
    if not m:
        return source_text, None

    kw = m.group(1)
    updated = re.sub(rf"\b{kw}\s+(.+)", rf"{kw} (\1", line_no_nl, count=1)
    lines[idx] = updated + nl
    return "".join(lines), f"inserted missing '(' after {kw}"


def _insert_missing_rparen(source_text: str, error_line: int) -> Tuple[str, Optional[str]]:
    lines = source_text.splitlines(keepends=True)
    idx = error_line - 1
    if idx < 0 or idx >= len(lines):
        return source_text, None

    line = lines[idx]
    line_no_nl = line.rstrip("\r\n")
    nl = line[len(line_no_nl):]

    # classic if/while/for ... {
    if re.search(r"\b(if|while|for)\s*\(", line_no_nl) and "{" in line_no_nl and ")" not in line_no_nl:
        updated = line_no_nl.replace("{", ") {", 1)
        lines[idx] = updated + nl
        return "".join(lines), "inserted missing ')' before '{'"

    # generic function call missing ')'
    if "(" in line_no_nl and ")" not in line_no_nl and line_no_nl.strip().endswith(";"):
        updated = line_no_nl[:-1] + ");"
        lines[idx] = updated + nl
        return "".join(lines), "inserted missing ')' before ';'"

    return source_text, None


# -----------------------------
# Extraneous token deletion
# -----------------------------
def _delete_extraneous_token_at(source_text: str, error_line: int, error_column: int) -> Tuple[str, Optional[str]]:
    lines = source_text.splitlines(keepends=True)
    idx = error_line - 1
    if idx < 0 or idx >= len(lines):
        return source_text, None

    line = lines[idx]
    line_no_nl = line.rstrip("\r\n")
    nl = line[len(line_no_nl):]

    col = max(0, min(len(line_no_nl), error_column))

    if col >= len(line_no_nl):
        return source_text, None

    ch = line_no_nl[col]
    if ch not in (";", ",", ")", "]"):
        if col > 0 and line_no_nl[col - 1] in (";", ",", ")", "]"):
            col = col - 1
            ch = line_no_nl[col]
        else:
            return source_text, None

    updated = line_no_nl[:col] + line_no_nl[col + 1:]
    lines[idx] = updated + nl
    return "".join(lines), f"deleted extraneous token '{ch}'"


# -----------------------------
# Special-case main() {
# -----------------------------
def _fix_main_parentheses(source_text: str) -> Tuple[str, Optional[str]]:
    pattern = re.compile(r"\bmain\s*\{")
    if not pattern.search(source_text):
        return source_text, None
    updated = pattern.sub("main() {", source_text, count=1)
    return updated, "replaced '{' with '() {' after main"


# -----------------------------
# New: dangling type-line removal
# -----------------------------
def _remove_dangling_type_line(source_text: str, error_line: int) -> Tuple[str, Optional[str]]:
    """
    Remove an incomplete declaration line containing only a type keyword, e.g.

        int
        return 0;

    This is conservative:
    - only removes a line that is exactly one type keyword
    - only when the next non-empty line starts with something statement-like
    """
    lines = source_text.splitlines(keepends=True)

    type_only_re = re.compile(r"^\s*(int|float|char|double|void)\s*(//.*)?$")
    next_stmt_re = re.compile(
        r"^\s*(return|if|while|for|break|continue|\{|\}|[A-Za-z_])\b"
    )

    # First try the line just before the reported error
    candidates = [error_line - 2, error_line - 1]

    for idx in candidates:
        if idx < 0 or idx >= len(lines):
            continue

        cur = lines[idx].rstrip("\r\n")
        if not type_only_re.match(cur):
            continue

        j = idx + 1
        while j < len(lines) and not lines[j].strip():
            j += 1

        if j >= len(lines):
            continue

        nxt = lines[j].rstrip("\r\n")
        if not next_stmt_re.match(nxt):
            continue

        new_lines = lines[:idx] + lines[idx + 1:]
        return "".join(new_lines), "removed dangling incomplete declaration"

    return source_text, None

def _repair_missing_rhs(source_text: str, error_line: int) -> Tuple[str, Optional[str]]:
    """
    Repair patterns like:
        x = ;
        int x = ;
    Conservative strategy:
    - If line looks like a declaration assignment, use 0 as initializer
    - If line looks like a normal assignment, use 0 as RHS
    """
    lines = source_text.splitlines(keepends=True)
    idx = error_line - 1
    if idx < 0 or idx >= len(lines):
        return source_text, None

    line = lines[idx]
    line_no_nl = line.rstrip("\r\n")
    nl = line[len(line_no_nl):]

    # declaration with missing initializer
    decl_pat = re.compile(r"^(\s*(?:int|float|char|double)\s+[A-Za-z_]\w*\s*=\s*);(\s*(?://.*)?)$")
    m = decl_pat.match(line_no_nl)
    if m:
        updated = m.group(1) + "0;" + m.group(2)
        lines[idx] = updated + nl
        return "".join(lines), "inserted default initializer '0' for missing RHS"

    # generic assignment with missing RHS
    assign_pat = re.compile(r"^(\s*[A-Za-z_]\w*\s*=\s*);(\s*(?://.*)?)$")
    m = assign_pat.match(line_no_nl)
    if m:
        updated = m.group(1) + "0;" + m.group(2)
        lines[idx] = updated + nl
        return "".join(lines), "inserted default RHS '0'"

    return source_text, None
def repair_missing_rhs(source: str, error_line: int) -> Tuple[str, Optional[str]]:
    """
    Fix patterns like:
        int x=;
        x=;
    """

    lines = source.splitlines(keepends=True)

    idx = error_line - 1
    if idx < 0 or idx >= len(lines):
        return source, None

    line = lines[idx]
    stripped = line.strip()

    # declaration initializer missing RHS
    m = re.match(r"(int|float|char|double)\s+[A-Za-z_]\w*\s*=\s*;", stripped)
    if m:
        fixed = stripped.replace("=;", "=0;")
        lines[idx] = line.replace(stripped, fixed)
        return "".join(lines), "inserted default initializer 0"

    # simple assignment missing RHS
    m = re.match(r"[A-Za-z_]\w*\s*=\s*;", stripped)
    if m:
        fixed = stripped.replace("=;", "=0;")
        lines[idx] = line.replace(stripped, fixed)
        return "".join(lines), "inserted default RHS 0"

    return source, None


# -----------------------------
# Week 5 New Deterministic Fixes
# -----------------------------
def _fix_missing_semicolon_after_prototype(source_text: str, error_line: int, error_column: int) -> Tuple[str, Optional[str]]:
    lines = source_text.splitlines(keepends=True)
    idx = error_line - 1
    cand_line = idx if idx < len(lines) else len(lines) - 1
    while cand_line >= 0:
        line_str = lines[cand_line]
        if "{" in line_str:
            cand_line -= 1
            continue
        if ")" in line_str:
            rpos = line_str.rfind(")")
            after = line_str[rpos + 1:].strip()
            if not after.startswith(";"):
                candidate_lines = list(lines)
                candidate_lines[cand_line] = line_str[:rpos + 1] + ";" + line_str[rpos + 1:]
                cand_src = "".join(candidate_lines)
                return _validate_fix(source_text, cand_src, "inserted ';' after prototype closing parenthesis")
        cand_line -= 1
    return source_text, None


def _fix_missing_comma_params(source_text: str, error_line: int, error_column: int) -> Tuple[str, Optional[str]]:
    lines = source_text.splitlines(keepends=True)
    idx = error_line - 1
    if 0 <= idx < len(lines):
        line = lines[idx]
        col = error_column if error_column < len(line) else len(line)
        prefix = line[:col].rstrip()
        suffix = line[col:].lstrip()
        candidate_lines = list(lines)
        candidate_lines[idx] = prefix + ", " + suffix
        cand_src = "".join(candidate_lines)
        return _validate_fix(source_text, cand_src, "inserted missing comma between parameters")
    return source_text, None


def _fix_missing_rparen_params(source_text: str, error_line: int, error_column: int) -> Tuple[str, Optional[str]]:
    lines = source_text.splitlines(keepends=True)
    idx = error_line - 1
    cand_line = idx if idx < len(lines) else len(lines) - 1
    while cand_line >= 0:
        line = lines[cand_line]
        if ";" in line:
            pos = line.find(";")
            candidate_lines = list(lines)
            candidate_lines[cand_line] = line[:pos].rstrip() + ");" + line[pos + 1:]
            cand_src = "".join(candidate_lines)
            res_src, res_msg = _validate_fix(source_text, cand_src, "inserted missing ')' in parameter list")
            if res_msg:
                return res_src, res_msg
        if "{" in line:
            pos = line.find("{")
            candidate_lines = list(lines)
            candidate_lines[cand_line] = line[:pos].rstrip() + ") " + line[pos:]
            cand_src = "".join(candidate_lines)
            res_src, res_msg = _validate_fix(source_text, cand_src, "inserted missing ')' in parameter list")
            if res_msg:
                return res_src, res_msg
        cand_line -= 1
    return source_text, None


def _fix_missing_semicolon_after_global(source_text: str, error_line: int, error_column: int) -> Tuple[str, Optional[str]]:
    lines = source_text.splitlines(keepends=True)
    idx = error_line - 1
    j = idx - 1 if idx < len(lines) else len(lines) - 2
    while j >= 0 and not lines[j].strip():
        j -= 1
    if j >= 0:
        prev_line = lines[j]
        clean = prev_line.split("//", 1)[0].rstrip()
        if not clean.endswith(";"):
            comment = prev_line[len(clean):]
            candidate_lines = list(lines)
            candidate_lines[j] = clean + ";" + comment
            cand_src = "".join(candidate_lines)
            return _validate_fix(source_text, cand_src, "inserted missing ';' after global declaration")
    return source_text, None


def _fix_missing_semicolon_after_do_while(source_text: str, error_line: int) -> Tuple[str, Optional[str]]:
    # The parser often reports the token *after* the `while (condition)`.
    # Find a do-body paired with a while whose closing ')' has no semicolon.
    for match in re.finditer(r"\bdo\b[\s\S]*?\bwhile\s*\([^)]*\)(?!\s*;)", source_text):
        insert_at = match.end()
        candidate = source_text[:insert_at] + ";" + source_text[insert_at:]
        fixed, msg = _validate_fix(source_text, candidate, "inserted missing ';' after do-while")
        if msg:
            return fixed, msg
    return source_text, None


def _fix_missing_rparen_cast_or_sizeof(source_text: str, error_line: int) -> Tuple[str, Optional[str]]:
    lines = source_text.splitlines(keepends=True)
    idx = error_line - 1
    if not (0 <= idx < len(lines)):
        return source_text, None
    raw = lines[idx]
    body = raw.rstrip("\r\n")
    match = re.search(r"\bsizeof\s*\([^;)]*;", body)
    if match:
        pos = match.end() - 1
        nl = raw[len(body):]
        candidate = "".join(lines[:idx] + [body[:pos] + ")" + body[pos:] + nl] + lines[idx + 1:])
        return _validate_fix(source_text, candidate, "inserted missing ')' in sizeof")

    # `(double value` / `(int value` has an unambiguous type prefix followed
    # by an operand. Insert the missing cast close-paren before that operand.
    cast = re.search(
        r"\((?:signed\s+|unsigned\s+)?(?:char|short|long|int|float|double|void)(?:\s*\*)?\s+([A-Za-z_]\w*)",
        body,
    )
    if cast:
        operand_start = cast.start(1)
        nl = raw[len(body):]
        candidate = "".join(lines[:idx] + [body[:operand_start] + ")" + body[operand_start:] + nl] + lines[idx + 1:])
        return _validate_fix(source_text, candidate, "inserted missing ')' in cast")
    return source_text, None
