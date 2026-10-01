# compiler/week5_repair_helpers.py
from __future__ import annotations

from compiler.preprocessor import repair_preprocessor_directives

import inspect
import os
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from generated.SimpleCParser import SimpleCParser
except ImportError:
    SimpleCParser = None

from compiler.keyword_corrector import _tokenize_code


# =====================================================================
# Problem 2: Stale Parser Detector
# =====================================================================

def check_parser_status(project_root: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Checks whether SimpleCParser knows CARET, TILDE and PIPE tokens.
    Returns:
      (is_fresh: bool, info_line: str, warning_line: Optional[str])
    """
    if project_root is None:
        project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    else:
        project_root = os.path.abspath(project_root)

    parser_path = ""
    knows_caret = False
    knows_tilde = False
    knows_pipe = False

    if SimpleCParser is not None:
        try:
            parser_path = os.path.abspath(inspect.getfile(SimpleCParser))
        except Exception:
            parser_path = os.path.join(project_root, "generated", "SimpleCParser.py")
        knows_caret = getattr(SimpleCParser, "CARET", None) is not None
        knows_tilde = getattr(SimpleCParser, "TILDE", None) is not None
        knows_pipe = getattr(SimpleCParser, "PIPE", None) is not None
    else:
        parser_path = os.path.join(project_root, "generated", "SimpleCParser.py")

    knows_all = bool(knows_caret and knows_tilde and knows_pipe)
    tokens_status = f"CARET={knows_caret}, TILDE={knows_tilde}, PIPE={knows_pipe} ({'YES' if knows_all else 'NO'})"
    info_line = f"Project: {project_root} | Parser: {parser_path} | Tokens (CARET, TILDE, PIPE): {tokens_status}"

    warning_line = None
    if not knows_all:
        warning_line = 'WARNING: Parser is stale: regenerate or copy the updated generated/ folder'

    return knows_all, info_line, warning_line


def print_parser_check(project_root: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Prints the startup / log check for parser freshness.
    """
    is_fresh, info_line, warning_line = check_parser_status(project_root)
    print(info_line)
    if warning_line:
        print(warning_line)
    return is_fresh, info_line, warning_line


# =====================================================================
# Problem 1: Split Operators Helper
# =====================================================================

SPLIT_OPERATORS = [
    # (regex_pattern, replacement, display_name, target_name)
    (re.compile(r"<<=\s*="), "<<=", "<<= =", "<<="),
    (re.compile(r">>=\s*="), ">>=", ">>= =", ">>="),
    (re.compile(r"<\s*<\s*<"), "<<", "<<<", "<<"),
    (re.compile(r">\s*>\s*>"), ">>", ">>>", ">>"),
    (re.compile(r"<\s+<"), "<<", "< <", "<<"),
    (re.compile(r">\s+>"), ">>", "> >", ">>"),
    (re.compile(r"&\s+="), "&=", "& =", "&="),
    (re.compile(r"\|\s+="), "|=", "| =", "|="),
    (re.compile(r"\^\s+="), "^=", "^ =", "^="),
    (re.compile(r"%\s+="), "%=", "% =", "%="),
]


def _split_code_and_noncode(source_text: str) -> List[Tuple[str, str]]:
    """
    Split source code into ('code', text) and ('noncode', text) segments
    so replacements only happen in code, never inside comments or strings.
    """
    result: List[Tuple[str, str]] = []
    i = 0
    n = len(source_text)
    code_buf: List[str] = []

    def flush_code():
        if code_buf:
            result.append(("code", "".join(code_buf)))
            code_buf.clear()

    while i < n:
        ch = source_text[i]

        # line comment
        if ch == "/" and i + 1 < n and source_text[i + 1] == "/":
            flush_code()
            j = i + 2
            while j < n and source_text[j] != "\n":
                j += 1
            result.append(("noncode", source_text[i:j]))
            i = j
            continue

        # block comment
        if ch == "/" and i + 1 < n and source_text[i + 1] == "*":
            flush_code()
            j = i + 2
            while j + 1 < n and not (source_text[j] == "*" and source_text[j + 1] == "/"):
                j += 1
            j = min(j + 2, n)
            result.append(("noncode", source_text[i:j]))
            i = j
            continue

        # string literal
        if ch == '"':
            flush_code()
            j = i + 1
            while j < n:
                if source_text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if source_text[j] == '"':
                    j += 1
                    break
                j += 1
            result.append(("noncode", source_text[i:j]))
            i = j
            continue

        # char literal
        if ch == "'":
            flush_code()
            j = i + 1
            while j < n:
                if source_text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if source_text[j] == "'":
                    j += 1
                    break
                j += 1
            result.append(("noncode", source_text[i:j]))
            i = j
            continue

        code_buf.append(ch)
        i += 1

    flush_code()
    return result


def fix_split_operators(source: str) -> Tuple[str, Optional[str]]:
    """
    Merges split operators outside strings/comments:
    & =, | =, ^ =, % =, < <, > >, <<<, >>>, <<= =, >>= =
    Applies one merge per call.
    Returns: (new_source, description_or_None)
    """
    segments = _split_code_and_noncode(source)
    for seg_idx, (kind, chunk) in enumerate(segments):
        if kind != "code":
            continue

        for pat, repl, display_name, target_name in SPLIT_OPERATORS:
            m = pat.search(chunk)
            if m:
                new_chunk = chunk[: m.start()] + repl + chunk[m.end() :]
                segments[seg_idx] = ("code", new_chunk)
                new_source = "".join(seg[1] for seg in segments)
                desc = f"merged split operator '{display_name}' -> '{target_name}'"
                return new_source, desc

    return source, None


# =====================================================================
# Problem 1: Fuzzy Keyword Typos Helper
# =====================================================================

DECL_TYPE_KEYWORDS = [
    "int", "float", "char", "void", "double", "unsigned", "signed", "short", "long", "struct"
]

ALL_C_KEYWORDS = {
    "return", "if", "else", "while", "for", "break", "continue",
    "int", "float", "char", "void", "double", "unsigned", "signed", "short", "long", "struct", "main"
}


def _damerau_levenshtein(a: str, b: str, max_dist: int = 2) -> int:
    """
    Optimal String Alignment (OSA) Damerau-Levenshtein distance.
    """
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > max_dist:
        return max_dist + 1

    prevprev = list(range(lb + 1))
    prev = [0] * (lb + 1)

    for i in range(1, la + 1):
        cur = [0] * (lb + 1)
        cur[0] = i
        row_min = cur[0]

        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1

            deletion = prev[j] + 1
            insertion = cur[j - 1] + 1
            substitution = prev[j - 1] + cost
            cur[j] = min(deletion, insertion, substitution)

            if (
                i > 1 and j > 1
                and a[i - 1] == b[j - 2]
                and a[i - 2] == b[j - 1]
            ):
                cur[j] = min(cur[j], prevprev[j - 2] + 1)

            if cur[j] < row_min:
                row_min = cur[j]

        if row_min > max_dist:
            return max_dist + 1

        prevprev, prev = prev, cur

    return prev[lb]


def _closest_declaration_keyword(word: str) -> Optional[str]:
    w = word.strip().lower()
    if not w or w in ALL_C_KEYWORDS:
        return None

    candidates: List[Tuple[int, str]] = []
    for kw in DECL_TYPE_KEYWORDS:
        max_dist = 1 if len(kw) <= 4 else 2
        d = _damerau_levenshtein(w, kw, max_dist=max_dist)
        if d <= max_dist:
            candidates.append((d, kw))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    min_dist = candidates[0][0]
    best_matches = [kw for d, kw in candidates if d == min_dist]

    # Skip ambiguous matches (multiple keywords tie for minimum edit distance)
    if len(best_matches) > 1:
        return None

    return best_matches[0]


def _is_declaration_position(tokens: List[Dict[str, Any]], idx: int) -> bool:
    cur = tokens[idx]
    if cur["kind"] != "IDENT":
        return False
    if cur["value"] in ALL_C_KEYWORDS:
        return False

    prev = tokens[idx - 1] if idx > 0 else None
    nxt = tokens[idx + 1] if idx + 1 < len(tokens) else None

    # Must be followed by an identifier (variable/function name), pointer '*',
    # or another declaration type keyword (e.g. `unsgined int x;`)
    if nxt is None:
        return False
    if nxt["kind"] == "IDENT":
        if nxt["value"] in (ALL_C_KEYWORDS - set(DECL_TYPE_KEYWORDS)):
            return False
    elif nxt["kind"] == "SYMBOL" and nxt["value"] == "*":
        pass
    else:
        return False

    # Check preceding context
    if prev is None:
        return True
    if prev["kind"] == "SYMBOL" and prev["value"] in ("{", ";", "}"):
        return True
    if prev["kind"] == "IDENT" and prev["value"] in DECL_TYPE_KEYWORDS:
        return True
    if prev["kind"] == "SYMBOL" and prev["value"] in ("(", ","):
        # for-loop init: e.g. for (inte i = 0; ...)
        if idx >= 2 and tokens[idx - 2]["kind"] == "IDENT" and tokens[idx - 2]["value"] == "for":
            return True
        # function parameter list: check if enclosed in (...) followed by { or ;
        for j in range(idx + 1, len(tokens)):
            if tokens[j]["kind"] == "SYMBOL" and tokens[j]["value"] == ")":
                if j + 1 < len(tokens) and tokens[j + 1]["kind"] == "SYMBOL" and tokens[j + 1]["value"] in ("{", ";"):
                    return True
                break

    return False


def fix_keyword_typos_fuzzy(source: str) -> Tuple[str, Optional[str]]:
    """
    Fuzzy typo correction for type keywords in declaration position.
    Within edit distance 1 for keywords of <= 4 letters, 2 for longer ones.
    Skips ambiguous matches.
    Returns: (new_source, description_or_None)
    """
    tokens = _tokenize_code(source)
    if not tokens:
        return source, None

    for idx, tok in enumerate(tokens):
        if not _is_declaration_position(tokens, idx):
            continue

        word = tok["value"]
        best = _closest_declaration_keyword(word)
        if best is None or best == word:
            continue

        new_source = source[: tok["start"]] + best + source[tok["end"] :]
        return new_source, f"corrected keyword typo '{word}' -> '{best}'"

    return source, None


# =====================================================================


# =====================================================================
# Week 7 & 8 Deterministic Repair Rules
# =====================================================================

def fix_missing_colon_case_default(source: str) -> Tuple[str, Optional[str]]:
    lines = source.splitlines(keepends=True)
    for idx, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        m_def = re.search(r"\bdefault\b(?!\s*:)", line)
        if m_def:
            end_pos = m_def.end()
            new_line = line[:end_pos] + ":" + line[end_pos:]
            lines[idx] = new_line + raw_line[len(line):]
            return "".join(lines), "inserted missing ':' after 'default'"

        m_case = re.search(r"\bcase\s+([^:;\r\n{]+)(?<!:)$", line)
        if m_case:
            content = m_case.group(1).rstrip()
            if not content.endswith(":"):
                new_line = line[:m_case.start(1)] + content + ":" + line[m_case.start(1) + len(content):]
                lines[idx] = new_line + raw_line[len(line):]
                return "".join(lines), "inserted missing ':' after 'case'"
    return source, None


def fix_unbalanced_braces_initializer(source: str) -> Tuple[str, Optional[str]]:
    lines = source.splitlines(keepends=True)
    for idx, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        if "{" in line and "}" not in line and line.strip().endswith(";"):
            pos = line.rfind(";")
            new_line = line[:pos] + "}" + line[pos:]
            lines[idx] = new_line + raw_line[len(line):]
            return "".join(lines), "inserted missing '}' in initializer"
    return source, None


def fix_struct_missing_semicolon(source: str) -> Tuple[str, Optional[str]]:
    lines = source.splitlines(keepends=True)
    in_struct = False
    brace_depth = 0
    for idx, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        if re.search(r"\bstruct\b\s+[A-Za-z_]\w*\s*\{", line):
            in_struct = True
        if in_struct:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0 and "}" in line:
                r_brace_pos = line.rfind("}")
                after_brace = line[r_brace_pos + 1:].strip()
                if not after_brace.startswith(";") and not after_brace.endswith(";"):
                    new_line = line[:r_brace_pos + 1] + ";" + line[r_brace_pos + 1:]
                    lines[idx] = new_line + raw_line[len(line):]
                    return "".join(lines), "inserted missing ';' after struct declaration"
                in_struct = False
    return source, None


def fix_struct_member_missing_semicolon(source: str) -> Tuple[str, Optional[str]]:
    lines = source.splitlines(keepends=True)
    in_struct = False
    for idx, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        if re.search(r"\bstruct\b\s+[A-Za-z_]\w*\s*\{", line):
            in_struct = True
            continue
        if in_struct:
            if "}" in line:
                in_struct = False
                continue
            stripped = line.strip()
            if stripped and not stripped.endswith(";") and not stripped.endswith("{") and not stripped.endswith("}"):
                if re.match(r"^(?:int|float|char|void|double|short|long|unsigned|signed|struct\s+[A-Za-z_]\w*)\s+\*?[A-Za-z_]\w*(?:\[[^\]]*\])?$", stripped):
                    new_line = line + ";"
                    lines[idx] = new_line + raw_line[len(line):]
                    return "".join(lines), "inserted missing ';' after struct member declaration"
    return source, None
# Shared Rule Dispatcher with Strict Safety Check
# =====================================================================

def try_week5_rules(
    working: str,
    cur_error_count: int,
    parse_source_fn,
    source_label: str = "week5-rule",
) -> Tuple[Optional[str], Optional[str], Any, Any, Any]:
    """
    Attempts to apply week 5 rules (fix_split_operators, then fix_keyword_typos_fuzzy).
    SAFETY: accepts a change ONLY if the ANTLR error count drops.
    Returns:
      (new_working, rule_desc, tree, listeners, parser) if successful,
      else (None, None, None, None, None).
    """
    # 1) Try preprocessor directive fixes
    cand_src, cand_msg = repair_preprocessor_directives(working)
    if cand_msg is not None and cand_src != working:
        tree_try, listeners_try, parser_try = parse_source_fn(cand_src, source_label)
        if tree_try is not None:
            err_count = sum(len(l.errors) for l in listeners_try.values())
            if err_count < cur_error_count:
                return cand_src, cand_msg, tree_try, listeners_try, parser_try

    # 2) Try missing colon after case / default
    cand_src, cand_msg = fix_missing_colon_case_default(working)
    if cand_msg is not None and cand_src != working:
        tree_try, listeners_try, parser_try = parse_source_fn(cand_src, source_label)
        if tree_try is not None:
            err_count = sum(len(l.errors) for l in listeners_try.values())
            if err_count < cur_error_count:
                return cand_src, cand_msg, tree_try, listeners_try, parser_try

    # 3) Try unbalanced braces in initializer
    cand_src, cand_msg = fix_unbalanced_braces_initializer(working)
    if cand_msg is not None and cand_src != working:
        tree_try, listeners_try, parser_try = parse_source_fn(cand_src, source_label)
        if tree_try is not None:
            err_count = sum(len(l.errors) for l in listeners_try.values())
            if err_count < cur_error_count:
                return cand_src, cand_msg, tree_try, listeners_try, parser_try

    # 4) Try missing semicolon after struct
    cand_src, cand_msg = fix_struct_missing_semicolon(working)
    if cand_msg is not None and cand_src != working:
        tree_try, listeners_try, parser_try = parse_source_fn(cand_src, source_label)
        if tree_try is not None:
            err_count = sum(len(l.errors) for l in listeners_try.values())
            if err_count < cur_error_count:
                return cand_src, cand_msg, tree_try, listeners_try, parser_try

    # 5) Try missing semicolon on struct member
    cand_src, cand_msg = fix_struct_member_missing_semicolon(working)
    if cand_msg is not None and cand_src != working:
        tree_try, listeners_try, parser_try = parse_source_fn(cand_src, source_label)
        if tree_try is not None:
            err_count = sum(len(l.errors) for l in listeners_try.values())
            if err_count < cur_error_count:
                return cand_src, cand_msg, tree_try, listeners_try, parser_try

    # 6) Try split operators
    cand_src, cand_msg = fix_split_operators(working)
    if cand_msg is not None and cand_src != working:
        tree_try, listeners_try, parser_try = parse_source_fn(cand_src, source_label)
        if tree_try is not None:
            err_count = sum(len(l.errors) for l in listeners_try.values())
            if err_count < cur_error_count:
                return cand_src, cand_msg, tree_try, listeners_try, parser_try

    # 2) Try fuzzy keyword typos
    cand_src, cand_msg = fix_keyword_typos_fuzzy(working)
    if cand_msg is not None and cand_src != working:
        tree_try, listeners_try, parser_try = parse_source_fn(cand_src, source_label)
        if tree_try is not None:
            err_count = sum(len(l.errors) for l in listeners_try.values())
            if err_count < cur_error_count:
                return cand_src, cand_msg, tree_try, listeners_try, parser_try

    return None, None, None, None, None
