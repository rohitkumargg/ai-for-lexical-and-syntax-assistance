from typing import Dict, Any

from generated.SimpleCVisitor import SimpleCVisitor
from generated.SimpleCParser import SimpleCParser


BUILTIN_FUNCTIONS = {
    "printf": {"kind": "func", "type": "int", "line": 0, "builtin": True},
    "scanf": {"kind": "func", "type": "int", "line": 0, "builtin": True},
    "snprintf": {"kind": "func", "type": "int", "line": 0, "builtin": True},
    "vsnprintf": {"kind": "func", "type": "int", "line": 0, "builtin": True},
    "fgets": {"kind": "func", "type": "char*", "line": 0, "builtin": True},
    "strlen": {"kind": "func", "type": "int", "line": 0, "builtin": True},
    "memcpy": {"kind": "func", "type": "void*", "line": 0, "builtin": True},
    "memmove": {"kind": "func", "type": "void*", "line": 0, "builtin": True},
    "memset": {"kind": "func", "type": "void*", "line": 0, "builtin": True},
    "malloc": {"kind": "func", "type": "void*", "line": 0, "builtin": True},
    "calloc": {"kind": "func", "type": "void*", "line": 0, "builtin": True},
    "free": {"kind": "func", "type": "void", "line": 0, "builtin": True},
    "strncpy": {"kind": "func", "type": "char*", "line": 0, "builtin": True},
    "strncat": {"kind": "func", "type": "char*", "line": 0, "builtin": True},
}


class SymbolTableBuilder(SimpleCVisitor):
    """
    Builds a simple flat symbol table:
      name -> {"kind": "var"|"param"|"func", "type": <type>, "line": <line>, ...}

    Flat table is fine for:
    - deterministic typo correction
    - undeclared identifier checks
    - simple semantic support

    We also preload a few builtin/library functions so they are not treated
    as undeclared identifiers.
    """

    def __init__(self):
        super().__init__()
        self.symbols: Dict[str, Dict[str, Any]] = {}

        # Preload builtins
        for name, info in BUILTIN_FUNCTIONS.items():
            self.symbols[name] = dict(info)

    def _type_text(self, type_ctx) -> str:
        return type_ctx.getText() if type_ctx else "?"

    def _add_symbol(self, name: str, kind: str, typ: str, line: int, builtin: bool = False):
        if not name:
            return

        # Do not overwrite an existing symbol.
        # This preserves first declaration behavior and keeps builtins stable.
        if name not in self.symbols:
            entry = {
                "kind": kind,
                "type": typ,
                "line": line,
            }
            if builtin:
                entry["builtin"] = True
            self.symbols[name] = entry

    # -------------------------
    # Top-level items & Functions / Prototypes
    # -------------------------
    def visitTopLevelItem(self, ctx: SimpleCParser.TopLevelItemContext):
        return self.visitChildren(ctx)

    def visitFunctionDeclaration(self, ctx: SimpleCParser.FunctionDeclarationContext):
        ret_type = self._type_text(ctx.typeSpecifier())
        fn_ident = ctx.IDENTIFIER()
        if fn_ident is not None:
            name = fn_ident.getText()
            line = fn_ident.symbol.line if hasattr(fn_ident, "symbol") else -1
            self._add_symbol(name, "func", ret_type, line)
        return self.visitChildren(ctx)

    def visitFunctionDef(self, ctx: SimpleCParser.FunctionDefContext):
        ret_type = self._type_text(ctx.typeSpecifier())

        fn_ident = ctx.IDENTIFIER()
        if fn_ident is not None:
            name = fn_ident.getText()
            line = fn_ident.symbol.line if hasattr(fn_ident, "symbol") else -1
            self._add_symbol(name, "func", ret_type, line)

        return self.visitChildren(ctx)

    def visitParam(self, ctx: SimpleCParser.ParamContext):
        typ = self._type_text(ctx.typeSpecifier())
        ident = ctx.IDENTIFIER()
        if ident is not None:
            name = ident.getText()
            line = ident.symbol.line if hasattr(ident, "symbol") else -1
            self._add_symbol(name, "param", typ, line)

        return self.visitChildren(ctx)

    # -------------------------
    # Declarations (normal)
    # -------------------------
    def visitDeclaration(self, ctx: SimpleCParser.DeclarationContext):
        """
        declaration : declarationNoSemi SEMI
        or older direct form if grammar/generated code differs.

        We handle both conservatively.
        """
        type_ctx = getattr(ctx, "typeSpecifier", None)
        list_ctx = getattr(ctx, "initDeclaratorList", None)

        # Older/direct shape
        if callable(type_ctx) and callable(list_ctx):
            typ = self._type_text(ctx.typeSpecifier())
            lst = ctx.initDeclaratorList()
            if lst is None:
                return self.visitChildren(ctx)

            for init_ctx in lst.initDeclarator():
                ident = init_ctx.IDENTIFIER()
                if ident is None:
                    continue
                name = ident.getText()
                line = ident.symbol.line if hasattr(ident, "symbol") else -1
                self._add_symbol(name, "var", typ, line)

            return self.visitChildren(ctx)

        # Current wrapped shape
        dn = None
        try:
            dn = ctx.declarationNoSemi()
        except Exception:
            dn = None

        if dn is not None:
            return self.visit(dn)

        return self.visitChildren(ctx)

    def visitDeclarationNoSemi(self, ctx: SimpleCParser.DeclarationNoSemiContext):
        """
        declarationNoSemi : typeSpecifier initDeclaratorList ;
        Used inside normal declarations and forInit.
        """
        typ = self._type_text(ctx.typeSpecifier())
        lst = ctx.initDeclaratorList()
        if lst is None:
            return self.visitChildren(ctx)

        for init_ctx in lst.initDeclarator():
            ident = init_ctx.IDENTIFIER()
            if ident is None:
                continue
            name = ident.getText()
            line = ident.symbol.line if hasattr(ident, "symbol") else -1
            self._add_symbol(name, "var", typ, line)

        return self.visitChildren(ctx)

    def get_symbols(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.symbols)