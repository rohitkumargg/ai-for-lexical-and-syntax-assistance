# Python Language Support in Hybrid AI-Assisted Compiler IDE

## 1. Architecture Overview
The Hybrid AI-Assisted Compiler IDE features a pluggable multi-language front-end architecture:
- **C Pipeline**: Uses ANTLR4-generated lexer/parser with a grammar listener, deterministic C correction rules, and optional AI model patch fallbacks.
- **Python Pipeline**: Uses CPython's native `ast` module (no ANTLR, no neural network dependency). All syntax repairs, semantic diagnostics, and security patches are deterministic rule-based transformations applied via exact line and column coordinates to preserve formatting, whitespace, and comments without relying on `ast.unparse`.

Language selection is mediated by `compiler/languages/__init__.py`, supporting dynamic registration, extension detection, and language-specific workspace persistence in the Monaco GUI.

---

## 2. Python Repair Pipeline Flowchart
```
                [ Input Python Source Code ]
                             │
                             ▼
                    ┌─────────────────┐
                    │  Initial Parse  │ ── (ast.parse)
                    └─────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼ (Syntax Error)                  ▼ (Clean AST)
   ┌──────────────────┐                       │
   │  Syntax Repair   │                       │
   │ (Candidate Loop) │                       │
   └──────────────────┘                       │
            │                                 │
     (Parsed Cleanly)                         │
            └────────────────┬────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Semantic Phase  │ ── (Scope & Def/Use Analysis)
                    │  & Auto-Fixes   │ ── (ACCEPT-ONLY-IF-SAFER Guard)
                    └─────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Security Phase  │ ── (Taint Analysis & Rule Engine)
                    │  & Auto-Fixes   │ ── (ACCEPT-ONLY-IF-SAFER Guard)
                    └─────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Green Metrics  │ ── (Energy & System Profiling)
                    └─────────────────┘
                             │
                             ▼
                  [ Final Result Payload ]
```

---

## 3. Rules and Identifiers

### Syntax Repair Rules
- **Token-Level (`LEX:`)**:
  - `else if -> elif`: Convert C-style `else if` to Python `elif`.
  - `print statement -> call`: Convert Python 2 `print "..."` to `print(...)`.
  - `&&/|| -> and/or`: Replace C logical operators with Python keywords.
  - `x++ / x-- -> x += 1 / x -= 1`: Convert increment/decrement operators.
  - `keyword typo <typo> -> <kw>`: Correct typos in Python keywords within edit distance.
- **Structural (`RULE:`)**:
  - `added ':'`: Insert missing colons on compound statement headers (`if`, `for`, `def`, etc.).
  - `closed ')' / ']' / '}'`: Insert missing closing brackets.
  - `closed string`: Close unterminated single/double quote literals.
  - `= -> ==`: Replace assignment operator in condition expressions.
  - `indent -> <spaces>`: Adjust invalid indentation to valid scope levels.
  - `convert tabs to spaces`: Expand inconsistent leading tabs to 4 spaces.

### Semantic Rules
- `undefined_name` (Auto-fix for typos / Python literals `true`/`false`/`null` -> `True`/`False`/`None`).
- `unused_import` (Auto-fix: delete unused import statements).
- `unused_variable` (Auto-fix: remove assignments with side-effect-free RHS).
- `comparison_to_none` (Auto-fix: `== None` -> `is None`, `!= None` -> `is not None`).
- `method_missing_self` (Auto-fix: add `self` or `cls` parameter to methods).
- `call_arity_mismatch` (Report-only: parameter count mismatch in same-file calls).
- `return_outside_function`, `break_outside_loop`, `continue_outside_loop` (Report-only).
- `unreachable_code` (Report-only: statements after return, raise, break, continue).

### Security Rules
- `PY-SEC-01` (Auto-fix): `yaml.load(x)` without Loader -> `yaml.safe_load(x)`.
- `PY-SEC-02` (Auto-fix): Weak hash `hashlib.md5`/`sha1` -> `hashlib.sha256`.
- `PY-SEC-03` (Auto-fix): `eval(input(...))` or tainted eval -> `ast.literal_eval(...)` with `import ast`.
- `PY-SEC-04` (Auto-fix): `subprocess.<fn>("<cmd>", shell=True)` without shell metachars -> word list.
- `PY-SEC-05` (Auto-fix): `requests.<fn>(..., verify=False)` -> `verify=True`.
- `PY-SEC-06` (Auto-fix): `Flask.run(debug=True)` -> `debug=False`.
- `PY-SEC-07` (Report-only): Hardcoded password/secret string literals. Suggests `os.environ`.
- `PY-SEC-08` (Report-only): SQL injection via string concatenation or formatting. Suggests parameterized queries.
- `PY-SEC-09` (Report-only): Dangerous functions (`exec`, `pickle.load`, complex `shell=True`).

---

## 4. Limitations
- **No AI Model for Python**: Python repair runs exclusively via deterministic syntax and AST rules.
- **No Static Type Checking**: Type incompatibilities and attribute resolution on dynamic objects are not checked.
- **Single-File Analysis**: Cross-file imports, project packages, and external module symbols are not resolved.
- **Intra-Scope Taint Tracking**: Taint tracking tracks sources (`input`, `sys.argv`, `os.environ`) within the local module/function scope and does not perform inter-procedural data flow tracking.
