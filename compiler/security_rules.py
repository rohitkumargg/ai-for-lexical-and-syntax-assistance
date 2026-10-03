"""
Security Rules and Deterministic Auto-Fix Engine for SimpleC Compiler.
Implements SEC-01 through SEC-10 rules with ANTLR parse tree visitor detection
and token-position-based auto-fixes under ACCEPT-ONLY-IF-SAFER guarantees.
"""

import copy
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from generated.SimpleCParser import SimpleCParser
from generated.SimpleCVisitor import SimpleCVisitor
from compiler.semantic_checker import SemanticChecker, _canonical_type
from test_parser import parse_source, has_any_errors, get_all_error_strings


# Size assumptions: char 1, short 2, int 4, long 8, long long 8, float 4, double 8, pointer 8.
TYPE_SIZES = {
    "char": 1,
    "signed char": 1,
    "unsigned char": 1,
    "short": 2,
    "signed short": 2,
    "unsigned short": 2,
    "int": 4,
    "signed int": 4,
    "unsigned int": 4,
    "long": 8,
    "signed long": 8,
    "unsigned long": 8,
    "long long": 8,
    "signed long long": 8,
    "unsigned long long": 8,
    "float": 4,
    "double": 8,
}

INT32_MIN = -2147483648
INT32_MAX = 2147483647


class Finding(dict):
    """Represents a security finding from SEC-01..SEC-10."""
    def __init__(
        self,
        rule: str,
        kind: str,
        line: int,
        message: str,
        severity: str = "WARNING",
        action: str = "warned",
        suggestion: str = "",
        fix_edits: Optional[List[Tuple[int, int, str]]] = None,
        what_changed: str = "",
        target_key: Optional[str] = None,
    ):
        super().__init__()
        self["rule"] = rule
        self["kind"] = kind
        self["finding"] = kind
        self["line"] = line
        self["message"] = message
        self["severity"] = severity
        self["action"] = action
        self["suggestion"] = suggestion
        self.rule = rule
        self.kind = kind
        self.line = line
        self.message = message
        self.severity = severity
        self.action = action
        self.suggestion = suggestion
        self.fix_edits = fix_edits
        self.what_changed = what_changed
        self.target_key = target_key or f"{rule}:{line}:{kind}"

    def __getattr__(self, name: str) -> Any:
        if name in self:
            return self[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("fix_edits", "what_changed", "target_key", "rule", "kind", "line", "message", "severity", "action", "suggestion"):
            self.__dict__[name] = value
            if name in ("rule", "kind", "line", "message", "severity", "action", "suggestion"):
                self[name] = value
        else:
            self.__dict__[name] = value


def apply_edits(source: str, edits: List[Tuple[int, int, str]]) -> str:
    """Applies non-overlapping character range replacements to source text."""
    # Sort edits descending by start index so earlier indices remain valid
    sorted_edits = sorted(edits, key=lambda e: e[0], reverse=True)
    res = source
    for start, end, repl in sorted_edits:
        res = res[:start] + repl + res[end:]
    return res


def get_type_size(ctype: str) -> int:
    c = _canonical_type(ctype)
    if c.endswith("*"):
        return 8
    return TYPE_SIZES.get(c, 4)


def eval_const_int_expr(node: Any) -> Optional[int]:
    """
    Evaluates a constant integer expression (+, -, * of integer literals).
    Returns exact int value or None if non-constant or unsupported operators.
    """
    if node is None:
        return None
    cls = node.__class__.__name__

    if cls == "PrimaryExpressionContext":
        if node.INTEGER() is not None:
            txt = node.INTEGER().getText()
            try:
                if txt.startswith(("0x", "0X")):
                    return int(txt, 16)
                if txt.startswith("0") and len(txt) > 1 and txt.isdigit():
                    return int(txt, 8)
                return int(txt)
            except ValueError:
                return None
        if node.expression() is not None:
            return eval_const_int_expr(node.expression())
        return None

    if cls == "PostfixExpressionContext":
        if node.postfixPart() and len(node.postfixPart()) > 0:
            return None
        return eval_const_int_expr(node.primaryExpression())

    if cls == "UnaryExpressionContext":
        if node.postfixExpression() is not None:
            return eval_const_int_expr(node.postfixExpression())
        # Unary + or -
        sub = node.unaryExpression()
        sub_v = eval_const_int_expr(sub)
        if sub_v is None:
            return None
        txt = node.getText()
        if txt.startswith("-"):
            return -sub_v
        if txt.startswith("+"):
            return sub_v
        return None

    if cls == "MultiplicativeExpressionContext":
        subs = node.unaryExpression()
        if not subs:
            return None
        val = eval_const_int_expr(subs[0])
        if val is None:
            return None
        for i in range(1, len(subs)):
            op = node.getChild(2 * i - 1).getText()
            next_v = eval_const_int_expr(subs[i])
            if next_v is None:
                return None
            if op == "*":
                val = val * next_v
            else:
                return None  # Only +, -, * for SEC-01 constant expression
        return val

    if cls == "AdditiveExpressionContext":
        subs = node.multiplicativeExpression()
        if not subs:
            return None
        val = eval_const_int_expr(subs[0])
        if val is None:
            return None
        for i in range(1, len(subs)):
            op = node.getChild(2 * i - 1).getText()
            next_v = eval_const_int_expr(subs[i])
            if next_v is None:
                return None
            if op == "+":
                val = val + next_v
            elif op == "-":
                val = val - next_v
            else:
                return None
        return val

    # Fall-through for intermediate precedence wrappers
    for getter in (
        "assignmentExpression",
        "conditionalExpression",
        "logicalOrExpression",
        "logicalAndExpression",
        "inclusiveOrExpression",
        "exclusiveOrExpression",
        "andExpression",
        "equalityExpression",
        "relationalExpression",
        "shiftExpression",
        "additiveExpression",
    ):
        fn = getattr(node, getter, None)
        if fn is not None:
            try:
                res = fn()
                if isinstance(res, list) and len(res) == 1:
                    return eval_const_int_expr(res[0])
                elif not isinstance(res, list) and res is not None:
                    return eval_const_int_expr(res)
            except Exception:
                pass

    return None


def get_first_integer_literal_token(node: Any) -> Optional[Any]:
    """Finds the first integer literal terminal token inside node."""
    if node is None:
        return None
    cls = node.__class__.__name__
    if cls == "PrimaryExpressionContext":
        tok = getattr(node, "INTEGER", lambda: None)()
        if tok is not None:
            return tok.getSymbol()
    for i in range(node.getChildCount()):
        child = node.getChild(i)
        sub = get_first_integer_literal_token(child)
        if sub is not None:
            return sub
    return None


def find_token_by_text(node: Any, text: str) -> Optional[Any]:
    """Recursively searches for a terminal symbol matching text."""
    if hasattr(node, "getSymbol") and node.getSymbol() is not None:
        if node.getText() == text:
            return node.getSymbol()
    for i in range(node.getChildCount()):
        tok = find_token_by_text(node.getChild(i), text)
        if tok is not None:
            return tok
    return None


class SecurityRulesCollector(SimpleCVisitor):
    """
    Visitor that detects SEC-01 through SEC-10 issues across the AST.
    """
    def __init__(self, source_text: str):
        super().__init__()
        self.source = source_text
        self.findings: List[Finding] = []

        # Scope and symbol tracking:
        self.global_vars: Dict[str, Dict[str, Any]] = {}
        self.local_vars: Dict[str, Dict[str, Any]] = {}
        self.all_funcs_local_vars: List[Tuple[Any, Dict[str, Dict[str, Any]]]] = []
        self.is_inside_func: bool = False
        self.current_func_ret: Optional[str] = None

        # Value tracking in current block for SEC-02 & SEC-03:
        self.known_negative_vars: Set[str] = set()
        self.null_pointers: Set[str] = set()
        self.guarded_pointers: Set[str] = set()

    def _get_line_indent(self, char_idx: int) -> str:
        line_start = self.source.rfind("\n", 0, char_idx)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1
        indent = ""
        while line_start + len(indent) < len(self.source) and self.source[line_start + len(indent)] in " \t":
            indent += self.source[line_start + len(indent)]
        return indent

    def visitFunctionDef(self, ctx: SimpleCParser.FunctionDefContext):
        prev_inside = self.is_inside_func
        prev_locals = self.local_vars
        self.is_inside_func = True
        self.local_vars = {}
        self.known_negative_vars = set()
        self.null_pointers = set()
        self.guarded_pointers = set()

        type_spec = getattr(ctx, "typeSpecifier", lambda: None)()
        self.current_func_ret = type_spec.getText() if type_spec else None

        res = self.visitChildren(ctx)

        # Save locals for uninitialized variable checks
        self.all_funcs_local_vars.append((ctx, dict(self.local_vars)))

        self.is_inside_func = prev_inside
        self.local_vars = prev_locals
        return res

    def visitDeclaration(self, ctx: SimpleCParser.DeclarationContext):
        d_no_semi = getattr(ctx, "declarationNoSemi", lambda: None)()
        if d_no_semi is None:
            return self.visitChildren(ctx)

        type_spec = getattr(d_no_semi, "typeSpecifier", lambda: None)()
        base_type = type_spec.getText() if type_spec else "int"

        decl_list = getattr(d_no_semi, "initDeclaratorList", lambda: None)()
        if decl_list is None:
            return self.visitChildren(ctx)

        for init_decl in decl_list.initDeclarator():
            ident = getattr(init_decl, "IDENTIFIER", lambda: None)()
            if ident is None:
                continue
            name = ident.getText()
            sym = ident.getSymbol()
            line = sym.line

            has_pointer = getattr(init_decl, "pointer", lambda: None)() is not None
            ptr_depth = len(init_decl.pointer().getText()) if has_pointer else 0
            full_type = _canonical_type(base_type + ("*" * ptr_depth))

            arr_suffix = getattr(init_decl, "arraySuffix", lambda: None)()
            arr_size = None
            if arr_suffix is not None:
                try:
                    exprs = arr_suffix.expression()
                    if exprs:
                        arr_size = eval_const_int_expr(exprs[0])
                except Exception:
                    arr_size = None

            # Look up initializer
            init_expr = None
            for _getter in ("initializer", "assignmentExpression", "expression"):
                _fn = getattr(init_decl, _getter, None)
                if _fn is not None:
                    try:
                        init_expr = _fn()
                        if init_expr is not None:
                            break
                    except Exception:
                        pass

            var_info = {
                "name": name,
                "base_type": base_type,
                "full_type": full_type,
                "is_pointer": (ptr_depth > 0),
                "is_array": (arr_suffix is not None),
                "array_size": arr_size,
                "line": line,
                "ident_token": sym,
                "type_spec_node": type_spec,
                "init_decl_node": init_decl,
                "has_init": (init_expr is not None),
            }

            if self.is_inside_func:
                self.local_vars[name] = var_info

                # Rule SEC-01 check on local variable initialization:
                # int x = 2147483647 + 1;
                if full_type in ("int", "signed int") and init_expr is not None:
                    exact_val = eval_const_int_expr(init_expr)
                    if exact_val is not None and (exact_val < INT32_MIN or exact_val > INT32_MAX):
                        first_lit = get_first_integer_literal_token(init_expr)
                        if first_lit is not None and type_spec is not None:
                            t_start = type_spec.start.start
                            t_stop = type_spec.stop.stop + 1
                            lit_start = first_lit.start
                            lit_stop = first_lit.stop + 1
                            edits = [
                                (t_start, t_stop, "long long"),
                                (lit_start, lit_stop, f"(long long){first_lit.text}"),
                            ]
                            self.findings.append(Finding(
                                rule="SEC-01",
                                kind="integer_overflow",
                                line=line,
                                message=f"Constant integer expression overflow in initialization of '{name}' (value {exact_val})",
                                severity="HIGH",
                                action="auto_fixed",
                                suggestion="use long long and cast literal operand to (long long)",
                                fix_edits=edits,
                                what_changed=f"changed type of '{name}' to long long and cast literal to (long long)",
                            ))

                # Rule SEC-01 inline test case:
                # long long r = a * b; with int a, b -> long long r = (long long)a * b;
                if full_type in ("long long", "signed long long") and init_expr is not None:
                    curr = init_expr
                    while curr is not None and curr.getChildCount() == 1:
                        curr = curr.getChild(0)
                    if curr is not None and curr.__class__.__name__ == "MultiplicativeExpressionContext":
                        subs = getattr(curr, "unaryExpression", lambda: [])()
                        if len(subs) == 2 and curr.getChild(1).getText() == "*":
                            t1 = subs[0].getText()
                            t2 = subs[1].getText()
                            info1 = self.local_vars.get(t1) or self.global_vars.get(t1)
                            info2 = self.local_vars.get(t2) or self.global_vars.get(t2)
                            if info1 and info2 and info1.get("full_type") == "int" and info2.get("full_type") == "int":
                                op1_start = subs[0].start.start
                                op1_stop = subs[0].stop.stop + 1
                                edits = [(op1_start, op1_stop, f"(long long){t1}")]
                                self.findings.append(Finding(
                                    rule="SEC-01",
                                    kind="integer_overflow",
                                    line=line,
                                    message=f"Multiplication '{t1} * {t2}' of 32-bit ints overflows before conversion to long long",
                                    severity="HIGH",
                                    action="auto_fixed",
                                    suggestion=f"cast '{t1}' to (long long)",
                                    fix_edits=edits,
                                    what_changed=f"cast '{t1}' to (long long) in multiplication",
                                ))

                # Track negative values for SEC-02:
                if init_expr is not None:
                    const_v = eval_const_int_expr(init_expr)
                    if const_v is not None and const_v < 0:
                        self.known_negative_vars.add(name)

                # Rule SEC-02 check on initialization:
                is_unsigned = ("unsigned" in full_type)
                if is_unsigned and init_expr is not None:
                    txt = init_expr.getText()
                    is_neg = False
                    rhs_var = None
                    const_v = eval_const_int_expr(init_expr)
                    if const_v is not None and const_v < 0:
                        is_neg = True
                    elif txt in self.known_negative_vars:
                        is_neg = True
                        rhs_var = txt

                    if is_neg:
                        var_label = rhs_var or name
                        nl = "\r\n" if "\r\n" in self.source else "\n"
                        indent = self._get_line_indent(ctx.start.start)
                        if rhs_var:
                            replacement = (
                                f"{base_type} {name} = 0;{nl}"
                                f"{indent}if ({rhs_var} >= 0) {{{nl}"
                                f"{indent}    {name} = (unsigned){rhs_var};{nl}"
                                f"{indent}}}"
                            )
                        else:
                            replacement = (
                                f"{base_type} {name} = 0;{nl}"
                                f"{indent}if ({var_label} >= 0) {{{nl}"
                                f"{indent}    {name} = (unsigned)({txt});{nl}"
                                f"{indent}}}"
                            )
                        edits = [(ctx.start.start, ctx.stop.stop + 1, replacement)]
                        self.findings.append(Finding(
                            rule="SEC-02",
                            kind="signed_to_unsigned",
                            line=line,
                            message=f"Conversion of negative signed expression to unsigned '{name}'",
                            severity="WARNING",
                            action="auto_fixed",
                            suggestion=f"guard with if ({var_label} >= 0) before converting, or declare {var_label} as unsigned",
                            fix_edits=edits,
                            what_changed=f"guarded conversion of '{var_label}' to unsigned '{name}' with if ({var_label} >= 0)",
                        ))

                # Track pointer nullness for SEC-03:
                if var_info["is_pointer"]:
                    if init_expr is not None:
                        itxt = init_expr.getText()
                        if itxt == "NULL" or eval_const_int_expr(init_expr) == 0:
                            self.null_pointers.add(name)

            else:
                self.global_vars[name] = var_info

        return self.visitChildren(ctx)

    def visitBlock(self, ctx: SimpleCParser.BlockContext):
        items = getattr(ctx, "blockItem", lambda: [])()
        for item in items:
            self.visit(item)
        return None

    def visitIfStatement(self, ctx: SimpleCParser.IfStatementContext):
        cond = getattr(ctx, "expression", lambda: None)()
        guarded_var_nonneg = None
        guarded_ptr_nonnull = None
        if cond is not None:
            c_text = cond.getText()
            m_nonneg = re.search(r"\b([a-zA-Z_]\w*)\s*(>=|>)\s*(-?0|-?1)\b", c_text)
            if m_nonneg:
                guarded_var_nonneg = m_nonneg.group(1)
            m_nonnull = re.search(r"\b([a-zA-Z_]\w*)\s*!=\s*(NULL|0)\b", c_text)
            if m_nonnull:
                guarded_ptr_nonnull = m_nonnull.group(1)
            elif re.fullmatch(r"[a-zA-Z_]\w*", c_text.strip()):
                guarded_ptr_nonnull = c_text.strip()

        prev_neg = set(self.known_negative_vars)
        prev_null = set(self.null_pointers)

        if guarded_var_nonneg in self.known_negative_vars:
            self.known_negative_vars.remove(guarded_var_nonneg)
        if guarded_ptr_nonnull in self.null_pointers:
            self.null_pointers.remove(guarded_ptr_nonnull)
            self.guarded_pointers.add(guarded_ptr_nonnull)

        stmts = getattr(ctx, "statement", lambda: [])()
        if stmts:
            self.visit(stmts[0])

        self.known_negative_vars = prev_neg
        self.null_pointers = prev_null

        if len(stmts) > 1:
            self.visit(stmts[1])

        return None

    def visitExprStatement(self, ctx: SimpleCParser.ExprStatementContext):
        expr = getattr(ctx, "expression", lambda: None)()
        if expr is None:
            return None

        line = ctx.start.line

        # Check for assignment: x = <expr>;
        assign_ctx = None
        curr = expr
        while curr is not None and curr.getChildCount() == 1:
            curr = curr.getChild(0)
        if curr is not None and curr.__class__.__name__ == "AssignmentExpressionContext":
            op_node = getattr(curr, "assignmentOperator", lambda: None)()
            if op_node is not None and op_node.getText() == "=":
                assign_ctx = curr

        if assign_ctx is not None:
            lhs_node = getattr(assign_ctx, "unaryExpression", lambda: None)()
            lhs = lhs_node.getText() if lhs_node else ""
            rhs_node = assign_ctx.assignmentExpression()

            # SEC-01 check on assignment:
            v_info = self.local_vars.get(lhs)
            if v_info and v_info.get("full_type") in ("int", "signed int"):
                exact_val = eval_const_int_expr(rhs_node)
                if exact_val is not None and (exact_val < INT32_MIN or exact_val > INT32_MAX):
                    first_lit = get_first_integer_literal_token(rhs_node)
                    type_spec = v_info.get("type_spec_node")
                    if first_lit is not None and type_spec is not None:
                        t_start = type_spec.start.start
                        t_stop = type_spec.stop.stop + 1
                        lit_start = first_lit.start
                        lit_stop = first_lit.stop + 1
                        edits = [
                            (t_start, t_stop, "long long"),
                            (lit_start, lit_stop, f"(long long){first_lit.text}"),
                        ]
                        self.findings.append(Finding(
                            rule="SEC-01",
                            kind="integer_overflow",
                            line=line,
                            message=f"Constant integer expression overflow in assignment to '{lhs}' (value {exact_val})",
                            severity="HIGH",
                            action="auto_fixed",
                            suggestion="use long long and cast literal operand to (long long)",
                            fix_edits=edits,
                            what_changed=f"changed type of '{lhs}' to long long and cast literal to (long long)",
                        ))

            # SEC-02 check on assignment:
            if v_info and "unsigned" in v_info.get("full_type", ""):
                rhs_txt = rhs_node.getText()
                is_neg = False
                rhs_var = None
                const_v = eval_const_int_expr(rhs_node)
                if const_v is not None and const_v < 0:
                    is_neg = True
                elif rhs_txt in self.known_negative_vars:
                    is_neg = True
                    rhs_var = rhs_txt

                if is_neg:
                    var_label = rhs_var or lhs
                    nl = "\r\n" if "\r\n" in self.source else "\n"
                    indent = self._get_line_indent(ctx.start.start)
                    stmt_text = self.source[ctx.start.start : ctx.stop.stop + 1]
                    if rhs_var:
                        replacement = (
                            f"if ({rhs_var} >= 0) {{{nl}"
                            f"{indent}    {lhs} = (unsigned){rhs_var};{nl}"
                            f"{indent}}}"
                        )
                    else:
                        replacement = (
                            f"if ({var_label} >= 0) {{{nl}"
                            f"{indent}    {stmt_text}{nl}"
                            f"{indent}}}"
                        )
                    edits = [(ctx.start.start, ctx.stop.stop + 1, replacement)]
                    self.findings.append(Finding(
                        rule="SEC-02",
                        kind="signed_to_unsigned",
                        line=line,
                        message=f"Conversion of negative signed expression to unsigned '{lhs}'",
                        severity="WARNING",
                        action="auto_fixed",
                        suggestion=f"guard with if ({var_label} >= 0) before converting, or declare {var_label} as unsigned",
                        fix_edits=edits,
                        what_changed=f"guarded conversion of '{var_label}' to unsigned '{lhs}' with if ({var_label} >= 0)",
                    ))

            # Track negative assignment:
            const_v = eval_const_int_expr(rhs_node)
            if const_v is not None and const_v < 0:
                self.known_negative_vars.add(lhs)
            elif lhs in self.known_negative_vars:
                self.known_negative_vars.remove(lhs)

            # Pointer assignment updates:
            if v_info and v_info.get("is_pointer"):
                rhs_txt = rhs_node.getText()
                if rhs_txt == "NULL" or eval_const_int_expr(rhs_node) == 0:
                    self.null_pointers.add(lhs)
                elif lhs in self.null_pointers:
                    self.null_pointers.remove(lhs)

        # Rule SEC-03 check: *p or p[i] on NULL pointer
        for p_name in list(self.null_pointers):
            stmt_text = self.source[ctx.start.start : ctx.stop.stop + 1]
            pattern = rf"(\*\s*{re.escape(p_name)}\b|{re.escape(p_name)}\s*\[)"
            if re.search(pattern, stmt_text):
                indent = self._get_line_indent(ctx.start.start)
                wrapped = f"if ({p_name} != NULL) {{\n{indent}    {stmt_text}\n{indent}}}"
                edits = [(ctx.start.start, ctx.stop.stop + 1, wrapped)]
                self.findings.append(Finding(
                    rule="SEC-03",
                    kind="null_dereference",
                    line=line,
                    message=f"Dereference of pointer '{p_name}' which is currently NULL",
                    severity="HIGH",
                    action="auto_fixed",
                    suggestion=f"guard with if ({p_name} != NULL)",
                    fix_edits=edits,
                    what_changed=f"guarded dereference of '{p_name}' with if ({p_name} != NULL)",
                ))
                self.null_pointers.remove(p_name)

        # Rule SEC-10 check: uninitialized pointer dereference (*p, p[i])
        for p_name, p_info in list(self.local_vars.items()):
            if p_info["is_pointer"] and not p_info["has_init"] and p_name not in self.null_pointers:
                stmt_text = self.source[ctx.start.start : ctx.stop.stop + 1]
                pattern = rf"(\*\s*{re.escape(p_name)}\b|{re.escape(p_name)}\s*\[)"
                if re.search(pattern, stmt_text):
                    sym = p_info["ident_token"]
                    insert_pos = sym.stop + 1
                    edits = [(insert_pos, insert_pos, " = NULL")]
                    self.findings.append(Finding(
                        rule="SEC-10",
                        kind="uninitialized_pointer",
                        line=line,
                        message=f"Pointer '{p_name}' used before initialization and was never allocated (suggest malloc)",
                        severity="HIGH",
                        action="auto_fixed",
                        suggestion=f"initialize '{p_name}' with NULL or allocate with malloc",
                        fix_edits=edits,
                        what_changed=f"initialized pointer '{p_name}' with NULL",
                    ))
                    p_info["has_init"] = True

        return self.visitChildren(ctx)

    def visitForStatement(self, ctx: SimpleCParser.ForStatementContext):
        line = ctx.start.line
        exprs = getattr(ctx, "expression", lambda: [])()
        cond = exprs[0] if exprs else None

        if cond is not None:
            # Rule SEC-06 check: for (int i = 0; i <= C; i++) with array of size C
            c_text = cond.getText()
            m = re.match(r"^([a-zA-Z_]\w*)\s*<=\s*(\d+)$", c_text)
            if m:
                loop_var = m.group(1)
                limit_c = int(m.group(2))
                stmt = getattr(ctx, "statement", lambda: None)()
                if stmt is not None:
                    body_text = self.source[stmt.start.start : stmt.stop.stop + 1]
                    m_idx = re.search(rf"\b([a-zA-Z_]\w*)\s*\[\s*{re.escape(loop_var)}\s*\]", body_text)
                    if m_idx:
                        arr_name = m_idx.group(1)
                        arr_info = self.local_vars.get(arr_name) or self.global_vars.get(arr_name)
                        if arr_info and arr_info.get("array_size") == limit_c:
                            lte_tok = find_token_by_text(cond, "<=")
                            if lte_tok is not None:
                                edits = [(lte_tok.start, lte_tok.stop + 1, "<")]
                                self.findings.append(Finding(
                                    rule="SEC-06",
                                    kind="off_by_one",
                                    line=line,
                                    message=f"Loop bound '{loop_var} <= {limit_c}' causes off-by-one buffer overflow on array '{arr_name}[{limit_c}]'",
                                    severity="HIGH",
                                    action="auto_fixed",
                                    suggestion=f"change '<=' to '<'",
                                    fix_edits=edits,
                                    what_changed=f"changed '<=' to '<' in loop bound for array '{arr_name}'",
                                ))

        return self.visitChildren(ctx)

    def visitPostfixExpression(self, ctx: SimpleCParser.PostfixExpressionContext):
        prim = getattr(ctx, "primaryExpression", lambda: None)()
        if prim is None:
            return self.visitChildren(ctx)

        parts = getattr(ctx, "postfixPart", lambda: [])()
        prim_text = prim.getText()
        line = ctx.start.line

        # Rule SEC-05 check: array out of bounds a[5] on int a[3]
        for p in parts:
            txt = p.getText()
            if txt.startswith("[") and txt.endswith("]"):
                sub_expr = getattr(p, "expression", lambda: None)()
                if sub_expr is not None:
                    idx_val = eval_const_int_expr(sub_expr)
                    if idx_val is not None:
                        arr_info = self.local_vars.get(prim_text) or self.global_vars.get(prim_text)
                        if arr_info and arr_info.get("array_size") is not None:
                            N = arr_info["array_size"]
                            if idx_val < 0 or idx_val >= N:
                                p_line = p.start.line if hasattr(p, "start") else line
                                fixed_idx = max(0, min(idx_val, N - 1)) if idx_val >= N else 0
                                edits = [(sub_expr.start.start, sub_expr.stop.stop + 1, str(fixed_idx))]
                                self.findings.append(Finding(
                                    rule="SEC-05",
                                    kind="array_out_of_bounds",
                                    line=p_line,
                                    message=f"Array index '{idx_val}' is out of bounds for array '{prim_text}' of size {N}",
                                    severity="WARNING",
                                    action="auto_fixed",
                                    suggestion=f"valid indexes are 0..{N - 1}; use {prim_text}[{N - 1}] or enlarge the array",
                                    fix_edits=edits,
                                    what_changed=f"changed array index '{idx_val}' to '{fixed_idx}'",
                                ))

        # Function call checks: memcpy, memmove, memset, printf, scanf
        if prim_text in ("memcpy", "memmove", "memset", "printf", "scanf"):
            for p in parts:
                al = getattr(p, "argumentList", lambda: None)()
                if al is None:
                    continue
                args = getattr(al, "assignmentExpression", lambda: [])()

                # Rule SEC-07: unsafe_memcpy / memmove / memset
                if prim_text in ("memcpy", "memmove", "memset") and len(args) >= 3:
                    dst_node = args[0]
                    dst_name = dst_node.getText().strip()
                    size_node = args[2]
                    size_txt = size_node.getText().strip()
                    size_val = eval_const_int_expr(size_node)

                    # If already sizeof(...), it is safe!
                    if size_txt.startswith("sizeof"):
                        pass
                    else:
                        dst_info = self.local_vars.get(dst_name) or self.global_vars.get(dst_name)
                        if dst_info and dst_info.get("is_array") and dst_info.get("array_size") is not None:
                            elem_type = dst_info.get("base_type", "char")
                            byte_size = dst_info["array_size"] * get_type_size(elem_type)
                            if size_val is not None and size_val > byte_size:
                                s_start = size_node.start.start
                                s_stop = size_node.stop.stop + 1
                                edits = [(s_start, s_stop, f"sizeof({dst_name})")]
                                self.findings.append(Finding(
                                    rule="SEC-07",
                                    kind="unsafe_memcpy",
                                    line=line,
                                    message=f"Buffer overflow in {prim_text}: size {size_val} exceeds '{dst_name}' capacity of {byte_size} bytes",
                                    severity="HIGH",
                                    action="auto_fixed",
                                    suggestion=f"use sizeof({dst_name}) instead of constant size",
                                    fix_edits=edits,
                                    what_changed=f"replaced size with sizeof({dst_name}) in {prim_text}",
                                ))
                            elif size_val is not None and size_val <= byte_size:
                                pass  # Safe
                            else:
                                self.findings.append(Finding(
                                    rule="SEC-07",
                                    kind="unsafe_memcpy",
                                    line=line,
                                    message=f"Potentially unsafe {prim_text} on destination '{dst_name}'",
                                    severity="WARNING",
                                    action="warned",
                                    suggestion=f"use sizeof({dst_name})",
                                    fix_edits=None,
                                ))
                        elif dst_info and not dst_info.get("is_array"):
                            self.findings.append(Finding(
                                rule="SEC-07",
                                kind="unsafe_memcpy",
                                line=line,
                                message=f"memcpy to pointer '{dst_name}' with non-array destination",
                                severity="WARNING",
                                action="warned",
                                suggestion=f"use sizeof({dst_name})",
                                fix_edits=None,
                            ))

                # Rule SEC-08: format_type_mismatch in printf
                if prim_text == "printf" and len(args) >= 1:
                    fmt_node = args[0]
                    fmt_text = fmt_node.getText()
                    if fmt_text.startswith('"') and fmt_text.endswith('"'):
                        raw_fmt = fmt_text[1:-1]
                        spec_pattern = re.compile(r"%([0-9+\-# .*]*)([hl]{0,2})([diuoxXfFeEgGaAcspn])")
                        clean_fmt = raw_fmt.replace("%%", "XX")
                        specs = list(spec_pattern.finditer(clean_fmt))
                        arg_nodes = args[1:]

                        if len(specs) != len(arg_nodes):
                            if len(specs) > 0:
                                self.findings.append(Finding(
                                    rule="SEC-08",
                                    kind="format_type_mismatch",
                                    line=line,
                                    message=f"printf argument count ({len(arg_nodes)}) does not match format specifier count ({len(specs)})",
                                    severity="WARNING",
                                    action="warned",
                                    suggestion="ensure specifier count matches argument count",
                                    fix_edits=None,
                                ))
                        else:
                            checker = SemanticChecker()
                            modified_fmt = raw_fmt
                            mismatches = 0
                            offset = 0

                            for spec_match, arg_n in zip(specs, arg_nodes):
                                flags_width = spec_match.group(1)
                                length_mod = spec_match.group(2)
                                conv_char = spec_match.group(3)

                                arg_txt = arg_n.getText().strip()
                                arg_t = checker._infer_expr_type(arg_n)
                                if arg_t is None:
                                    if arg_txt.startswith('"') and arg_txt.endswith('"'):
                                        arg_t = "string"
                                    else:
                                        v = self.local_vars.get(arg_txt) or self.global_vars.get(arg_txt)
                                        if v:
                                            if v.get("is_array") and v.get("base_type") == "char":
                                                arg_t = "char*"
                                            elif v.get("is_array"):
                                                arg_t = v.get("base_type", "") + "*"
                                            else:
                                                arg_t = v.get("full_type")

                                # Check if arg_txt is a char array variable
                                v_chk = self.local_vars.get(arg_txt) or self.global_vars.get(arg_txt)
                                if v_chk and v_chk.get("is_array") and v_chk.get("base_type") == "char":
                                    arg_t = "char*"

                                # Canonical target specifier
                                target_spec = "d"
                                c_t = _canonical_type(arg_t) if arg_t else ""
                                if arg_t == "string" or "char*" in c_t:
                                    target_spec = "s"
                                elif c_t in ("char", "signed char", "unsigned char") and not c_t.endswith("*"):
                                    target_spec = "c"
                                elif "long long" in c_t:
                                    target_spec = "lld"
                                elif "long" in c_t:
                                    target_spec = "ld"
                                elif "unsigned" in c_t:
                                    target_spec = "u"
                                elif c_t in ("float", "double"):
                                    target_spec = "f"
                                elif c_t.endswith("*"):
                                    target_spec = "p"
                                else:
                                    target_spec = "d"

                                if (length_mod + conv_char) != target_spec:
                                    mismatches += 1
                                    start_i = spec_match.start() + offset
                                    end_i = spec_match.end() + offset
                                    new_spec = f"%{flags_width}{target_spec}"
                                    modified_fmt = modified_fmt[:start_i] + new_spec + modified_fmt[end_i:]
                                    offset += len(new_spec) - (end_i - start_i)

                            if mismatches > 0:
                                new_fmt_literal = f'"{modified_fmt}"'
                                f_start = fmt_node.start.start
                                f_stop = fmt_node.stop.stop + 1
                                edits = [(f_start, f_stop, new_fmt_literal)]
                                self.findings.append(Finding(
                                    rule="SEC-08",
                                    kind="format_type_mismatch",
                                    line=line,
                                    message=f"Format specifier mismatch in printf",
                                    severity="HIGH",
                                    action="auto_fixed",
                                    suggestion=f"use canonical format specifiers for argument types",
                                    fix_edits=edits,
                                    what_changed=f"fixed format specifier in printf",
                                ))

                # Rule SEC-09: unsafe_scanf
                if prim_text == "scanf" and len(args) >= 2:
                    fmt_node = args[0]
                    fmt_text = fmt_node.getText()
                    if fmt_text.startswith('"') and fmt_text.endswith('"'):
                        raw_fmt = fmt_text[1:-1]
                        arg1_node = args[1]
                        arg1_name = arg1_node.getText().strip()

                        arg1_info = self.local_vars.get(arg1_name) or self.global_vars.get(arg1_name)
                        if arg1_info and arg1_info.get("is_array") and arg1_info.get("array_size") is not None:
                            N = arg1_info["array_size"]
                            if "%s" in raw_fmt:
                                max_width = N - 1
                                new_raw = raw_fmt.replace("%s", f"%{max_width}s", 1)
                                new_fmt_literal = f'"{new_raw}"'
                                f_start = fmt_node.start.start
                                f_stop = fmt_node.stop.stop + 1
                                edits = [(f_start, f_stop, new_fmt_literal)]
                                self.findings.append(Finding(
                                    rule="SEC-09",
                                    kind="unsafe_scanf",
                                    line=line,
                                    message=f"Unbounded '%s' format specifier in scanf overflows buffer '{arg1_name}' of size {N}",
                                    severity="HIGH",
                                    action="auto_fixed",
                                    suggestion=f"use %{max_width}s to prevent buffer overflow",
                                    fix_edits=edits,
                                    what_changed=f"added buffer limit %{max_width}s to scanf",
                                ))
                        elif "%s" in raw_fmt:
                            self.findings.append(Finding(
                                rule="SEC-09",
                                kind="unsafe_scanf",
                                line=line,
                                message="Unbounded '%s' in scanf with pointer/buffer of unknown size",
                                severity="WARNING",
                                action="warned",
                                suggestion="specify buffer length in format string",
                                fix_edits=None,
                            ))

        return self.visitChildren(ctx)

    def check_uninitialized_variables_pass(self, tree: Any):
        """
        Rule SEC-04: uninitialized_variable (AUTO).
        Detect a scalar local declared without initializer whose first use in source order is a read.
        """
        for func_ctx, locals_dict in self.all_funcs_local_vars:
            for var_name, var_info in list(locals_dict.items()):
                if var_info["is_pointer"] or var_info["is_array"] or var_info["has_init"]:
                    continue

                decl_line = var_info["line"]

                class UseCollector(SimpleCVisitor):
                    def __init__(self, target_name: str, min_line: int):
                        super().__init__()
                        self.target = target_name
                        self.min_line = min_line
                        self.reads = []
                        self.writes = []

                    def visitExprStatement(self, ctx: SimpleCParser.ExprStatementContext):
                        expr = getattr(ctx, "expression", lambda: None)()
                        if expr is not None:
                            curr = expr
                            while curr is not None and curr.getChildCount() == 1:
                                curr = curr.getChild(0)
                            if curr is not None and curr.__class__.__name__ == "AssignmentExpressionContext":
                                lhs_node = getattr(curr, "unaryExpression", lambda: None)()
                                if lhs_node and lhs_node.getText().strip() == self.target:
                                    self.writes.append((ctx.start.line, "assign"))
                                    # Still visit rhs for potential reads
                                    rhs = getattr(curr, "assignmentExpression", lambda: None)()
                                    if rhs:
                                        self.visit(rhs)
                                    return None
                        return self.visitChildren(ctx)

                    def visitPrimaryExpression(self, ctx: SimpleCParser.PrimaryExpressionContext):
                        ident = getattr(ctx, "IDENTIFIER", lambda: None)()
                        if ident is not None and ident.getText() == self.target:
                            sym = ident.getSymbol()
                            if sym.line >= self.min_line:
                                p = getattr(ctx, "parentCtx", None)
                                # Check if address of &x
                                if p and getattr(p, "AMP", lambda: None)() is not None:
                                    self.writes.append((sym.line, "addr"))
                                else:
                                    self.reads.append((sym.line, "read"))
                        return self.visitChildren(ctx)

                collector = UseCollector(var_name, decl_line)
                collector.visit(func_ctx)

                first_read_line = collector.reads[0][0] if collector.reads else None
                first_write_line = collector.writes[0][0] if collector.writes else None

                if first_read_line is not None:
                    if first_write_line is None or first_read_line <= first_write_line:
                        sym = var_info["ident_token"]
                        insert_pos = sym.stop + 1
                        edits = [(insert_pos, insert_pos, " = 0")]
                        self.findings.append(Finding(
                            rule="SEC-04",
                            kind="uninitialized_variable",
                            line=first_read_line,
                            message=f"Local scalar variable '{var_name}' read before initialization",
                            severity="HIGH",
                            action="auto_fixed",
                            suggestion=f"initialize '{var_name}' with 0 at declaration",
                            fix_edits=edits,
                            what_changed=f"initialized '{var_name}' with 0",
                        ))
                        var_info["has_init"] = True


def run_security_rules(source: str) -> Tuple[str, List[Finding], List[str]]:
    """
    Driver run_security_rules(source):
    Loops up to 20 times: parse, collect findings, apply ONE fixable finding, re-parse, repeat.
    Warn-only findings are collected once and never change the code.
    ACCEPT-ONLY-IF-SAFER:
      (1) code still parses
      (2) semantic issue count did not rise
      (3) targeted finding is gone
      (4) no new security finding appeared
    """
    current_source = source
    applied_steps: List[str] = []
    tried_fixes: Set[str] = set()
    all_findings_history: List[Finding] = []

    for round_idx in range(20):
        tree, listeners, parser = parse_source(current_source, f"<sec_round_{round_idx}>")
        if tree is None or has_any_errors(listeners):
            break

        checker = SemanticChecker()
        checker.visit(tree)
        base_sem_count = len(checker.get_issues())

        collector = SecurityRulesCollector(current_source)
        collector.visit(tree)
        collector.check_uninitialized_variables_pass(tree)
        findings = collector.findings

        # Record findings into all_findings_history
        for f in findings:
            if not any(h.rule == f.rule and h.line == f.line and h.kind == f.kind for h in all_findings_history):
                all_findings_history.append(f)

        # Find ONE fixable finding that hasn't failed
        target_finding = None
        for f in findings:
            if f.fix_edits and f.target_key not in tried_fixes:
                target_finding = f
                break

        if target_finding is None:
            break

        # Apply candidate fix
        candidate_source = apply_edits(current_source, target_finding.fix_edits)

        # ACCEPT-ONLY-IF-SAFER checks:
        cand_tree, cand_listeners, _ = parse_source(candidate_source, f"<sec_check_{round_idx}>")
        cand_parses = (cand_tree is not None) and (not has_any_errors(cand_listeners))

        if not cand_parses:
            tried_fixes.add(target_finding.target_key)
            target_finding.action = "warned"
            target_finding.fix_edits = None
            continue

        cand_checker = SemanticChecker()
        cand_checker.visit(cand_tree)
        cand_sem_count = len(cand_checker.get_issues())
        if cand_sem_count > base_sem_count:
            tried_fixes.add(target_finding.target_key)
            target_finding.action = "warned"
            target_finding.fix_edits = None
            continue

        new_collector = SecurityRulesCollector(candidate_source)
        new_collector.visit(cand_tree)
        new_collector.check_uninitialized_variables_pass(cand_tree)
        new_findings = new_collector.findings

        # Condition 3: targeted finding is gone
        still_present = any(
            nf.rule == target_finding.rule and nf.kind == target_finding.kind and nf.line == target_finding.line
            for nf in new_findings
        )
        if still_present:
            tried_fixes.add(target_finding.target_key)
            target_finding.action = "warned"
            target_finding.fix_edits = None
            continue

        # Condition 4: no brand-new security rule violation appeared
        old_rules = {f.rule for f in findings}
        new_rules = {nf.rule for nf in new_findings}
        added_rules = new_rules - old_rules
        if target_finding.rule == "SEC-10":
            added_rules -= {"SEC-03"}

        if added_rules:
            tried_fixes.add(target_finding.target_key)
            target_finding.action = "warned"
            target_finding.fix_edits = None
            continue

        # ACCEPTED!
        target_finding.action = "auto_fixed"
        for h in all_findings_history:
            if h.rule == target_finding.rule and h.line == target_finding.line and h.kind == target_finding.kind:
                h.action = "auto_fixed"
                h.what_changed = target_finding.what_changed

        applied_step = f"{target_finding.rule}: {target_finding.what_changed}"
        applied_steps.append(applied_step)
        current_source = candidate_source

    return current_source, all_findings_history, applied_steps
