"""Pipeline safety guard for verified security repairs.

Validates that any security fix candidate:
1. Re-parses cleanly with ANTLR (0 syntax errors).
2. Introduces NO new semantic issue (kind, name) that was not present before the fix.
3. If validation fails, rolls back the fix, preserves the original line, and records
   the diagnostic as SUGGESTED with the specific reason.

Shared by both gui_bridge.py and test_parser.py to avoid duplicated pipeline logic.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from compiler.semantic_checker import SemanticChecker
from compiler.security_auto_fixer import SecurityAutoFixer, AutoFixResult, _split_lines
from test_parser import parse_source, has_any_errors, get_all_error_strings, build_symbols


def collect_semantic_issues(tree) -> List[Dict[str, Any]]:
    """Run SemanticChecker and UndeclaredIdentifierChecker to gather all semantic diagnostics."""
    if tree is None:
        return []
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


def apply_security_fixes_with_safety_guard(
    source: str,
    filename: str = "main.c",
    auto_fixer: Optional[SecurityAutoFixer] = None,
) -> AutoFixResult:
    """Run SecurityAutoFixer and strictly validate candidate fixes.

    Accept candidate lines only if:
    - ANTLR parse succeeds without errors.
    - No new semantic issues (kind, name) are introduced.

    Failed fixes are rolled back to the original source line and recorded in
    AutoFixResult.suggestions.
    """
    if auto_fixer is None:
        auto_fixer = SecurityAutoFixer()

    fix_result = auto_fixer.apply_fixes(source)

    if fix_result.source == source:
        return fix_result

    # Gather baseline issues before security fix
    tree_before, listeners_before, _ = parse_source(source, f"{filename} (guard-before)")
    before_issue_keys: Set[Tuple[str, str]] = set()
    if tree_before is not None and not has_any_errors(listeners_before):
        before_sem = collect_semantic_issues(tree_before)
        before_issue_keys = {
            (str(iss.get("kind") or ""), str(iss.get("name") or ""))
            for iss in before_sem
        }

    # First test: check candidate as a whole
    tree_cand, listeners_cand, _ = parse_source(fix_result.source, f"{filename} (guard-candidate)")
    if tree_cand is not None and not has_any_errors(listeners_cand):
        cand_sem = collect_semantic_issues(tree_cand)
        cand_issue_keys = {
            (str(iss.get("kind") or ""), str(iss.get("name") or ""))
            for iss in cand_sem
        }
        new_issues = cand_issue_keys - before_issue_keys
        if not new_issues:
            # Candidate passed completely!
            return fix_result

    # If full candidate failed, validate line-by-line to roll back bad edits
    before_lines, before_eols = _split_lines(source)
    cand_lines, _ = _split_lines(fix_result.source)

    accepted_lines = list(before_lines)
    accepted_steps: List[str] = []
    suggestions: List[str] = list(fix_result.suggestions)

    min_len = min(len(before_lines), len(cand_lines))
    for i in range(min_len):
        if cand_lines[i] != before_lines[i]:
            trial_lines = list(accepted_lines)
            trial_lines[i] = cand_lines[i]
            trial_src = "".join(f"{line}{eol}" for line, eol in zip(trial_lines, before_eols))

            t_tree, t_list, _ = parse_source(trial_src, f"{filename} (guard-line-{i+1})")
            line_ok = False
            line_reason = ""

            if t_tree is not None and not has_any_errors(t_list):
                t_sem = collect_semantic_issues(t_tree)
                t_keys = {
                    (str(iss.get("kind") or ""), str(iss.get("name") or ""))
                    for iss in t_sem
                }
                t_new = t_keys - before_issue_keys
                if not t_new:
                    line_ok = True
                else:
                    new_summary = ", ".join(f"{k}({n})" for k, n in sorted(t_new))
                    line_reason = f"introduced new semantic issue(s): {new_summary}"
            else:
                errs = get_all_error_strings(t_list) if t_tree is not None else ["parse failure"]
                line_reason = f"syntax error: {errs[0] if errs else 'parse error'}"

            if line_ok:
                accepted_lines[i] = cand_lines[i]
                matching_steps = [s for s in fix_result.applied_steps if f"line {i+1}:" in s]
                accepted_steps.extend(matching_steps if matching_steps else [f"SEC: line {i+1} fixed"])
            else:
                # Roll back this line edit!
                suggestions.append(
                    f"SUGGESTION: line {i+1}: security fix rejected ({line_reason}) - kept original: '{before_lines[i].strip()}'"
                )

    accepted_source = "".join(f"{line}{eol}" for line, eol in zip(accepted_lines, before_eols))
    return AutoFixResult(
        source=accepted_source,
        applied_steps=accepted_steps,
        suggestions=suggestions,
    )
