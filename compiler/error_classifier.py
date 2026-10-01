from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ErrorClassification:
    fixable: bool
    category: str
    reason: str


def classify_error_message(msg: str) -> ErrorClassification:
    lower = (msg or "").lower().strip()

    # missing rhs
    if (
        "mismatched input ';' expecting" in lower
        and (
            "identifier" in lower
            or "integer" in lower
            or "float_literal" in lower
            or "char_literal" in lower
            or "string_literal" in lower
        )
    ):
        return ErrorClassification(True, "MISSING_OPERAND", "missing_rhs")

    _TYPE_KW = r"(?:int|float|char|void|double|short|long|unsigned|signed)"

    # (e) Invalid type combination (detect-only, whole tokens)
    _INVALID_TYPE_COMBOS = (
        "longshort", "shortlong", "unsignedfloat", "signedfloat",
        "unsigneddouble", "signeddouble", "floatdouble", "doublefloat",
        "voidint", "intvoid", "voidfloat", "voidchar", "voiddouble",
        "charfloat", "floatchar", "shortfloat", "longfloat",
        "shortdouble", "chardouble", "doublechar", "floatint", "intfloat"
    )
    if "no viable alternative at input" in lower:
        pattern = r"no viable alternative at input\s+'(?:.*?[^a-z0-9_])?(" + "|".join(_INVALID_TYPE_COMBOS) + r")(?:[^a-z0-9_]|$)"
        if re.search(pattern, lower):
            return ErrorClassification(False, "TYPE_ERROR", "invalid_type_combination")

    # (a) Missing semicolon after prototype (whole tokens)
    if "mismatched input ')' expecting ';'" in lower:
        return ErrorClassification(True, "MISSING_TOKEN", "missing_semicolon_after_prototype")
    if re.search(r"no viable alternative at input\s+'" + _TYPE_KW + r"[a-z0-9_]+\([^)]*\)" + _TYPE_KW, lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_semicolon_after_prototype")

    # (c) Missing ')' in prototype/definition parameter list
    if re.search(r"no viable alternative at input\s+'" + _TYPE_KW + r"[a-z0-9_]+\([^)]*[;{]'", lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_rparen_params")

    # (b) Missing comma between parameters
    if re.search(r"no viable alternative at input\s+'" + _TYPE_KW + r"[a-z0-9_]+\(.*?" + _TYPE_KW + r"[a-z0-9_]+" + _TYPE_KW, lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_comma_params")
    if re.search(r"mismatched\s+input\s+'" + _TYPE_KW + r"'\s+expecting\s+'\)'", lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_comma_params")

    # (d) Missing semicolon after global declaration
    if re.search(r"missing\s+';'\s+at\s+'" + _TYPE_KW + r"'", lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_semicolon_after_global")
    if "(" not in lower and re.search(r"no viable alternative at input\s+'" + _TYPE_KW + r"[a-z0-9_]+" + _TYPE_KW + r"['\b]", lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_semicolon_after_global")

    # Week 6 parser diagnostics. ANTLR's context text lets the repair UI
    # distinguish these from generic missing-token reports.
    if "do" in lower and ("expecting ';'" in lower or "missing ';'" in lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_semicolon_after_do_while")
    if ("sizeof" in lower or "cast" in lower) and ("expecting ')'" in lower or "missing ')'" in lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_rparen_cast_or_sizeof")
    if "no viable alternative" in lower and re.search(r"sizeof\([^)]*[;]", lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_rparen_cast_or_sizeof")
    if "'*'" in lower and ("extraneous input" in lower or "mismatched input" in lower):
        return ErrorClassification(False, "POINTER_ERROR", "pointer_star_misuse")

    # token families
    if re.search(r"missing\s+';'", lower) or re.search(r"expecting\s+';'", lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_semicolon")

    if re.search(r"missing\s+'\}'", lower) or re.search(r"expecting\s+'\}'", lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_rbrace")

    if re.search(r"missing\s+'\{'", lower) or re.search(r"expecting\s+'\{'", lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_lbrace")

    if re.search(r"missing\s+'\)'", lower) or re.search(r"expecting\s+'\)'", lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_rparen")

    if re.search(r"missing\s+'\('", lower) or re.search(r"expecting\s+'\('", lower):
        return ErrorClassification(True, "MISSING_TOKEN", "missing_lparen")

    if "expecting '('" in lower and "main" in lower:
        return ErrorClassification(True, "MISSING_TOKEN", "main_lparen_expected")

    # comma heuristics from parser phrasing
    if "extraneous input" in lower and "expecting ')'" in lower:
        return ErrorClassification(True, "MISSING_TOKEN", "missing_comma_args")

    # generic extra token
    if "extraneous input" in lower:
        return ErrorClassification(True, "EXTRA_TOKEN", "extraneous_token")

    # lexer
    if "token recognition error" in lower:
        return ErrorClassification(True, "ILLEGAL_TOKEN", "illegal_token")

    # structural
    if "no viable alternative" in lower:
        return ErrorClassification(True, "STRUCTURAL_ERROR", "no_viable_alternative")

    if "mismatched input" in lower:
        return ErrorClassification(True, "MISMATCHED_TOKEN", "mismatched_token")

    if "input mismatch" in lower:
        return ErrorClassification(True, "MISMATCHED_TOKEN", "mismatched_token")

    if "failed predicate" in lower:
        return ErrorClassification(False, "PREDICATE_ERROR", "failed_predicate")

    if "unexpected token" in lower:
        return ErrorClassification(True, "STRUCTURAL_ERROR", "unexpected_token")

    return ErrorClassification(False, "STRUCTURAL_ERROR", "unknown")
