from typing import Dict, Any, List, Optional
import time

from compiler.error_classifier import classify_error_message
from compiler.error_corrector import apply_correction
from compiler.lexical_corrector import fix_common_lexical_issues
try:
    from compiler.ai_error_corrector import ai_generate_patch_candidates
except (ImportError, Exception):
    def ai_generate_patch_candidates(*args, **kwargs):
        return []
from compiler.identifier_corrector import fix_identifier_typo_at
from compiler.semantic_checker import SemanticChecker
from compiler.security_checker import SecurityChecker
from compiler.taint_checker import TaintChecker
from compiler.string_flow_checker import StringFlowChecker
from compiler.unused_var_fixer import remove_unused_decl_at
from compiler.semantic_auto_fixer import fix_semantic_issue
from compiler.security_auto_fixer import SecurityAutoFixer
from compiler.green_energy import GreenEnergyTracker
from compiler.green_system import GreenSystemTracker

from compiler.week5_repair_helpers import (
    check_parser_status,
    try_week5_rules,
    fix_split_operators,
    fix_keyword_typos_fuzzy,
)

from test_parser import (
    parse_source,
    has_any_errors,
    get_all_error_strings,
    get_first_error_object,
    build_symbols,
    DETERMINISTIC_REASONS,
    _select_best_ai_candidate_by_reparse,
)

# ---------------------------------------------------------
# Optional green modules
# Safe fallback if the files are not created yet
# ---------------------------------------------------------
try:
    from compiler.green_metrics import GreenMetrics  # type: ignore
except Exception:
    class GreenMetrics:
        def __init__(self):
            self._starts = {}
            self._phase_ms = {}
            self._counters = {}
            self._values = {}

        def start(self, phase: str) -> None:
            self._starts[phase] = time.perf_counter()

        def end(self, phase: str) -> None:
            started = self._starts.get(phase)
            if started is None:
                return
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self._phase_ms[phase] = self._phase_ms.get(phase, 0.0) + elapsed_ms
            del self._starts[phase]

        def inc(self, key: str, value: int = 1) -> None:
            self._counters[key] = self._counters.get(key, 0) + value

        def set(self, key: str, value: Any) -> None:
            self._values[key] = value

        def to_dict(self) -> Dict[str, Any]:
            total_ms = sum(self._phase_ms.values())
            return {
                "total_runtime_ms": round(total_ms, 2),
                "phase_ms": {k: round(v, 2) for k, v in self._phase_ms.items()},
                "counters": dict(self._counters),
                "values": dict(self._values),
            }


try:
    from compiler.green_scorer import build_green_report  # type: ignore
except Exception:
    def build_green_report(metrics: Dict[str, Any]) -> Dict[str, Any]:
        phase_ms = metrics.get("phase_ms", {})
        counters = metrics.get("counters", {})
        values = metrics.get("values", {})

        score = 100
        total_ms = metrics.get("total_runtime_ms", 0.0)

        score -= min(int(total_ms / 80), 30)
        score -= min(counters.get("ai_fixes", 0) * 4, 20)
        score -= min(counters.get("rule_fixes", 0) * 2, 10)
        score -= min(counters.get("lex_fixes", 0), 5)
        score -= min(values.get("semantic_issue_count", 0) * 3, 15)

        if values.get("parse_success"):
            score += 5

        if values.get("status") == "STOPPED":
            score -= 15
        elif values.get("status") == "UNFIXABLE":
            score -= 10

        score = max(0, min(100, score))

        hotspot = "overall pipeline"
        hotspot_time = -1.0
        for name, ms in phase_ms.items():
            if ms > hotspot_time:
                hotspot = name
                hotspot_time = ms

        suggestion = "Pipeline looks efficient."
        if counters.get("ai_fixes", 0) >= 4:
            suggestion = "Reduce repeated AI fallback by improving deterministic fixes and early stopping."
        elif hotspot == "syntax_repair":
            suggestion = "Syntax repair dominates runtime; add stronger sync-point recovery and candidate pruning."
        elif hotspot == "semantic_phase":
            suggestion = "Semantic checking dominates runtime; consider lightweight pre-checks before full analysis."
        elif hotspot == "security_phase":
            suggestion = "Security phase dominates runtime; run targeted checks only after parse success."
        elif values.get("semantic_issue_count", 0) > 0:
            suggestion = "Reduce downstream semantic issues by improving identifier and declaration fixes earlier."

        return {
            **metrics,
            "green_score": score,
            "hotspot": hotspot,
            "suggestion": suggestion,
        }


try:
    from compiler.green_logger import GreenLogger  # type: ignore
except Exception:
    class GreenLogger:
        def log_run(self, payload: Dict[str, Any]) -> None:
            return


def _compute_changed_lines(old_text: str, new_text: str) -> List[int]:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    max_len = max(len(old_lines), len(new_lines))
    changed = []

    for i in range(max_len):
        old_line = old_lines[i] if i < len(old_lines) else ""
        new_line = new_lines[i] if i < len(new_lines) else ""
        if old_line != new_line:
            changed.append(i + 1)

    return changed


def _collect_security_issues(source_text: str) -> List[str]:
    issues = []

    security_checker = SecurityChecker()
    taint_checker = TaintChecker()
    string_checker = StringFlowChecker()

    for issue in security_checker.check(source_text):
        issues.append(f"[{issue.severity}] {issue.message} (score={issue.score})")

    for issue in taint_checker.check(source_text):
        issues.append(f"[{issue.severity}] {issue.message} (score={issue.score})")

    for issue in string_checker.check(source_text):
        issues.append(f"[{issue.severity}] {issue.message} (score={issue.score})")

    return issues


def _collect_semantic_issues(tree) -> List[Dict[str, Any]]:
    checker = SemanticChecker()
    checker.visit(tree)
    issues = list(checker.get_issues())

    try:
        symbols = build_symbols(tree)
        from compiler.undeclared_identifier_checker import UndeclaredIdentifierChecker
        u_checker = UndeclaredIdentifierChecker(symbols, require_decl_before_use=True)
        u_checker.visit(tree)
        u_issues = u_checker.get_issues()

        # If an 'undeclared' issue is actually a 'use_before_declare', refine the kind
        ubd_by_var = {
            (ui.get("name"), ui.get("line")): ui
            for ui in u_issues
            if ui.get("kind") == "use_before_declare"
        }
        for iss in issues:
            k = (iss.get("name"), iss.get("line"))
            if iss.get("kind") == "undeclared" and k in ubd_by_var:
                iss["kind"] = "use_before_declare"
                iss["msg"] = f"Variable '{iss.get('name')}' used before declaration"
    except Exception:
        pass

    return issues


def _status_from_security(security_warnings: List[str]) -> str:
    if not security_warnings:
        return "SUCCESS"

    blocked = False
    total_score = 0

    for item in security_warnings:
        if "[CRITICAL]" in item:
            blocked = True

        marker = "(score="
        pos = item.find(marker)
        if pos != -1:
            end = item.find(")", pos)
            if end != -1:
                try:
                    total_score += int(item[pos + len(marker):end])
                except ValueError:
                    pass

    if blocked or total_score >= 6:
        return "BLOCKED_SECURITY"

    return "SUCCESS_WITH_WARNINGS"


def _try_remove_unused_decl(
    working: str,
    issue: Dict[str, Any],
) -> tuple[str, Optional[str]]:
    name = issue.get("name")
    line = issue.get("line")
    col = issue.get("col")

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

    return corrected if corrected is not None else working, msg


def _run_semantic_phase_for_gui(
    filename: str,
    working: str,
    tree,
    listeners,
    parser,
    steps: List[str],
    logs: List[str],
    stats: Dict[str, int],
    green: Optional[GreenMetrics] = None,
):
    MAX_SEM_EDITS = 20
    sem_edits = 0

    if green is not None:
        green.start("semantic_phase")

    failed_issue_keys = set()  # Track issues we failed to fix on this source
    while sem_edits < MAX_SEM_EDITS:
        issues = _collect_semantic_issues(tree)

        if not issues:
            break

        # Find the first issue whose key we have not already failed on
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
            break  # All remaining issues are ones we cannot fix

        cid = (
            first.get("kind"),
            first.get("line"),
            first.get("col"),
            first.get("msg"),
        )
        kind = first.get("kind")

        if kind == "unused":
            # Guard: do not remove an unused variable declaration if that variable or line
            # has other unresolved semantic issues (e.g. type_mismatch, invalid_operand_type, pointer_assignment_warning).
            # Deleting the declaration would mask the underlying semantic issue instead of fixing it.
            has_conflicting_issue = any(
                other is not first
                and other.get("kind") != "unused"
                and (
                    other.get("line") == first.get("line")
                    or (first.get("name") and other.get("name") == first.get("name"))
                )
                for other in issues
            )
            if has_conflicting_issue:
                failed_issue_keys.add(cid)
                continue

            corrected, msg = _try_remove_unused_decl(working, first)

            if msg is None or corrected == working:
                failed_issue_keys.add(cid)
                continue

            working = corrected
            failed_issue_keys.clear()
            steps.append(f"SEM: {msg}")
            logs.append(f"Applied semantic fix: {msg}")
            stats["sem_fixes"] = stats.get("sem_fixes", 0) + 1
            sem_edits += 1

            if green is not None:
                green.inc("sem_fixes")

            tree2, listeners2, parser2 = parse_source(working, f"{filename} (unused-removed)")
            if tree2 is None or has_any_errors(listeners2):
                remaining = get_all_error_strings(listeners2) if tree2 is not None else []
                if green is not None:
                    green.end("semantic_phase")
                return {
                    "status": "STOPPED",
                    "working": working,
                    "tree": tree2,
                    "listeners": listeners2,
                    "parser": parser2,
                    "semantic_issues": issues,
                    "parse_errors": remaining,
                }

            tree, listeners, parser = tree2, listeners2, parser2
            continue

        if kind == "undeclared":
            name = first.get("name")
            line = first.get("line")
            col = first.get("col")

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
                failed_issue_keys.add(cid)
                continue

            working = corrected
            failed_issue_keys.clear()
            steps.append(f"SEM: {msg}")
            logs.append(f"Applied semantic fix: {msg}")
            stats["sem_fixes"] = stats.get("sem_fixes", 0) + 1
            sem_edits += 1

            if green is not None:
                green.inc("sem_fixes")

            tree2, listeners2, parser2 = parse_source(working, f"{filename} (sym-fixed-sem)")
            if tree2 is None or has_any_errors(listeners2):
                remaining = get_all_error_strings(listeners2) if tree2 is not None else []
                if green is not None:
                    green.end("semantic_phase")
                return {
                    "status": "STOPPED",
                    "working": working,
                    "tree": tree2,
                    "listeners": listeners2,
                    "parser": parser2,
                    "semantic_issues": issues,
                    "parse_errors": remaining,
                }

            tree, listeners, parser = tree2, listeners2, parser2
            continue

        corrected, msg = fix_semantic_issue(working, first)
        if msg is None or corrected == working:
            failed_issue_keys.add(cid)
            continue

        # Semantic repair is accepted only after a clean reparse.  The next
        # loop iteration recomputes all diagnostics before another edit.
        tree2, listeners2, parser2 = parse_source(working, f"{filename} (semantic-candidate)")
        before_count = len(issues)
        candidate_tree, candidate_listeners, candidate_parser = parse_source(corrected, f"{filename} (semantic-fixed)")
        if candidate_tree is None or has_any_errors(candidate_listeners):
            failed_issue_keys.add(cid)
            continue
        if len(_collect_semantic_issues(candidate_tree)) >= before_count:
            failed_issue_keys.add(cid)
            continue
        failed_issue_keys.clear()
        working = corrected
        tree, listeners, parser = candidate_tree, candidate_listeners, candidate_parser
        steps.append(f"SEM: {msg}")
        logs.append(f"Applied semantic fix: {msg}")
        stats["sem_fixes"] = stats.get("sem_fixes", 0) + 1
        sem_edits += 1
        if green is not None:
            green.inc("sem_fixes")
        continue

    issues = _collect_semantic_issues(tree)

    if green is not None:
        green.end("semantic_phase")

    return {
        "status": "SEM_CLEAN" if not issues else "SEM_ISSUES",
        "working": working,
        "tree": tree,
        "listeners": listeners,
        "parser": parser,
        "semantic_issues": issues,
    }


def _emit_progress(
    kind: str,
    message: str,
    working: str,
    steps: List[str],
    stats: Dict[str, int],
    status: str = "RUNNING",
) -> Dict[str, Any]:
    total_done = (
        stats.get("lex_fixes", 0)
        + stats.get("rule_fixes", 0)
        + stats.get("ai_fixes", 0)
        + stats.get("sym_fixes", 0)
        + stats.get("sem_fixes", 0)
    )

    return {
        "type": kind,
        "status": status,
        "message": message,
        "corrected_code": working,
        "applied_steps": steps[:],
        "stats": dict(stats),
        "total_repairs": total_done,
    }


def _finalize_green_report(
    green: GreenMetrics,
    filename: str,
    result: Dict[str, Any],
) -> None:
    green.set("status", result.get("status"))
    green.set("parse_success", result.get("status") not in {"STOPPED", "UNFIXABLE"})
    green.set("semantic_issue_count", len(result.get("semantic_issues", [])))
    green.set("security_warning_count", len(result.get("security_warnings", [])))

    metrics = green.to_dict()
    result["green_report"] = build_green_report(metrics)

    try:
        logger = GreenLogger()
        logger.log_run({
            "filename": filename,
            "status": result.get("status"),
            "green_report": result["green_report"],
            "stats": result.get("stats", {}),
        })
    except Exception:
        pass


def repair_source_for_gui_stream(source_text: str, filename: str = "main.c", enable_ai: bool = True):
    original_source = source_text
    working = source_text

    steps: List[str] = []
    logs: List[str] = []
    parse_errors: List[str] = []
    semantic_issues: List[Dict[str, Any]] = []
    security_warnings: List[str] = []
    security_changed_lines: List[int] = []

    MAX_LEX_EDITS = 5
    MAX_SYN_EDITS = 120
    NO_IMPROVE_LIMIT = 8
    REPEAT_LIMIT = 6

    stats = {
        "lex_fixes": 0,
        "rule_fixes": 0,
        "ai_fixes": 0,
        "sym_fixes": 0,
        "sem_fixes": 0,
        "iterations": 0,
    }

    is_fresh, p_info, p_warn = check_parser_status()
    print(p_info)
    logs.append(p_info)
    if p_warn:
        print(p_warn)
        logs.append(p_warn)

    yield _emit_progress("start", f"Started repairing {filename}", working, steps, stats)

    green = GreenMetrics()

    energy = GreenEnergyTracker()
    system = GreenSystemTracker()

    energy.start()
    system.start()

    green.start("total")
    green.start("lexical_phase")

    for _ in range(MAX_LEX_EDITS):
        new_src, lex_fix = fix_common_lexical_issues(working)
        if not lex_fix or new_src == working:
            break

        working = new_src
        step_msg = f"LEX: {lex_fix}"
        steps.append(step_msg)
        logs.append(f"Applied lexical fix: {lex_fix}")
        stats["lex_fixes"] += 1
        green.inc("lex_fixes")

        yield _emit_progress("fix", step_msg, working, steps, stats)

    green.end("lexical_phase")
    green.start("initial_parse")

    tree, listeners, parser = parse_source(working, f"{filename} (gui-after-lex)")

    green.end("initial_parse")

    if tree is None:
        green.end("total")
        final_payload = {
            "type": "done",
            "status": "STOPPED",
            "message": "Parsing stopped after lexical phase.",
            "corrected_code": working,
            "applied_steps": steps,
            "stats": stats,
            "logs": logs,
            "errors": parse_errors,
            "semantic_issues": [],
            "security_warnings": [],
            "changed_lines": _compute_changed_lines(original_source, working),
            "security_changed_lines": [],
            "success": False,
        }
        _finalize_green_report(green, filename, final_payload)
        yield final_payload
        return

    edits = 0
    parse_errors = get_all_error_strings(listeners) if has_any_errors(listeners) else []
    best_error_count = len(parse_errors)
    no_improve_rounds = 0
    last_sig = None
    repeat = 0

    green.start("syntax_repair")

    while has_any_errors(listeners) and edits < MAX_SYN_EDITS:
        stats["iterations"] += 1
        errs = get_all_error_strings(listeners)
        parse_errors = errs[:]

        error_obj = get_first_error_object(listeners)
        if not error_obj:
            break

        msg = error_obj["msg"]
        line = error_obj["line"]
        col = error_obj["column"]
        stage = error_obj.get("stage", "?")
        off = error_obj.get("offending")

        classification = classify_error_message(msg)

        yield _emit_progress(
            "detect",
            f"Detected {classification.reason} at line {line}",
            working,
            steps,
            stats,
        )

        sig = (stage, line, col, classification.reason, msg)
        if sig == last_sig:
            repeat += 1
        else:
            repeat = 0
        last_sig = sig

        if repeat >= REPEAT_LIMIT:
            break

        symbols = build_symbols(tree)

        if off and isinstance(off, str):
            import re
            if re.match(r"^[A-Za-z_][A-Za-z_0-9]*$", off):
                corrected, msg2 = fix_identifier_typo_at(working, line, col, symbols, max_dist=2)
                if msg2 is not None and corrected != working:
                    working = corrected
                    steps.append(f"SYM: {msg2}")
                    stats["sym_fixes"] += 1
                    green.inc("sym_fixes")
                    edits += 1

                    yield _emit_progress("fix", f"SYM: {msg2}", working, steps, stats)

                    tree, listeners, parser = parse_source(working, f"{filename} (gui-sym-fixed)")
                    if tree is None:
                        break

                    cur_error_count = len(get_all_error_strings(listeners))
                    if cur_error_count < best_error_count:
                        best_error_count = cur_error_count
                        no_improve_rounds = 0
                    else:
                        no_improve_rounds += 1

                    if no_improve_rounds >= NO_IMPROVE_LIMIT:
                        break

                    if not has_any_errors(listeners):
                        break
                    continue

        if stage == "LEX":
            cur_err_cnt = len(get_all_error_strings(listeners))
            cand_src, applied_msg, tree_try, listeners_try, parser_try = try_week5_rules(
                working, cur_err_cnt, parse_source, f"{filename} (gui-week5-rule)"
            )
            if applied_msg is not None:
                working = cand_src
                tree, listeners, parser = tree_try, listeners_try, parser_try
                steps.append(f"RULE: {applied_msg}")
                logs.append(f"Applied deterministic fix: {applied_msg}")
                stats["rule_fixes"] += 1
                green.inc("rule_fixes")
                edits += 1
                yield _emit_progress("fix", f"RULE: {applied_msg}", working, steps, stats)
                if not has_any_errors(listeners):
                    break
                continue

            if not enable_ai:
                break
            candidates = ai_generate_patch_candidates(
                working, line, col, reason=classification.reason, top_k=5, debug=False
            )

            ai_src, cmd, tree2, listeners2, parser2 = _select_best_ai_candidate_by_reparse(
                filename, working, candidates
            )

            if cmd is None or ai_src == working or tree2 is None:
                break

            working = ai_src
            steps.append(f"AI: {cmd}")
            stats["ai_fixes"] += 1
            green.inc("ai_fixes")
            edits += 1
            tree, listeners, parser = tree2, listeners2, parser2

            yield _emit_progress("fix", f"AI: {cmd}", working, steps, stats)

        else:
            deterministic_attempted = False
            deterministic_changed = False

            # Always try apply_correction first -- it has internal
            # _validate_fix safety and handles cast/sizeof/do-while
            # patterns even for non-deterministic error reasons.
            corrected, applied = apply_correction(working, line, col, classification)

            if applied is not None and corrected != working:
                deterministic_attempted = True
                deterministic_changed = True
                working = corrected
                steps.append(f"RULE: {applied}")
                stats["rule_fixes"] += 1
                green.inc("rule_fixes")
                edits += 1

                tree, listeners, parser = parse_source(working, f"{filename} (gui-rule-fixed)")
                if tree is None:
                    break

                yield _emit_progress("fix", f"RULE: {applied}", working, steps, stats)
            elif classification.reason in DETERMINISTIC_REASONS:
                deterministic_attempted = True

            if has_any_errors(listeners):
                if not deterministic_changed:
                    cur_err_cnt = len(get_all_error_strings(listeners))
                    cand_src, applied_msg, tree_try, listeners_try, parser_try = try_week5_rules(
                        working, cur_err_cnt, parse_source, f"{filename} (gui-week5-rule)"
                    )
                    if applied_msg is not None:
                        working = cand_src
                        tree, listeners, parser = tree_try, listeners_try, parser_try
                        steps.append(f"RULE: {applied_msg}")
                        logs.append(f"Applied deterministic fix: {applied_msg}")
                        stats["rule_fixes"] += 1
                        green.inc("rule_fixes")
                        edits += 1
                        yield _emit_progress("fix", f"RULE: {applied_msg}", working, steps, stats)
                        if not has_any_errors(listeners):
                            break
                        continue

                    if not enable_ai:
                        break
                    candidates = ai_generate_patch_candidates(
                        working, line, col, reason=classification.reason, top_k=5, debug=False
                    )

                    ai_src, cmd, tree2, listeners2, parser2 = _select_best_ai_candidate_by_reparse(
                        filename, working, candidates
                    )

                    if cmd is None or ai_src == working or tree2 is None:
                        break

                    working = ai_src
                    steps.append(f"AI: {cmd}")
                    stats["ai_fixes"] += 1
                    green.inc("ai_fixes")
                    edits += 1
                    tree, listeners, parser = tree2, listeners2, parser2

                    yield _emit_progress("fix", f"AI: {cmd}", working, steps, stats)

        cur_error_count = len(get_all_error_strings(listeners))
        if cur_error_count < best_error_count:
            best_error_count = cur_error_count
            no_improve_rounds = 0
        else:
            no_improve_rounds += 1

        if no_improve_rounds >= NO_IMPROVE_LIMIT:
            break

        if not has_any_errors(listeners):
            break

    green.end("syntax_repair")

    final_result = repair_source_for_gui(working, filename, enable_ai=enable_ai)
    final_result["type"] = "done"
    final_result["total_repairs"] = (
        final_result["stats"].get("lex_fixes", 0)
        + final_result["stats"].get("rule_fixes", 0)
        + final_result["stats"].get("ai_fixes", 0)
        + final_result["stats"].get("sym_fixes", 0)
        + final_result["stats"].get("sem_fixes", 0)
    )
    yield final_result


def repair_source_for_gui(source_text: str, filename: str = "main.c", enable_ai: bool = True) -> Dict[str, Any]:
    original_source = source_text
    working = source_text

    steps: List[str] = []
    logs: List[str] = []
    parse_errors: List[str] = []
    semantic_issues: List[Dict[str, Any]] = []
    security_warnings: List[str] = []
    security_changed_lines: List[int] = []

    MAX_LEX_EDITS = 5
    MAX_SYN_EDITS = 120
    MAX_SECURITY_ROUNDS = 5
    NO_IMPROVE_LIMIT = 8
    REPEAT_LIMIT = 6

    stats = {
        "lex_fixes": 0,
        "rule_fixes": 0,
        "ai_fixes": 0,
        "sym_fixes": 0,
        "sem_fixes": 0,
        "iterations": 0,
    }

    green = GreenMetrics()

    energy = GreenEnergyTracker()
    system = GreenSystemTracker()

    energy.start()
    system.start()

    green.start("total")

    is_fresh, p_info, p_warn = check_parser_status()
    print(p_info)
    logs.append(p_info)
    if p_warn:
        print(p_warn)
        logs.append(p_warn)

    result: Dict[str, Any] = {
        "success": False,
        "status": "STOPPED",
        "filename": filename,
        "corrected_code": working,
        "applied_steps": [],
        "logs": [],
        "errors": [],
        "semantic_issues": [],
        "security_warnings": [],
        "changed_lines": [],
        "security_changed_lines": [],
        "stats": stats,
        "green_report": {},
    }

    # ---------------------------------------------------------
    # Phase 1: lexical cleanup
    # ---------------------------------------------------------
    green.start("lexical_phase")

    for _ in range(MAX_LEX_EDITS):
        new_src, lex_fix = fix_common_lexical_issues(working)
        if not lex_fix or new_src == working:
            break

        working = new_src
        step_msg = f"LEX: {lex_fix}"
        steps.append(step_msg)
        logs.append(f"Applied lexical fix: {lex_fix}")
        stats["lex_fixes"] += 1
        green.inc("lex_fixes")

    green.end("lexical_phase")

    # ---------------------------------------------------------
    # Initial parse after lexical cleanup
    # ---------------------------------------------------------
    green.start("initial_parse")
    tree, listeners, parser = parse_source(working, f"{filename} (gui-after-lex)")
    green.end("initial_parse")

    if tree is None:
        result["status"] = "STOPPED"
        result["corrected_code"] = working
        result["applied_steps"] = steps
        result["logs"] = logs + ["Parsing stopped: tree is None after lexical phase."]
        result["changed_lines"] = _compute_changed_lines(original_source, working)
        result["security_changed_lines"] = []
        green.end("total")
        _finalize_green_report(green, filename, result)
        return result

    if has_any_errors(listeners):
        parse_errors = get_all_error_strings(listeners)

    # ---------------------------------------------------------
    # Phase 2: syntax repair loop
    # ---------------------------------------------------------
    edits = 0
    best_error_count = len(parse_errors) if parse_errors else 0
    no_improve_rounds = 0
    last_sig = None
    repeat = 0

    green.start("syntax_repair")

    while has_any_errors(listeners) and edits < MAX_SYN_EDITS:
        stats["iterations"] += 1
        errs = get_all_error_strings(listeners)
        parse_errors = errs[:]
        logs.append("Parsing failed; attempting repair.")
        logs.extend(errs)

        error_obj = get_first_error_object(listeners)
        if not error_obj:
            result["status"] = "STOPPED"
            break

        msg = error_obj["msg"]
        line = error_obj["line"]
        col = error_obj["column"]
        stage = error_obj.get("stage", "?")
        off = error_obj.get("offending")

        classification = classify_error_message(msg)

        logs.append(
            f"Classified error -> stage={stage}, category={classification.category}, "
            f"reason={classification.reason}, fixable={classification.fixable}"
        )

        sig = (stage, line, col, classification.reason, msg)
        if sig == last_sig:
            repeat += 1
        else:
            repeat = 0
        last_sig = sig

        if repeat >= REPEAT_LIMIT:
            logs.append("Stopping: repeating same error (stuck).")
            result["status"] = "STOPPED"
            break

        symbols = build_symbols(tree)

        if off and isinstance(off, str):
            import re
            if re.match(r"^[A-Za-z_][A-Za-z_0-9]*$", off):
                corrected, msg2 = fix_identifier_typo_at(working, line, col, symbols, max_dist=2)
                if msg2 is not None and corrected != working:
                    working = corrected
                    steps.append(f"SYM: {msg2}")
                    logs.append(f"Applied symbol fix: {msg2}")
                    stats["sym_fixes"] += 1
                    green.inc("sym_fixes")
                    edits += 1

                    tree, listeners, parser = parse_source(working, f"{filename} (gui-sym-fixed)")
                    if tree is None:
                        result["status"] = "STOPPED"
                        break

                    cur_error_count = len(get_all_error_strings(listeners))
                    if cur_error_count < best_error_count:
                        best_error_count = cur_error_count
                        no_improve_rounds = 0
                    else:
                        no_improve_rounds += 1

                    if no_improve_rounds >= NO_IMPROVE_LIMIT:
                        logs.append("Stopping: not improving error count (stuck).")
                        result["status"] = "STOPPED"
                        break

                    if not has_any_errors(listeners):
                        break

                    continue

        if stage == "LEX":
            cur_err_cnt = len(get_all_error_strings(listeners))
            cand_src, applied_msg, tree_try, listeners_try, parser_try = try_week5_rules(
                working, cur_err_cnt, parse_source, f"{filename} (gui-week5-rule)"
            )
            if applied_msg is not None:
                working = cand_src
                tree, listeners, parser = tree_try, listeners_try, parser_try
                steps.append(f"RULE: {applied_msg}")
                logs.append(f"Applied deterministic fix: {applied_msg}")
                stats["rule_fixes"] += 1
                green.inc("rule_fixes")
                edits += 1

                if not has_any_errors(listeners):
                    break
                continue

            if not enable_ai:
                logs.append("AI disabled; stopping on lexer error.")
                result["status"] = "UNFIXABLE"
                break

            logs.append("Lexer-stage error remains; invoking AI patch candidates.")

            candidates = ai_generate_patch_candidates(
                working,
                line,
                col,
                reason=classification.reason,
                top_k=5,
                debug=False,
            )

            ai_src, cmd, tree2, listeners2, parser2 = _select_best_ai_candidate_by_reparse(
                filename,
                working,
                candidates,
            )

            if cmd is None or ai_src == working or tree2 is None:
                logs.append("AI: no valid patch produced.")
                result["status"] = "UNFIXABLE"
                break

            working = ai_src
            steps.append(f"AI: {cmd}")
            logs.append(f"Applied AI patch: {cmd}")
            stats["ai_fixes"] += 1
            green.inc("ai_fixes")
            edits += 1

            tree, listeners, parser = tree2, listeners2, parser2

        else:
            deterministic_attempted = False
            deterministic_changed = False

            # Always try apply_correction first -- it has internal
            # _validate_fix safety and handles cast/sizeof/do-while
            # patterns even for non-deterministic error reasons.
            corrected, applied = apply_correction(working, line, col, classification)

            if applied is not None and corrected != working:
                deterministic_attempted = True
                deterministic_changed = True
                working = corrected
                steps.append(f"RULE: {applied}")
                logs.append(f"Applied deterministic fix: {applied}")
                stats["rule_fixes"] += 1
                green.inc("rule_fixes")
                edits += 1

                tree, listeners, parser = parse_source(working, f"{filename} (gui-rule-fixed)")
                if tree is None:
                    result["status"] = "STOPPED"
                    break
            elif classification.reason in DETERMINISTIC_REASONS:
                deterministic_attempted = True
                logs.append("Deterministic fix made no change; allowing AI fallback.")

            if has_any_errors(listeners):
                if not deterministic_changed:
                    cur_err_cnt = len(get_all_error_strings(listeners))
                    cand_src, applied_msg, tree_try, listeners_try, parser_try = try_week5_rules(
                        working, cur_err_cnt, parse_source, f"{filename} (gui-week5-rule)"
                    )
                    if applied_msg is not None:
                        working = cand_src
                        tree, listeners, parser = tree_try, listeners_try, parser_try
                        steps.append(f"RULE: {applied_msg}")
                        logs.append(f"Applied deterministic fix: {applied_msg}")
                        stats["rule_fixes"] += 1
                        green.inc("rule_fixes")
                        edits += 1

                        if not has_any_errors(listeners):
                            break
                        continue

                    if not enable_ai:
                        logs.append("AI disabled; no deterministic fix available.")
                        result["status"] = "UNFIXABLE"
                        break

                    logs.append("Invoking AI patch-based correction.")

                    candidates = ai_generate_patch_candidates(
                        working,
                        line,
                        col,
                        reason=classification.reason,
                        top_k=5,
                        debug=False,
                    )

                    ai_src, cmd, tree2, listeners2, parser2 = _select_best_ai_candidate_by_reparse(
                        filename,
                        working,
                        candidates,
                    )

                    if cmd is None or ai_src == working or tree2 is None:
                        logs.append("AI: no valid patch produced.")
                        result["status"] = "UNFIXABLE"
                        break

                    working = ai_src
                    steps.append(f"AI: {cmd}")
                    logs.append(f"Applied AI patch: {cmd}")
                    stats["ai_fixes"] += 1
                    green.inc("ai_fixes")
                    edits += 1

                    tree, listeners, parser = tree2, listeners2, parser2

        cur_error_count = len(get_all_error_strings(listeners))
        if cur_error_count < best_error_count:
            best_error_count = cur_error_count
            no_improve_rounds = 0
        else:
            no_improve_rounds += 1

        if no_improve_rounds >= NO_IMPROVE_LIMIT:
            logs.append("Stopping: not improving error count (stuck).")
            result["status"] = "STOPPED"
            break

        if not has_any_errors(listeners):
            break

    green.end("syntax_repair")

    # ---------------------------------------------------------
    # Final status after syntax phase
    # ---------------------------------------------------------
    if tree is None:
        result["status"] = "STOPPED"
    elif has_any_errors(listeners):
        if result["status"] not in {"STOPPED", "UNFIXABLE"}:
            result["status"] = "UNFIXABLE"
        parse_errors = get_all_error_strings(listeners)
    else:
        result["status"] = "PARSE_SUCCESS"
        parse_errors = []

    # ---------------------------------------------------------
    # Phase 3: semantic + iterative security
    # ---------------------------------------------------------
    if tree is not None and not has_any_errors(listeners):
        security_rounds = 0

        while True:
            sem_result = _run_semantic_phase_for_gui(
                filename,
                working,
                tree,
                listeners,
                parser,
                steps,
                logs,
                stats,
                green=green,
            )

            working = sem_result["working"]
            tree = sem_result["tree"]
            listeners = sem_result["listeners"]
            parser = sem_result["parser"]
            semantic_issues = sem_result.get("semantic_issues", [])
            parse_errors = sem_result.get("parse_errors", parse_errors)

            if sem_result["status"] == "STOPPED":
                result["status"] = "STOPPED"
                result["success"] = False
                break

            green.start("security_phase")
            security_warnings = _collect_security_issues(working)

            if security_warnings:
                logs.append(f"Security issues detected: {len(security_warnings)}")
                logs.append("Invoking SecurityAutoFixer for GUI parity with CLI.")

                try:
                    auto_fixer = SecurityAutoFixer()
                    fix_result = auto_fixer.apply_fixes(working)

                    if fix_result.source != working:
                        changed_now = _compute_changed_lines(working, fix_result.source)
                        security_changed_lines = sorted(set(security_changed_lines + changed_now))

                        for step in fix_result.applied_steps:
                            steps.append(step)
                            logs.append(f"Applied security fix: {step}")

                        ai_sec_count = sum(1 for s in fix_result.applied_steps if s.startswith("AISEC:"))
                        stats["ai_fixes"] += ai_sec_count
                        if ai_sec_count > 0:
                            green.inc("ai_fixes", ai_sec_count)

                        working = fix_result.source
                        security_rounds += 1

                        if security_rounds > MAX_SECURITY_ROUNDS:
                            green.end("security_phase")
                            logs.append("Stopping: exceeded maximum security reparse rounds.")
                            result["status"] = "STOPPED"
                            result["success"] = False
                            break

                        tree2, listeners2, parser2 = parse_source(
                            working,
                            f"{filename} (gui-after-security-{security_rounds})",
                        )

                        if tree2 is None or has_any_errors(listeners2):
                            green.end("security_phase")
                            logs.append("Stopping: security fix broke parsing.")
                            parse_errors = get_all_error_strings(listeners2) if tree2 is not None else []
                            result["status"] = "STOPPED"
                            result["success"] = False
                            tree = tree2
                            listeners = listeners2
                            parser = parser2
                            break

                        tree, listeners, parser = tree2, listeners2, parser2
                        green.end("security_phase")
                        continue

                    logs.append("SecurityAutoFixer produced no code change.")
                except Exception as e:
                    logs.append(f"Security auto-fix failed: {str(e)}")

            green.end("security_phase")

            if semantic_issues:
                result["status"] = "SEM_ISSUES"
                result["success"] = True
                break

            final_status = _status_from_security(security_warnings)

            if security_warnings:
                logs.append(f"Security warnings remaining: {len(security_warnings)}")
            else:
                logs.append("No security warnings found.")

            result["status"] = final_status
            result["success"] = final_status in {"SUCCESS", "SUCCESS_WITH_WARNINGS"}
            break

        result["semantic_issues"] = semantic_issues
        result["security_warnings"] = security_warnings

    else:
        result["semantic_issues"] = []
        result["security_warnings"] = _collect_security_issues(working)
        result["success"] = False

    # ---------------------------------------------------------
    # Final payload
    # ---------------------------------------------------------
    changed_lines = _compute_changed_lines(original_source, working)

    result["corrected_code"] = working
    result["applied_steps"] = steps
    result["logs"] = logs
    result["errors"] = parse_errors
    result["changed_lines"] = changed_lines
    result["security_changed_lines"] = security_changed_lines
    result["stats"] = stats
    result["total_applied_steps"] = len(steps)
    logs.append(f"Total applied steps: {len(steps)}")

    green.end("total")

    system.sample()
    sys_stats = system.stop()
    energy_stats = energy.stop()

    for k, v in sys_stats.items():
        green.set(k, v)

    for k, v in energy_stats.items():
        green.set(k, v)

    _finalize_green_report(green, filename, result)

    return result
