import re
from typing import Dict, Any, Optional, Tuple, List

C_KEYWORDS = {
    "int", "float", "char", "void",
    "return", "if", "else",
    "while", "for",
    "break", "continue",
}


IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def damerau_levenshtein(a: str, b: str) -> int:
    """
    Damerau–Levenshtein distance (optimal string alignment variant).
    Good enough for typos: insertion, deletion, substitution, transposition.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    la, lb = len(a), len(b)
    dp = [[0] * (lb + 1) for _ in range(la + 1)]

    for i in range(la + 1):
        dp[i][0] = i
    for j in range(lb + 1):
        dp[0][j] = j

    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,        # deletion
                dp[i][j - 1] + 1,        # insertion
                dp[i - 1][j - 1] + cost  # substitution
            )
            # transposition
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                dp[i][j] = min(dp[i][j], dp[i - 2][j - 2] + 1)

    return dp[la][lb]


def _common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


STD_LIB_SYMBOLS: Dict[str, Dict[str, Any]] = {
    "printf": {"type": "int", "line": 0},
    "scanf": {"type": "int", "line": 0},
    "malloc": {"type": "void*", "line": 0},
    "free": {"type": "void", "line": 0},
    "strlen": {"type": "int", "line": 0},
    "strcpy": {"type": "char*", "line": 0},
    "strncpy": {"type": "char*", "line": 0},
    "strcmp": {"type": "int", "line": 0},
    "strncmp": {"type": "int", "line": 0},
    "puts": {"type": "int", "line": 0},
    "gets": {"type": "char*", "line": 0},
    "putchar": {"type": "int", "line": 0},
    "getchar": {"type": "int", "line": 0},
    "sprintf": {"type": "int", "line": 0},
    "snprintf": {"type": "int", "line": 0},
    "exit": {"type": "void", "line": 0},
}


def _best_symbol_match(
    word: str,
    symbols: Dict[str, Dict[str, Any]],
    max_dist: int
) -> Optional[str]:
    """
    Find a unique best match from declared symbols and standard library symbols using DL distance.
    """
    if word in C_KEYWORDS:
        return None

    best_name: Optional[str] = None
    best_key: Optional[tuple] = None
    tie = False

    merged_symbols = dict(STD_LIB_SYMBOLS)
    if symbols:
        merged_symbols.update(symbols)

    for name, info in merged_symbols.items():
        if name in C_KEYWORDS:
            continue

        if name == word:
            return name

        d = damerau_levenshtein(word, name)
        if d > max_dist:
            continue

        prefix = _common_prefix_len(word, name)

        # Prefer later declarations (often closer scope)
        decl_line = info.get("line", 0)

        # Ranking tuple (smaller is better except prefix which we negate)
        key = (
            d,                # primary: distance
            -prefix,          # secondary: larger prefix better
            -decl_line,       # tertiary: later declaration preferred
            name              # stable deterministic ordering
        )

        if best_key is None or key < best_key:
            best_key = key
            best_name = name
            tie = False
        elif key == best_key:
            tie = True

    if best_name is None:
        return None
    if tie:
        return None

    return best_name

def _line_col_to_abs_index(text: str, line_1based: int, col_0based: int) -> Optional[int]:
    """
    Convert (line, col) to absolute index in string.
    Handles both \\n and \\r\\n properly by scanning the original text.
    """
    if line_1based <= 0:
        return None
    if col_0based < 0:
        col_0based = 0

    cur_line = 1
    i = 0
    n = len(text)

    # Move i to start of desired line
    while i < n and cur_line < line_1based:
        if text[i] == "\n":
            cur_line += 1
        i += 1

    if cur_line != line_1based:
        return None

    # Now i is at start-of-line (or somewhere after scanning newlines)
    # But for CRLF we might be just after '\n' already; scanning logic still correct.
    return min(i + col_0based, n)


def _find_identifier_span_in_line(line_text: str, col: int, expected_name: Optional[str] = None) -> Optional[Tuple[int, int, str]]:
    """
    Given a single line and a column, return (start, end, ident) for a nearby identifier.

    Strategy:
    1) If expected_name is provided and exists on the line, prefer the occurrence whose span is nearest to col.
    2) Otherwise, find an identifier whose span contains col.
    3) Otherwise, pick the nearest identifier span to col (left/right).
    """
    if col < 0:
        col = 0
    if col > len(line_text):
        col = len(line_text)

    matches = list(IDENT_RE.finditer(line_text))
    if not matches:
        return None

    # Prefer exact expected identifier occurrences if provided
    if expected_name:
        cand = [m for m in matches if m.group(0) == expected_name]
        if cand:
            best = None
            best_dist = 10**9
            for m in cand:
                s, e = m.start(), m.end()
                # distance from col to span
                if s <= col < e:
                    dist = 0
                elif col < s:
                    dist = s - col
                else:
                    dist = col - e
                if dist < best_dist:
                    best_dist = dist
                    best = m
            if best is not None:
                return best.start(), best.end(), best.group(0)

    # If col is inside an identifier, use it
    for m in matches:
        if m.start() <= col < m.end():
            return m.start(), m.end(), m.group(0)

    # Otherwise choose nearest identifier to col
    best = None
    best_dist = 10**9
    for m in matches:
        s, e = m.start(), m.end()
        if col < s:
            dist = s - col
        else:
            dist = col - e
        if dist < best_dist:
            best_dist = dist
            best = m

    if best is None:
        return None

    return best.start(), best.end(), best.group(0)


def fix_identifier_typo_at(
    src: str,
    line: int,
    col: int,
    symbols: Dict[str, Dict[str, Any]],
    max_dist: int = 2,
    expected_name: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """
    Fix an identifier typo at/near (line, col) by replacing it with the closest declared symbol.

    This is intentionally conservative:
    - Only replaces identifiers
    - Must have a unique best match within max_dist
    - If symbol has 'line', we prefer declared-before-use safety check (best-effort)

    expected_name (optional):
    - If you already know the undeclared identifier text (e.g., from checker), pass it here.
      We will try to target that exact identifier occurrence on the line.
    """

    # Do NOT auto-correct known stdlib / security-sensitive function names.
    # These may legitimately be undeclared in this subset grammar but must be
    # preserved so that security analysis and auto-fix can see them.
    PROTECTED_IDENTIFIERS = {
        "printf",
        "scanf",
        "gets",
        "fgets",
        "strcpy",
        "strncpy",
        "strcat",
        "strncat",
        "sprintf",
        "snprintf",
        "vsprintf",
        "vsnprintf",
        "system",
        "popen",
        "execl",
        "execv",
        "execvp",
        "execve",
        "WinExec",
        "ShellExecute",
        "CreateProcess",
        "malloc",
        "calloc",
        "realloc",
        "free",
        "getenv",
        "open",
    }

    merged_symbols = dict(STD_LIB_SYMBOLS)
    if symbols:
        merged_symbols.update(symbols)
    if not merged_symbols:
        return src, None

    # Split into lines without losing raw text indexing for replacement
    lines = src.splitlines(keepends=True)
    idx = line - 1
    if idx < 0 or idx >= len(lines):
        return src, None

    raw_line = lines[idx]
    line_no_nl = raw_line.rstrip("\r\n")
    nl = raw_line[len(line_no_nl):]

    # Find identifier span in this line (robust to column mismatch)
    span = _find_identifier_span_in_line(line_no_nl, col, expected_name=expected_name)
    if span is None:
        return src, None

    start_in_line, end_in_line, word = span

    # Do not "fix" protected identifiers
    if word in PROTECTED_IDENTIFIERS:
        return src, None

    # If the identifier is already declared, no fix needed
    if word in symbols:
        return src, None

    # Find best match among declared and standard symbols
    best = _best_symbol_match(word, merged_symbols, max_dist=max_dist)
    if best is None:
        return src, None

    # Never rewrite TO a dangerous security sink
    DANGEROUS_SINKS = {"gets", "system", "popen"}
    if best in DANGEROUS_SINKS:
        return src, None

    # Optional safety: declared-before-use (best-effort)
    info = merged_symbols.get(best, {})
    decl_line = info.get("line")
    if isinstance(decl_line, int) and decl_line > 0:
        if decl_line > line:
            return src, None

    # Apply replacement in the single line
    new_line = line_no_nl[:start_in_line] + best + line_no_nl[end_in_line:]
    lines[idx] = new_line + nl
    new_src = "".join(lines)

    return new_src, f"fixed identifier typo: {word} -> {best}"