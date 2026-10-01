"""SimpleC Preprocessor pass and directive repair engine.

Architecture Choice:
We chose a two-pass architecture because:
1. Separation of Concerns: Preprocessing is syntactically distinct from grammar.
   It shouldn't pollute parser with macro replacement complexity and character collisions
   (angle brackets in #include <stdio.h> vs less-than operator in expressions).
2. Line Number Preservation: Line numbering is maintained exactly so compiler diagnostics,
   line numbers, and patch ranges remain aligned with user source code.
3. Symbol Table Integration: Macro names (#define NAME value, function-like macros
   #define SQUARE(x) ...) are recorded into symbol table so semantic checker
   recognizes them without emitting false undeclared identifier issues.
4. Deterministic Repairs: Syntax errors in directives (typos like #incude, missing '#',
   unclosed '<' or '"') are detected and repaired before parser sees them.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


def repair_preprocessor_directives(source: str) -> Tuple[str, Optional[str]]:
    """
    Detects and repairs malformed preprocessor directives in source text.
    Handles:
      - missing '>': #include <stdio.h -> #include <stdio.h>
      - missing closing quote: #include "file.h -> #include "file.h"
      - misspelled directives: #incude, #incldue -> #include; #defien, #defin -> #define
      - missing '#': include <stdio.h> -> #include <stdio.h>; define MAX 100 -> #define MAX 100
    Returns: (new_source, fix_description_or_None)
    """
    lines = source.splitlines(keepends=True)

    for idx, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")

        # 1) missing '#' before include
        if re.match(r"^include\s*(<[^>]*>?|\"[^\"]*\"?)", line.strip()):
            repaired_line = re.sub(r"^(\s*)include", r"\1#include", line)
            lines[idx] = repaired_line + raw_line[len(line):]
            return "".join(lines), "added missing '#' before 'include'"

        # 2) missing '#' before define
        if re.match(r"^define\s+[A-Za-z_]\w*", line.strip()):
            repaired_line = re.sub(r"^(\s*)define", r"\1#define", line)
            lines[idx] = repaired_line + raw_line[len(line):]
            return "".join(lines), "added missing '#' before 'define'"

        # 3) misspelled #include
        if re.match(r"^\s*#\s*(?:incude|incldue|inlcude|includ)\b", line):
            repaired_line = re.sub(r"#(?:incude|incldue|inlcude|includ)\b", "#include", line)
            lines[idx] = repaired_line + raw_line[len(line):]
            return "".join(lines), "corrected misspelled '#include' directive"

        # 4) misspelled #define
        if re.match(r"^\s*#\s*(?:defien|defin|defne)\b", line):
            repaired_line = re.sub(r"#(?:defien|defin|defne)\b", "#define", line)
            lines[idx] = repaired_line + raw_line[len(line):]
            return "".join(lines), "corrected misspelled '#define' directive"

        # 5) missing '>' on #include <...
        m_angle = re.match(r"^(\s*#\s*include\s*<[^>\r\n]+)$", line)
        if m_angle and not line.endswith(">"):
            repaired_line = line + ">"
            lines[idx] = repaired_line + raw_line[len(line):]
            return "".join(lines), "added missing '>' to '#include' directive"

        # 6) missing closing quote on #include "..."
        m_quote = re.match(r"^(\s*#\s*include\s*\"[^\"]+)$", line)
        if m_quote and not line.endswith('"'):
            repaired_line = line + '"'
            lines[idx] = repaired_line + raw_line[len(line):]
            return "".join(lines), "added missing closing quote to '#include' directive"

    return source, None


def extract_preprocessor_symbols(source: str) -> Dict[str, Any]:
    """
    Extracts macros and includes from source code.
    Returns: {
      "includes": list of header strings,
      "macros": dict of name -> {"args": [...], "body": str, "is_func": bool}
    }
    """
    includes: List[str] = []
    macros: Dict[str, Any] = {}

    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line.startswith("#"):
            continue

        m_inc = re.match(r"^#\s*include\s*(<[^>]+>|\"[^\"]+\")", line)
        if m_inc:
            includes.append(m_inc.group(1))
            continue

        m_fn = re.match(r"^#\s*define\s+([A-Za-z_]\w*)\(([^)]*)\)\s*(.*)", line)
        if m_fn:
            name = m_fn.group(1)
            raw_args = m_fn.group(2)
            args = [a.strip() for a in raw_args.split(",") if a.strip()]
            body = m_fn.group(3).strip()
            macros[name] = {"args": args, "body": body, "is_func": True}
            continue

        m_obj = re.match(r"^#\s*define\s+([A-Za-z_]\w*)\s*(.*)", line)
        if m_obj:
            name = m_obj.group(1)
            body = m_obj.group(2).strip()
            macros[name] = {"args": [], "body": body, "is_func": False}
            continue

    return {"includes": includes, "macros": macros}


def strip_preprocessor_lines(source: str) -> str:
    """
    Blanks valid preprocessor directive lines so ANTLR parses remaining source
    without syntax errors from directives, while preserving line numbers.
    """
    lines = source.splitlines(keepends=True)
    out: List[str] = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#\s*(?:include\s*(?:<[^>]+>|\"[^\"]+\")|define\s+[A-Za-z_]\w*)", stripped):
            out.append("\n" if line.endswith("\n") else "")
        else:
            out.append(line)
    return "".join(out)
