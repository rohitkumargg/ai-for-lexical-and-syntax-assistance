"""
Call site and AST entity extractor for SimpleC.
Resolves exact function call expressions and variable declarations,
excluding function prototypes/declarations from being treated as calls.
"""

from dataclasses import dataclass
import logging
import re
from typing import Any, Dict, List, Optional
from collections import OrderedDict

_CALL_CACHE: OrderedDict[str, List[CallSite]] = OrderedDict()
_VAR_CACHE: OrderedDict[str, Dict[str, VarDeclaration]] = OrderedDict()
_PARSE_SYNTAX_STATUS_CACHE: OrderedDict[str, int] = OrderedDict()
_EXTRACT_CACHE_MAX = 256

def clear_extractor_cache():
    _CALL_CACHE.clear()
    _VAR_CACHE.clear()


from antlr4 import InputStream, CommonTokenStream
from generated.SimpleCLexer import SimpleCLexer
from generated.SimpleCParser import SimpleCParser
from generated.SimpleCVisitor import SimpleCVisitor

logger = logging.getLogger("CallExtractor")


@dataclass
class CallSite:
    fn_name: str
    line: int
    col: int
    args: List[str]
    raw_arg_text: str = ""
    node: Any = None
    from_ast: bool = True


@dataclass
class VarDeclaration:
    name: str
    base_type: str
    is_pointer: bool
    is_array: bool
    array_size: Optional[int]
    line: int


class _AstEntityVisitor(SimpleCVisitor):
    def __init__(self):
        super().__init__()
        self.calls: List[CallSite] = []
        self.decls: Dict[str, VarDeclaration] = {}

    def visitDeclarationNoSemi(self, ctx: SimpleCParser.DeclarationNoSemiContext):
        type_spec = getattr(ctx, "typeSpecifier", lambda: None)()
        base_type = type_spec.getText() if type_spec else "int"
        decl_list = getattr(ctx, "initDeclaratorList", lambda: None)()
        if decl_list:
            for init_decl in getattr(decl_list, "initDeclarator", lambda: [])():
                ident = getattr(init_decl, "IDENTIFIER", lambda: None)()
                if ident:
                    name = ident.getText()
                    line = ident.getSymbol().line
                    has_ptr = getattr(init_decl, "pointer", lambda: None)() is not None
                    arr_suffix = getattr(init_decl, "arraySuffix", lambda: None)()
                    is_arr = arr_suffix is not None
                    arr_size = None
                    if is_arr:
                        try:
                            exprs = arr_suffix.expression()
                            if exprs:
                                arr_size = int(exprs[0].getText(), 0)
                        except Exception:
                            arr_size = None
                    self.decls[name] = VarDeclaration(
                        name=name,
                        base_type=base_type,
                        is_pointer=has_ptr,
                        is_array=is_arr,
                        array_size=arr_size,
                        line=line,
                    )
        return self.visitChildren(ctx)

    def visitParam(self, ctx: SimpleCParser.ParamContext):
        type_spec = getattr(ctx, "typeSpecifier", lambda: None)()
        base_type = type_spec.getText() if type_spec else "int"
        ident = getattr(ctx, "IDENTIFIER", lambda: None)()
        if ident:
            name = ident.getText()
            line = ident.getSymbol().line
            has_ptr = getattr(ctx, "pointer", lambda: None)() is not None
            arr_suffix = getattr(ctx, "arraySuffix", lambda: None)()
            is_arr = arr_suffix is not None
            self.decls[name] = VarDeclaration(
                name=name,
                base_type=base_type,
                is_pointer=has_ptr or is_arr,
                is_array=is_arr,
                array_size=None,
                line=line,
            )
        return self.visitChildren(ctx)

    def visitPostfixExpression(self, ctx: SimpleCParser.PostfixExpressionContext):
        primary = getattr(ctx, "primaryExpression", lambda: None)()
        if primary is not None:
            ident = getattr(primary, "IDENTIFIER", lambda: None)()
            if ident is not None:
                fn_name = ident.getText()
                parts = getattr(ctx, "postfixPart", lambda: [])()
                if parts:
                    first_part = parts[0]
                    # Check if first postfixPart is a call '(' argumentList? ')'
                    is_call = False
                    lparen = getattr(first_part, "LPAREN", lambda: None)()
                    if lparen is not None or (first_part.getChildCount() >= 1 and first_part.getChild(0).getText() == "("):
                        is_call = True

                    if is_call:
                        sym = ident.getSymbol()
                        line = sym.line
                        col = sym.column
                        args: List[str] = []
                        raw_arg_text = ""
                        arg_list = getattr(first_part, "argumentList", lambda: None)()
                        if arg_list is not None:
                            raw_arg_text = arg_list.getText()
                            assign_exprs = getattr(arg_list, "assignmentExpression", lambda: [])()
                            for a in assign_exprs:
                                args.append(a.getText().strip())

                        self.calls.append(CallSite(
                            fn_name=fn_name,
                            line=line,
                            col=col,
                            args=args,
                            raw_arg_text=raw_arg_text,
                            node=ctx,
                        ))
                        for p in parts[1:]:
                            self.visit(p)
                        return None
        return self.visitChildren(ctx)


def strip_c_comments_and_strings(code: str) -> str:
    """
    Replaces C comments and string/char literals with spaces while strictly preserving line structure.
    Correctly handles:
    - Line comments: // ... (to end of line)
    - Block comments: /* ... */ (can span lines)
    - String literals: " ... " (with escape sequences like \\", \\\\, \\n)
    - Character literals: ' ... ' (with escape sequences like \\', \\\\)
    - Escaped quotes inside strings: "\\" // not comment gets(buf) \\""
    - Comment delimiters inside strings: "// not comment", "/* not comment */"
    - String quotes inside comments: // don't " quote
    """
    if not code:
        return ""
    out = []
    n = len(code)
    i = 0
    in_line_comment = False
    in_block_comment = False
    in_string = False
    in_char = False

    while i < n:
        c = code[i]
        nxt = code[i + 1] if i + 1 < n else ""

        if in_line_comment:
            if c == "\n":
                out.append("\n")
                in_line_comment = False
            else:
                out.append(" ")
            i += 1
        elif in_block_comment:
            if c == "*" and nxt == "/":
                out.append("  ")
                in_block_comment = False
                i += 2
            elif c == "\n":
                out.append("\n")
                i += 1
            else:
                out.append(" ")
                i += 1
        elif in_string:
            if c == "\\":
                if nxt == "\n":
                    out.append(" \n")
                    i += 2
                else:
                    out.append("  ")
                    i += 2
            elif c == '"':
                out.append(" ")
                in_string = False
                i += 1
            elif c == "\n":
                out.append("\n")
                in_string = False
                i += 1
            else:
                out.append(" ")
                i += 1
        elif in_char:
            if c == "\\":
                if nxt == "\n":
                    out.append(" \n")
                    i += 2
                else:
                    out.append("  ")
                    i += 2
            elif c == "'":
                out.append(" ")
                in_char = False
                i += 1
            elif c == "\n":
                out.append("\n")
                in_char = False
                i += 1
            else:
                out.append(" ")
                i += 1
        else:
            if c == "/" and nxt == "/":
                out.append("  ")
                in_line_comment = True
                i += 2
            elif c == "/" and nxt == "*":
                out.append("  ")
                in_block_comment = True
                i += 2
            elif c == '"':
                out.append(" ")
                in_string = True
                i += 1
            elif c == "'":
                out.append(" ")
                in_char = True
                i += 1
            else:
                out.append(c)
                i += 1

    return "".join(out)


def strip_c_comments_only(code: str) -> str:
    """
    Replaces only C comments with spaces, preserving string literals and line structure.
    """
    if not code:
        return ""
    out = []
    n = len(code)
    i = 0
    in_line_comment = False
    in_block_comment = False
    in_string = False
    in_char = False

    while i < n:
        c = code[i]
        nxt = code[i + 1] if i + 1 < n else ""

        if in_line_comment:
            if c == "\n":
                out.append("\n")
                in_line_comment = False
            else:
                out.append(" ")
            i += 1
        elif in_block_comment:
            if c == "*" and nxt == "/":
                out.append("  ")
                in_block_comment = False
                i += 2
            elif c == "\n":
                out.append("\n")
                i += 1
            else:
                out.append(" ")
                i += 1
        elif in_string:
            out.append(c)
            if c == "\\":
                if nxt:
                    out.append(nxt)
                    i += 2
                else:
                    i += 1
            elif c == '"':
                in_string = False
                i += 1
            else:
                i += 1
        elif in_char:
            out.append(c)
            if c == "\\":
                if nxt:
                    out.append(nxt)
                    i += 2
                else:
                    i += 1
            elif c == "'":
                in_char = False
                i += 1
            else:
                i += 1
        else:
            if c == "/" and nxt == "/":
                out.append("  ")
                in_line_comment = True
                i += 2
            elif c == "/" and nxt == "*":
                out.append("  ")
                in_block_comment = True
                i += 2
            elif c == '"':
                out.append(c)
                in_string = True
                i += 1
            elif c == "'":
                out.append(c)
                in_char = True
                i += 1
            else:
                out.append(c)
                i += 1

    return "".join(out)


def extract_call_sites(source_text: str) -> List[CallSite]:
    """
    Extracts all call sites from source_text.
    First tries ANTLR parse tree. If that fails (e.g. snippet), falls back to regex-based extraction
    that ignores declarations.
    """
    if source_text in _CALL_CACHE:
        _CALL_CACHE.move_to_end(source_text)
        return list(_CALL_CACHE[source_text])
    known_err_cnt = _PARSE_SYNTAX_STATUS_CACHE.get(source_text)
    if known_err_cnt is not None and known_err_cnt > 0:
        err_cnt = known_err_cnt
    elif "===" in source_text or re.search(r'\[[^\]\n]*;', source_text) or re.search(r'[@$`]', source_text):
        err_cnt = 1
        _PARSE_SYNTAX_STATUS_CACHE[source_text] = 1
    else:
        err_cnt = 0
        try:
            input_stream = InputStream(source_text)
            lexer = SimpleCLexer(input_stream)
            lexer.removeErrorListeners()
            token_stream = CommonTokenStream(lexer)
            parser = SimpleCParser(token_stream)
            parser.removeErrorListeners()
            tree = parser.program()
            err_cnt = parser.getNumberOfSyntaxErrors()
            if len(_PARSE_SYNTAX_STATUS_CACHE) >= _EXTRACT_CACHE_MAX:
                _PARSE_SYNTAX_STATUS_CACHE.popitem(last=False)
            _PARSE_SYNTAX_STATUS_CACHE[source_text] = err_cnt
            if err_cnt == 0:
                visitor = _AstEntityVisitor()
                visitor.visit(tree)
                res = visitor.calls
                if len(_CALL_CACHE) >= _EXTRACT_CACHE_MAX:
                    _CALL_CACHE.popitem(last=False)
                _CALL_CACHE[source_text] = res
                return list(res)
        except Exception as e:
            logger.warning(f"AST call extraction raised exception: {e}; falling back to regex mode.")

    logger.debug(f"AST parsing had {err_cnt} syntax errors; falling back to regex call extraction mode.")
    # Regex fallback for snippets
    calls: List[CallSite] = []
    clean_text = strip_c_comments_and_strings(source_text)
    lines = clean_text.splitlines()
    decl_pattern = re.compile(
        r"^\s*(?:(?:extern|static|inline|const|unsigned|signed|struct\s+\w+)\s+)*(?:void|int|char|short|long|float|double|size_t|\w+_t)\s*(?:\*+\s*)?([A-Za-z_]\w*)\s*\([^)]*\)\s*;"
    )

    call_pattern = re.compile(r"\b([A-Za-z_]\w*)\s*\((.*?)\)", re.DOTALL)

    for line_idx, line_str in enumerate(lines, start=1):
        if decl_pattern.match(line_str):
            continue

        for m in call_pattern.finditer(line_str):
            fn_name = m.group(1)
            prefix = line_str[:m.start()].strip()
            if re.search(r"\b(?:void|int|char|short|long|float|double|size_t)\s*\*?$", prefix):
                continue
            if fn_name in {"if", "while", "for", "switch", "return", "sizeof"}:
                continue

            raw_args = m.group(2).strip()
            args = [a.strip() for a in raw_args.split(",") if a.strip()] if raw_args else []
            calls.append(CallSite(
                fn_name=fn_name,
                line=line_idx,
                col=m.start(1),
                args=args,
                raw_arg_text=raw_args,
                from_ast=False,
            ))

    if len(_CALL_CACHE) >= _EXTRACT_CACHE_MAX:
        _CALL_CACHE.popitem(last=False)
    _CALL_CACHE[source_text] = calls
    return list(calls)


def extract_var_declarations(source_text: str) -> Dict[str, VarDeclaration]:
    """
    Extracts all declared local and global variables from source_text.
    """
    if source_text in _VAR_CACHE:
        _VAR_CACHE.move_to_end(source_text)
        return dict(_VAR_CACHE[source_text])
    known_err_cnt = _PARSE_SYNTAX_STATUS_CACHE.get(source_text)
    if known_err_cnt is not None and known_err_cnt > 0:
        err_cnt = known_err_cnt
    elif "===" in source_text or re.search(r'\[[^\]\n]*;', source_text) or re.search(r'[@$`]', source_text):
        err_cnt = 1
        _PARSE_SYNTAX_STATUS_CACHE[source_text] = 1
    else:
        err_cnt = 0
        try:
            input_stream = InputStream(source_text)
            lexer = SimpleCLexer(input_stream)
            lexer.removeErrorListeners()
            token_stream = CommonTokenStream(lexer)
            parser = SimpleCParser(token_stream)
            parser.removeErrorListeners()
            tree = parser.program()
            err_cnt = parser.getNumberOfSyntaxErrors()
            if len(_PARSE_SYNTAX_STATUS_CACHE) >= _EXTRACT_CACHE_MAX:
                _PARSE_SYNTAX_STATUS_CACHE.popitem(last=False)
            _PARSE_SYNTAX_STATUS_CACHE[source_text] = err_cnt
            if err_cnt == 0:
                visitor = _AstEntityVisitor()
                visitor.visit(tree)
                res_decls = visitor.decls
                if len(_VAR_CACHE) >= _EXTRACT_CACHE_MAX:
                    _VAR_CACHE.popitem(last=False)
                _VAR_CACHE[source_text] = res_decls
                return dict(res_decls)
        except Exception as e:
            logger.warning(f"AST variable extraction raised exception: {e}; falling back to regex mode.")

    logger.debug(f"AST parsing had {err_cnt} syntax errors; falling back to regex variable declaration extraction mode.")
    # Regex fallback
    decls: Dict[str, VarDeclaration] = {}
    decl_re = re.compile(
        r"(?<!\w)\b(char|int|short|long|float|double)\b(?!\s*\))\s+(\*+)?\s*([A-Za-z_]\w*)(?!\s*\()\s*(?:\[\s*(\d*)\s*\])?"
    )
    clean_text = strip_c_comments_only(source_text)
    lines = clean_text.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        # In C declarations, variable declarations only appear before '='
        decl_part = line.split("=")[0] if "=" in line else line
        for m in decl_re.finditer(decl_part):
            btype = m.group(1)
            is_ptr = bool(m.group(2))
            vname = m.group(3)
            is_arr = m.group(4) is not None
            arr_sz = int(m.group(4)) if m.group(4) else None
            decls[vname] = VarDeclaration(
                name=vname,
                base_type=btype,
                is_pointer=is_ptr,
                is_array=is_arr,
                array_size=arr_sz,
                line=line_idx,
            )
    if len(_VAR_CACHE) >= _EXTRACT_CACHE_MAX:
        _VAR_CACHE.popitem(last=False)
    _VAR_CACHE[source_text] = decls
    return dict(decls)


def get_extraction_mode(source_text: str) -> str:
    """
    Determines whether source_text is parsed via AST or takes regex fallback mode.
    Parseable code with zero syntax errors returns 'AST'; otherwise returns 'REGEX_FALLBACK'.
    """
    try:
        input_stream = InputStream(source_text)
        lexer = SimpleCLexer(input_stream)
        lexer.removeErrorListeners()
        token_stream = CommonTokenStream(lexer)
        parser = SimpleCParser(token_stream)
        parser.removeErrorListeners()
        parser.program()
        if parser.getNumberOfSyntaxErrors() == 0:
            return "AST"
    except Exception:
        pass
    return "REGEX_FALLBACK"
