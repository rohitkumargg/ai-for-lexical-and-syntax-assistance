import sys
import re
import argparse
import uuid
from typing import List, Dict, Optional

from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener
from antlr4.tree.Tree import TerminalNodeImpl

from compiler.error_classifier import classify_error_message
from compiler.error_corrector import apply_correction
from compiler.lexical_corrector import fix_common_lexical_issues
try:
    from compiler.ai_error_corrector import ai_correct_source_patch_mode
    from compiler.ai_error_corrector import ai_generate_patch_candidates
except (ImportError, Exception):
    def ai_correct_source_patch_mode(*args, **kwargs):
        return None, None
    def ai_generate_patch_candidates(*args, **kwargs):
        return []
from compiler.identifier_corrector import fix_identifier_typo_at
from compiler.semantic_checker import SemanticChecker
from compiler.semantic_auto_fixer import fix_semantic_issue
from compiler.unused_var_fixer import remove_unused_decl_at
from compiler.repair_logger import RepairLogger
from compiler.week5_repair_helpers import (
    check_parser_status,
    try_week5_rules,
    fix_split_operators,
    fix_keyword_typos_fuzzy,
)
from compiler.symbol_table_builder import SymbolTableBuilder
from compiler.security_engine import SecurityEngine
from compiler.security_auto_fixer import SecurityAutoFixer
from compiler.green_metrics import GreenMetrics
from compiler.green_scorer import build_green_report
from compiler.green_logger import GreenLogger

try:
    from generated.SimpleCLexer import SimpleCLexer
    from generated.SimpleCParser import SimpleCParser
except ImportError:
    print("ERROR: generated SimpleCLexer/SimpleCParser not found!")
    print("Generate them from grammar using ANTLR first.")
    sys.exit(1)


DETERMINISTIC_REASONS = {
    "missing_semicolon",
    "missing_rbrace",
    "missing_lbrace",
    "missing_lparen",
    "missing_rparen",
    "main_lparen_expected",
    "mismatched_token",
    "missing_rhs",
    "missing_semicolon_after_prototype",
    "missing_comma_params",
    "missing_rparen_params",
    "missing_semicolon_after_global",
    "missing_semicolon_after_do_while",
    "missing_rparen_cast_or_sizeof",
}


class CollectingErrorListener(ErrorListener):
    """
    Collect errors from BOTH lexer and parser.

    ANTLR calls syntaxError for lexer problems too (token recognition error, etc.)
    We tag them by stage so the pipeline can decide what to do.
    """

    def __init__(self, stage: str):
        super().__init__()
        self.stage = stage  # "LEX" or "PARSE"
        self.errors: List[Dict] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        off_text = None
        try:
            if offendingSymbol is not None and hasattr(offendingSymbol, "text"):
                off_text = offendingSymbol.text
        except Exception:
            off_text = None

        self.errors.append(
            {
                "stage": self.stage,
                "line": line,
                "column": column,
                "msg": msg,
                "offending": off_text,
            }
        )

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def get_errors(self) -> List[str]:
        out = []
        for e in self.errors:
            stage = e.get("stage", "?")
            off = e.get("offending")
            off_part = f" (offending: {off})" if off else ""
            out.append(f"Line {e['line']}:{e['column']} - {stage} Error: {e['msg']}{off_part}")
        return out

    def get_error_objects(self) -> List[Dict]:
        return list(self.errors)


def parse_source(source_text: str, source_name: str = "<input>"):
    print(f"\n{'=' * 70}")
    print(f"Parsing: {source_name}")
    print("=" * 70)

    input_stream = InputStream(source_text)

    lexer = SimpleCLexer(input_stream)
    lexer.removeErrorListeners()
    lex_listener = CollectingErrorListener(stage="LEX")
    lexer.addErrorListener(lex_listener)

    token_stream = CommonTokenStream(lexer)

    parser = SimpleCParser(token_stream)
    parser.removeErrorListeners()
    parse_listener = CollectingErrorListener(stage="PARSE")
    parser.addErrorListener(parse_listener)

    tree = parser.program()

    combined = {"lex": lex_listener, "parse": parse_listener}
    return tree, combined, parser


def parse_file(filename: str):
    try:
        with open(filename, "r", encoding="utf-8") as handle:
            source_text = handle.read()

        # Normalize common invisible leading characters that can poison parsing
        if source_text.startswith("\ufeff"):
            source_text = source_text.lstrip("\ufeff")

        tree, listeners, parser = parse_source(source_text, filename)
        return tree, listeners, parser, source_text

    except FileNotFoundError:
        print(f"ERROR: File '{filename}' not found!")
        return None, None, None, None
    except Exception as e:
        print(f"ERROR: Unexpected error occurred: {e}")
        return None, None, None, None


def has_any_errors(listeners: Dict[str, CollectingErrorListener]) -> bool:
    return listeners["lex"].has_errors() or listeners["parse"].has_errors()


def get_all_error_strings(listeners: Dict[str, CollectingErrorListener]) -> List[str]:
    return listeners["lex"].get_errors() + listeners["parse"].get_errors()


def get_first_error_object(listeners: Dict[str, CollectingErrorListener]) -> Optional[Dict]:
    """
    Prefer lexer errors first.
    But aggressively skip bogus parser start-of-file errors at line 1, col 0
    whenever any later real parse error exists.
    """
    if listeners["lex"].has_errors():
        lex_errs = listeners["lex"].get_error_objects()

        for e in lex_errs:
            line = e.get("line")
            col = e.get("column")
            msg = (e.get("msg") or "").lower()
            off = e.get("offending")

            bogus = (
                line == 1
                and col == 0
                and (
                    off is None
                    or str(off) == ""
                    or str(off).strip() == ""
                    or str(off) in {"\ufeff", "\x00"}
                )
                and (
                    "token recognition error" in msg
                    or "extraneous input" in msg
                    or "mismatched input" in msg
                )
            )

            if not bogus:
                return e

        return lex_errs[0]

    if not listeners["parse"].has_errors():
        return None

    errs = listeners["parse"].get_error_objects()

    def is_bogus_start_error(e: Dict) -> bool:
        msg = (e.get("msg") or "").lower()
        line = e.get("line")
        col = e.get("column")
        off = e.get("offending")

        off_str = "" if off is None else str(off)

        return (
            line == 1
            and col == 0
            and (
                off is None
                or off_str == ""
                or off_str.strip() == ""
                or off_str in {"\ufeff", "\x00"}
            )
            and (
                "extraneous input" in msg
                or "mismatched input" in msg
                or "no viable alternative" in msg
            )
        )

    for e in errs:
        if not is_bogus_start_error(e):
            return e

    return errs[0]


def print_parse_tree(node, parser, indent: int = 0):
    pad = "  " * indent

    if isinstance(node, TerminalNodeImpl):
        text = node.getText()
        print(pad + f"└─ {text}")
        return

    child_count = node.getChildCount() if hasattr(node, "getChildCount") else 0
    if child_count == 0:
        text = node.getText() if hasattr(node, "getText") else str(node)
        print(pad + f"└─ {text}")
        return

    rule_name = "unknown"
    try:
        if hasattr(node, "getRuleIndex"):
            idx = node.getRuleIndex()
            if 0 <= idx < len(parser.ruleNames):
                rule_name = parser.ruleNames[idx]
    except Exception:
        rule_name = "unknown"

    print(pad + f"[{rule_name}]")
    for i in range(child_count):
        print_parse_tree(node.getChild(i), parser, indent + 1)


def build_symbols(tree):
    builder = SymbolTableBuilder()
    builder.visit(tree)
    return builder.get_symbols()


def print_analysis(tree):
    print("\nIR Analysis: Variable Declaration Check")
    print("-" * 70)

    symbols = build_symbols(tree)

    print("Symbol Table:")
    if symbols:
        for n, info in symbols.items():
            print(f"  {n}: {info}")
    else:
        print("  <empty>")

    print("\nAnalysis Errors: None")
    return symbols


def _print_semantic_issues(issues):
    """
    issues: list[dict] returned by SemanticChecker.get_issues()

    kinds:
      - undeclared
      - redeclared
      - use_before_declare
      - unused
    """
    if not issues:
        print("No semantic issues.")
        return

    order = ["undeclared", "redeclared", "use_before_declare", "unused"]
    buckets = {k: [] for k in order}
    other = []

    for it in issues:
        k = it.get("kind", "unknown")
        if k in buckets:
            buckets[k].append(it)
        else:
            other.append(it)

    def fmt(it):
        line = it.get("line", "?")
        col = it.get("col", "?")
        name = it.get("name", "")
        msg = it.get("msg", "")
        if name:
            return f"L{line}:{col}  {name}  -> {msg}"
        return f"L{line}:{col}  -> {msg}"

    total = 0
    for k in order:
        arr = buckets[k]
        if not arr:
            continue
        total += len(arr)
        title = {
            "undeclared": "UNDECLARED IDENTIFIERS",
            "redeclared": "REDECLARATIONS",
            "use_before_declare": "USE-BEFORE-DECLARE",
            "unused": "UNUSED VARIABLES",
        }.get(k, k.upper())

        print(f"{title} ({len(arr)}):")
        for it in arr:
            print("  - " + fmt(it))
        print()

    if other:
        total += len(other)
        print(f"OTHER ({len(other)}):")
        for it in other:
            print("  - " + fmt(it))
        print()

    print(f"Total semantic issues: {total}")


def run_security_checks(source_text: str):
    """
    Returns:
        ok: bool
        final_source: str
        auto_steps: List[str]
    """
    engine = SecurityEngine()
    auto_fixer = SecurityAutoFixer()

    issues, blocked, categorized = engine.analyze(source_text)

    if not issues:
        print("\nSECURITY ANALYSIS")
        print("------------------------------------------------")
        print("No security issues detected.")
        return True, source_text, []

    engine.print_summary(categorized)

    # Try safe auto-fixes even for blocked cases first.
    # If the fixer changes the source, allow the pipeline to continue
    # with the repaired version. If nothing safe can be done, keep blocked.
    fix_result = auto_fixer.apply_fixes(source_text)

    if fix_result.source != source_text:
        if blocked:
            print("\nAUTO SECURITY FIX APPLIED (CRITICAL)")
        else:
            print("\nAUTO SECURITY FIX APPLIED")

        print("-" * 50)
        for step in fix_result.applied_steps:
            print(step)
        print("-" * 50)
        print(fix_result.source.rstrip())
        print("-" * 50)
        return True, fix_result.source, fix_result.applied_steps

    if blocked:
        print("FINAL RESULT: BLOCKED BY SECURITY POLICY")
        print("Dangerous or exploitable code detected.")
        return False, source_text, []

    print("Security result: warnings present but allowed.")
    return True, source_text, []


def _used_ai(applied_steps: List[str]) -> bool:
    return any(
        step.startswith("AI:") or step.startswith("AISEC:")
        for step in applied_steps
    )


def _print_ai_repair_debug(working: str, tree, parser):
    print("\nRepaired Source After AI:")
    print("-" * 70)
    print(working.rstrip())
    print("-" * 70)

    print("Parse Tree After AI Repair:")
    print("-" * 70)
    print_parse_tree(tree, parser)

    print("\nS-Expression After AI Repair:")
    print(tree.toStringTree(recog=parser))
    print("-" * 70)


def _select_best_ai_candidate_by_reparse(
    filename: str,
    current_source: str,
    candidates,
):
    """
    candidates: list of (new_source, cmd_text, heuristic_score)

    Selection priority:
      1. candidate that fully parses
      2. candidate with fewer remaining errors
      3. higher heuristic score
      4. smaller edit delta

    Returns:
      (best_source, best_cmd, best_tree, best_listeners, best_parser)
      or
      (current_source, None, None, None, None) if no usable candidate
    """
    if not candidates:
        return current_source, None, None, None, None

    best = None
    best_key = None

    print("\nAI candidate reparsing:")
    print("-" * 70)

    for idx, (cand_src, cmd, heuristic_score) in enumerate(candidates, 1):
        # Guardrail: do not let AI remove pointer syntax from the source
        if "*" in current_source and "*" not in cand_src:
            print(f"[{idx}] {cmd} -> rejected (removed pointer syntax)")
            continue

        tree_c, listeners_c, parser_c = parse_source(cand_src, f"{filename} (ai-candidate-{idx})")

        if tree_c is None:
            print(f"[{idx}] {cmd} -> rejected (tree is None)")
            continue

        err_count = len(get_all_error_strings(listeners_c))
        success = not has_any_errors(listeners_c)
        delta = abs(len(cand_src) - len(current_source))

        key = (
            1 if success else 0,
            -err_count,
            heuristic_score,
            -delta,
        )

        status = "SUCCESS" if success else f"errors={err_count}"
        print(f"[{idx}] {cmd} -> {status}, heuristic={heuristic_score}, delta={delta}")

        if best is None or key > best_key:
            best = (cand_src, cmd, tree_c, listeners_c, parser_c)
            best_key = key

    print("-" * 70)

    if best is None:
        return current_source, None, None, None, None

    return best


def _finalize_semantic_with_security(
    working: str,
    tree,
    parser,
    issues,
    applied_steps: List[str],
    logger: RepairLogger,
    note: str,
) -> bool:
    if _used_ai(applied_steps):
        _print_ai_repair_debug(working, tree, parser)

    print("\nPARSING SUCCESSFUL (but semantic issues remain)")
    print("-" * 70)
    _print_semantic_issues(issues)
    print("-" * 70)

    logger.end_case(
        status="SEM_ISSUES",
        final_source=working,
        applied_steps=applied_steps,
        note=note,
    )
    return True


def _run_semantic_phase(
    filename: str,
    working: str,
    tree,
    listeners,
    parser,
    applied_steps: List[str],
    logger: RepairLogger,
) -> bool:
    """
    Unified iterative semantic + security phase.

    Returns True if the function fully handled output/finalization.
    """
    MAX_SEM_EDITS = 5
    MAX_SECURITY_ROUNDS = 3

    sem_edits = 0
    security_rounds = 0

    while True:
        # -----------------------------------------------------
        # A) Semantic repair loop on the CURRENT parsed tree
        # -----------------------------------------------------
        failed_issue_keys = set()
        while sem_edits < MAX_SEM_EDITS:
            checker = SemanticChecker()
            checker.visit(tree)
            issues = checker.get_issues()

            if issues:
                logger.log_semantic_issues(issues)

            if not issues:
                break

            first = None
            for candidate_issue in issues:
                cid = (
                    candidate_issue.get("kind"),
                    candidate_issue.get("line"),
                    candidate_issue.get("col"),
                    candidate_issue.get("msg"),
                )
                if cid not in failed_issue_keys:
                    first = candidate_issue
                    break
            if first is None:
                break

            cid = (
                first.get("kind"),
                first.get("line"),
                first.get("col"),
                first.get("msg"),
            )
            kind = first.get("kind")

            # 1) Auto-fix UNUSED
            if kind == "unused":
                name = first.get("name")
                line = first.get("line")
                col = first.get("col")

                corrected = None
                msg = None

                try:
                    corrected, msg = remove_unused_decl_at(working, line, col, name)
                except TypeError:
                    try:
                        corrected, msg = remove_unused_decl_at(working, line, col)
                    except TypeError:
                        try:
                            corrected, msg = remove_unused_decl_at(working, line, name)
                        except Exception:
                            corrected, msg = None, None
                except Exception:
                    corrected, msg = None, None

                if msg is None or corrected is None or corrected == working:
                    failed_issue_keys.add(cid)
                    continue

                working = corrected
                failed_issue_keys.clear()
                applied_steps.append(f"SEM: {msg}")
                logger.log_sem_step(step=msg, source_after=working)
                sem_edits += 1

                tree2, listeners2, parser2 = parse_source(working, f"{filename} (unused-removed)")
                if tree2 is None:
                    logger.end_case(
                        status="STOPPED",
                        final_source=working,
                        applied_steps=applied_steps,
                        note="tree None after unused fix",
                    )
                    return True

                if has_any_errors(listeners2):
                    print("\nStopping: unused-var fix broke parsing; refusing further edits.")
                    logger.log_parse_errors(stage="LEX/PARSE", errors=get_all_error_strings(listeners2))
                    logger.end_case(
                        status="STOPPED",
                        final_source=working,
                        applied_steps=applied_steps,
                        note="unused fix broke parsing",
                    )
                    return True

                tree, listeners, parser = tree2, listeners2, parser2
                continue

            # 2) Auto-fix UNDECLARED via identifier typo correction
            if kind == "undeclared":
                name = first["name"]
                line = first["line"]
                col = first["col"]

                symbols = build_symbols(tree)

                corrected, msg = fix_identifier_typo_at(
                    working,
                    line,
                    col,
                    symbols,
                    max_dist=2,
                    expected_name=name,
                )

                if msg is None or corrected == working:
                    try:
                        line_text = working.splitlines()[line - 1]
                        idx = line_text.find(name)
                        if idx != -1:
                            corrected, msg = fix_identifier_typo_at(
                                working,
                                line,
                                idx,
                                symbols,
                                max_dist=2,
                                expected_name=name,
                            )
                    except Exception:
                        pass

                if msg is None or corrected == working:
                    failed_issue_keys.add(cid)
                    continue

                working = corrected
                failed_issue_keys.clear()
                applied_steps.append(f"SYM: {msg}")
                logger.log_sem_step(step=msg, source_after=working)
                sem_edits += 1

                tree2, listeners2, parser2 = parse_source(working, f"{filename} (sym-fixed)")
                if tree2 is None:
                    logger.end_case(
                        status="STOPPED",
                        final_source=working,
                        applied_steps=applied_steps,
                        note="tree None after sym fix",
                    )
                    return True

                if has_any_errors(listeners2):
                    print("\nStopping: semantic fix broke parsing; refusing further edits.")
                    logger.log_parse_errors(stage="LEX/PARSE", errors=get_all_error_strings(listeners2))
                    logger.end_case(
                        status="STOPPED",
                        final_source=working,
                        applied_steps=applied_steps,
                        note="semantic fix broke parsing",
                    )
                    return True

                tree, listeners, parser = tree2, listeners2, parser2
                continue

            # 3) General semantic issues (type mismatch, invalid operand, prototype, shadow, etc.)
            corrected, msg = fix_semantic_issue(working, first)
            if msg is None or corrected == working:
                failed_issue_keys.add(cid)
                continue

            tree2, listeners2, parser2 = parse_source(working, f"{filename} (semantic-candidate)")
            before_count = len(issues)
            candidate_tree, candidate_listeners, candidate_parser = parse_source(corrected, f"{filename} (semantic-fixed)")
            if candidate_tree is None or has_any_errors(candidate_listeners):
                failed_issue_keys.add(cid)
                continue
            cand_checker = SemanticChecker()
            cand_checker.visit(candidate_tree)
            if len(cand_checker.get_issues()) >= before_count:
                failed_issue_keys.add(cid)
                continue

            failed_issue_keys.clear()
            working = corrected
            tree, listeners, parser = candidate_tree, candidate_listeners, candidate_parser
            applied_steps.append(f"SEM: {msg}")
            logger.log_sem_step(step=msg, source_after=working)
            sem_edits += 1
            continue

        # Recompute semantic issues after the semantic-fix loop
        checker = SemanticChecker()
        checker.visit(tree)
        issues = checker.get_issues()

        if issues:
            logger.log_semantic_issues(issues)

        # -----------------------------------------------------
        # B) Security phase on the CURRENT parse
        # -----------------------------------------------------
        ok, sec_fixed_source, sec_steps = run_security_checks(working)

        if not ok:
            logger.end_case(
                status="BLOCKED_SECURITY",
                final_source=working,
                applied_steps=applied_steps,
                note="blocked by security analysis",
            )
            return True

        # Security changed the source -> iterate whole phase again
        if sec_fixed_source != working:
            for step in sec_steps:
                applied_steps.append(step)

            working = sec_fixed_source
            security_rounds += 1

            if security_rounds > MAX_SECURITY_ROUNDS:
                print("\nStopping: exceeded maximum security reparse rounds.")
                logger.end_case(
                    status="STOPPED",
                    final_source=working,
                    applied_steps=applied_steps,
                    note="exceeded security rounds",
                )
                return True

            tree2, listeners2, parser2 = parse_source(
                working,
                f"{filename} (after-security-{security_rounds})",
            )
            if tree2 is None:
                logger.end_case(
                    status="STOPPED",
                    final_source=working,
                    applied_steps=applied_steps,
                    note="tree None after security fix",
                )
                return True

            if has_any_errors(listeners2):
                print("\nStopping: security fix broke parsing; refusing further edits.")
                logger.log_parse_errors(stage="LEX/PARSE", errors=get_all_error_strings(listeners2))
                logger.end_case(
                    status="STOPPED",
                    final_source=working,
                    applied_steps=applied_steps,
                    note="security fix broke parsing",
                )
                return True

            tree, listeners, parser = tree2, listeners2, parser2
            sem_edits = 0
            continue

        # No security change.
        # If semantic issues still remain, finalize as semantic issues.
        if issues:
            return _finalize_semantic_with_security(
                working=working,
                tree=tree,
                parser=parser,
                issues=issues,
                applied_steps=applied_steps,
                logger=logger,
                note="issues remain after semantic/security loop",
            )

        # Clean semantic + clean security -> final success
        print("\nFINAL RESULT: SUCCESSFUL" + (" after repair" if applied_steps else ""))
        print("-" * 70)
        if applied_steps:
            print("Applied steps:")
            for s in applied_steps:
                print(f"  - {s}")
            print("-" * 70)

        if _used_ai(applied_steps):
            _print_ai_repair_debug(working, tree, parser)
        else:
            print("Parse Tree:")
            print("-" * 70)
            print_parse_tree(tree, parser)

            print("\nS-Expression Format:")
            print(tree.toStringTree(recog=parser))
            print("-" * 70)

        print_analysis(tree)

        logger.end_case(
            status="SUCCESS",
            final_source=working,
            applied_steps=applied_steps,
            note="parse+sem+security clean",
        )
        return True


def test_file(filename: str):
    is_fresh, p_info, p_warn = check_parser_status()
    print(p_info)
    if p_warn:
        print(p_warn)

    tree, listeners, parser, source_text = parse_file(filename)
    if tree is None:
        return

    logger = RepairLogger()
    green = GreenMetrics()
    green.start_total()
    case_id = str(uuid.uuid4())
    logger.start_case(
        case_id=case_id,
        filename=filename,
        original_source=source_text,
        meta={"runner": "test_parser.py"},
    )

    MAX_LEX_EDITS = 5
    MAX_SYN_EDITS = 120
    NO_IMPROVE_LIMIT = 8

    working = source_text
    applied_steps: List[str] = []

    # ---------------------------------------------------------
    # Phase 1: deterministic lexical cleanup loop
    # ---------------------------------------------------------
    for _ in range(MAX_LEX_EDITS):
        new_src, lex_fix = fix_common_lexical_issues(working)
        if lex_fix is None or new_src == working:
            break

        working = new_src
        step_msg = f"LEX: {lex_fix}"
        print("Applied lexical fix:", step_msg)
        applied_steps.append(step_msg)
        logger.log_lex_step(step=lex_fix, source_after=working)

    tree, listeners, parser = parse_source(working, f"{filename} (after-lex)")
    if tree is None:
        logger.end_case(
            status="STOPPED",
            final_source=working,
            applied_steps=applied_steps,
            note="tree None after lex",
        )
        return

    if has_any_errors(listeners):
        logger.log_parse_errors(stage="LEX/PARSE", errors=get_all_error_strings(listeners))

    # ---------------------------------------------------------
    # Fast path: if parsing already succeeded, go straight to semantic phase
    # ---------------------------------------------------------
    if not has_any_errors(listeners):
        _run_semantic_phase(filename, working, tree, listeners, parser, applied_steps, logger)
        return

    # ---------------------------------------------------------
    # Phase 2: syntax repair loop
    #   - if first error is lexer-stage: AI fallback
    #   - if parser-stage: deterministic rule first, then AI fallback
    # ---------------------------------------------------------
    edits = 0
    last_sig = None
    repeat = 0
    best_error_count = len(get_all_error_strings(listeners))
    no_improve_rounds = 0

    while has_any_errors(listeners) and edits < MAX_SYN_EDITS:
        errs = get_all_error_strings(listeners)

        print("\nPARSING FAILED - Errors Detected:")
        print("-" * 70)
        for e in errs:
            print(f"  {e}")
        print("-" * 70)

        logger.log_parse_errors(stage="LEX/PARSE", errors=errs)

        error_obj = get_first_error_object(listeners)
        if not error_obj:
            print("Stopping: error listener returned no error objects.")
            logger.end_case(
                status="STOPPED",
                final_source=working,
                applied_steps=applied_steps,
                note="no error objects",
            )
            return

        msg = error_obj["msg"]
        line = error_obj["line"]
        col = error_obj["column"]
        stage = error_obj.get("stage", "?")
        off = error_obj.get("offending")

        classification = classify_error_message(msg)

        print("\nError Classification:")
        print(f"  Stage: {stage}")
        print(f"  Fixable: {classification.fixable}")
        print(f"  Category: {classification.category}")
        print(f"  Reason: {classification.reason}")

        sig = (stage, line, col, classification.reason, msg)
        if sig == last_sig:
            repeat += 1
        else:
            repeat = 0
        last_sig = sig

        if repeat >= 6:
            print("\nStopping: repeating same error (stuck).")
            logger.end_case(
                status="STOPPED",
                final_source=working,
                applied_steps=applied_steps,
                note="repeat same error",
            )
            return

        symbols = build_symbols(tree)

        # -----------------------------------------------------
        # Optional identifier typo correction when offending token
        # looks like an identifier. This can help both parse and sem.
        # -----------------------------------------------------
        if off and re.match(r"^[A-Za-z_][A-Za-z_0-9]*$", off):
            corrected, msg2 = fix_identifier_typo_at(working, line, col, symbols, max_dist=2)
            if msg2 is not None and corrected != working:
                working = corrected
                applied_steps.append(f"SYM: {msg2}")
                logger.log_sem_step(step=msg2, source_after=working)
                edits += 1

                tree, listeners, parser = parse_source(working, f"{filename} (sym-fixed)")
                if tree is None:
                    logger.end_case(
                        status="STOPPED",
                        final_source=working,
                        applied_steps=applied_steps,
                        note="tree None after sym in parse-loop",
                    )
                    return

                cur_error_count = len(get_all_error_strings(listeners))
                if cur_error_count < best_error_count:
                    best_error_count = cur_error_count
                    no_improve_rounds = 0
                else:
                    no_improve_rounds += 1

                if no_improve_rounds >= NO_IMPROVE_LIMIT:
                    print("\nStopping: not improving error count (stuck).")
                    logger.end_case(
                        status="STOPPED",
                        final_source=working,
                        applied_steps=applied_steps,
                        note="no improvement rounds",
                    )
                    return

                if not has_any_errors(listeners):
                    _run_semantic_phase(filename, working, tree, listeners, parser, applied_steps, logger)
                    return

                continue

        # -----------------------------------------------------
        # Lexer-stage error -> AI fallback directly
        # -----------------------------------------------------
        if stage == "LEX":
            cur_err_cnt = len(get_all_error_strings(listeners))
            cand_src, applied_msg, tree_try, listeners_try, parser_try = try_week5_rules(
                working, cur_err_cnt, parse_source, f"{filename} (week5-rule)"
            )
            if applied_msg is not None:
                working = cand_src
                tree, listeners, parser = tree_try, listeners_try, parser_try
                applied_steps.append(f"RULE: {applied_msg}")
                logger.log_rule_step(step=applied_msg, source_after=working)
                edits += 1

                if not has_any_errors(listeners):
                    _run_semantic_phase(filename, working, tree, listeners, parser, applied_steps, logger)
                    return
                continue

            print("\nLexer-stage error remains after lexical correction; invoking AI patch-based correction...")

            candidates = ai_generate_patch_candidates(
                working,
                line,
                col,
                reason=classification.reason,
                top_k=5,
                debug=True,
            )

            ai_src, cmd, tree2, listeners2, parser2 = _select_best_ai_candidate_by_reparse(
                filename,
                working,
                candidates,
            )

            if cmd is None or ai_src == working or tree2 is None:
                print("AI: no valid patch produced")
                logger.end_case(
                    status="UNFIXABLE",
                    final_source=working,
                    applied_steps=applied_steps,
                    note="AI produced no patch for lexer-stage error",
                )
                return

            working = ai_src
            applied_steps.append(f"AI: {cmd}")
            logger.log_ai_step(cmd=cmd, source_after=working)
            edits += 1

            tree, listeners, parser = tree2, listeners2, parser2

        else:
            # -------------------------------------------------
            # Parser-stage error -> deterministic first, then AI
            # -------------------------------------------------
            deterministic_attempted = False
            deterministic_changed = False

            if classification.reason in DETERMINISTIC_REASONS:
                deterministic_attempted = True
                corrected, applied = apply_correction(working, line, col, classification)

                if applied is not None and corrected != working:
                    deterministic_changed = True
                    working = corrected
                    applied_steps.append(f"RULE: {applied}")
                    logger.log_rule_step(step=applied, source_after=working)
                    edits += 1

                    tree, listeners, parser = parse_source(working, f"{filename} (rule-fixed)")
                    if tree is None:
                        logger.end_case(
                            status="STOPPED",
                            final_source=working,
                            applied_steps=applied_steps,
                            note="tree None after rule fix",
                        )
                        return
                else:
                    print("\nDeterministic fix made no change; allowing AI fallback.")

            if has_any_errors(listeners):
                if classification.reason not in DETERMINISTIC_REASONS or (
                    deterministic_attempted and not deterministic_changed
                ):
                    cur_err_cnt = len(get_all_error_strings(listeners))
                    cand_src, applied_msg, tree_try, listeners_try, parser_try = try_week5_rules(
                        working, cur_err_cnt, parse_source, f"{filename} (week5-rule)"
                    )
                    if applied_msg is not None:
                        working = cand_src
                        tree, listeners, parser = tree_try, listeners_try, parser_try
                        applied_steps.append(f"RULE: {applied_msg}")
                        logger.log_rule_step(step=applied_msg, source_after=working)
                        edits += 1

                        if not has_any_errors(listeners):
                            _run_semantic_phase(filename, working, tree, listeners, parser, applied_steps, logger)
                            return
                        continue

                    print("\nInvoking AI patch-based correction...")

                    candidates = ai_generate_patch_candidates(
                        working,
                        line,
                        col,
                        reason=classification.reason,
                        top_k=5,
                        debug=True,
                    )

                    ai_src, cmd, tree2, listeners2, parser2 = _select_best_ai_candidate_by_reparse(
                        filename,
                        working,
                        candidates,
                    )

                    if cmd is None or ai_src == working or tree2 is None:
                        print("AI: no valid patch produced")
                        logger.end_case(
                            status="UNFIXABLE",
                            final_source=working,
                            applied_steps=applied_steps,
                            note="AI produced no patch",
                        )
                        return

                    working = ai_src
                    applied_steps.append(f"AI: {cmd}")
                    logger.log_ai_step(cmd=cmd, source_after=working)
                    edits += 1

                    tree, listeners, parser = tree2, listeners2, parser2

        cur_error_count = len(get_all_error_strings(listeners))
        if cur_error_count < best_error_count:
            best_error_count = cur_error_count
            no_improve_rounds = 0
        else:
            no_improve_rounds += 1

        if no_improve_rounds >= NO_IMPROVE_LIMIT:
            print("\nStopping: not improving error count (stuck).")
            logger.end_case(
                status="STOPPED",
                final_source=working,
                applied_steps=applied_steps,
                note="no improvement rounds",
            )
            return

        if not has_any_errors(listeners):
            _run_semantic_phase(filename, working, tree, listeners, parser, applied_steps, logger)
            return

    if has_any_errors(listeners):
        print("\nFINAL RESULT: UNFIXABLE within limits")
        print("-" * 70)
        print("Applied steps:")
        for s in applied_steps:
            print(f"  - {s}")

        logger.end_case(
            status="UNFIXABLE",
            final_source=working,
            applied_steps=applied_steps,
            note="still has parse/lex errors",
        )
        return

    _run_semantic_phase(filename, working, tree, listeners, parser, applied_steps, logger)


def main():
    parser = argparse.ArgumentParser(description="Simple C Parser - Test Suite")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Run a single file (e.g. examples/invalid_example1.c). If omitted, runs suite.",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(" Simple C Parser - Test Suite")
    print("=" * 70)

    if args.file:
        test_file(args.file)
    else:
        test_files = [
            "examples/block_scope.c",
            "examples/break_outside.c",
            "examples/call_check.c",
            "examples/for_decl_scope.c",
            "examples/missing_rbrace.c",
            "examples/missing_semi.c",
            "examples/param_scope.c",
            "examples/post_inc.c",
            "examples/redeclared.c",
        ]
        for filename in test_files:
            test_file(filename)

    print("\n" + "=" * 70)
    print(" Test Suite Complete")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
