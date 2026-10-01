# keyword_corrector.py
from __future__ import annotations

import re
from typing import List, Optional, Tuple, Dict


# =========================
# Config (keep aligned with your grammar)
# =========================
TYPE_KEYWORDS = ["int", "float", "char", "void", "double", "unsigned", "signed", "short", "long"]

# Token boundary identifier
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


# =========================
# Public API
# =========================
def fix_keyword_typos(source: str) -> Tuple[str, Optional[str]]:
    """
    Apply ONE safe keyword-typo fix per call.
    Right now: only fixes TYPE keywords (int/float/char/void) and only
    when the token is in a place where your grammar expects a typeSpecifier.

    Returns: (new_source, message_or_None)
    """
    tokens = _tokenize_code(source)
    if not tokens:
        return source, None

    # 1) Detect function headers: type IDENT '(' ... ')' '{'
    #    Mark tokens within param list so we can fix param types safely.
    param_ranges = _find_function_param_ranges(tokens)

    # 2) Find first eligible type-position identifier that is a near-miss of a type keyword
    for idx, tok in enumerate(tokens):
        if tok["kind"] != "IDENT":
            continue

        word = tok["value"]
        if word in TYPE_KEYWORDS:
            continue

        if not _is_type_position(tokens, idx, param_ranges):
            continue

        best = _closest_type_keyword(word)
        if best is None:
            continue

        # Replace once
        new_src = source[: tok["start"]] + best + source[tok["end"] :]
        return new_src, f"fixed type keyword typo: {word} -> {best}"

    return source, None


# =========================
# Tokenizer (ignores strings + comments)
# =========================
def _tokenize_code(src: str) -> List[Dict[str, object]]:
    """
    Produces a conservative token stream for:
      - IDENT, NUMBER, SYMBOL
    Skips:
      - whitespace
      - // line comments
      - /* block comments */
      - string literals "..."
      - char literals '...'

    Each token is dict: {kind, value, start, end} where [start,end) are indices in src.
    """
    tokens: List[Dict[str, object]] = []
    i = 0
    n = len(src)

    def add(kind: str, val: str, s: int, e: int) -> None:
        tokens.append({"kind": kind, "value": val, "start": s, "end": e})

    while i < n:
        ch = src[i]

        # whitespace
        if ch.isspace():
            i += 1
            continue

        # line comment //
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            i += 2
            while i < n and src[i] != "\n":
                i += 1
            continue

        # block comment /* ... */
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i = min(n, i + 2)  # skip closing */
            continue

        # string literal "..."
        if ch == '"':
            i += 1
            while i < n:
                if src[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                if src[i] == '"':
                    i += 1
                    break
                i += 1
            continue

        # char literal '...'
        if ch == "'":
            i += 1
            while i < n:
                if src[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                if src[i] == "'":
                    i += 1
                    break
                i += 1
            continue

        # identifier
        if ch.isalpha() or ch == "_":
            s = i
            i += 1
            while i < n and (src[i].isalnum() or src[i] == "_"):
                i += 1
            add("IDENT", src[s:i], s, i)
            continue

        # number (int/float) - we don't need exact classification here
        if ch.isdigit():
            s = i
            i += 1
            while i < n and (src[i].isdigit() or src[i] == "."):
                i += 1
            add("NUMBER", src[s:i], s, i)
            continue

        # symbol (single-char is enough for our gates here)
        add("SYMBOL", ch, i, i + 1)
        i += 1

    return tokens


# =========================
# Function header detection
# =========================
def _find_function_param_ranges(tokens: List[Dict[str, object]]) -> List[Tuple[int, int]]:
    """
    Find ranges [l, r] (token indices) that correspond to *parameter list contents*
    for function definitions that match your grammar shape:

        type IDENT '(' paramList? ')' '{'

    Returns list of (l, r) inclusive bounds for tokens inside the parentheses,
    not including the parentheses themselves.
    """
    ranges: List[Tuple[int, int]] = []
    m = len(tokens)

    # helper to find matching ')'
    def find_matching_rparen(open_idx: int) -> Optional[int]:
        depth = 0
        for j in range(open_idx, m):
            v = tokens[j]["value"]
            k = tokens[j]["kind"]
            if k == "SYMBOL" and v == "(":
                depth += 1
            elif k == "SYMBOL" and v == ")":
                depth -= 1
                if depth == 0:
                    return j
        return None

    i = 0
    while i + 4 < m:
        t0, t1, t2 = tokens[i], tokens[i + 1], tokens[i + 2]
        if (
            t0["kind"] == "IDENT"
            and t0["value"] in TYPE_KEYWORDS
            and t1["kind"] == "IDENT"
            and t2["kind"] == "SYMBOL"
            and t2["value"] == "("
        ):
            rpar = find_matching_rparen(i + 2)
            if rpar is not None and rpar + 1 < m:
                # must be followed by '{' for a definition or ';' for a prototype
                nxt = tokens[rpar + 1]
                if nxt["kind"] == "SYMBOL" and nxt["value"] in ("{", ";"):
                    l = i + 3
                    r = rpar - 1
                    if l <= r:
                        ranges.append((l, r))
                    else:
                        # empty param list: still fine, just no range
                        pass
                    i = rpar + 2
                    continue
        i += 1

    return ranges


def _in_any_range(idx: int, ranges: List[Tuple[int, int]]) -> bool:
    for l, r in ranges:
        if l <= idx <= r:
            return True
    return False


# =========================
# Type-position gates
# =========================
def _prev_nontrivia_token(tokens: List[Dict[str, object]], idx: int) -> Optional[Dict[str, object]]:
    # Our tokenizer already skips whitespace/comments/strings, so just idx-1.
    if idx - 1 >= 0:
        return tokens[idx - 1]
    return None


def _next_token(tokens: List[Dict[str, object]], idx: int) -> Optional[Dict[str, object]]:
    if idx + 1 < len(tokens):
        return tokens[idx + 1]
    return None


def _is_type_position(tokens: List[Dict[str, object]], idx: int, param_ranges: List[Tuple[int, int]]) -> bool:
    """
    True if tokens[idx] is in a location where grammar expects a typeSpecifier:

    1) Declaration start inside blocks:
       after '{' or ';' or '}' or start-of-file, and followed by IDENT (variable name)
    2) for-loop init declaration:
       for ( <type> IDENT ... ; ... )  -> after '(' where previous token is 'for'
    3) Function parameter list:
       inside functionDef param list range, after '(' or ',' and followed by IDENT (param name)
    4) Function return type:
       start-of-file or after '}', followed by IDENT '(' ... '{' (handled indirectly by param range finder,
       but we also gate it directly here)
    """
    cur = tokens[idx]
    prev = _prev_nontrivia_token(tokens, idx)
    nxt = _next_token(tokens, idx)

    # Must be followed by an identifier (the declared name)
    if nxt is None or nxt["kind"] != "IDENT":
        return False

    # 3) Parameter type: inside a function param list range and preceded by '(' or ','
    if _in_any_range(idx, param_ranges):
        if prev is not None and prev["kind"] == "SYMBOL" and prev["value"] in ("(", ","):
            return True

    # 2) for-init type: pattern "for" "(" <type> IDENT ...
    if prev is not None and prev["kind"] == "SYMBOL" and prev["value"] == "(":
        # look one more back for "for"
        if idx - 2 >= 0:
            prev2 = tokens[idx - 2]
            if prev2["kind"] == "IDENT" and prev2["value"] == "for":
                return True

    # 1) Declaration type in blocks / at line starts:
    if prev is None:
        return True
    if prev["kind"] == "SYMBOL" and prev["value"] in ("{", ";", "}"):
        return True

    # 4) Function return type at top-level: after '}' or start, and followed by IDENT '(' ... '{'
    if prev["kind"] == "SYMBOL" and prev["value"] == "}":
        # check next tokens: type IDENT '('
        if idx + 2 < len(tokens):
            t2 = tokens[idx + 2]
            if t2["kind"] == "SYMBOL" and t2["value"] == "(":
                return True

    return False


# =========================
# Typo matching
# =========================
def _closest_type_keyword(word: str) -> Optional[str]:
    """
    Conservative typo matcher for TYPE keywords only.
    - require first character to match (case-insensitive)
    - require small edit distance (OSA Damerau-Levenshtein)
    """
    w = word.strip()
    if not w:
        return None

    best_kw = None
    best_d = 10**9

    for kw in TYPE_KEYWORDS:
        if w[0].lower() != kw[0].lower():
            continue

        # tighter distance for short keywords
        max_dist = 1 if len(kw) <= 3 else 2

        d = _damerau_levenshtein_osa(w.lower(), kw.lower(), max_dist=max_dist)
        if d <= max_dist and d < best_d:
            best_d = d
            best_kw = kw

    return best_kw


def _damerau_levenshtein_osa(a: str, b: str, max_dist: int = 2) -> int:
    """
    Optimal String Alignment (OSA) Damerau-Levenshtein distance.
    Early-exits if a row minimum exceeds max_dist.
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

            # transposition
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