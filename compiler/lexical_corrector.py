from __future__ import annotations

import re
from typing import Optional, Tuple, List


# Keywords supported by your grammar/project.
# Keep this aligned with the grammar.
# NOTE:
# - "main" is intentionally NOT treated as a generic keyword typo target here.
# - lexical typo correction must stay conservative.
KEYWORDS = [
    "int",
    "return",
    "if",
    "else",
    "while",
    "for",
    "break",
    "continue",
    "char",
    "float",
    "double",
    "void",
    "unsigned",
    "signed",
    "short",
    "long",
]

# Safe single-character normalizations that often appear from copy/paste.
CHAR_NORMALIZATIONS = {
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "—": "-",
    "–": "-",
    "；": ";",
    "，": ",",
    "（": "(",
    "）": ")",
    "｛": "{",
    "｝": "}",
    "＝": "=",
    "＜": "<",
    "＞": ">",
}

# Safe token-level normalizations.
TOKEN_NORMALIZATIONS = {
    "=<=": "<=",
    "=>=": ">=",
    "=<": "<=",
    "=>": ">=",
    "==>": "=>",
}

IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def fix_common_lexical_issues(source_text: str) -> Tuple[str, List[str]]:
    """
    Fast, deterministic lexical cleanup.

    Returns:
        (new_source, list_of_applied_fixes)

    Scope:
    - character normalization
    - safe token normalization outside strings/comments
    - conservative keyword typo correction outside strings/comments
    """
    fixes: List[str] = []

    new_text, char_fixes = _normalize_characters(source_text)
    fixes.extend(char_fixes)

    new_text, token_fixes = _normalize_common_tokens(new_text)
    fixes.extend(token_fixes)

    new_text, keyword_fixes = _fix_keyword_typos(new_text)
    fixes.extend(keyword_fixes)

    return new_text, fixes


# ------------------------------------------------------------------
# Character normalization
# ------------------------------------------------------------------

def _normalize_characters(source_text: str) -> Tuple[str, List[str]]:
    fixes: List[str] = []
    out_chars: List[str] = []

    changed_pairs = set()

    for ch in source_text:
        if ch in CHAR_NORMALIZATIONS:
            repl = CHAR_NORMALIZATIONS[ch]
            out_chars.append(repl)
            changed_pairs.add((ch, repl))
        else:
            out_chars.append(ch)

    for old, new in sorted(changed_pairs):
        fixes.append(f"normalized character {repr(old)} -> {repr(new)}")

    return "".join(out_chars), fixes


# ------------------------------------------------------------------
# Token normalization outside strings/comments
# ------------------------------------------------------------------

def _normalize_common_tokens(source_text: str) -> Tuple[str, List[str]]:
    segments = _split_code_and_noncode(source_text)
    fixes: List[str] = []
    changed = False

    normalized_segments: List[str] = []

    for kind, chunk in segments:
        if kind != "code":
            normalized_segments.append(chunk)
            continue

        updated = chunk
        for bad, good in TOKEN_NORMALIZATIONS.items():
            if bad in updated:
                count = updated.count(bad)
                updated = updated.replace(bad, good)
                if count > 0:
                    fixes.append(f"normalized token {bad!r} -> {good!r} ({count}x)")
                    changed = True

        normalized_segments.append(updated)

    if not changed:
        return source_text, []

    return "".join(normalized_segments), fixes


# ------------------------------------------------------------------
# Conservative keyword typo correction
# ------------------------------------------------------------------

def _fix_keyword_typos(source_text: str) -> Tuple[str, List[str]]:
    """
    Extremely conservative keyword typo correction.

    Design goals:
    - NEVER mutate common short identifiers like i/j/k into keywords
    - only fix a small allowlist of common, high-confidence typos
    - do not use generic edit-distance matching for lexical correction
    - stay outside strings/comments/chars
    """
    segments = _split_code_and_noncode(source_text)
    fixes: List[str] = []
    changed = False

    rebuilt: List[str] = []

    for kind, chunk in segments:
        if kind != "code":
            rebuilt.append(chunk)
            continue

        local_changes: List[Tuple[str, str]] = []

        def repl(match: re.Match[str]) -> str:
            nonlocal changed
            word = match.group(0)

            # Already a supported keyword -> keep it
            if word in KEYWORDS:
                return word

            # Very important safety: never keyword-correct 1-char identifiers
            # like i, j, k, x, y, z.
            if len(word) <= 1:
                return word

            replacement = _best_keyword_replacement(word)
            if replacement is None or replacement == word:
                return word

            local_changes.append((word, replacement))
            changed = True
            return replacement

        updated = IDENT_RE.sub(repl, chunk)
        rebuilt.append(updated)

        for old, new in local_changes:
            fixes.append(f"corrected keyword typo {old!r} -> {new!r}")

    if not changed:
        return source_text, []

    return "".join(rebuilt), fixes


def _best_keyword_replacement(word: str) -> Optional[str]:
    """
    High-confidence typo map only.

    No generic edit-distance search here.
    That was the source of the bug: 'i' -> 'if'.

    Keep this intentionally narrow.
    """
    common_map = {
        "retrun": "return",
        "reutrn": "return",
        "retun": "return",
        "retrn": "return",

        "innt": "int",
        "itn": "int",

        "whlie": "while",
        "wile": "while",

        "esle": "else",

        "contniue": "continue",
        "continuee": "continue",

        "breka": "break",

        "fro": "for",

        "flota": "float",
        "flaot": "float",

        "doulbe": "double",
        "doubel": "double",

        "unsinged": "unsigned",
        "unsignd": "unsigned",
        "unsigend": "unsigned",

        "singed": "signed",
        "signd": "signed",

        "shrot": "short",
        "sohrt": "short",
        "shotr": "short",

        "lnog": "long",
        "lonng": "long",

        "viod": "void",

        "cahr": "char",
        "prinft": "printf",
        "scnaf": "scanf",
    }

    return common_map.get(word)


# ------------------------------------------------------------------
# Code/non-code splitting
# ------------------------------------------------------------------

def _split_code_and_noncode(source_text: str) -> List[Tuple[str, str]]:
    """
    Splits source into tagged chunks:
      ("code", ...)
      ("noncode", ...)
    Non-code includes strings, char literals, // comments, /* */ comments.

    This is conservative and good enough for preprocessing.
    """
    result: List[Tuple[str, str]] = []
    i = 0
    n = len(source_text)

    code_buf: List[str] = []

    def flush_code() -> None:
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