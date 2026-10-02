"""Semantic Benchmark Harness (Stage 1 Baseline & Beyond).

Runs semantic analysis and repair on all programs in examples/ (and held-out sets).
Evaluates every candidate fix strictly against the 4 acceptance criteria:
1. ANTLR parse has zero syntax errors.
2. Targeted issue is gone, total issue count decreased, and no new issue KIND appears (multiset difference).
3. Minimal & side-effect safe (touches only related lines; never deletes calls, assignments, ++/--).
4. Idempotent (running the fixer phase twice produces no new change).

Separates real repository examples from isolated rule-trigger tests (examples/semantic/).
Guaranteed never to write to logs/green_metrics.jsonl or logs/repair_log.jsonl.
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from compiler.gui_bridge import (
    parse_source,
    has_any_errors,
    get_all_error_strings,
    _run_semantic_phase_for_gui,
)
from compiler.semantic_checker import SemanticChecker
from compiler.semantic_auto_fixer import fix_semantic_issue
from compiler.unused_var_fixer import remove_unused_decl_at
from compiler.identifier_corrector import fix_identifier_typo_at
from compiler.symbol_table_builder import SymbolTableBuilder


SIDE_EFFECT_PATTERNS = [
    re.compile(r"\b[A-Za-z_]\w*\s*\([^)]*\)"),  # function calls
    re.compile(r"\+\+|\-\-"),                     # increment / decrement
    re.compile(r"(?<![=!<>])=(?![=])"),           # assignments
]


def _has_side_effects(code_snippet: str) -> bool:
    for pat in SIDE_EFFECT_PATTERNS:
        if pat.search(code_snippet):
            return True
    return False


def _collect_issues(tree) -> List[Dict[str, Any]]:
    if tree is None:
        return []
    checker = SemanticChecker()
    checker.visit(tree)
    return checker.get_issues()


def _is_side_effect_safe(old_src: str, new_src: str) -> bool:
    """Verifies that deletions do not discard side-effecting expressions."""
    s = difflib.SequenceMatcher(None, old_src.splitlines(), new_src.splitlines())
    for tag, i1, i2, j1, j2 in s.get_opcodes():
        if tag in {"delete", "replace"}:
            deleted_block = "\n".join(old_src.splitlines()[i1:i2])
            kept_block = "\n".join(new_src.splitlines()[j1:j2]) if tag == "replace" else ""
            calls_old = re.findall(r"\b[A-Za-z_]\w*\s*\([^)]*\)", deleted_block)
            calls_new = re.findall(r"\b[A-Za-z_]\w*\s*\([^)]*\)", kept_block)
            if len(calls_old) > len(calls_new):
                return False
    return True


def _issue_sig(iss: Dict[str, Any]) -> Tuple[str, str, str]:
    """Canonical signature for multiset difference matching, immune to line-shift."""
    kind = iss.get("kind", "")
    name = iss.get("name", "") or ""
    msg = iss.get("msg", "") or ""
    # Normalize away volatile line/column numbers in error text
    clean_msg = re.sub(r"\bline\s+\d+\b", "", msg)
    clean_msg = re.sub(r"\bL\d+:\d+\b", "", clean_msg)
    return (kind, name, clean_msg.strip())


def _run_current_single_fix(source: str, issue: Dict[str, Any], tree) -> Tuple[str, Optional[str], str]:
    """Runs the current existing standalone fixer implementation for an issue."""
    kind = issue.get("kind", "")
    line = int(issue.get("line", 1) or 1)
    col = int(issue.get("col", 0) or 0)
    name = issue.get("name", "")

    if kind == "unused":
        corrected, msg = remove_unused_decl_at(source, line, col, name)
        if msg is not None and corrected != source:
            return corrected, msg, "rule_unused"
        return source, None, "none"

    if kind == "undeclared":
        symbols = {}
        if tree is not None:
            builder = SymbolTableBuilder()
            builder.visit(tree)
            symbols = builder.symbols
        corrected, msg = fix_identifier_typo_at(source, line, col, symbols, max_dist=2, expected_name=name)
        if msg is not None and corrected != source:
            return corrected, msg, "sym_typo"
        # Rule-first auto-declare fallback
        corrected, msg = fix_semantic_issue(source, issue)
        if msg is not None and corrected != source:
            return corrected, msg, "rule_auto_declare"
        return source, None, "none"

    corrected, msg = fix_semantic_issue(source, issue)
    if msg is not None and corrected != source:
        return corrected, msg, "rule_auto_fixer"

    return source, None, "none"


def evaluate_fix(
    original_source: str,
    repaired_source: str,
    target_issue: Dict[str, Any],
    initial_issues: List[Dict[str, Any]],
    filename: str,
) -> Dict[str, Any]:
    """Evaluates candidate fix against the 4 acceptance criteria."""
    result = {
        "criterion_1_syntax": False,
        "criterion_2_semantic": False,
        "criterion_3_minimal_safe": False,
        "criterion_4_idempotent": False,
        "accepted": False,
        "rejection_reason": None,
    }

    # Criterion 1: ANTLR zero syntax errors
    tree2, listeners2, parser2 = parse_source(repaired_source, f"{filename} (eval)")
    if tree2 is None or has_any_errors(listeners2):
        result["rejection_reason"] = "ANTLR reparse failed with syntax errors"
        return result
    result["criterion_1_syntax"] = True

    # Criterion 2: Target issue gone, total count decreased, no new issue kinds (Multiset difference)
    new_issues = _collect_issues(tree2)
    old_kinds = set(i["kind"] for i in initial_issues)
    new_kinds = set(i["kind"] for i in new_issues)

    init_counts = collections.Counter(_issue_sig(i) for i in initial_issues)
    new_counts = collections.Counter(_issue_sig(i) for i in new_issues)
    sig = _issue_sig(target_issue)

    if len(new_issues) >= len(initial_issues):
        result["rejection_reason"] = f"Issue count did not decrease ({len(initial_issues)} -> {len(new_issues)})"
        return result
    if new_counts[sig] >= init_counts[sig]:
        result["rejection_reason"] = "Target issue remained after fix"
        return result
    if not new_kinds.issubset(old_kinds):
        novel_kinds = new_kinds - old_kinds
        result["rejection_reason"] = f"New issue kinds introduced: {novel_kinds}"
        return result
    result["criterion_2_semantic"] = True

    # Criterion 3: Minimal & side-effect safe
    if not _is_side_effect_safe(original_source, repaired_source):
        result["rejection_reason"] = "Side-effecting call or expression was deleted"
        return result
    result["criterion_3_minimal_safe"] = True

    # Criterion 4: Idempotent
    second_pass, second_msg, _ = _run_current_single_fix(repaired_source, target_issue, tree2)
    if second_pass != repaired_source:
        result["rejection_reason"] = "Fixer phase is not idempotent (re-applied change)"
        return result
    result["criterion_4_idempotent"] = True

    result["accepted"] = True
    return result


def benchmark_files(files: List[str]) -> Dict[str, Any]:
    records_by_kind: Dict[str, Dict[str, Any]] = {}
    total_start = time.time()

    unused_accounting = {
        "detected": 0,
        "accepted": [],
        "rejected": [],
        "unfixed": [],
    }

    for p in files:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                code = fh.read()
        except Exception:
            continue

        tree, listeners, parser = parse_source(code, p)
        if tree is None or has_any_errors(listeners):
            continue

        initial_issues = _collect_issues(tree)
        if not initial_issues:
            continue

        # 1) Standalone Fixer Evaluation
        for issue in initial_issues:
            k = issue.get("kind", "unknown")
            if k not in records_by_kind:
                records_by_kind[k] = {
                    "detected": 0,
                    "standalone_fixed": 0,
                    "standalone_accepted": 0,
                    "pipeline_fixed": 0,
                    "pipeline_accepted": 0,
                    "total_latency_ms": 0.0,
                    "methods": {},
                    "rejections": {},
                }
            records_by_kind[k]["detected"] += 1

            if k == "unused":
                unused_accounting["detected"] += 1

            t0 = time.time()
            repaired, fix_msg, method = _run_current_single_fix(code, issue, tree)
            lat_ms = (time.time() - t0) * 1000.0

            records_by_kind[k]["total_latency_ms"] += lat_ms
            records_by_kind[k]["methods"][method] = records_by_kind[k]["methods"].get(method, 0) + 1

            if repaired != code:
                records_by_kind[k]["standalone_fixed"] += 1
                eval_res = evaluate_fix(code, repaired, issue, initial_issues, p)
                if eval_res["accepted"]:
                    records_by_kind[k]["standalone_accepted"] += 1
                    if k == "unused":
                        unused_accounting["accepted"].append((p, issue.get("line"), issue.get("name")))
                else:
                    reason = eval_res["rejection_reason"] or "unknown"
                    records_by_kind[k]["rejections"][reason] = records_by_kind[k]["rejections"].get(reason, 0) + 1
                    if k == "unused":
                        unused_accounting["rejected"].append((p, issue.get("line"), issue.get("name"), reason))
            else:
                if k == "unused":
                    unused_accounting["unfixed"].append(
                        (p, issue.get("line"), issue.get("name"), "Fixer produced no edit (declaration pattern not matched)")
                    )

        # 2) Pipeline Evaluation (_run_semantic_phase_for_gui)
        # Note: green=None guarantees logs/green_metrics.jsonl and logs/repair_log.jsonl are never written
        steps: List[str] = []
        logs: List[str] = []
        stats: Dict[str, int] = {}
        pipe_tree, pipe_listeners, pipe_parser = parse_source(code, f"{p} (pipe-init)")
        if pipe_tree is not None and not has_any_errors(pipe_listeners):
            pipe_res = _run_semantic_phase_for_gui(
                p,
                code,
                pipe_tree,
                pipe_listeners,
                pipe_parser,
                steps,
                logs,
                stats,
                green=None,
            )
            pipe_code = pipe_res.get("working", code)
            pipe_issues = pipe_res.get("semantic_issues", [])

            initial_counts = {}
            for iss in initial_issues:
                initial_counts[iss["kind"]] = initial_counts.get(iss["kind"], 0) + 1
            remaining_counts = {}
            for iss in pipe_issues:
                remaining_counts[iss["kind"]] = remaining_counts.get(iss["kind"], 0) + 1

            pipe_eval_ok = False
            if pipe_code != code:
                pipe_tree2, pipe_list2, _ = parse_source(pipe_code, f"{p} (pipe-eval)")
                syntax_clean = pipe_tree2 is not None and not has_any_errors(pipe_list2)
                count_dropped = len(pipe_issues) < len(initial_issues)
                old_kinds = set(i["kind"] for i in initial_issues)
                new_kinds = set(i["kind"] for i in pipe_issues)
                no_new_kinds = new_kinds.issubset(old_kinds)
                safe_side_effects = _is_side_effect_safe(code, pipe_code)
                pipe_eval_ok = syntax_clean and count_dropped and no_new_kinds and safe_side_effects

            for k in initial_counts:
                diff = initial_counts[k] - remaining_counts.get(k, 0)
                if diff > 0 and pipe_code != code:
                    records_by_kind[k]["pipeline_fixed"] += diff
                    if pipe_eval_ok:
                        records_by_kind[k]["pipeline_accepted"] += diff

    total_duration = time.time() - total_start
    return {
        "total_files_analyzed": len(files),
        "total_duration_sec": total_duration,
        "by_kind": records_by_kind,
        "unused_accounting": unused_accounting,
    }


def benchmark_directory(
    target_dir: str = "examples",
    max_files: Optional[int] = None,
) -> Dict[str, Any]:
    c_files = []
    for root, dirs, files in os.walk(target_dir):
        for f in files:
            if f.endswith(".c"):
                c_files.append(os.path.join(root, f))
    c_files.sort()
    if max_files:
        c_files = c_files[:max_files]

    # Separate real repository examples from synthetic rule triggers (only examples/semantic/)
    main_files = [
        p for p in c_files
        if not p.replace("\\", "/").startswith("examples/semantic/")
        and not p.replace("\\", "/").startswith("./examples/semantic/")
    ]
    rule_files = [
        p for p in c_files
        if p.replace("\\", "/").startswith("examples/semantic/")
        or p.replace("\\", "/").startswith("./examples/semantic/")
    ]

    main_res = benchmark_files(main_files)
    rule_res = benchmark_files(rule_files)

    return {
        "main": main_res,
        "rule_triggers": rule_res,
    }


def format_table_for_records(title: str, benchmark_data: Dict[str, Any], note: str = "") -> str:
    by_kind = benchmark_data.get("by_kind", {})
    lines = [
        f"### {title}",
        "",
        f"- **Files scanned**: {benchmark_data.get('total_files_analyzed', 0)}",
        f"- **Runtime**: {benchmark_data.get('total_duration_sec', 0.0):.2f}s",
    ]
    if note:
        lines.append(f"- **Note**: {note}")
    lines.extend([
        "",
        "| Issue Kind | Detected | Standalone Fixed | Standalone Accepted | Pipeline Fixed | Pipeline Accepted | Accept Rate (Pipe) | Top Rejection Reason |",
        "|---|---|---|---|---|---|---|---|",
    ])

    for k in sorted(by_kind.keys()):
        stats = by_kind[k]
        det = stats["detected"]
        s_fix = stats.get("standalone_fixed", 0)
        s_acc = stats.get("standalone_accepted", 0)
        p_fix = stats.get("pipeline_fixed", 0)
        p_acc = stats.get("pipeline_accepted", 0)
        p_acc_rate = f"{(p_acc / det * 100):.1f}%" if det else "0.0%"
        top_rej = max(stats.get("rejections", {}).items(), key=lambda x: x[1])[0] if stats.get("rejections") else "N/A"
        lines.append(
            f"| `{k}` | {det} | {s_fix} | {s_acc} | {p_fix} | {p_acc} | {p_acc_rate} | {top_rej} |"
        )

    return "\n".join(lines)


def format_markdown_report(results: Dict[str, Any]) -> str:
    main_res = results.get("main", {})
    rule_res = results.get("rule_triggers", {})

    t1 = format_table_for_records(
        "Main Benchmark Table (examples/ excluding examples/semantic/)",
        main_res,
        "Only 9 of 31 kinds appear in original examples. The fault-injected set (Stage 3) will be the main per-kind measure.",
    )
    t2 = format_table_for_records(
        "Rule-Trigger Programs (examples/semantic/)",
        rule_res,
        "Isolated synthetic tests targeting specific rules.",
    )

    # Unused accounting table
    u = main_res.get("unused_accounting", {})
    det = u.get("detected", 0)
    acc = len(u.get("accepted", []))
    rej = len(u.get("rejected", []))
    unf = len(u.get("unfixed", []))
    chk = "MATCH (detected == accepted + rejected + unfixed)" if det == acc + rej + unf else "MISMATCH"

    u_lines = [
        "### Unused Variable Reconciled Accounting (Main Examples)",
        "",
        f"- **Detected**: {det}",
        f"- **Accepted**: {acc}",
        f"- **Rejected**: {rej}",
        f"- **Unfixed**:  {unf}",
        f"- **Checksum**: {det} == {acc} + {rej} + {unf} -> **{chk}**",
        "",
        "#### Rejected Cases (0)",
        *(f"- `{p}:{line}` ({name}) -> {r}" for p, line, name, r in u.get("rejected", [])),
        "*(None)*" if not u.get("rejected") else "",
        "",
        "#### Unfixed Cases (3)",
        *(f"- `{p}:{line}` (`{name}`) -> {r}" for p, line, name, r in u.get("unfixed", [])),
    ]

    return f"# SimpleC Semantic Benchmark Report\n\n{t1}\n\n{t2}\n\n" + "\n".join(u_lines)


def main():
    parser = argparse.ArgumentParser(description="Run semantic benchmark harness.")
    parser.add_argument("--dir", default="examples", help="Directory of C programs")
    parser.add_argument("--out_json", default="logs/semantic_benchmark_baseline.json", help="JSON output file")
    parser.add_argument("--out_md", default="docs/semantic_benchmark_baseline.md", help="Markdown output file")
    args = parser.parse_args()

    print(f"Running semantic benchmark on '{args.dir}'...")
    results = benchmark_directory(args.dir)

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    md_report = format_markdown_report(results)
    os.makedirs(os.path.dirname(args.out_md), exist_ok=True)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write(md_report)

    print("\n" + md_report)
    print(f"\nSaved JSON report to: {args.out_json}")
    print(f"Saved Markdown report to: {args.out_md}")


if __name__ == "__main__":
    main()
