import ast
import re
from typing import List, Dict, Any, Optional, Tuple, Set

SHELL_META = set("|&;<>()$`\\\"'*?[]{}~!#")
SECRET_NAMES = re.compile(r'^(password|passwd|secret|api_key|apikey|token)$', re.IGNORECASE)

class SecurityVisitor(ast.NodeVisitor):
    def __init__(self, source: str):
        self.source = source
        self.findings: List[Dict[str, Any]] = []
        self.tainted_names: Set[str] = set()
        self.has_flask = False
        self.has_ast_import = False

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name == "ast":
                self.has_ast_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module == "ast":
            self.has_ast_import = True
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Taint tracking: assigned from input(), sys.argv, os.environ
        is_taint_source = False
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name) and node.value.func.id == "input":
                is_taint_source = True
        elif isinstance(node.value, ast.Attribute):
            if isinstance(node.value.value, ast.Name) and node.value.value.id == "sys" and node.value.attr == "argv":
                is_taint_source = True
            elif isinstance(node.value.value, ast.Name) and node.value.value.id == "os" and node.value.attr == "environ":
                is_taint_source = True
        elif isinstance(node.value, ast.Subscript):
            if isinstance(node.value.value, ast.Attribute):
                if isinstance(node.value.value.value, ast.Name) and node.value.value.value.id == "sys" and node.value.value.attr == "argv":
                    is_taint_source = True
                elif isinstance(node.value.value.value, ast.Name) and node.value.value.value.id == "os" and node.value.value.attr == "environ":
                    is_taint_source = True

        if is_taint_source:
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.tainted_names.add(t.id)

        # Check Flask app creation
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name) and node.value.func.id == "Flask":
                self.has_flask = True

        # Check PY-SEC-07: Hardcoded password/secret
        for t in node.targets:
            if isinstance(t, ast.Name) and SECRET_NAMES.match(t.id):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and node.value.value.strip():
                    self.findings.append({
                        "rule": "PY-SEC-07",
                        "action": "reported",
                        "line": node.lineno,
                        "col": node.col_offset,
                        "message": f"Hardcoded credential in '{t.id}'. Store credentials in environment variables using os.environ.",
                        "node": node
                    })

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check Flask app creation directly in calls
        if isinstance(node.func, ast.Name) and node.func.id == "Flask":
            self.has_flask = True

        # PY-SEC-01: yaml.load(x) without Loader keyword
        if isinstance(node.func, ast.Attribute) and node.func.attr == "load":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "yaml":
                has_loader = any(k.arg == "Loader" for k in node.keywords)
                if not has_loader:
                    self.findings.append({
                        "rule": "PY-SEC-01",
                        "action": "auto_fixed",
                        "line": node.lineno,
                        "col": node.col_offset,
                        "message": "yaml.load without Loader replaced with yaml.safe_load",
                        "node": node
                    })

        # PY-SEC-02: hashlib.md5 or hashlib.sha1
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("md5", "sha1"):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "hashlib":
                skip = any(
                    k.arg == "usedforsecurity" and isinstance(k.value, ast.Constant) and k.value.value is False
                    for k in node.keywords
                )
                if not skip:
                    self.findings.append({
                        "rule": "PY-SEC-02",
                        "action": "auto_fixed",
                        "line": node.lineno,
                        "col": node.col_offset,
                        "message": f"weak hash ({node.func.attr}) replaced with hashlib.sha256",
                        "node": node,
                        "algo": node.func.attr
                    })

        # PY-SEC-03 & PY-SEC-09: eval / exec
        if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            if node.func.id == "eval" and len(node.args) >= 1:
                arg0 = node.args[0]
                is_input_call = isinstance(arg0, ast.Call) and isinstance(arg0.func, ast.Name) and arg0.func.id == "input"
                is_tainted_name = isinstance(arg0, ast.Name) and arg0.id in self.tainted_names

                if is_input_call or is_tainted_name:
                    self.findings.append({
                        "rule": "PY-SEC-03",
                        "action": "auto_fixed",
                        "line": node.lineno,
                        "col": node.col_offset,
                        "message": "unsafe eval replaced with ast.literal_eval",
                        "node": node
                    })
                else:
                    self.findings.append({
                        "rule": "PY-SEC-09",
                        "action": "reported",
                        "line": node.lineno,
                        "col": node.col_offset,
                        "message": "eval/exec with non-fixable argument",
                        "node": node
                    })
            else:
                self.findings.append({
                    "rule": "PY-SEC-09",
                    "action": "reported",
                    "line": node.lineno,
                    "col": node.col_offset,
                    "message": "exec call is unsafe",
                    "node": node
                })

        # PY-SEC-04 & PY-SEC-09: subprocess call with shell=True
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
            shell_kw = next((k for k in node.keywords if k.arg == "shell"), None)
            if shell_kw and isinstance(shell_kw.value, ast.Constant) and shell_kw.value.value is True:
                if len(node.args) >= 1 and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    cmd_str = node.args[0].value
                    if not any(ch in SHELL_META for ch in cmd_str):
                        self.findings.append({
                            "rule": "PY-SEC-04",
                            "action": "auto_fixed",
                            "line": node.lineno,
                            "col": node.col_offset,
                            "message": "removed shell=True and converted command to argument list",
                            "node": node,
                            "cmd_str": cmd_str
                        })
                    else:
                        self.findings.append({
                            "rule": "PY-SEC-09",
                            "action": "reported",
                            "line": node.lineno,
                            "col": node.col_offset,
                            "message": "subprocess call with shell=True and shell metacharacters",
                            "node": node
                        })
                else:
                    self.findings.append({
                        "rule": "PY-SEC-09",
                        "action": "reported",
                        "line": node.lineno,
                        "col": node.col_offset,
                        "message": "subprocess call with non-literal shell=True command",
                        "node": node
                    })

        # PY-SEC-05: requests verify=False
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "requests":
            verify_kw = next((k for k in node.keywords if k.arg == "verify"), None)
            if verify_kw and isinstance(verify_kw.value, ast.Constant) and verify_kw.value.value is False:
                self.findings.append({
                    "rule": "PY-SEC-05",
                    "action": "auto_fixed",
                    "line": node.lineno,
                    "col": node.col_offset,
                    "message": "enabled TLS certificate verification (verify=True)",
                    "node": node
                })

        # PY-SEC-06: .run(debug=True) in Flask app
        if isinstance(node.func, ast.Attribute) and node.func.attr == "run":
            debug_kw = next((k for k in node.keywords if k.arg == "debug"), None)
            if debug_kw and isinstance(debug_kw.value, ast.Constant) and debug_kw.value.value is True:
                # We will verify if has_flask is true in second pass or post-process
                self.findings.append({
                    "rule": "PY-SEC-06",
                    "action": "auto_fixed",
                    "line": node.lineno,
                    "col": node.col_offset,
                    "message": "disabled Flask debug mode in production",
                    "node": node
                })

        # PY-SEC-08: cursor.execute(...) with concatenated SQL
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("execute", "executemany"):
            if len(node.args) >= 1:
                arg0 = node.args[0]
                is_sql_injection = False
                if isinstance(arg0, ast.BinOp) and isinstance(arg0.op, (ast.Add, ast.Mod)):
                    is_sql_injection = True
                elif isinstance(arg0, ast.JoinedStr):
                    is_sql_injection = True
                elif isinstance(arg0, ast.Call) and isinstance(arg0.func, ast.Attribute) and arg0.func.attr == "format":
                    is_sql_injection = True

                if is_sql_injection:
                    self.findings.append({
                        "rule": "PY-SEC-08",
                        "action": "reported",
                        "line": node.lineno,
                        "col": node.col_offset,
                        "message": "Possible SQL injection detected. Use parameterized queries instead of string concatenation/formatting.",
                        "node": node
                    })

        # PY-SEC-09: pickle.load / pickle.loads, os.system with non-literal
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle" and node.func.attr in ("load", "loads"):
                self.findings.append({
                    "rule": "PY-SEC-09",
                    "action": "reported",
                    "line": node.lineno,
                    "col": node.col_offset,
                    "message": f"Unsafe deserialization with pickle.{node.func.attr}",
                    "node": node
                })
            elif isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr == "system":
                if len(node.args) >= 1 and not (isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                    self.findings.append({
                        "rule": "PY-SEC-09",
                        "action": "reported",
                        "line": node.lineno,
                        "col": node.col_offset,
                        "message": "os.system with non-literal command",
                        "node": node
                    })

        self.generic_visit(node)

def analyze(source: str) -> List[Dict[str, Any]]:
    try:
        tree = ast.parse(source)
    except Exception:
        return []

    visitor = SecurityVisitor(source)
    # Check if Flask is created in source
    visitor.has_flask = ("Flask(" in source) or ("Flask (__name__)" in source)
    visitor.visit(tree)

    # Filter PY-SEC-06 if Flask app is not present
    filtered = []
    for f in visitor.findings:
        if f["rule"] == "PY-SEC-06" and not visitor.has_flask:
            continue
        filtered.append(f)

    # Sort by line, col
    filtered.sort(key=lambda x: (x["line"], x["col"]))
    return filtered

def get_fix_candidate(source: str, findings: List[Dict[str, Any]]) -> Optional[Tuple[str, str, str, int, Dict[str, Any]]]:
    """Returns (new_source, step_msg, warning_msg, changed_line, targeted_finding) or None"""
    if not findings:
        return None

    lines = source.split("\n")

    for f in findings:
        if f.get("action") != "auto_fixed":
            continue

        rule = f["rule"]
        line_num = f["line"]
        if line_num < 1 or line_num > len(lines):
            continue
        line_idx = line_num - 1
        line_text = lines[line_idx]

        if rule == "PY-SEC-01":
            if "yaml.load(" in line_text:
                new_line = line_text.replace("yaml.load(", "yaml.safe_load(", 1)
                new_lines = lines[:]
                new_lines[line_idx] = new_line
                warn = f"PY-SEC-01 [auto-fixed] line {line_num}: yaml.load without Loader replaced with yaml.safe_load"
                step = "SEC: replace yaml.load with yaml.safe_load"
                return "\n".join(new_lines), step, warn, line_num, f

        elif rule == "PY-SEC-02":
            algo = f.get("algo", "md5")
            target_call = f"hashlib.{algo}("
            if target_call in line_text:
                new_line = line_text.replace(target_call, "hashlib.sha256(", 1)
                new_lines = lines[:]
                new_lines[line_idx] = new_line
                warn = f"PY-SEC-02 [auto-fixed] line {line_num}: weak hash replaced with hashlib.sha256"
                step = "SEC: replace weak hash with hashlib.sha256"
                return "\n".join(new_lines), step, warn, line_num, f

        elif rule == "PY-SEC-03":
            if "eval(" in line_text:
                new_line = line_text.replace("eval(", "ast.literal_eval(", 1)
                new_lines = lines[:]
                new_lines[line_idx] = new_line

                # Check if "import ast" already exists
                has_ast = False
                try:
                    tree = ast.parse(source)
                    for n in ast.walk(tree):
                        if isinstance(n, ast.Import) and any(a.name == "ast" for a in n.names):
                            has_ast = True
                        elif isinstance(n, ast.ImportFrom) and n.module == "ast":
                            has_ast = True
                except Exception:
                    pass

                if not has_ast:
                    # Insert "import ast" after docstring / __future__ / top-level imports
                    insert_idx = 0
                    try:
                        tree = ast.parse("\n".join(new_lines))
                        # Find last import or docstring
                        for item in tree.body:
                            if isinstance(item, (ast.Import, ast.ImportFrom)):
                                insert_idx = max(insert_idx, item.end_lineno or item.lineno)
                            elif isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                                insert_idx = max(insert_idx, item.end_lineno or item.lineno)
                    except Exception:
                        pass
                    new_lines.insert(insert_idx, "import ast")
                    changed_line = line_num + (1 if insert_idx <= line_idx else 0)
                else:
                    changed_line = line_num

                warn = f"PY-SEC-03 [auto-fixed] line {line_num}: unsafe eval replaced with ast.literal_eval"
                step = "SEC: replace eval with ast.literal_eval"
                return "\n".join(new_lines), step, warn, changed_line, f

        elif rule == "PY-SEC-04":
            cmd_str = f.get("cmd_str", "")
            words = cmd_str.split()
            # Render words as double-quoted string list
            words_rendered = "[" + ", ".join(f'"{w}"' for w in words) + "]"
            # Replace string literal and shell=True in line_text
            new_line = line_text
            # Remove shell=True with possible comma
            new_line = re.sub(r',\s*shell\s*=\s*True', '', new_line)
            new_line = re.sub(r'shell\s*=\s*True\s*,\s*', '', new_line)
            new_line = re.sub(r'shell\s*=\s*True', '', new_line)
            # Replace cmd literal
            new_line = re.sub(r'["\']' + re.escape(cmd_str) + r'["\']', words_rendered, new_line, count=1)

            new_lines = lines[:]
            new_lines[line_idx] = new_line
            warn = f"PY-SEC-04 [auto-fixed] line {line_num}: removed shell=True and converted command to argument list"
            step = "SEC: remove shell=True and convert command to list"
            return "\n".join(new_lines), step, warn, line_num, f

        elif rule == "PY-SEC-05":
            if "verify=False" in line_text or "verify = False" in line_text:
                new_line = re.sub(r'verify\s*=\s*False', 'verify=True', line_text, count=1)
                new_lines = lines[:]
                new_lines[line_idx] = new_line
                warn = f"PY-SEC-05 [auto-fixed] line {line_num}: enabled TLS certificate verification (verify=True)"
                step = "SEC: enable TLS certificate verification (verify=True)"
                return "\n".join(new_lines), step, warn, line_num, f

        elif rule == "PY-SEC-06":
            if "debug=True" in line_text or "debug = True" in line_text:
                new_line = re.sub(r'debug\s*=\s*True', 'debug=False', line_text, count=1)
                new_lines = lines[:]
                new_lines[line_idx] = new_line
                warn = f"PY-SEC-06 [auto-fixed] line {line_num}: disabled Flask debug mode in production"
                step = "SEC: disable Flask debug mode"
                return "\n".join(new_lines), step, warn, line_num, f

    return None

def auto_fix_security(source: str):
    working = source
    warnings = []
    steps = []
    changed_lines = []
    rounds = 0
    max_rounds = 20

    while rounds < max_rounds:
        findings = analyze(working)
        cand = get_fix_candidate(working, findings)
        if not cand:
            break

        new_src, step_msg, warn_msg, chg_line, targeted = cand
        try:
            ast.parse(new_src)
            new_findings = analyze(new_src)
            old_rules = {f["rule"] for f in findings}
            new_rules = {f["rule"] for f in new_findings}

            # Acceptance condition:
            # (1) parses
            # (2) no new security finding appeared
            # (3) targeted rule is reduced or gone
            if new_rules.issubset(old_rules) and len(new_findings) < len(findings):
                working = new_src
                steps.append(step_msg)
                warnings.append(warn_msg)
                if chg_line not in changed_lines:
                    changed_lines.append(chg_line)
                rounds += 1
            else:
                break
        except Exception:
            break

    # Append remaining reported findings
    remaining = analyze(working)
    for f in remaining:
        rule = f["rule"]
        msg = f["message"]
        line = f["line"]
        rep_warn = f"{rule} [reported] line {line}: {msg}"
        if rep_warn not in warnings:
            warnings.append(rep_warn)

    return working, warnings, steps, changed_lines
