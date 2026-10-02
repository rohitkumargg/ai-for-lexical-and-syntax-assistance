"""Side-effect safe removal and preservation for unused declarations.

Criterion 3 Enforcement:
- If an unused variable has no side-effecting initializer (e.g. 'int x;' or 'int x = 5;'):
  it is safely removed.
- If an unused variable has a side-effecting initializer (e.g. 'int x = f();' or 'int x = count++;'):
  it MUST NOT delete the side effect. Instead, it converts the statement to 'f();' or 'count++;'.
- For multi-variable declarations ('int a = 1, x = 2;'): only the unused declarator is removed.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple


SIDE_EFFECT_RE = re.compile(
    r"""
    \b[A-Za-z_]\w*\s*\(      # function calls like f(...)
    |\+\+|\-\-               # increments / decrements
    |(?<![=!<>])=(?![=])     # assignments
    """,
    re.VERBOSE,
)


def _contains_side_effects(expr: str) -> bool:
    return bool(SIDE_EFFECT_RE.search(expr))


def _split_declarators(decl_body: str) -> list[str]:
    """Splits declarators in a declaration list, respecting commas inside (), {}, []."""
    decls = []
    cur = []
    depth_paren = 0
    depth_brace = 0
    depth_bracket = 0
    in_quote = False
    quote_char = ""

    for ch in decl_body:
        if in_quote:
            cur.append(ch)
            if ch == quote_char:
                in_quote = False
            continue

        if ch in ("'", '"'):
            in_quote = True
            quote_char = ch
            cur.append(ch)
        elif ch == "(":
            depth_paren += 1
            cur.append(ch)
        elif ch == ")":
            depth_paren = max(0, depth_paren - 1)
            cur.append(ch)
        elif ch == "{":
            depth_brace += 1
            cur.append(ch)
        elif ch == "}":
            depth_brace = max(0, depth_brace - 1)
            cur.append(ch)
        elif ch == "[":
            depth_bracket += 1
            cur.append(ch)
        elif ch == "]":
            depth_bracket = max(0, depth_bracket - 1)
            cur.append(ch)
        elif ch == "," and depth_paren == 0 and depth_brace == 0 and depth_bracket == 0:
            decls.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)

    if cur:
        decls.append("".join(cur).strip())

    return decls


def _extract_name_from_declarator(decl: str) -> Optional[str]:
    """Extracts identifier name from declarator like '*p', 'arr[10]', 'x = 5'."""
    part = decl.split("=")[0].strip()
    part = part.split("[")[0].strip()
    part = part.lstrip("* \t")
    m = re.search(r"\b([A-Za-z_]\w*)\b", part)
    return m.group(1) if m else None


def _is_trivial_literal(expr: str) -> bool:
    e = expr.strip()
    if re.match(r"^[+-]?(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d*)?|\.\d+)[uUlLfF]*$", e):
        return True
    if re.match(r"^'(?:\\.|[^\\'])*'$", e):
        return True
    if re.match(r'^"(?:\\.|[^"\\])*"$', e):
        return True
    if e in ("NULL", "true", "false", "0"):
        return True
    return False


def remove_unused_decl_at(
    source: str,
    decl_line: int,
    decl_col: int = 0,
    name: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """
    Remove or convert an unused declaration at the given line, preserving side effects.
    """
    lines = source.splitlines(keepends=True)
    idx = int(decl_line or 1) - 1
    if idx < 0 or idx >= len(lines):
        return source, None

    orig_line = lines[idx]
    line_no_nl = orig_line.rstrip("\r\n")
    indent = line_no_nl[:len(line_no_nl) - len(line_no_nl.lstrip())]

    # Must contain a semicolon
    if ";" not in line_no_nl:
        return source, None

    # Separate code from trailing comments
    comment = ""
    code_part = line_no_nl
    if "//" in line_no_nl:
        pos = line_no_nl.find("//")
        comment = line_no_nl[pos:]
        code_part = line_no_nl[:pos]

    semi_idx = code_part.rfind(";")
    if semi_idx == -1:
        return source, None

    stmt = code_part[:semi_idx].strip()

    # Match declaration pattern: <type> <declarators>
    # Type can be: int, unsigned int, signed long, long long, char*, struct Foo, etc.
    type_kws = r"(?:void|char|short|int|long|float|double|signed|unsigned|size_t)"
    type_match = re.match(
        rf"^(?P<type>(?:struct\s+[A-Za-z_]\w*|(?:{type_kws}\b\s*)+|[A-Za-z_]\w+)(?:\s*\*+)*)\s+(?P<decls>[*A-Za-z_].*)$",
        stmt,
    )
    if not type_match:
        return source, None

    type_str = type_match.group("type").strip()
    decls_str = type_match.group("decls").strip()

    decls = _split_declarators(decls_str)
    if not decls:
        return source, None

    # Find the target declarator matching name
    target_idx = -1
    for i, d in enumerate(decls):
        d_name = _extract_name_from_declarator(d)
        if name and d_name == name:
            target_idx = i
            break
        elif not name and len(decls) == 1:
            target_idx = 0
            name = d_name
            break

    if target_idx == -1:
        return source, None

    target_decl = decls[target_idx]

    # Check if initializer exists and if it has side effects
    init_expr = None
    if "=" in target_decl:
        init_expr = target_decl.split("=", 1)[1].strip()

    has_side_effect = init_expr is not None and _contains_side_effects(init_expr)

    # Criterion 3: Unused variable with non-trivial computation expression (e.g. 'int r1 = f & a;')
    # must not be deleted if it is neither a simple literal constant nor a side effect.
    if init_expr is not None and not has_side_effect and not _is_trivial_literal(init_expr):
        return source, None

    # Case 1: Single declarator in statement
    if len(decls) == 1:
        if has_side_effect and init_expr:
            # Preserve side effect as an expression statement
            nl = orig_line[len(line_no_nl):]
            lines[idx] = f"{indent}{init_expr};{nl}"
            return "".join(lines), f"converted unused variable '{name}' with side-effects to expression statement"
        else:
            # Completely safe to delete the line
            del lines[idx]
            return "".join(lines), f"removed unused declaration: {name}"

    # Case 2: Multi-variable declaration (e.g. 'int a = 1, x = f();')
    remaining_decls = [d for i, d in enumerate(decls) if i != target_idx]
    nl = orig_line[len(line_no_nl):]

    new_decl_stmt = f"{indent}{type_str} {', '.join(remaining_decls)};"
    if has_side_effect and init_expr:
        # Emit remaining decls + expression statement for side effect
        lines[idx] = f"{new_decl_stmt}\n{indent}{init_expr};{nl}"
        return "".join(lines), f"removed unused '{name}', preserving side-effect expression"
    else:
        lines[idx] = f"{new_decl_stmt}{nl}"
        return "".join(lines), f"removed unused variable '{name}' from multi-declaration"