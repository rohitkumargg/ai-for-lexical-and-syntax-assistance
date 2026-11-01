import ast
import re
import keyword
from typing import Dict, Any, List, Optional, Tuple, Generator

from compiler.gui_bridge import (
    GreenMetrics,
    GreenEnergyTracker,
    GreenSystemTracker,
    _finalize_green_report,
    _emit_progress,
    _compute_changed_lines,
)
from compiler.languages import python_semantic, python_security

HEAD = re.compile(r'^\s*(if|elif|else|for|while|def|class|try|except|finally|with)\b')
KW = [k for k in keyword.kwlist if k not in ('True', 'False', 'None')]

def err(src: str) -> Optional[Tuple[int, int, str]]:
    try:
        ast.parse(src)
        return None
    except SyntaxError as e:
        return (e.lineno or 1, e.offset or 0, e.msg or "syntax error")
    except Exception as e:
        return (1, 0, str(e))

def lev(a: str, b: str) -> int:
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (ca != cb))
    return d[-1]

def swap1(a: str, b: str) -> bool:
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 2 and sorted(a) == sorted(b)

def close_kw(w: str) -> Optional[str]:
    if w in keyword.kwlist or len(w) < 3:
        return None
    c = []
    for k in KW:
        d = 1 if swap1(w, k) else lev(w, k)
        if d <= (1 if len(k) <= 4 else 2):
            c.append((d, k))
    c.sort()
    if not c or (len(c) > 1 and c[0][0] == c[1][0]):
        return None
    return c[0][1]

def is_token_level(desc: str) -> bool:
    return any(desc.startswith(p) for p in [
        "else if",
        "print statement",
        "&&/||",
        "x++",
        "keyword typo",
    ])

def candidates(src: str) -> Generator[Tuple[str, str], None, None]:
    lines = src.split('\n')
    e = err(src)
    if not e:
        return
    ln = min(e[0], len(lines))
    for L in sorted({ln, max(1, ln - 1)}, reverse=True):
        t = lines[L - 1]
        core = re.sub(r'\s*#.*$', '', t).rstrip()

        def put(txt: str) -> str:
            n = lines[:]
            n[L - 1] = txt
            return '\n'.join(n)

        if re.match(r'^\s*else\s+if\b', t):
            yield "else if -> elif", put(re.sub(r'else\s+if', 'elif', t, count=1))
        if HEAD.match(t) and not core.endswith(':'):
            yield "added ':'", put(core + ':')
        for ch, op in ((')', '('), (']', '['), ('}', '{')):
            if core.count(op) > core.count(ch):
                yield f"closed '{ch}'", put(core + ch)
        if core.count('"') % 2 == 1:
            yield 'closed string', put(core + '"')
        if core.count("'") % 2 == 1:
            yield 'closed string', put(core + "'")
        if re.match(r'^\s*(if|elif|while)\b', t) and re.search(r'[^=!<>]=[^=]', t):
            yield "= -> ==", put(re.sub(r'([^=!<>])=([^=])', r'\1==\2', t, count=1))
        m = re.match(r'^(\s*)print\s+(.+)$', t)
        if m:
            yield "print statement -> call", put(f"{m.group(1)}print({m.group(2)})")
        if '&&' in t or '||' in t:
            yield "&&/|| -> and/or", put(t.replace('&&', 'and').replace('||', 'or'))
        m = re.match(r'^(\s*)(\w+)(\+\+|--)\s*$', t)
        if m:
            op = '+=' if m.group(3) == '++' else '-='
            yield "x++ -> x += 1", put(f"{m.group(1)}{m.group(2)} {op} 1")
        m = re.match(r'^(\s*)(\w+)(\s.*)?$', t)
        if m:
            k = close_kw(m.group(2))
            if k:
                yield f"keyword typo {m.group(2)} -> {k}", put(f"{m.group(1)}{k}{m.group(3) or ''}")
        if '\t' in t:
            yield "convert tabs to spaces", put(t.expandtabs(4))
        prev = next((lines[i] for i in range(L - 2, -1, -1) if lines[i].strip()), '')
        lv = {len(x) - len(x.lstrip(' ')) for x in lines[:L - 1] if x.strip()}
        lv |= {len(prev) - len(prev.lstrip(' ')) + 4}
        for n_sp in sorted(lv, reverse=True):
            yield f"indent -> {n_sp}", put(' ' * n_sp + t.lstrip(' '))

def repair_python_stream(source: str, filename: str = "main.py") -> Generator[Dict[str, Any], None, None]:
    original_source = source
    working = source

    steps: List[str] = []
    logs: List[str] = []
    parse_errors: List[str] = []
    semantic_issues: List[Dict[str, Any]] = []
    security_warnings: List[str] = []
    security_changed_lines: List[int] = []

    MAX_SYN_EDITS = 60
    NO_IMPROVE_LIMIT = 8
    REPEAT_LIMIT = 6

    stats = {
        "lex_fixes": 0,
        "rule_fixes": 0,
        "ai_fixes": 0,
        "sym_fixes": 0,
        "sem_fixes": 0,
        "sec_det_fixes": 0,
        "iterations": 0,
    }

    green = GreenMetrics()
    energy = GreenEnergyTracker()
    system = GreenSystemTracker()

    energy.start()
    system.start()
    green.start("total")

    yield _emit_progress("start", f"Started repairing {filename}", working, steps, stats)

    green.start("initial_parse")
    initial_err = err(working)
    green.end("initial_parse")

    stopped_due_to_limits = False
    unfixable = False

    if initial_err:
        logs.append("Parsing failed; attempting repair.")
        logs.append("AI repair is not available for Python (rule-based only)")

        edits = 0
        no_improve_rounds = 0
        seen_sources: Dict[str, int] = {working: 1}
        best_err = initial_err

        green.start("syntax_repair")

        while edits < MAX_SYN_EDITS:
            stats["iterations"] += 1
            e0 = err(working)
            if not e0:
                break

            accepted = False
            for d, c in candidates(working):
                e1 = err(c)
                # Accepted only if parses or first error is strictly later
                if e1 is None or ((e1[0], e1[1]) > (e0[0], e0[1]) and e1[0] >= e0[0]):
                    working = c
                    accepted = True
                    edits += 1

                    if is_token_level(d):
                        step_msg = f"LEX: {d}"
                        stats["lex_fixes"] += 1
                    else:
                        step_msg = f"RULE: {d}"
                        stats["rule_fixes"] += 1

                    steps.append(step_msg)
                    logs.append(f"Candidate accepted: {d}")
                    yield _emit_progress("fix", step_msg, working, steps, stats)

                    # Track stall / repeat limits
                    count = seen_sources.get(working, 0) + 1
                    seen_sources[working] = count
                    if count >= REPEAT_LIMIT:
                        stopped_due_to_limits = True
                        break

                    if e1 is None:
                        break
                    elif (e1[0], e1[1]) > (best_err[0], best_err[1]):
                        best_err = e1
                        no_improve_rounds = 0
                    else:
                        no_improve_rounds += 1
                        if no_improve_rounds >= NO_IMPROVE_LIMIT:
                            stopped_due_to_limits = True
                            break
                    break

            if not accepted or stopped_due_to_limits:
                if not accepted and err(working) is not None:
                    unfixable = True
                break

        green.end("syntax_repair")

        if edits >= MAX_SYN_EDITS:
            stopped_due_to_limits = True
    else:
        # Initial parse was clean
        green.start("syntax_repair")
        green.end("syntax_repair")

    final_err = err(working)
    if final_err is not None:
        parse_errors.append(f"Line {final_err[0]}:{final_err[1]} - PARSE Error: {final_err[2]}")
        status = "STOPPED" if stopped_due_to_limits else "UNFIXABLE"
        success = False
    else:
        # Phase 3: Semantic Phase
        green.start("semantic_phase")
        try:
            sem_rounds = 0
            while sem_rounds < 20:
                cur_sem = python_semantic.analyze(working)
                cur_sec = python_security.analyze(working)
                cand = python_semantic.get_fix_candidate(working, cur_sem)
                if not cand:
                    break
                cand_src, step_msg, targeted = cand
                if err(cand_src) is not None:
                    break
                new_sem = python_semantic.analyze(cand_src)
                new_sec = python_security.analyze(cand_src)
                kinds_old = {i["kind"] for i in cur_sem}
                kinds_new = {i["kind"] for i in new_sem}
                if len(new_sem) > len(cur_sem) or not kinds_new.issubset(kinds_old):
                    break
                if any(i["kind"] == targeted["kind"] and i["name"] == targeted["name"] for i in new_sem):
                    break
                rules_old = {f["rule"] for f in cur_sec}
                rules_new = {f["rule"] for f in new_sec}
                if not rules_new.issubset(rules_old) or len(new_sec) > len(cur_sec):
                    break

                working = cand_src
                steps.append(step_msg)
                if step_msg.startswith("SYM:"):
                    stats["sym_fixes"] += 1
                else:
                    stats["sem_fixes"] += 1
                sem_rounds += 1

            semantic_issues = python_semantic.analyze(working)
        except Exception:
            semantic_issues = []
        green.end("semantic_phase")

        # Phase 4: Security Phase
        green.start("security_phase")
        try:
            sec_rounds = 0
            while sec_rounds < 20:
                cur_sem = python_semantic.analyze(working)
                cur_sec = python_security.analyze(working)
                cand = python_security.get_fix_candidate(working, cur_sec)
                if not cand:
                    break
                cand_src, step_msg, warn_msg, chg_line, targeted = cand
                if err(cand_src) is not None:
                    break
                new_sem = python_semantic.analyze(cand_src)
                new_sec = python_security.analyze(cand_src)
                kinds_old = {i["kind"] for i in cur_sem}
                kinds_new = {i["kind"] for i in new_sem}
                if len(new_sem) > len(cur_sem) or not kinds_new.issubset(kinds_old):
                    break
                old_rule_cnt = sum(1 for f in cur_sec if f["rule"] == targeted["rule"])
                new_rule_cnt = sum(1 for f in new_sec if f["rule"] == targeted["rule"])
                if new_rule_cnt >= old_rule_cnt:
                    break
                rules_old = {f["rule"] for f in cur_sec}
                rules_new = {f["rule"] for f in new_sec}
                if not rules_new.issubset(rules_old):
                    break

                working = cand_src
                steps.append(step_msg)
                stats["sem_fixes"] += 1
                security_warnings.append(warn_msg)
                if chg_line not in security_changed_lines:
                    security_changed_lines.append(chg_line)
                sec_rounds += 1

            remaining_sec = python_security.analyze(working)
            for f in remaining_sec:
                rep_msg = f"{f['rule']} [reported] line {f['line']}: {f['message']}"
                if rep_msg not in security_warnings:
                    security_warnings.append(rep_msg)
        except Exception:
            security_warnings = []
        green.end("security_phase")

        if len(semantic_issues) > 0:
            status = "SEM_ISSUES"
            success = True
        elif len(security_warnings) > 0:
            status = "SUCCESS_WITH_WARNINGS"
            success = True
        else:
            status = "SUCCESS"
            success = True

    green.end("total")

    system.sample()
    sys_stats = system.stop()
    energy_stats = energy.stop()
    for k, v in sys_stats.items():
        green.set(k, v)
    for k, v in energy_stats.items():
        green.set(k, v)

    changed_lines = _compute_changed_lines(original_source, working)
    logs.append(f"Total applied steps: {len(steps)}")

    result: Dict[str, Any] = {
        "success": success,
        "status": status,
        "filename": filename,
        "corrected_code": working,
        "applied_steps": steps,
        "logs": logs,
        "errors": parse_errors,
        "semantic_issues": semantic_issues,
        "security_warnings": security_warnings,
        "changed_lines": changed_lines,
        "security_changed_lines": security_changed_lines,
        "stats": stats,
        "total_applied_steps": len(steps),
        "language": "python",
    }

    _finalize_green_report(green, filename, result)

    yield {**result, "type": "done"}

def repair_python(source: str, filename: str = "main.py") -> Dict[str, Any]:
    final_payload = None
    for event in repair_python_stream(source, filename):
        if event.get("type") == "done":
            final_payload = event
            break
    if final_payload is None:
        final_payload = {}
    # Make a clean copy without "type" key for repair_python direct return if needed
    res = dict(final_payload)
    if "type" in res:
        del res["type"]
    return res
