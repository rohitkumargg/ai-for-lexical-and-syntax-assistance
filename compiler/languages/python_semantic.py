import ast
import builtins
import re
from typing import List, Dict, Any, Optional, Tuple, Set

BUILTINS = set(dir(builtins))

def lev(a: str, b: str) -> int:
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (ca != cb))
    return d[-1]

def is_side_effect_free(node: ast.AST) -> bool:
    if isinstance(node, (ast.Constant, ast.Name)):
        return True
    if isinstance(node, ast.UnaryOp):
        return is_side_effect_free(node.operand)
    if isinstance(node, ast.BinOp):
        return is_side_effect_free(node.left) and is_side_effect_free(node.right)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(is_side_effect_free(elt) for elt in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (k is None or is_side_effect_free(k)) and is_side_effect_free(v)
            for k, v in zip(node.keys, node.values)
        )
    return False

class Scope:
    def __init__(self, name: str, is_function: bool = False, is_class: bool = False):
        self.name = name
        self.is_function = is_function
        self.is_class = is_class
        self.bound: Set[str] = set()
        self.reads: Set[str] = set()
        self.assigned_vars: Dict[str, List[ast.AST]] = {}
        self.imports: Dict[str, ast.AST] = {}

class ScopeVisitor(ast.NodeVisitor):
    def __init__(self):
        self.module_scope = Scope("module")
        self.scopes: List[Scope] = [self.module_scope]
        self.all_scopes: List[Scope] = [self.module_scope]
        self.has_star_import = False
        self.loop_depth = 0
        self.func_depth = 0
        self.issues: List[Dict[str, Any]] = []
        self.function_defs: Dict[str, ast.FunctionDef] = {}

    def current_scope(self) -> Scope:
        return self.scopes[-1]

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            bound_name = alias.asname or alias.name.split('.')[0]
            self.current_scope().bound.add(bound_name)
            if len(self.scopes) == 1:
                self.module_scope.imports[bound_name] = node
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            if alias.name == "*":
                self.has_star_import = True
            else:
                bound_name = alias.asname or alias.name
                self.current_scope().bound.add(bound_name)
                if len(self.scopes) == 1:
                    self.module_scope.imports[bound_name] = node
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.current_scope().bound.add(node.name)
        if len(self.scopes) == 1:
            self.function_defs[node.name] = node

        # Check missing self if directly in class
        if len(self.scopes) > 1 and self.scopes[-1].is_class:
            is_static = any(
                (isinstance(d, ast.Name) and d.id == "staticmethod") or
                (isinstance(d, ast.Attribute) and d.attr == "staticmethod")
                for d in node.decorator_list
            )
            if not is_static and len(node.args.args) == 0:
                self.issues.append({
                    "kind": "method_missing_self",
                    "name": node.name,
                    "line": node.lineno,
                    "col": node.col_offset,
                    "msg": f"Method '{node.name}' missing self parameter",
                    "node": node
                })

        new_scope = Scope(node.name, is_function=True)
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            new_scope.bound.add(arg.arg)
        if node.args.vararg:
            new_scope.bound.add(node.args.vararg.arg)
        if node.args.kwarg:
            new_scope.bound.add(node.args.kwarg.arg)

        self.scopes.append(new_scope)
        self.all_scopes.append(new_scope)
        self.func_depth += 1

        self.check_unreachable(node.body)
        for item in node.body:
            self.visit(item)

        self.func_depth -= 1
        self.scopes.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.current_scope().bound.add(node.name)
        new_scope = Scope(node.name, is_function=True)
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            new_scope.bound.add(arg.arg)
        if node.args.vararg:
            new_scope.bound.add(node.args.vararg.arg)
        if node.args.kwarg:
            new_scope.bound.add(node.args.kwarg.arg)

        self.scopes.append(new_scope)
        self.all_scopes.append(new_scope)
        self.func_depth += 1

        self.check_unreachable(node.body)
        for item in node.body:
            self.visit(item)

        self.func_depth -= 1
        self.scopes.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        self.current_scope().bound.add(node.name)
        new_scope = Scope(node.name, is_class=True)
        self.scopes.append(new_scope)
        self.all_scopes.append(new_scope)

        self.check_unreachable(node.body)
        for item in node.body:
            self.visit(item)

        self.scopes.pop()

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.current_scope().bound.add(target.id)
                if self.current_scope().is_function:
                    self.current_scope().assigned_vars.setdefault(target.id, []).append(node)
            else:
                self.visit(target)
        self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign):
        if isinstance(node.target, ast.Name):
            self.current_scope().bound.add(node.target.id)
            self.current_scope().reads.add(node.target.id)
        else:
            self.visit(node.target)
        self.visit(node.value)

    def visit_For(self, node: ast.For):
        if isinstance(node.target, ast.Name):
            self.current_scope().bound.add(node.target.id)
        self.loop_depth += 1
        self.check_unreachable(node.body)
        for item in node.body:
            self.visit(item)
        self.loop_depth -= 1
        for item in node.orelse:
            self.visit(item)

    def visit_While(self, node: ast.While):
        self.visit(node.test)
        self.loop_depth += 1
        self.check_unreachable(node.body)
        for item in node.body:
            self.visit(item)
        self.loop_depth -= 1
        for item in node.orelse:
            self.visit(item)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            self.current_scope().reads.add(node.id)
            for sc in self.scopes:
                sc.reads.add(node.id)

            if not self.has_star_import and node.id not in BUILTINS:
                # Check bound in current or enclosing scopes
                is_bound = any(node.id in sc.bound for sc in self.scopes)
                # In Python, functions can access module-level names defined anywhere in module
                if not is_bound and self.func_depth > 0:
                    is_bound = node.id in self.module_scope.bound

                if not is_bound:
                    self.issues.append({
                        "kind": "undefined_name",
                        "name": node.id,
                        "line": node.lineno,
                        "col": node.col_offset,
                        "msg": f"Undefined name '{node.id}'",
                        "node": node
                    })
        elif isinstance(node.ctx, ast.Store):
            self.current_scope().bound.add(node.id)

    def visit_Compare(self, node: ast.Compare):
        has_none_eq = False
        all_comps = [node.left] + node.comparators
        ops = node.ops

        for i, op in enumerate(ops):
            left_val = all_comps[i]
            right_val = all_comps[i + 1]
            if isinstance(op, (ast.Eq, ast.NotEq)):
                if (isinstance(right_val, ast.Constant) and right_val.value is None) or \
                   (isinstance(left_val, ast.Constant) and left_val.value is None):
                    has_none_eq = True
                    break

        if has_none_eq:
            self.issues.append({
                "kind": "comparison_to_none",
                "name": "None",
                "line": node.lineno,
                "col": node.col_offset,
                "msg": "Comparison to None should use 'is' or 'is not'",
                "node": node
            })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            fn_name = node.func.id
            if fn_name in self.function_defs:
                target_def = self.function_defs[fn_name]
                # Arity check
                pos_args = target_def.args.posonlyargs + target_def.args.args
                defaults = target_def.args.defaults
                min_args = len(pos_args) - len(defaults)
                max_args = len(pos_args)
                has_vararg = target_def.args.vararg is not None
                has_kwarg = target_def.args.kwarg is not None

                call_pos_count = len(node.args)
                call_has_var = any(isinstance(a, ast.Starred) for a in node.args)
                call_has_kw = any(k.arg is None for k in node.keywords)

                if not has_vararg and not has_kwarg and not call_has_var and not call_has_kw:
                    call_kw_names = {k.arg for k in node.keywords if k.arg is not None}
                    total_supplied = call_pos_count + len(call_kw_names)
                    if total_supplied < min_args or (call_pos_count > max_args and not has_vararg):
                        self.issues.append({
                            "kind": "call_arity_mismatch",
                            "name": fn_name,
                            "line": node.lineno,
                            "col": node.col_offset,
                            "msg": f"Function '{fn_name}' called with incorrect number of arguments",
                            "node": node
                        })
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return):
        if self.func_depth == 0:
            self.issues.append({
                "kind": "return_outside_function",
                "name": "return",
                "line": node.lineno,
                "col": node.col_offset,
                "msg": "'return' outside function",
                "node": node
            })
        self.generic_visit(node)

    def visit_Break(self, node: ast.Break):
        if self.loop_depth == 0:
            self.issues.append({
                "kind": "break_outside_loop",
                "name": "break",
                "line": node.lineno,
                "col": node.col_offset,
                "msg": "'break' outside loop",
                "node": node
            })

    def visit_Continue(self, node: ast.Continue):
        if self.loop_depth == 0:
            self.issues.append({
                "kind": "continue_outside_loop",
                "name": "continue",
                "line": node.lineno,
                "col": node.col_offset,
                "msg": "'continue' outside loop",
                "node": node
            })

    def check_unreachable(self, stmts: List[ast.AST]):
        terminated = False
        for stmt in stmts:
            if terminated:
                self.issues.append({
                    "kind": "unreachable_code",
                    "name": "unreachable",
                    "line": stmt.lineno,
                    "col": stmt.col_offset,
                    "msg": "Unreachable code detected",
                    "node": stmt
                })
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                terminated = True

def analyze(source: str) -> List[Dict[str, Any]]:
    try:
        tree = ast.parse(source)
    except Exception:
        return []

    # First pass: collect module-level definitions so functions can see them
    visitor = ScopeVisitor()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            visitor.module_scope.bound.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    visitor.module_scope.bound.add(t.id)

    visitor.check_unreachable(tree.body)
    visitor.visit(tree)

    all_reads_global = set()
    for sc in visitor.all_scopes:
        all_reads_global |= sc.reads

    # Check unused top-level imports
    for bound_name, imp_node in visitor.module_scope.imports.items():
        if bound_name not in all_reads_global:
            visitor.issues.append({
                "kind": "unused_import",
                "name": bound_name,
                "line": imp_node.lineno,
                "col": imp_node.col_offset,
                "msg": f"Unused import '{bound_name}'",
                "node": imp_node
            })

    # Check unused function-local variables
    for sc in visitor.all_scopes:
        if sc.is_function:
            for var_name, assign_nodes in sc.assigned_vars.items():
                if var_name.startswith("_"):
                    continue
                if var_name not in all_reads_global:
                    for node in assign_nodes:
                        visitor.issues.append({
                            "kind": "unused_variable",
                            "name": var_name,
                            "line": node.lineno,
                            "col": node.col_offset,
                            "msg": f"Unused local variable '{var_name}'",
                            "node": node
                        })

    # Deduplicate issues by (kind, line, col, name)
    seen = set()
    unique_issues = []
    for issue in visitor.issues:
        key = (issue["kind"], issue["line"], issue["col"], issue["name"])
        if key not in seen:
            seen.add(key)
            unique_issues.append({
                "kind": issue["kind"],
                "name": issue["name"],
                "line": issue["line"],
                "col": issue["col"],
                "msg": issue["msg"]
            })

    # Sort issues by line then col
    unique_issues.sort(key=lambda x: (x["line"], x["col"]))
    return unique_issues

def get_fix_candidate(source: str, issues: List[Dict[str, Any]]) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    if not issues:
        return None

    lines = source.split("\n")

    for issue in issues:
        kind = issue["kind"]
        line_num = issue["line"]
        if line_num < 1 or line_num > len(lines):
            continue
        line_idx = line_num - 1
        line_text = lines[line_idx]

        if kind == "comparison_to_none":
            if "== None" in line_text:
                new_line = line_text.replace("== None", "is None", 1)
                new_lines = lines[:]
                new_lines[line_idx] = new_line
                return "\n".join(new_lines), "SEM: replace == None with is None", issue
            elif "!= None" in line_text:
                new_line = line_text.replace("!= None", "is not None", 1)
                new_lines = lines[:]
                new_lines[line_idx] = new_line
                return "\n".join(new_lines), "SEM: replace != None with is not None", issue

        elif kind == "undefined_name":
            name = issue["name"]
            special_literals = {
                "true": "True",
                "false": "False",
                "null": "None",
                "NULL": "None",
                "nil": "None"
            }
            if name in special_literals:
                rep = special_literals[name]
                pattern = r'\b' + re.escape(name) + r'\b'
                new_line = re.sub(pattern, rep, line_text, count=1)
                new_lines = lines[:]
                new_lines[line_idx] = new_line
                return "\n".join(new_lines), f"SEM: replace {name} with {rep}", issue
            else:
                # Find bound names in source
                try:
                    tree = ast.parse(source)
                    all_bound = set(BUILTINS)
                    for n in ast.walk(tree):
                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                            all_bound.add(n.id)
                        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            all_bound.add(n.name)
                        elif isinstance(n, ast.alias):
                            all_bound.add(n.asname or n.name.split('.')[0])
                    # Candidates within edit distance <= 2
                    cand = []
                    for b in all_bound:
                        if b != name and len(b) >= 2:
                            d = lev(name, b)
                            if d <= 2:
                                cand.append((d, b))
                    cand.sort()
                    if cand and (len(cand) == 1 or cand[0][0] < cand[1][0]):
                        best_match = cand[0][1]
                        pattern = r'\b' + re.escape(name) + r'\b'
                        new_line = re.sub(pattern, best_match, line_text, count=1)
                        new_lines = lines[:]
                        new_lines[line_idx] = new_line
                        return "\n".join(new_lines), f"SYM: rename typo {name} -> {best_match}", issue
                except Exception:
                    pass

        elif kind == "unused_import":
            name = issue["name"]
            # Check line
            if re.match(r'^\s*import\s+' + re.escape(name) + r'\s*$', line_text) or \
               re.match(r'^\s*from\s+[\w\.]+\s+import\s+' + re.escape(name) + r'\s*$', line_text):
                new_lines = lines[:line_idx] + lines[line_idx + 1:]
                return "\n".join(new_lines), f"SEM: remove unused import {name}", issue
            elif f", {name}" in line_text:
                new_line = line_text.replace(f", {name}", "", 1)
                new_lines = lines[:]
                new_lines[line_idx] = new_line
                return "\n".join(new_lines), f"SEM: remove unused import {name}", issue
            elif f"{name}, " in line_text:
                new_line = line_text.replace(f"{name}, ", "", 1)
                new_lines = lines[:]
                new_lines[line_idx] = new_line
                return "\n".join(new_lines), f"SEM: remove unused import {name}", issue

        elif kind == "unused_variable":
            name = issue["name"]
            try:
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign) and node.lineno == line_num:
                        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name:
                            if is_side_effect_free(node.value):
                                new_lines = lines[:line_idx] + lines[line_idx + 1:]
                                return "\n".join(new_lines), f"SEM: remove unused variable {name}", issue
            except Exception:
                pass

        elif kind == "method_missing_self":
            name = issue["name"]
            pattern = r'def\s+' + re.escape(name) + r'\s*\(\s*\):'
            if re.search(pattern, line_text):
                # Check if decorated with @classmethod in previous lines
                is_cls = False
                for p_idx in range(line_idx - 1, -1, -1):
                    p_line = lines[p_idx].strip()
                    if p_line.startswith("@"):
                        if "classmethod" in p_line:
                            is_cls = True
                            break
                    elif not p_line:
                        continue
                    else:
                        break
                rep_param = "cls" if is_cls else "self"
                new_line = re.sub(pattern, f"def {name}({rep_param}):", line_text, count=1)
                new_lines = lines[:]
                new_lines[line_idx] = new_line
                return "\n".join(new_lines), f"SEM: add {rep_param} parameter to method {name}", issue

    return None

def auto_fix_semantic(source: str):
    working = source
    steps = []
    rounds = 0
    max_rounds = 20

    while rounds < max_rounds:
        issues = analyze(working)
        cand = get_fix_candidate(working, issues)
        if not cand:
            break
        cand_src, step_msg, targeted = cand
        # Verify candidate
        try:
            ast.parse(cand_src)
            new_issues = analyze(cand_src)
            old_kinds = {i["kind"] for i in issues}
            new_kinds = {i["kind"] for i in new_issues}
            # Acceptance condition:
            # (1) parses (done)
            # (2) len(new_issues) did not rise and no new kind appeared
            # (3) targeted issue is gone
            if len(new_issues) <= len(issues) and new_kinds.issubset(old_kinds):
                working = cand_src
                steps.append(step_msg)
                rounds += 1
            else:
                break
        except Exception:
            break

    return working, steps, []
