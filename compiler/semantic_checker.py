# compiler/semantic_checker.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from antlr4.tree.Tree import TerminalNodeImpl

try:
    from generated.SimpleCParser import SimpleCParser
except Exception as e:
    raise ImportError(
        "generated SimpleCParser not found. Run ANTLR generation into 'generated/' first."
    ) from e

_VISITOR_BASE = None
try:
    from generated.SimpleCVisitor import SimpleCVisitor as _V  # type: ignore
    _VISITOR_BASE = _V
except Exception:
    try:
        from generated.SimpleCParserVisitor import SimpleCParserVisitor as _V  # type: ignore
        _VISITOR_BASE = _V
    except Exception as e:
        raise ImportError(
            "generated visitor not found. Generate with ANTLR '-visitor'. "
            "Expected generated/SimpleCVisitor.py or generated/SimpleCParserVisitor.py"
        ) from e

@dataclass
class _DeclInfo:
    name: str
    ctype: str          # for vars/params: "int"/"float"/"char"/"void"; for funcs: "func"
    line: int
    col: int
    used: bool = False


@dataclass
class _FuncSig:
    name: str
    ret_type: str
    param_types: List[str]
    line: int
    col: int


def _tok_line_col(node: Any) -> Tuple[int, int]:
    try:
        sym = node.getSymbol()
        if sym is not None:
            return int(sym.line), int(sym.column)
    except Exception:
        pass
    try:
        st = getattr(node, "start", None)
        if st is not None:
            return int(st.line), int(st.column)
    except Exception:
        pass
    return (0, 0)


def _is_identifier_terminal(node: TerminalNodeImpl) -> bool:
    try:
        sym = node.getSymbol()
        if sym is None:
            return False
        return sym.type == SimpleCParser.IDENTIFIER
    except Exception:
        return False


def _infer_literal_type_from_token_type(tok_type: int) -> Optional[str]:
    if tok_type == SimpleCParser.INTEGER:
        return "int"
    if tok_type == SimpleCParser.FLOAT_LITERAL:
        return "float"
    if tok_type == SimpleCParser.CHAR_LITERAL:
        return "char"
    return None


def _canonical_type(t: Optional[str]) -> str:
    if not t:
        return "?"
    s = t.replace(" ", "").lower()
    # Keep pointer depth in the type system instead of treating it as text that
    # happens to be attached to a declaration.
    pointer_depth = len(s) - len(s.rstrip("*"))
    if pointer_depth:
        return _canonical_type(s[:-pointer_depth]) + ("*" * pointer_depth)
    if s in {"unsigned", "unsignedint"}:
        return "unsigned int"
    if s in {"signed", "signedint", "int"}:
        return "int"
    if s in {"short", "shortint", "signedshort", "signedshortint"}:
        return "short"
    if s in {"unsignedshort", "unsignedshortint"}:
        return "unsigned short"
    if s in {"long", "longint", "signedlong", "signedlongint"}:
        return "long"
    if s in {"unsignedlong", "unsignedlongint"}:
        return "unsigned long"
    if s in {"longlong", "longlongint", "signedlonglong", "signedlonglongint"}:
        return "long long"
    if s in {"unsignedlonglong", "unsignedlonglongint"}:
        return "unsigned long long"
    if s in {"signedchar"}:
        return "signed char"
    if s in {"unsignedchar"}:
        return "unsigned char"
    if s in {"char"}:
        return "char"
    if s in {"float"}:
        return "float"
    if s in {"double"}:
        return "double"
    if s in {"void"}:
        return "void"
    if s.startswith("struct"):
        pointer_depth = len(s) - len(s.rstrip("*"))
        base_s = s[:-pointer_depth] if pointer_depth else s
        parts = t.split("*")[0].split()
        struct_name = parts[1] if len(parts) > 1 else base_s[6:]
        return f"struct {struct_name}" + ("*" * pointer_depth)
    return t.strip()


_TYPE_RANKS = {
    "char": 0,
    "signed char": 0,
    "unsigned char": 0,
    "short": 1,
    "unsigned short": 1,
    "int": 2,
    "unsigned int": 2,
    "long": 3,
    "unsigned long": 3,
    "long long": 4,
    "unsigned long long": 4,
    "float": 5,
    "double": 6,
    "void": -100,
}

_INTEGRAL_TYPES = {
    "char", "signed char", "unsigned char",
    "short", "unsigned short",
    "int", "unsigned int",
    "long", "unsigned long",
    "long long", "unsigned long long"
}

_INT_RANGES = {
    "char": (-128, 255),
    "signed char": (-128, 127),
    "unsigned char": (0, 255),
    "short": (-32768, 32767),
    "unsigned short": (0, 65535),
    "int": (-2147483648, 2147483647),
    "unsigned int": (0, 4294967295),
    "long": (-9223372036854775808, 9223372036854775807),
    "unsigned long": (0, 18446744073709551615),
    "long long": (-9223372036854775808, 9223372036854775807),
    "unsigned long long": (0, 18446744073709551615),
}


def _get_int_constant_value(ctx: Any) -> Optional[int]:
    if ctx is None:
        return None
    cls = ctx.__class__.__name__
    if isinstance(ctx, TerminalNodeImpl):
        sym = ctx.getSymbol()
        if sym and sym.type == SimpleCParser.INTEGER:
            try:
                return int(ctx.getText(), 0)
            except Exception:
                return None
        return None

    if cls == "UnaryExpressionContext":
        if ctx.getChildCount() == 1:
            return _get_int_constant_value(ctx.getChild(0))
        if ctx.getChildCount() == 2:
            op = ctx.getChild(0).getText()
            val = _get_int_constant_value(ctx.getChild(1))
            if val is not None:
                if op == "+":
                    return val
                elif op == "-":
                    return -val
        return None

    if cls == "PrimaryExpressionContext":
        try:
            fn = getattr(ctx, "INTEGER", None)
            if callable(fn) and fn() is not None:
                return int(fn().getText(), 0)
        except Exception:
            pass
        try:
            inner = ctx.expression()
            if inner is not None:
                return _get_int_constant_value(inner)
        except Exception:
            pass
        return None

    if ctx.getChildCount() == 1:
        return _get_int_constant_value(ctx.getChild(0))

    return None


class SemanticChecker(_VISITOR_BASE):
    """
    Semantic checks aligned to your current grammar.

    Emits issues (dict):
      - undeclared
      - redeclared
      - use_before_declare (best-effort, same-line conservative)
      - unused
      - type_mismatch
      - return_type_mismatch
      - call_arity_mismatch
      - call_type_mismatch
      - break_outside_loop
      - continue_outside_loop
      - prototype_mismatch
      - invalid_operand_type
      - shadow_warning
    """

    def __init__(self):
        super().__init__()
        self._issues: List[Dict[str, Any]] = []

        # scope stack: each scope is name -> _DeclInfo
        self._scopes: List[Dict[str, _DeclInfo]] = []
        self._decl_pos: Dict[Tuple[int, str], Tuple[int, int]] = {}

        # function signatures (global)
        self._funcs: Dict[str, _FuncSig] = {}
        self._prototypes: Dict[str, _FuncSig] = {}
        self._defined_funcs: set = set()

        # current function return type
        self._current_func_ret: Optional[str] = None

        # loop depth for break/continue validation
        self._loop_depth: int = 0

        # switch / case state
        self._switch_depth: int = 0
        self._current_switch_cases: set = set()
        self._current_switch_has_default: bool = False

        # struct registry: struct_name -> { member_name: member_type }
        self._structs: Dict[str, Dict[str, str]] = {}

    # -----------------------------
    # Public API
    # -----------------------------
    def get_issues(self) -> List[Dict[str, Any]]:
        return list(self._issues)

    # -----------------------------
    # Helpers
    # -----------------------------
    def _push_scope(self) -> None:
        self._scopes.append({})

    def _pop_scope(self) -> Dict[str, _DeclInfo]:
        return self._scopes.pop()

    def _cur_scope(self) -> Dict[str, _DeclInfo]:
        if not self._scopes:
            self._push_scope()
        return self._scopes[-1]

    def _lookup(self, name: str) -> Optional[_DeclInfo]:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None

    def _lookup_in_current(self, name: str) -> Optional[_DeclInfo]:
        return self._cur_scope().get(name)

    def _add_issue(self, kind: str, name: str, line: int, col: int, msg: str, severity: Optional[str] = None) -> None:
        issue = {"kind": kind, "name": name, "line": line, "col": col, "msg": msg}
        if severity:
            issue["severity"] = severity
        if issue not in self._issues:
            self._issues.append(issue)

    def _emit_unused_for_scope(self, scope: Dict[str, _DeclInfo]) -> None:
        for name, info in scope.items():
            if info.ctype == "func":
                continue
            if not info.used:
                self._add_issue("unused", name, info.line, info.col, f"Variable '{name}' declared but never used")

    # -----------------------------
    # Types & Ranking
    # -----------------------------
    def _is_integral_type(self, t: Optional[str]) -> bool:
        if not t:
            return False
        return _canonical_type(t) in _INTEGRAL_TYPES

    def _is_pointer_type(self, t: Optional[str]) -> bool:
        return bool(t) and _canonical_type(t).endswith("*")

    def _pointer_target(self, t: str) -> str:
        return _canonical_type(t)[:-1]

    def _type_rank(self, t: str) -> int:
        ct = _canonical_type(t)
        return _TYPE_RANKS.get(ct, -1)

    def _can_assign(self, lhs: str, rhs: str, rhs_val: Optional[int] = None) -> bool:
        c_lhs = _canonical_type(lhs)
        c_rhs = _canonical_type(rhs)
        if c_lhs == c_rhs:
            return True

        if self._is_pointer_type(c_lhs):
            # NULL and the literal 0 are accepted as null pointer constants.
            if c_rhs == "null" or (c_rhs == "int" and rhs_val == 0):
                return True
            # Pointer conversions require an explicit cast unless targets match.
            return False
        if self._is_pointer_type(c_rhs):
            return False

        if rhs_val is not None:
            if self._is_integral_type(c_lhs):
                if c_lhs in _INT_RANGES:
                    min_v, max_v = _INT_RANGES[c_lhs]
                    return min_v <= rhs_val <= max_v
            elif c_lhs in {"float", "double"}:
                return True

        r_lhs = self._type_rank(c_lhs)
        r_rhs = self._type_rank(c_rhs)
        if c_lhs == "?" or c_rhs == "?":
            return True
        if r_lhs < 0 or r_rhs < 0:
            return False
        return r_rhs <= r_lhs

    def _promote(self, a: str, b: str) -> str:
        ca = _canonical_type(a)
        cb = _canonical_type(b)
        return ca if self._type_rank(ca) >= self._type_rank(cb) else cb

    def _type_text(self, type_ctx) -> str:
        if type_ctx is None:
            return "?"
        try:
            s_spec = type_ctx.structSpecifier()
            if s_spec is not None:
                ident = s_spec.IDENTIFIER()
                sname = ident.getText() if ident is not None else "<anon>"
                return f"struct {sname}"
        except Exception:
            pass
        return _canonical_type(type_ctx.getText())

    def _type_with_pointer(self, type_ctx: Any, pointer_ctx: Any = None, array_ctx: Any = None) -> str:
        base = self._type_text(type_ctx)
        depth = len(pointer_ctx.getText()) if pointer_ctx is not None else 0
        # Function parameters declared as arrays decay to pointers, as in C.
        if array_ctx is not None:
            depth += 1
        return _canonical_type(base + ("*" * depth))

    def _is_lvalue(self, ctx: Any) -> bool:
        if ctx is None:
            return False
        cls = ctx.__class__.__name__
        if cls == "PrimaryExpressionContext":
            try:
                return ctx.IDENTIFIER() is not None
            except Exception:
                return False
        if cls == "PostfixExpressionContext":
            try:
                return bool(ctx.postfixPart()) or self._is_lvalue(ctx.primaryExpression())
            except Exception:
                return False
        if cls == "UnaryExpressionContext" and ctx.getChildCount() == 2:
            return ctx.getChild(0).getText() == "*"
        if ctx.getChildCount() == 1:
            return self._is_lvalue(ctx.getChild(0))
        return False

    # -----------------------------
    # Expression type inference + call detection
    # -----------------------------
    def _infer_expr_type(self, ctx: Any) -> Optional[str]:
        if ctx is None:
            return None

        # Terminal
        if isinstance(ctx, TerminalNodeImpl):
            try:
                sym = ctx.getSymbol()
                if sym is None:
                    return None
                if sym.type == SimpleCParser.IDENTIFIER:
                    d = self._lookup(ctx.getText())
                    return d.ctype if d else None
                return _infer_literal_type_from_token_type(sym.type)
            except Exception:
                return None

        cls = ctx.__class__.__name__

        # primaryExpression: IDENTIFIER | literal | (expression)
        if cls == "PrimaryExpressionContext":
            try:
                if ctx.NULL() is not None:
                    return "null"
            except Exception:
                pass
            try:
                ident = ctx.IDENTIFIER()
                if ident is not None:
                    d = self._lookup(ident.getText())
                    return d.ctype if d else None
            except Exception:
                pass
            try:
                # literals
                for tok_attr, tname in [("INTEGER", "int"), ("FLOAT_LITERAL", "float"), ("CHAR_LITERAL", "char")]:
                    fn = getattr(ctx, tok_attr, None)
                    if callable(fn) and fn() is not None:
                        return tname
            except Exception:
                pass
            try:
                inner = ctx.expression()
                if inner is not None:
                    return self._infer_expr_type(inner)
            except Exception:
                pass

        # postfixExpression: primaryExpression postfixPart*
        # If it includes a call "(...)" we treat type as function return type (if known).
        if cls == "PostfixExpressionContext":
            # detect f(...) calls: primary IDENTIFIER + postfixPart with LPAREN
            try:
                prim = ctx.primaryExpression()
                fname = None
                try:
                    ident = prim.IDENTIFIER()
                    if ident is not None:
                        fname = ident.getText()
                except Exception:
                    fname = None

                if fname:
                    # scan postfixPart for a call
                    parts = []
                    try:
                        parts = list(ctx.postfixPart())
                    except Exception:
                        parts = []

                    for p in parts:
                        if p.__class__.__name__ == "PostfixPartContext":
                            # p has LPAREN? RPAREN?
                            if getattr(p, "LPAREN", None) is not None:
                                # not reliable; fall back to text check
                                pass
                        txt = p.getText()
                        if txt.startswith("(") and txt.endswith(")"):
                            sig = self._funcs.get(fname)
                            if sig:
                                return sig.ret_type
                            return None
            except Exception:
                pass

            try:
                base = self._infer_expr_type(ctx.primaryExpression())
                for part in ctx.postfixPart():
                    txt = part.getText()
                    if txt.startswith("[") and base and self._is_pointer_type(base):
                        base = self._pointer_target(base)
                    elif txt.startswith(".") and not txt.startswith(".."):
                        m_ident = getattr(part, "IDENTIFIER", lambda: None)()
                        mname = m_ident.getText() if m_ident else txt[1:].strip()
                        line, col = _tok_line_col(part)
                        if base is None:
                            continue
                        if self._is_pointer_type(base):
                            self._add_issue("dot_on_pointer", mname, line, col, f"'.' used on pointer '{base}'; did you mean '->'?")
                            base_struct = base.rstrip("*").strip()
                        else:
                            base_struct = base.strip()

                        sname = base_struct[6:].strip() if base_struct.startswith("struct ") else base_struct
                        if sname not in self._structs:
                            self._add_issue("unknown_struct_type", sname, line, col, f"request for member '{mname}' in unknown or incomplete type 'struct {sname}'")
                            base = "?"
                        else:
                            s_members = self._structs[sname]
                            if mname not in s_members:
                                self._add_issue("unknown_member", mname, line, col, f"'struct {sname}' has no member named '{mname}'")
                                base = "?"
                            else:
                                base = s_members[mname]
                    elif txt.startswith("->"):
                        m_ident = getattr(part, "IDENTIFIER", lambda: None)()
                        mname = m_ident.getText() if m_ident else txt[2:].strip()
                        line, col = _tok_line_col(part)
                        if base is None:
                            continue
                        if not self._is_pointer_type(base):
                            self._add_issue("arrow_on_value", mname, line, col, f"'->' used on non-pointer '{base}'; did you mean '.'?")
                            base_struct = base.strip()
                        else:
                            base_struct = base.rstrip("*").strip()

                        sname = base_struct[6:].strip() if base_struct.startswith("struct ") else base_struct
                        if sname not in self._structs:
                            self._add_issue("unknown_struct_type", sname, line, col, f"request for member '{mname}' in unknown or incomplete type 'struct {sname}'")
                            base = "?"
                        else:
                            s_members = self._structs[sname]
                            if mname not in s_members:
                                self._add_issue("unknown_member", mname, line, col, f"'struct {sname}' has no member named '{mname}'")
                                base = "?"
                            else:
                                base = s_members[mname]
                return base
            except Exception:
                return None

        # unaryExpression: postfixExpression | (op) unaryExpression
        if cls == "UnaryExpressionContext":
            try:
                if ctx.getChildCount() == 1:
                    return self._infer_expr_type(ctx.getChild(0))
                # (type) expr
                if ctx.getChild(0).getText() == "(" and ctx.typeSpecifier() is not None:
                    return self._type_with_pointer(ctx.typeSpecifier(), ctx.pointer())
                # This educational C subset models sizeof as an int-sized
                # integral result, which keeps the common `int n = sizeof x`
                # teaching pattern free of a narrowing diagnostic.
                if ctx.getChild(0).getText() == "sizeof":
                    return "int"
                sub_ctx = ctx.getChild(ctx.getChildCount() - 1)
                t = self._infer_expr_type(sub_ctx)
                if ctx.getChildCount() == 2:
                    op_node = ctx.getChild(0)
                    op = op_node.getText()
                    if op == "~":
                        if t is not None and not self._is_integral_type(t):
                            line, col = _tok_line_col(op_node)
                            self._add_issue("invalid_operand_type", "", line, col, f"Bitwise NOT operator '~' requires integral operand, got '{t}'")
                    elif op == "!":
                        return "int"
                    elif op == "&":
                        if not self._is_lvalue(sub_ctx):
                            line, col = _tok_line_col(op_node)
                            self._add_issue("invalid_address_of", "", line, col, "Address-of operator '&' requires an lvalue")
                            return None
                        return _canonical_type((t or "?") + "*")
                    elif op == "*":
                        if not self._is_pointer_type(t):
                            line, col = _tok_line_col(op_node)
                            self._add_issue("invalid_dereference", "", line, col, f"Cannot dereference non-pointer type '{t or '?'}'")
                            return None
                        return self._pointer_target(t)
                return t
            except Exception:
                return None

        # multiplicative / additive: promote
        if cls in {"MultiplicativeExpressionContext", "AdditiveExpressionContext"}:
            try:
                if ctx.getChildCount() == 1:
                    return self._infer_expr_type(ctx.getChild(0))
                t = self._infer_expr_type(ctx.getChild(0))
                if t is None:
                    return None
                i = 2
                while i < ctx.getChildCount():
                    rhs = self._infer_expr_type(ctx.getChild(i))
                    if rhs is not None:
                        if self._is_pointer_type(t) or self._is_pointer_type(rhs):
                            # Pointer arithmetic is deliberately outside this
                            # teaching subset; retain pointer type for p +/- n.
                            if self._is_pointer_type(t) and self._is_integral_type(rhs):
                                continue
                            line, col = _tok_line_col(ctx.getChild(i))
                            self._add_issue("invalid_operand_type", "", line, col, "Invalid pointer arithmetic operands")
                            return None
                        t = self._promote(t, rhs)
                    i += 2
                return t
            except Exception:
                return None

        # shiftExpression: <<, >> (operands must be integral)
        if cls == "ShiftExpressionContext":
            try:
                if ctx.getChildCount() == 1:
                    return self._infer_expr_type(ctx.getChild(0))
                lhs_t = self._infer_expr_type(ctx.getChild(0))
                for i in range(0, ctx.getChildCount(), 2):
                    sub_ctx = ctx.getChild(i)
                    sub_t = self._infer_expr_type(sub_ctx)
                    if sub_t is not None and not self._is_integral_type(sub_t):
                        line, col = _tok_line_col(sub_ctx)
                        self._add_issue("invalid_operand_type", "", line, col, f"Shift operator requires integral operands, got '{sub_t}'")
                return lhs_t if (lhs_t and self._is_integral_type(lhs_t)) else "int"
            except Exception:
                return None

        # relational/equality always produce int when comparing, else pass through
        if cls in {"RelationalExpressionContext", "EqualityExpressionContext"}:
            try:
                if ctx.getChildCount() == 1:
                    return self._infer_expr_type(ctx.getChild(0))
                if cls == "EqualityExpressionContext":
                    left_t = self._infer_expr_type(ctx.getChild(0))
                    for i in range(2, ctx.getChildCount(), 2):
                        right_ctx = ctx.getChild(i)
                        right_t = self._infer_expr_type(right_ctx)
                        if (
                            self._is_pointer_type(left_t)
                            and self._is_pointer_type(right_t)
                            and _canonical_type(left_t) != _canonical_type(right_t)
                        ):
                            line, col = _tok_line_col(right_ctx)
                            self._add_issue("pointer_type_mismatch", "", line, col, f"Cannot compare '{left_t}' with '{right_t}'")
                        left_t = right_t
                return "int"
            except Exception:
                return None

        # andExpression: & (operands must be integral)
        if cls == "AndExpressionContext":
            try:
                if ctx.getChildCount() == 1:
                    return self._infer_expr_type(ctx.getChild(0))
                op_types = []
                for i in range(0, ctx.getChildCount(), 2):
                    sub_ctx = ctx.getChild(i)
                    sub_t = self._infer_expr_type(sub_ctx)
                    op_types.append(sub_t)
                    if sub_t is not None and not self._is_integral_type(sub_t):
                        line, col = _tok_line_col(sub_ctx)
                        self._add_issue("invalid_operand_type", "", line, col, f"Bitwise operator '&' requires integral operands, got '{sub_t}'")
                res = "int"
                for t in op_types:
                    if t and self._is_integral_type(t) and self._type_rank(t) > self._type_rank(res):
                        res = _canonical_type(t)
                return res
            except Exception:
                return None

        # exclusiveOrExpression: ^ (operands must be integral)
        if cls == "ExclusiveOrExpressionContext":
            try:
                if ctx.getChildCount() == 1:
                    return self._infer_expr_type(ctx.getChild(0))
                op_types = []
                for i in range(0, ctx.getChildCount(), 2):
                    sub_ctx = ctx.getChild(i)
                    sub_t = self._infer_expr_type(sub_ctx)
                    op_types.append(sub_t)
                    if sub_t is not None and not self._is_integral_type(sub_t):
                        line, col = _tok_line_col(sub_ctx)
                        self._add_issue("invalid_operand_type", "", line, col, f"Bitwise operator '^' requires integral operands, got '{sub_t}'")
                res = "int"
                for t in op_types:
                    if t and self._is_integral_type(t) and self._type_rank(t) > self._type_rank(res):
                        res = _canonical_type(t)
                return res
            except Exception:
                return None

        # inclusiveOrExpression: | (operands must be integral)
        if cls == "InclusiveOrExpressionContext":
            try:
                if ctx.getChildCount() == 1:
                    return self._infer_expr_type(ctx.getChild(0))
                op_types = []
                for i in range(0, ctx.getChildCount(), 2):
                    sub_ctx = ctx.getChild(i)
                    sub_t = self._infer_expr_type(sub_ctx)
                    op_types.append(sub_t)
                    if sub_t is not None and not self._is_integral_type(sub_t):
                        line, col = _tok_line_col(sub_ctx)
                        self._add_issue("invalid_operand_type", "", line, col, f"Bitwise operator '|' requires integral operands, got '{sub_t}'")
                res = "int"
                for t in op_types:
                    if t and self._is_integral_type(t) and self._type_rank(t) > self._type_rank(res):
                        res = _canonical_type(t)
                return res
            except Exception:
                return None

        # logical always produce int when comparing, else pass through
        if cls in {"LogicalAndExpressionContext", "LogicalOrExpressionContext"}:
            try:
                if ctx.getChildCount() == 1:
                    return self._infer_expr_type(ctx.getChild(0))
                return "int"
            except Exception:
                return None

        # conditional: promote arms
        if cls == "ConditionalExpressionContext":
            try:
                if ctx.getChildCount() == 1:
                    return self._infer_expr_type(ctx.getChild(0))
                t1 = self._infer_expr_type(ctx.getChild(2))
                t2 = self._infer_expr_type(ctx.getChild(4))
                if t1 and t2:
                    return self._promote(t1, t2)
                return t1 or t2
            except Exception:
                return None

        # assignmentExpression: LHS type
        if cls == "AssignmentExpressionContext":
            try:
                if ctx.getChildCount() == 1:
                    return self._infer_expr_type(ctx.getChild(0))
                lhs_ctx = ctx.getChild(0)
                op_ctx = ctx.getChild(1)
                rhs_ctx = ctx.getChild(2)
                op = op_ctx.getText()
                lhs_t = self._infer_expr_type(lhs_ctx)
                rhs_t = self._infer_expr_type(rhs_ctx)
                if op in {"&=", "|=", "^=", "<<=", ">>=", "%="}:
                    if lhs_t is not None and not self._is_integral_type(lhs_t):
                        line, col = _tok_line_col(lhs_ctx)
                        self._add_issue("invalid_operand_type", "", line, col, f"Operator '{op}' requires integral operands, got '{lhs_t}'")
                    if rhs_t is not None and not self._is_integral_type(rhs_t):
                        line, col = _tok_line_col(rhs_ctx)
                        self._add_issue("invalid_operand_type", "", line, col, f"Operator '{op}' requires integral operands, got '{rhs_t}'")
                elif op == "=":
                    rhs_val = _get_int_constant_value(rhs_ctx)
                    if lhs_t and rhs_t and not self._can_assign(lhs_t, rhs_t, rhs_val=rhs_val):
                        line, col = _tok_line_col(op_ctx)
                        pointer_from_integer = self._is_pointer_type(lhs_t) and self._is_integral_type(rhs_t)
                        kind = "pointer_assignment_warning" if pointer_from_integer else ("pointer_type_mismatch" if self._is_pointer_type(lhs_t) or self._is_pointer_type(rhs_t) else "type_mismatch")
                        self._add_issue(kind, "", line, col, f"Cannot assign '{rhs_t}' to '{lhs_t}'", "warning" if pointer_from_integer else None)
                return lhs_t
            except Exception:
                return None

        # expression: comma operator => type of last
        if cls == "ExpressionContext":
            try:
                if ctx.getChildCount() == 1:
                    return self._infer_expr_type(ctx.getChild(0))
                return self._infer_expr_type(ctx.getChild(ctx.getChildCount() - 1))
            except Exception:
                return None

        # fallback: walk children
        try:
            for i in range(ctx.getChildCount()):
                t = self._infer_expr_type(ctx.getChild(i))
                if t is not None:
                    return t
        except Exception:
            pass

        return None

    # -----------------------------
    # Visitors
    # -----------------------------
    def visitProgram(self, ctx: SimpleCParser.ProgramContext):
        self._push_scope()
        out = self.visitChildren(ctx)
        # Global-scope variables are not flagged as unused (Bug 5 fix)
        self._pop_scope()
        return out

    def visitTopLevelItem(self, ctx: SimpleCParser.TopLevelItemContext):
        return self.visitChildren(ctx)

    def visitFunctionDeclaration(self, ctx: SimpleCParser.FunctionDeclarationContext):
        rtype = self._type_with_pointer(ctx.typeSpecifier(), ctx.pointer())
        fname_node = ctx.IDENTIFIER()
        fname = fname_node.getText() if fname_node else None
        if not fname:
            return self.visitChildren(ctx)

        line, col = _tok_line_col(fname_node)

        param_types: List[str] = []
        pl = ctx.paramList()
        if pl is not None:
            for p in pl.param():
                ptype = self._type_with_pointer(p.typeSpecifier(), p.pointer(), p.arraySuffix())
                if ptype == "void" and p.IDENTIFIER() is None and len(pl.param()) == 1:
                    continue
                param_types.append(ptype)

        if fname in self._prototypes:
            prev = self._prototypes[fname]
            if prev.ret_type != rtype or prev.param_types != param_types:
                self._add_issue(
                    "prototype_mismatch",
                    fname,
                    line,
                    col,
                    f"Conflicting function prototype for '{fname}'",
                )
        elif fname in self._defined_funcs:
            prev = self._funcs.get(fname)
            if prev and (prev.ret_type != rtype or prev.param_types != param_types):
                self._add_issue(
                    "prototype_mismatch",
                    fname,
                    line,
                    col,
                    f"Prototype for '{fname}' does not match prior definition",
                )

        sig = _FuncSig(fname, rtype, param_types, line, col)
        self._prototypes[fname] = sig
        if fname not in self._funcs:
            self._funcs[fname] = sig

        if self._scopes and fname not in self._scopes[0]:
            self._scopes[0][fname] = _DeclInfo(name=fname, ctype="func", line=line, col=col, used=True)

        return None

    def visitFunctionDef(self, ctx: SimpleCParser.FunctionDefContext):
        rtype = self._type_with_pointer(ctx.typeSpecifier(), ctx.pointer())
        fname_node = ctx.IDENTIFIER()
        fname = fname_node.getText() if fname_node else None
        line, col = _tok_line_col(fname_node) if fname_node else (0, 0)

        param_types: List[str] = []
        pl = ctx.paramList()
        if pl is not None:
            for p in pl.param():
                ptype = self._type_with_pointer(p.typeSpecifier(), p.pointer(), p.arraySuffix())
                if ptype == "void" and p.IDENTIFIER() is None and len(pl.param()) == 1:
                    continue
                param_types.append(ptype)

        if fname:
            if fname in self._defined_funcs:
                self._add_issue("redeclared", fname, line, col, f"Redeclaration of function '{fname}'")
            else:
                self._defined_funcs.add(fname)

            if fname in self._prototypes:
                proto = self._prototypes[fname]
                if proto.ret_type != rtype:
                    self._add_issue(
                        "prototype_mismatch",
                        fname,
                        line,
                        col,
                        f"Definition return type '{rtype}' does not match prototype return type '{proto.ret_type}'",
                    )
                elif len(proto.param_types) != len(param_types):
                    self._add_issue(
                        "prototype_mismatch",
                        fname,
                        line,
                        col,
                        f"Definition parameter count ({len(param_types)}) does not match prototype ({len(proto.param_types)})",
                    )
                else:
                    for i, (pt, dt) in enumerate(zip(proto.param_types, param_types), start=1):
                        if pt != dt:
                            self._add_issue(
                                "prototype_mismatch",
                                fname,
                                line,
                                col,
                                f"Definition parameter {i} type '{dt}' does not match prototype type '{pt}'",
                            )

            self._funcs[fname] = _FuncSig(fname, rtype, param_types, line, col)
            if self._scopes and fname not in self._scopes[0]:
                self._scopes[0][fname] = _DeclInfo(name=fname, ctype="func", line=line, col=col, used=True)

        prev_ret = self._current_func_ret
        self._current_func_ret = rtype

        self._push_scope()
        if pl is not None:
            self.visit(pl)

        out = self.visit(ctx.block())
        self._emit_unused_for_scope(self._cur_scope())
        self._pop_scope()

        self._current_func_ret = prev_ret
        return out

    def visitParam(self, ctx: SimpleCParser.ParamContext):
        try:
            name_node = ctx.IDENTIFIER()
            if name_node is None:
                return self.visitChildren(ctx)
            name = name_node.getText()
            ctype = self._type_with_pointer(ctx.typeSpecifier(), ctx.pointer(), ctx.arraySuffix())
            line, col = _tok_line_col(name_node)
        except Exception:
            return self.visitChildren(ctx)

        if self._lookup_in_current(name) is not None:
            self._add_issue("redeclared", name, line, col, f"Redeclaration of '{name}' in the same scope")
            return None

        depth = len(self._scopes) - 1
        self._cur_scope()[name] = _DeclInfo(name=name, ctype=ctype, line=line, col=col, used=False)
        self._decl_pos[(depth, name)] = (line, col)
        return None

    def visitBlock(self, ctx: SimpleCParser.BlockContext):
        self._push_scope()
        out = self.visitChildren(ctx)
        self._emit_unused_for_scope(self._cur_scope())
        self._pop_scope()
        return out

    def visitDeclaration(self, ctx: SimpleCParser.DeclarationContext):
        dn = None
        try:
            dn = ctx.declarationNoSemi()
        except Exception:
            dn = None

        if dn is not None:
            return self.visit(dn)

        return None

    def _handle_struct_specifier(self, struct_ctx) -> None:
        sname = None
        try:
            ident = struct_ctx.IDENTIFIER()
            if ident is not None:
                sname = ident.getText()
        except Exception:
            sname = None

        member_decls = None
        try:
            member_decls = struct_ctx.structMemberDeclaration()
        except Exception:
            member_decls = None

        if member_decls:
            if sname:
                if sname in self._structs:
                    line, col = _tok_line_col(struct_ctx)
                    self._add_issue("redeclared_struct", sname, line, col, f"Redeclaration of 'struct {sname}'")
                members: Dict[str, str] = {}
                for m_decl in member_decls:
                    try:
                        m_type = self._type_text(m_decl.typeSpecifier())
                        for s_decl in m_decl.structDeclarator():
                            m_ident = s_decl.IDENTIFIER()
                            if m_ident:
                                m_name = m_ident.getText()
                                m_line, m_col = _tok_line_col(m_ident)
                                if m_name in members:
                                    self._add_issue("duplicate_member", m_name, m_line, m_col, f"Duplicate member '{m_name}' in 'struct {sname}'")
                                else:
                                    ptr_depth = len(s_decl.pointer().getText()) if s_decl.pointer() else 0
                                    arr_depth = 1 if s_decl.arraySuffix() else 0
                                    final_m_type = _canonical_type(m_type + ("*" * (ptr_depth + arr_depth)))
                                    members[m_name] = final_m_type
                    except Exception:
                        pass
                if sname:
                    self._structs[sname] = members
        else:
            if sname and sname not in self._structs:
                line, col = _tok_line_col(struct_ctx)
                self._add_issue("unknown_struct_type", sname, line, col, f"Variable has incomplete or unknown type 'struct {sname}'")

    def visitDeclarationNoSemi(self, ctx: SimpleCParser.DeclarationNoSemiContext):
        try:
            ctype = self._type_text(ctx.typeSpecifier())
        except Exception:
            return None

        # Check struct definition / usage
        try:
            struct_ctx = ctx.typeSpecifier().structSpecifier()
            if struct_ctx is not None:
                self._handle_struct_specifier(struct_ctx)
        except Exception:
            pass

        lst = None
        try:
            lst = ctx.initDeclaratorList()
        except Exception:
            lst = None

        if lst is None:
            return None

        for init_ctx in lst.initDeclarator():
            self._handle_init_declarator(init_ctx, ctype)

        return None

    def _handle_init_declarator(self, ctx: SimpleCParser.InitDeclaratorContext, ctype: str) -> None:
        ident = None
        try:
            ident = ctx.IDENTIFIER()
        except Exception:
            ident = None
        if ident is None:
            return

        name = ident.getText()
        line, col = _tok_line_col(ident)

        if self._lookup_in_current(name) is not None:
            self._add_issue("redeclared", name, line, col, f"Redeclaration of '{name}' in the same scope")
            return

        depth = len(self._scopes) - 1
        # Shadowing check: local shadows global
        if depth > 0 and len(self._scopes) > 0:
            global_scope = self._scopes[0]
            if name in global_scope and global_scope[name].ctype != "func":
                self._add_issue(
                    "shadow_warning",
                    name,
                    line,
                    col,
                    f"Declaration of '{name}' shadows global variable",
                )

        # Merge the declarator's pointer/array depth with declarationNoSemi's
        # base type. Arrays decay to pointers in expression contexts.
        suffix_depth = len(ctx.pointer().getText()) if ctx.pointer() is not None else 0
        if ctx.arraySuffix() is not None:
            suffix_depth += 1
        decl_type = _canonical_type(ctype + ("*" * suffix_depth))
        self._cur_scope()[name] = _DeclInfo(name=name, ctype=decl_type, line=line, col=col, used=False)
        self._decl_pos[(depth, name)] = (line, col)

        # initializer check (handles expression and array initializers)
        init_node = getattr(ctx, "initializer", lambda: None)()
        if init_node is not None:
            if getattr(init_node, "LBRACE", lambda: None)() is not None:
                elem_inits = getattr(init_node, "initializer", lambda: [])()
                arr_suffix = getattr(ctx, "arraySuffix", lambda: None)()
                if arr_suffix is not None:
                    try:
                        exprs = arr_suffix.expression()
                        if exprs:
                            decl_size = _get_int_constant_value(exprs[0])
                            if decl_size is not None and len(elem_inits) > decl_size:
                                self._add_issue("too_many_initializers", name, line, col, f"too many initializers for array '{name}' (expected at most {decl_size}, got {len(elem_inits)})")
                    except Exception:
                        pass
                base_elem_type = decl_type.rstrip("*")
                for sub_init in elem_inits:
                    self.visit(sub_init)
                    sub_expr = getattr(sub_init, "assignmentExpression", lambda: None)()
                    if sub_expr is not None:
                        sub_t = self._infer_expr_type(sub_expr)
                        if sub_t is not None and not self._can_assign(base_elem_type, sub_t):
                            sub_line, sub_col = _tok_line_col(sub_init)
                            self._add_issue("element_type_mismatch", name, sub_line, sub_col, f"element type mismatch in array initializer: cannot convert '{sub_t}' to '{base_elem_type}'")
            else:
                sub_expr = getattr(init_node, "assignmentExpression", lambda: None)()
                if sub_expr is not None:
                    self.visit(sub_expr)
                    rhs_t = self._infer_expr_type(sub_expr)
                    rhs_val = _get_int_constant_value(sub_expr)
                    if self._is_pointer_type(decl_type) and "char" in decl_type and rhs_t == "string":
                        arr_suffix = getattr(ctx, "arraySuffix", lambda: None)()
                        if arr_suffix is not None:
                            try:
                                exprs = arr_suffix.expression()
                                if exprs:
                                    decl_size = _get_int_constant_value(exprs[0])
                                    str_len = len(sub_expr.getText()) - 2 + 1
                                    if decl_size is not None and str_len > decl_size:
                                        self._add_issue("too_many_initializers", name, line, col, f"initializer-string for char array '{name}' is too long (size {decl_size}, string with null requires {str_len})")
                            except Exception:
                                pass
                    elif rhs_t is not None and not self._can_assign(decl_type, rhs_t, rhs_val=rhs_val):
                        pointer_from_integer = self._is_pointer_type(decl_type) and self._is_integral_type(rhs_t)
                        kind = "pointer_assignment_warning" if pointer_from_integer else ("pointer_type_mismatch" if self._is_pointer_type(decl_type) or self._is_pointer_type(rhs_t) else "type_mismatch")
                        self._add_issue(kind, name, line, col, f"Cannot assign '{rhs_t}' to '{decl_type}' for variable '{name}'", "warning" if pointer_from_integer else None)
        else:
            expr = getattr(ctx, "assignmentExpression", lambda: None)()
            if expr is not None:
                self.visit(expr)
                rhs_t = self._infer_expr_type(expr)
                rhs_val = _get_int_constant_value(expr)
                if rhs_t is not None and not self._can_assign(decl_type, rhs_t, rhs_val=rhs_val):
                    pointer_from_integer = self._is_pointer_type(decl_type) and self._is_integral_type(rhs_t)
                    kind = "pointer_assignment_warning" if pointer_from_integer else ("pointer_type_mismatch" if self._is_pointer_type(decl_type) or self._is_pointer_type(rhs_t) else "type_mismatch")
                    self._add_issue(kind, name, line, col, f"Cannot assign '{rhs_t}' to '{decl_type}' for variable '{name}'", "warning" if pointer_from_integer else None)

    def visitShiftExpression(self, ctx: SimpleCParser.ShiftExpressionContext):
        self._infer_expr_type(ctx)
        return self.visitChildren(ctx)

    def visitAndExpression(self, ctx: SimpleCParser.AndExpressionContext):
        self._infer_expr_type(ctx)
        return self.visitChildren(ctx)

    def visitExclusiveOrExpression(self, ctx: SimpleCParser.ExclusiveOrExpressionContext):
        self._infer_expr_type(ctx)
        return self.visitChildren(ctx)

    def visitInclusiveOrExpression(self, ctx: SimpleCParser.InclusiveOrExpressionContext):
        self._infer_expr_type(ctx)
        return self.visitChildren(ctx)

    def visitAssignmentExpression(self, ctx: SimpleCParser.AssignmentExpressionContext):
        self._infer_expr_type(ctx)
        return self.visitChildren(ctx)

    def visitReturnStatement(self, ctx: SimpleCParser.ReturnStatementContext):
        if self._current_func_ret is None:
            return self.visitChildren(ctx)

        expr = None
        try:
            expr = ctx.expression()
        except Exception:
            expr = None

        line, col = _tok_line_col(ctx)

        if self._current_func_ret == "void":
            if expr is not None:
                self._add_issue("return_type_mismatch", "", line, col, "Void function should not return a value")
            return self.visitChildren(ctx)

        if expr is None:
            self._add_issue(
                "return_type_mismatch",
                "",
                line,
                col,
                f"Non-void function should return a value of type '{self._current_func_ret}'",
            )
            return self.visitChildren(ctx)

        t = self._infer_expr_type(expr)
        rhs_val = _get_int_constant_value(expr)
        if t is not None and not self._can_assign(self._current_func_ret, t, rhs_val=rhs_val):
            self._add_issue(
                "return_type_mismatch",
                "",
                line,
                col,
                f"Return type '{t}' not compatible with function return type '{self._current_func_ret}'",
            )

        return self.visitChildren(ctx)

    def visitWhileStatement(self, ctx: SimpleCParser.WhileStatementContext):
        self._loop_depth += 1
        out = self.visitChildren(ctx)
        self._loop_depth -= 1
        return out

    def visitDoWhileStatement(self, ctx: SimpleCParser.DoWhileStatementContext):
        self._loop_depth += 1
        out = self.visitChildren(ctx)
        self._loop_depth -= 1
        return out

    def visitForStatement(self, ctx: SimpleCParser.ForStatementContext):
        # forStatement : FOR LPAREN forInit? SEMI expression? SEMI expression? RPAREN statement ;

        # Enter loop context (for break/continue validation)
        self._loop_depth += 1

        # The for-loop introduces its own scope in C when init contains a declaration.
        # We will ALWAYS push a scope here; it's safe and matches typical C behavior.
        self._push_scope()

        # Visit init first so declared vars (e.g., int i=0) exist for cond/update/body
        try:
            fi = ctx.forInit()
            if fi is not None:
                self.visit(fi)
        except Exception:
            pass

        # Visit condition expression (optional)
        try:
            # expression() appears 0..2 times here: cond and update
            exprs = list(ctx.expression())
            if len(exprs) >= 1 and exprs[0] is not None:
                self.visit(exprs[0])
            if len(exprs) >= 2 and exprs[1] is not None:
                self.visit(exprs[1])
        except Exception:
            pass

        # Visit the loop body statement
        out = None
        try:
            st = ctx.statement()
            out = self.visit(st) if st is not None else self.visitChildren(ctx)
        except Exception:
            out = self.visitChildren(ctx)

        # End loop scope
        self._emit_unused_for_scope(self._cur_scope())
        self._pop_scope()

        # Exit loop context
        self._loop_depth -= 1
        return out

    def _check_switch_fallthrough(self, body_ctx):
        try:
            block = body_ctx.block() if hasattr(body_ctx, "block") and body_ctx.block() else body_ctx
            items = getattr(block, "blockItem", lambda: [])()
            if not items:
                return
            n = len(items)
            for i, it in enumerate(items):
                st = getattr(it, "statement", lambda: None)()
                if st is not None and getattr(st, "labeledStatement", lambda: None)() is not None:
                    has_stmts = False
                    ends_cleanly = False
                    j = i + 1
                    while j < n:
                        next_st = getattr(items[j], "statement", lambda: None)()
                        if next_st is not None and getattr(next_st, "labeledStatement", lambda: None)() is not None:
                            break
                        has_stmts = True
                        if next_st is not None:
                            if getattr(next_st, "breakStatement", lambda: None)() is not None or getattr(next_st, "returnStatement", lambda: None)() is not None:
                                ends_cleanly = True
                        j += 1
                    if has_stmts and not ends_cleanly and j < n:
                        line, col = _tok_line_col(st)
                        self._add_issue("fallthrough_warning", "switch", line, col, "fall-through from case without 'break'", severity="warning")
        except Exception:
            pass

    def visitSwitchStatement(self, ctx: SimpleCParser.SwitchStatementContext):
        self._switch_depth += 1
        prev_cases = self._current_switch_cases
        prev_default = self._current_switch_has_default
        self._current_switch_cases = set()
        self._current_switch_has_default = False

        try:
            cond_expr = ctx.expression()
            if cond_expr is not None:
                self.visit(cond_expr)
                cond_type = self._infer_expr_type(cond_expr)
                if cond_type and not self._is_integral_type(cond_type):
                    line, col = _tok_line_col(cond_expr)
                    self._add_issue("invalid_operand_type", "switch", line, col, f"switch expression must have integral type, got '{cond_type}'")
        except Exception:
            pass

        try:
            body = ctx.statement()
            if body is not None:
                self.visit(body)
                self._check_switch_fallthrough(body)
        except Exception:
            pass

        if not self._current_switch_has_default:
            line, col = _tok_line_col(ctx)
            self._add_issue("missing_default", "switch", line, col, "switch statement missing 'default' label", severity="warning")

        self._current_switch_cases = prev_cases
        self._current_switch_has_default = prev_default
        self._switch_depth -= 1
        return None

    def visitLabeledStatement(self, ctx: SimpleCParser.LabeledStatementContext):
        line, col = _tok_line_col(ctx)
        if self._switch_depth <= 0:
            self._add_issue("case_outside_switch", "", line, col, "'case' or 'default' label outside of switch statement")
            return self.visitChildren(ctx)

        if ctx.DEFAULT() is not None:
            if self._current_switch_has_default:
                self._add_issue("duplicate_default", "default", line, col, "multiple 'default' labels in one switch")
            self._current_switch_has_default = True
        elif ctx.CASE() is not None:
            cond_expr = ctx.conditionalExpression()
            val = _get_int_constant_value(cond_expr)
            if val is None:
                self._add_issue("non_constant_case", cond_expr.getText(), line, col, f"case expression '{cond_expr.getText()}' is not an integer constant")
            else:
                if val in self._current_switch_cases:
                    self._add_issue("duplicate_case", str(val), line, col, f"duplicate case value '{val}' in switch")
                else:
                    self._current_switch_cases.add(val)
        return self.visitChildren(ctx)

    def visitBreakStatement(self, ctx: SimpleCParser.BreakStatementContext):
        if self._loop_depth <= 0 and self._switch_depth <= 0:
            line, col = _tok_line_col(ctx)
            self._add_issue("break_outside_loop", "", line, col, "break used outside of a loop or switch")
        return self.visitChildren(ctx)

    def visitContinueStatement(self, ctx: SimpleCParser.ContinueStatementContext):
        if self._loop_depth <= 0:
            line, col = _tok_line_col(ctx)
            self._add_issue("continue_outside_loop", "", line, col, "continue used outside of a loop")
        return self.visitChildren(ctx)

    def visitAssignStmt(self, ctx):
        # your grammar doesn't have AssignStmtContext anymore; ignore if present in older generated code
        return self.visitChildren(ctx)

    def visitTerminal(self, node: TerminalNodeImpl):
        if not _is_identifier_terminal(node):
            return None

        parent = getattr(node, "parentCtx", None)
        if parent is not None:
            pname = parent.__class__.__name__
            if pname in {"InitDeclaratorContext", "ParamContext", "FunctionDefContext", "FunctionDeclarationContext", "PostfixPartContext", "StructDeclaratorContext", "StructSpecifierContext"}:
                return None

        name = node.getText()
        line, col = _tok_line_col(node)

        # hard allowlist for builtin/library functions
        # hard allowlist for builtin/library functions & keywords
        if name in {
            "printf",
            "scanf",
            "fgets",
            "snprintf",
            "vsnprintf",
            "strncpy",
            "strncat",
            "sizeof",
            "stdin",
        }:
            return None

        decl = self._lookup(name)
        if decl is None:
            self._add_issue("undeclared", name, line, col, f"Use of undeclared identifier '{name}'")
            return None

        depth = len(self._scopes) - 1
        if (depth, name) in self._decl_pos:
            dline, dcol = self._decl_pos[(depth, name)]
            if line == dline and col < dcol:
                self._add_issue(
                    "use_before_declare",
                    name,
                    line,
                    col,
                    f"Identifier '{name}' used before its declaration in the same scope"
                )

        if decl.ctype != "func":
            decl.used = True

        return None

    # -----------------------------
    # Function call validation
    # -----------------------------
    def visitPostfixExpression(self, ctx: SimpleCParser.PostfixExpressionContext):
        # Detect f(...) and validate args
        try:
            prim = ctx.primaryExpression()
        except Exception:
            prim = None

        fname = None
        try:
            if prim is not None and prim.IDENTIFIER() is not None:
                fname = prim.IDENTIFIER().getText()
        except Exception:
            fname = None

        if not fname:
            return self.visitChildren(ctx)

        # find a call postfixPart: '(' argumentList? ')'
        call_parts = []
        try:
            call_parts = list(ctx.postfixPart())
        except Exception:
            call_parts = []

        for p in call_parts:
            txt = p.getText()
            if txt.startswith("(") and txt.endswith(")"):
                sig = self._funcs.get(fname)
                if sig is None:
                    # if it's not a known function, treat as undeclared use of identifier (already handled by visitTerminal)
                    continue

                # count argument expressions
                arg_types: List[Optional[str]] = []
                try:
                    al = p.argumentList()
                except Exception:
                    al = None

                if al is not None:
                    try:
                        # argumentList: assignmentExpression (COMMA assignmentExpression)*
                        for ae in al.assignmentExpression():
                            arg_types.append(self._infer_expr_type(ae))
                    except Exception:
                        pass

                # arity check
                if len(arg_types) != len(sig.param_types):
                    line, col = _tok_line_col(prim.IDENTIFIER())
                    self._add_issue(
                        "call_arity_mismatch",
                        fname,
                        line,
                        col,
                        f"Function '{fname}' expects {len(sig.param_types)} argument(s) but got {len(arg_types)}",
                    )
                else:
                    # type check
                    for i, (got, expected) in enumerate(zip(arg_types, sig.param_types), start=1):
                        if got is None:
                            continue
                        ae_node = None
                        try:
                            ae_node = al.assignmentExpression()[i - 1]
                        except Exception:
                            ae_node = None
                        arg_val = _get_int_constant_value(ae_node)
                        if not self._can_assign(expected, got, rhs_val=arg_val):
                            line, col = _tok_line_col(prim.IDENTIFIER())
                            self._add_issue(
                                "call_type_mismatch",
                                fname,
                                line,
                                col,
                                f"Argument {i} of '{fname}' expects '{expected}' but got '{got}'",
                            )

        return self.visitChildren(ctx)
