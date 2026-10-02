"""Conservative and verified source repairs for semantic diagnostics.

All repairs adhere to the 4 Acceptance Criteria:
1. ANTLR zero syntax errors.
2. Targeted issue removed, total issue count decreased, no new issue kinds.
3. Minimal & side-effect safe (touches only related lines, never deletes calls/assignments/++/--).
4. Idempotent (running twice produces no change).

Lossy casts are rejected and downgraded to SUGGESTED.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple


LOSSLESS_CONVERSIONS: Dict[str, Set[str]] = {
    "char": {"short", "int", "long", "long long", "float", "double"},
    "signed char": {"short", "int", "long", "long long", "float", "double"},
    "unsigned char": {"unsigned short", "int", "unsigned int", "long", "unsigned long", "long long", "double"},
    "short": {"int", "long", "long long", "double"},
    "unsigned short": {"int", "unsigned int", "long", "unsigned long", "long long", "double"},
    "int": {"long", "long long", "double"},
    "unsigned int": {"long long", "double"},
    "long": {"long long", "double"},
    "float": {"double"},
}


def is_lossless_cast(from_type: Optional[str], to_type: Optional[str], val: Optional[int] = None) -> bool:
    """Returns True if converting from_type to to_type is value-preserving."""
    if not from_type or not to_type:
        return False

    f = from_type.strip().lower()
    t = to_type.strip().lower()

    if f == t:
        return True

    # NULL / 0 to any pointer type (only literal 0, NULL, or nullptr is lossless)
    if (f in {"0", "null", "nullptr"} or val == 0) and t.endswith("*"):
        return True

    # void* to any pointer or any pointer to void*
    if (f == "void*" and t.endswith("*")) or (f.endswith("*") and t == "void*"):
        return True

    # Same pointer target
    if f.endswith("*") and t.endswith("*") and f == t:
        return True

    # Scalar widening promotions
    allowed = LOSSLESS_CONVERSIONS.get(f, set())
    return t in allowed


def _line_at(source: str, line: int) -> Tuple[list[str], int]:
    lines = source.splitlines(keepends=True)
    idx = int(line or 1) - 1
    if idx < 0 or idx >= len(lines):
        return lines, -1
    return lines, idx


def _replace_line(source: str, line: int, old: str, new: str, note: str) -> Tuple[str, Optional[str]]:
    lines, index = _line_at(source, line)
    if index == -1 or not lines or old == new:
        return source, None
    lines[index] = new
    return "".join(lines), note


def _expected_type(message: str) -> Optional[str]:
    match = re.search(r"(?:to|expects|returns) '([^']+)'", message or "")
    if match:
        return match.group(1)
    match2 = re.search(r"to '([^']+)'", message or "")
    return match2.group(1) if match2 else None


def _source_type(message: str) -> Optional[str]:
    match = re.search(r"(?:Cannot assign|convert|got) '([^']+)'", message or "")
    return match.group(1) if match else None


def _split_balanced_args(args_str: str) -> List[Tuple[int, int, str]]:
    """
    Splits comma-separated arguments while respecting nested parentheses, brackets, and quotes.
    Returns list of (start_index, end_index, arg_text).
    """
    args = []
    depth = 0
    in_quote = False
    quote_char = ""
    start = 0

    for i, ch in enumerate(args_str):
        if in_quote:
            if ch == quote_char:
                in_quote = False
            continue
        if ch in ('"', "'"):
            in_quote = True
            quote_char = ch
        elif ch in ("(", "{", "["):
            depth += 1
        elif ch in (")", "}", "]"):
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            arg_text = args_str[start:i]
            args.append((start, i, arg_text))
            start = i + 1

    if start < len(args_str):
        arg_text = args_str[start:]
        if arg_text.strip() or args:
            args.append((start, len(args_str), arg_text))

    return args


def _safe_rename_identifier(source: str, start_line: int, old_name: str, new_name: str) -> str:
    """
    Renames identifier old_name to new_name within the block scope, avoiding:
    - String literals ("...")
    - Comments (/* ... */ and // ...)
    - Member accesses (obj.name, ptr->name)
    """
    lines = source.splitlines(keepends=True)
    start_idx = max(0, start_line - 1)

    brace_depth = 0
    started = False

    for j in range(start_idx, len(lines)):
        orig_l = lines[j]

        # Tokenize line into strings, comments, and code tokens
        # Pattern matches: comments, strings, member accesses, identifiers, other
        tok_regex = re.compile(
            r"""
            (?P<comment>//.*?$|/\*.*?\*/)
            |(?P<string>\"(?:\\.|[^\"\\])*\"|\'(?:\\.|[^\'\\])*\')
            |(?P<member>(?:\.|\-\>)\s*[A-Za-z_]\w*)
            |(?P<ident>\b[A-Za-z_]\w*\b)
            """,
            re.VERBOSE | re.DOTALL,
        )

        def replace_tok(m):
            if m.group("ident") == old_name:
                return new_name
            return m.group(0)

        lines[j] = tok_regex.sub(replace_tok, orig_l)

        # Track block depth
        code_without_strings = re.sub(r'\"(?:\\.|[^\"\\])*\"|\'(?:\\.|[^\'\\])*\'', '', orig_l)
        brace_depth += code_without_strings.count("{") - code_without_strings.count("}")
        if "{" in code_without_strings:
            started = True
        if started and brace_depth <= 0:
            break

    return "".join(lines)


STD_LIB_PROTOTYPES: Dict[str, str] = {
    "system": "int system(char *command);",
    "gets": "char *gets(char *str);",
    "strcpy": "char *strcpy(char *dest, char *src);",
    "malloc": "void *malloc(int size);",
    "free": "void free(void *ptr);",
    "puts": "int puts(char *s);",
    "strlen": "int strlen(char *s);",
}


def fix_semantic_issue(source: str, issue: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """
    Main rule-based semantic auto-fixer.
    Returns (new_source, note_or_None).
    If an issue cannot be safely fixed, returns (source, None).
    """
    kind = issue.get("kind", "")
    line = int(issue.get("line", 1) or 1)
    col = int(issue.get("col", 0) or 0)
    message = issue.get("msg", "")

    lines, index = _line_at(source, line)
    if not lines or index == -1:
        return source, None
    text = lines[index]

    # -------------------------------------------------------------
    # 1. Type Mismatches & Lossless Casts
    # -------------------------------------------------------------
    if kind in {"type_mismatch", "pointer_type_mismatch", "pointer_assignment_warning", "element_type_mismatch"}:
        expected = _expected_type(message)
        from_t = _source_type(message)

        # Enforce Lossless Casts Table: lossy conversions are SUGGESTED, not auto-fixed
        if expected and from_t and not is_lossless_cast(from_t, expected):
            return source, None

        # Check single line assignment
        match = re.search(r"(?P<prefix>=\s*)(?P<rhs>[^;]+)(?P<end>;)", text)
        if expected and match:
            rhs_str = match.group("rhs").strip()
            # Idempotency guard: do not re-cast
            if not rhs_str.startswith(f"({expected})"):
                replacement = f"{match.group('prefix')}({expected}){rhs_str}{match.group('end')}"
                updated = text[:match.start()] + replacement + text[match.end():]
                return _replace_line(source, line, text, updated, f"inserted explicit cast to '{expected}'")

        # Multi-line assignment
        if expected and "=" in text and ";" not in text:
            for j in range(index + 1, min(len(lines), index + 5)):
                fwd_text = lines[j]
                m_rhs = re.search(r"(?P<indent>^\s*)(?P<rhs>[A-Za-z_]\w*|\d+)(?P<end>\s*;)", fwd_text)
                if m_rhs and not m_rhs.group("rhs").startswith(f"({expected})"):
                    new_fwd = fwd_text[:m_rhs.start()] + f"{m_rhs.group('indent')}({expected}){m_rhs.group('rhs')}{m_rhs.group('end')}" + fwd_text[m_rhs.end():]
                    lines[j] = new_fwd
                    return "".join(lines), f"inserted explicit cast to '{expected}'"
                if ";" in fwd_text:
                    break

    # -------------------------------------------------------------
    # 1b. Invalid Operand Type (float operands in bitwise/shift ops, switch condition -> SUGGESTED)
    # -------------------------------------------------------------
    if kind == "invalid_operand_type":
        # Operations like float in bitwise/shift (&, |, ^, ~, <<, >>) or non-integral switch
        # cannot be cast losslessly without truncating values. Downgrade to SUGGESTED.
        return source, None

    # -------------------------------------------------------------
    # 2. Member Access: dot_on_pointer ('.' -> '->') and arrow_on_value ('->' -> '.')
    # -------------------------------------------------------------
    if kind == "dot_on_pointer":
        # e.g. ptr.field -> ptr->field
        # Look around column or search for .<name>
        mname = issue.get("name")
        if mname:
            updated = re.sub(rf"\.(?=\s*{re.escape(mname)}\b)", "->", text, count=1)
        else:
            updated = text[:col] + text[col:].replace(".", "->", 1)
        if updated != text:
            return _replace_line(source, line, text, updated, "replaced '.' with '->' on pointer")

    if kind == "arrow_on_value":
        # e.g. val->field -> val.field
        mname = issue.get("name")
        if mname:
            updated = re.sub(rf"\-\>(?=\s*{re.escape(mname)}\b)", ".", text, count=1)
        else:
            updated = text[:col] + text[col:].replace("->", ".", 1)
        if updated != text:
            return _replace_line(source, line, text, updated, "replaced '->' with '.' on value")

    # -------------------------------------------------------------
    # 3. Invalid Address-of ('&') and Dereference ('*')
    # -------------------------------------------------------------
    if kind == "invalid_address_of":
        # col points directly at the unary '&' operator
        target_idx = max(0, col)
        if target_idx < len(text) and text[target_idx] == '&':
            before = text[:target_idx].rstrip()
            if not before or before[-1] in "=({[,+-\t ":
                updated = text[:target_idx] + text[target_idx + 1:]
                return _replace_line(source, line, text, updated, "removed invalid address-of operator")

    if kind == "invalid_dereference":
        # col points directly at the unary '*' operator
        target_idx = max(0, col)
        if target_idx < len(text) and text[target_idx] == '*':
            before = text[:target_idx].rstrip()
            if not before or before[-1] in "=({[,+-\t ":
                updated = text[:target_idx] + text[target_idx + 1:]
                return _replace_line(source, line, text, updated, "removed invalid dereference operator")

    # -------------------------------------------------------------
    # 4. Return Type Mismatch
    # -------------------------------------------------------------
    if kind == "return_type_mismatch":
        if "Void function should not return a value" in message:
            # Change 'return expr;' to 'return;'
            updated = re.sub(r"\breturn\s+[^;]+;", "return;", text, count=1)
            if updated != text:
                return _replace_line(source, line, text, updated, "removed return expression in void function")

        expected = _expected_type(message)
        from_t = _source_type(message)
        if expected and from_t and not is_lossless_cast(from_t, expected):
            return source, None  # Lossy return cast -> SUGGESTED

        match = re.search(r"\breturn\s+([^;]+);", text)
        if expected and match:
            ret_expr = match.group(1).strip()
            if not ret_expr.startswith(f"({expected})"):
                updated = text[:match.start(1)] + f"({expected}){ret_expr}" + text[match.end(1):]
                return _replace_line(source, line, text, updated, f"cast return value to '{expected}'")

    # -------------------------------------------------------------
    # 5. Call Type Mismatch
    # -------------------------------------------------------------
    if kind == "call_type_mismatch":
        expected = _expected_type(message)
        from_t = _source_type(message)
        if expected and from_t and not is_lossless_cast(from_t, expected):
            return source, None  # Lossy argument cast -> SUGGESTED

        arg_m = re.search(r"Argument (\d+)", message)
        call_m = re.search(r"\((.*)\)", text)
        if expected and arg_m and call_m:
            arg_pos = int(arg_m.group(1)) - 1
            inside_paren = call_m.group(1)
            args = _split_balanced_args(inside_paren)
            if 0 <= arg_pos < len(args):
                start, end, arg_str = args[arg_pos]
                leading_ws = arg_str[:len(arg_str) - len(arg_str.lstrip())]
                clean_arg = arg_str.strip()
                trailing_ws = arg_str[len(arg_str.rstrip()):]
                if not clean_arg.startswith(f"({expected})"):
                    cast_arg = f"{leading_ws}({expected}){clean_arg}{trailing_ws}"
                    new_inside = inside_paren[:start] + cast_arg + inside_paren[end:]
                    updated = text[:call_m.start(1)] + new_inside + text[call_m.end(1):]
                    return _replace_line(source, line, text, updated, f"cast argument {arg_pos + 1} to '{expected}'")

    # -------------------------------------------------------------
    # 6. Call Arity Mismatch (User change 4: remove extra only if side-effect free)
    # -------------------------------------------------------------
    if kind == "call_arity_mismatch":
        # Function 'f' expects N argument(s) but got M
        m_counts = re.search(r"expects (\d+) arguments?(?:\(s\))? but got (\d+)", message)
        if m_counts:
            expected_n = int(m_counts.group(1))
            got_m = int(m_counts.group(2))
            if got_m > expected_n:
                call_m = re.search(r"\((.*)\)", text)
                if call_m:
                    inside = call_m.group(1)
                    args = _split_balanced_args(inside)
                    if len(args) == got_m:
                        extra_args = args[expected_n:]
                        # Check Criterion 3: extra args must have no side effects
                        for _, _, a_txt in extra_args:
                            if re.search(r"\b[A-Za-z_]\w*\s*\(|\+\+|\-\-|(?<![=!<>])=(?![=])", a_txt):
                                return source, None  # Has side-effects -> SUGGESTED
                        # Safe to trim extra args
                        kept_args = args[:expected_n]
                        new_inside = ", ".join(a_txt.strip() for _, _, a_txt in kept_args)
                        updated = text[:call_m.start(1)] + new_inside + text[call_m.end(1):]
                        return _replace_line(source, line, text, updated, f"removed {got_m - expected_n} unused side-effect free argument(s)")
        return source, None  # too few args -> SUGGESTED

    # -------------------------------------------------------------
    # 7. Invalid Operand Type (Bitwise & Shift operators)
    # -------------------------------------------------------------
    if kind == "invalid_operand_type":
        # Per user instruction: float/double operands in bitwise/shift ops are lossy -> SUGGESTED
        if "got 'float'" in message or "got 'double'" in message:
            return source, None

        # Pointer arithmetic errors or switch errors -> SUGGESTED
        if "pointer arithmetic" in message or "switch expression" in message:
            return source, None

    # -------------------------------------------------------------
    # 8. Loop Control outside loops: break_outside_loop & continue_outside_loop
    # -------------------------------------------------------------
    if kind in {"break_outside_loop", "continue_outside_loop"}:
        keyword = "break" if kind.startswith("break") else "continue"
        # Match only statement keyword
        updated = re.sub(rf"^\s*{keyword}\s*;\s*", "", text, flags=re.MULTILINE)
        if updated != text:
            if not updated.strip():
                del lines[index]
                return "".join(lines), f"removed {keyword} outside loop"
            return _replace_line(source, line, text, updated, f"removed {keyword} outside loop")

    # -------------------------------------------------------------
    # 9. Case / Default Outside Switch (User change 2: remove only label, never block)
    # -------------------------------------------------------------
    if kind == "case_outside_switch":
        # Remove only the 'case <val>:' or 'default:' label
        updated = re.sub(r"^\s*(?:case\s+[^:]+|default)\s*:\s*", "", text)
        if updated != text:
            if not updated.strip():
                del lines[index]
                return "".join(lines), "removed stray case/default label outside switch"
            return _replace_line(source, line, text, updated, "removed stray case/default label outside switch")

    # -------------------------------------------------------------
    # 10. Duplicate Default (User change: removing label merges code into previous case -> SUGGESTED)
    # -------------------------------------------------------------
    if kind == "duplicate_default":
        # Removing duplicate default label merges code into preceding case, altering control flow.
        # Per instruction, this must be SUGGESTED, not auto-fixed.
        return source, None

    # -------------------------------------------------------------
    # 11. Duplicate Member (in struct: remove exact duplicate declaration)
    # -------------------------------------------------------------
    if kind == "duplicate_member":
        mname = issue.get("name")
        if mname and mname in text:
            # If line is just 'type mname;'
            if re.search(rf"\b{re.escape(mname)}\s*;", text):
                del lines[index]
                return "".join(lines), f"removed duplicate struct member '{mname}'"

    # -------------------------------------------------------------
    # 12. Redeclared Struct (remove exact duplicate struct definition)
    # -------------------------------------------------------------
    if kind == "redeclared_struct":
        sname = issue.get("name")
        # Remove duplicate struct S { ... }; only if there is an existing definition earlier
        has_earlier = any(f"struct {sname}" in lines[prev_k] for prev_k in range(0, index))
        if sname and f"struct {sname}" in text and has_earlier:
            end_idx = index
            brace_count = 0
            started = False
            for k in range(index, len(lines)):
                l = lines[k]
                brace_count += l.count("{") - l.count("}")
                if "{" in l:
                    started = True
                if started and brace_count <= 0 and ";" in l:
                    end_idx = k
                    break
            del lines[index:end_idx + 1]
            return "".join(lines), f"removed redeclaration of struct '{sname}'"

    # -------------------------------------------------------------
    # 13. Use Before Declare (User change 3: hoist bare declaration, leave initializer as assignment in place)
    # -------------------------------------------------------------
    if kind == "use_before_declare":
        name = issue.get("name")
        KEYWORD_EXCLUSIONS = {
            "return", "break", "continue", "goto", "case", "default",
            "if", "else", "switch", "while", "for", "do", "sizeof"
        }
        if name:
            decl_idx = -1
            decl_m = None
            for k in range(index + 1, min(len(lines), index + 50)):
                l_k = lines[k]
                m = re.search(
                    r"^(?P<indent>\s*)(?P<type>(?:unsigned\s+|signed\s+|struct\s+[A-Za-z_]\w*\s*|[A-Za-z_]\w+\s*\*+|\b[A-Za-z_]\w+\b)+)\s+(?P<ptr>\*+\s*)?"
                    + re.escape(name)
                    + r"(?:\s*=\s*(?P<init>[^;]+))?\s*;",
                    l_k,
                )
                if m:
                    type_words = m.group("type").strip().split()
                    if not any(w in KEYWORD_EXCLUSIONS for w in type_words):
                        decl_idx = k
                        decl_m = m
                        break

            if decl_idx != -1 and decl_m:
                indent = decl_m.group("indent") or "    "
                type_str = decl_m.group("type").strip()
                ptr_str = decl_m.group("ptr") or ""
                init_expr = decl_m.group("init")

                if init_expr:
                    # Check if initializer depends on variables assigned between index and decl_idx
                    init_clean = init_expr.strip()
                    assigned_vars = set()
                    for mid in range(index, decl_idx):
                        for asgn in re.finditer(r"\b([A-Za-z_]\w*)\s*(?:=|\+\+|\-\-)", lines[mid]):
                            assigned_vars.add(asgn.group(1))

                    init_identifiers = set(re.findall(r"\b([A-Za-z_]\w*)\b", init_clean))
                    # If initializer depends on later-assigned variables, reject fix -> SUGGESTED
                    if assigned_vars.intersection(init_identifiers):
                        return source, None

                    # Hoist bare declaration above first use
                    bare_decl = f"{indent}{type_str} {ptr_str}{name};\n"
                    # Leave assignment in place
                    lines[decl_idx] = f"{indent}{name} = {init_clean};\n"
                    lines.insert(index, bare_decl)
                    return "".join(lines), f"hoisted bare declaration of '{name}' above first use"
                else:
                    # Bare declaration without initializer: simply hoist
                    bare_decl = lines.pop(decl_idx)
                    lines.insert(index, bare_decl)
                    return "".join(lines), f"moved declaration of '{name}' above its first use"

    # -------------------------------------------------------------
    # 14. Shadow Warning (Token/AST safe rename avoiding strings and members)
    # -------------------------------------------------------------
    if kind == "shadow_warning":
        name = issue.get("name")
        if not name:
            shadow_m = re.search(r"Declaration of '([^']+)' shadows", message or "")
            if shadow_m:
                name = shadow_m.group(1)
        if name:
            new_name = f"local_{name}"
            updated_source = _safe_rename_identifier(source, line, name, new_name)
            if updated_source != source:
                return updated_source, f"renamed shadowed variable '{name}' to '{new_name}'"

    # -------------------------------------------------------------
    # 15. Prototype Mismatch (Synchronize definition with prototype)
    # -------------------------------------------------------------
    if kind == "prototype_mismatch":
        param_match = re.search(
            r"Definition parameter (\d+) type '([^']+)' does not match prototype type '([^']+)'",
            message or "",
        )
        if param_match:
            param_idx = int(param_match.group(1))
            def_type = param_match.group(2)
            proto_type = param_match.group(3)
            fn_match = re.search(r"\(([^)]+)\)", text)
            if fn_match:
                params = [p.strip() for p in fn_match.group(1).split(",")]
                if 0 <= param_idx - 1 < len(params):
                    old_param = params[param_idx - 1]
                    new_param = re.sub(rf"\b{re.escape(def_type)}\b", proto_type, old_param, count=1)
                    if new_param != old_param:
                        params[param_idx - 1] = new_param
                        new_header = text[:fn_match.start(1)] + ", ".join(params) + text[fn_match.end(1):]
                        return _replace_line(source, line, text, new_header, f"updated parameter {param_idx} type to '{proto_type}'")

        ret_match = re.search(
            r"Definition return type '([^']+)' does not match prototype return type '([^']+)'",
            message or "",
        )
        if ret_match:
            def_ret = ret_match.group(1)
            proto_ret = ret_match.group(2)
            updated = re.sub(rf"\b{re.escape(def_ret)}\b", proto_ret, text, count=1)
            if updated != text:
                return _replace_line(source, line, text, updated, f"updated return type to '{proto_ret}'")

    # -------------------------------------------------------------
    # 16. Too Many Initializers (User change 5: enlarge array dimension)
    # -------------------------------------------------------------
    if kind == "too_many_initializers":
        m_dim = re.search(r"(?:expected at most \d+, got (\d+)|has size \d+ but (\d+) initializers)", message or "")
        name = issue.get("name")
        if m_dim and name:
            new_size = m_dim.group(1) or m_dim.group(2)
            # Update arr[N] -> arr[new_size]
            updated = re.sub(rf"\b{re.escape(name)}\s*\[\s*\d+\s*\]", f"{name}[{new_size}]", text, count=1)
            if updated != text:
                return _replace_line(source, line, text, updated, f"enlarged array '{name}' dimension to {new_size}")

    # -------------------------------------------------------------
    # 17. Undeclared Identifier (Rule-first: typo match <= 2, inferable auto-declare, known library, else SUGGESTED)
    # -------------------------------------------------------------
    if kind == "undeclared":
        target_name = (issue.get("name") or "").strip()
        # 1. Typo correction if close to stdlib or declared symbols
        symbols = dict(issue.get("symbols") or {})
        if not symbols:
            from compiler.security_auto_fixer import _split_lines, _code_mask, _function_spans
            _lines, _ = _split_lines(source)
            _mask = _code_mask(_lines)
            _spans = _function_spans(_lines, _mask)
            _idx = line - 1
            _span = next((s for s in _spans if s.open_idx <= _idx <= s.end_idx), None)
            if _span:
                for k in range(_span.open_idx, _span.end_idx + 1):
                    for dm in re.finditer(r'\b(?:char|int|float|double|short|long|unsigned|signed|void)\b[^;()]*\b([A-Za-z_]\w*)\b', _lines[k]):
                        symbols[dm.group(1)] = {"type": "local", "line": k + 1}

        from compiler.identifier_corrector import fix_identifier_typo_at
        typo_src, typo_msg = fix_identifier_typo_at(source, line, col, symbols, max_dist=2, expected_name=target_name)
        if typo_msg is not None and typo_src != source:
            return typo_src, typo_msg

        # 2. Known library function: inject standard forward prototype
        if target_name in STD_LIB_PROTOTYPES:
            proto = STD_LIB_PROTOTYPES[target_name]
            if proto not in source:
                return f"{proto}\n" + source, f"added forward declaration for library function '{target_name}'"

        # 3. Undeclared buffer argument rule (gets/fgets/scanf("%s")/strcpy/strcat/sprintf)
        is_buf_arg = False
        m_scanf = None
        if target_name:
            m_gets = re.search(r'\bgets\s*\(\s*' + re.escape(target_name) + r'\s*\)', text)
            m_fgets = re.search(r'\bfgets\s*\(\s*' + re.escape(target_name) + r'\s*,', text)
            m_scanf = re.search(r'\bscanf\s*\(\s*"(%\d*[dsx])"\s*,\s*' + re.escape(target_name) + r'\s*\)', text)
            m_strcpy = re.search(r'\bstrcpy\s*\(\s*' + re.escape(target_name) + r'\s*,', text)
            m_strcat = re.search(r'\bstrcat\s*\(\s*' + re.escape(target_name) + r'\s*,', text)
            m_sprintf = re.search(r'\bsprintf\s*\(\s*' + re.escape(target_name) + r'\s*,', text)
            is_buf_arg = bool(m_gets or m_fgets or m_scanf or m_strcpy or m_strcat or m_sprintf)

        if is_buf_arg:
            from compiler.security_auto_fixer import _split_lines, _code_mask, _function_spans
            lines, _ = _split_lines(source)
            mask = _code_mask(lines)
            spans = _function_spans(lines, mask)
            idx = line - 1
            span = next((s for s in spans if s.open_idx <= idx <= s.end_idx), None)
            if span:
                char_arrays: List[Tuple[str, int]] = []
                for k in range(span.open_idx, span.end_idx + 1):
                    for cm in re.finditer(r'\b(?:char)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]', lines[k]):
                        if mask[k][cm.start()]:
                            char_arrays.append((cm.group(1), int(cm.group(2))))

                if len(char_arrays) == 1:
                    c_name, c_size = char_arrays[0]
                    updated_line = text
                    if m_scanf:
                        fmt_spec = m_scanf.group(1)
                        if fmt_spec.endswith("s") and c_size >= 2:
                            new_fmt = f"%{c_size - 1}s"
                        else:
                            new_fmt = fmt_spec
                        old_call = m_scanf.group(0)
                        new_call = f'scanf("{new_fmt}", {c_name})'
                        updated_line = updated_line.replace(old_call, new_call, 1)
                    else:
                        updated_line = re.sub(r'\b' + re.escape(target_name) + r'\b', c_name, updated_line, count=1)

                    if updated_line != text:
                        return _replace_line(
                            source, line, text, updated_line,
                            f"replaced undeclared buffer '{target_name}' with local array '{c_name}'"
                        )
                elif len(char_arrays) == 0:
                    issue["suggestion"] = f"undeclared buffer '{target_name}' in buffer API: no char[] found in enclosing function"
                    return source, None
                else:
                    candidates_str = ", ".join(f"'{name}'[{sz}]" for name, sz in char_arrays)
                    issue["suggestion"] = f"undeclared buffer '{target_name}' in buffer API: multiple char[] candidates ({candidates_str})"
                    return source, None

        # 4. Auto-declaration only when type is clearly inferable from usage
        if target_name:
            # Direct assignment: target_name = <rhs>;
            assign_pattern = rf"^(?P<indent>\s*){re.escape(target_name)}\s*=\s*(?P<rhs>[^;]+);(?P<rest>.*)$"
            m_assign = re.match(assign_pattern, text)
            if m_assign:
                rhs = m_assign.group("rhs").strip()
                inferred_type = None
                if re.match(r"^[+-]?(?:0[xX][0-9a-fA-F]+|\d+)[uUlL]*$", rhs):
                    inferred_type = "int"
                elif re.match(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+[eE][+-]?\d+)[fFlL]?$", rhs):
                    inferred_type = "float" if rhs.endswith(("f", "F")) else "double"
                elif re.match(r"^'(\\.|[^\\'])'$", rhs):
                    inferred_type = "char"
                elif re.match(r'^"([^"\\]|\\.)*"$', rhs):
                    inferred_type = "char*"

                if inferred_type:
                    indent = m_assign.group("indent")
                    rest = m_assign.group("rest")
                    ending = "\n" if text.endswith("\n") else ""
                    if inferred_type == "char*":
                        updated = f"{indent}char *{target_name} = {rhs};{rest}{ending}"
                    else:
                        updated = f"{indent}{inferred_type} {target_name} = {rhs};{rest}{ending}"
                    return _replace_line(source, line, text, updated, f"declared '{target_name}' as '{inferred_type}' inferred from assignment")

            # For loop header: for (target_name = 0; ...)
            for_pattern = rf"^(?P<before>.*?\bfor\s*\(\s*){re.escape(target_name)}\s*=\s*(?P<rhs>[^;]+);(?P<after>.*)$"
            m_for = re.match(for_pattern, text)
            if m_for:
                rhs = m_for.group("rhs").strip()
                if re.match(r"^[+-]?\d+$", rhs):
                    updated = re.sub(rf"\bfor\s*\(\s*{re.escape(target_name)}\s*=", f"for (int {target_name} =", text, count=1)
                    return _replace_line(source, line, text, updated, f"declared '{target_name}' as 'int' in for loop header")

        # Ambiguous or non-inferable usage remains SUGGESTED / model
        return source, None

    return source, None
