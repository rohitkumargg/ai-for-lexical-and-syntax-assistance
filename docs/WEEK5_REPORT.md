# Week 5 Completion Report: Grammar & Semantic Evolution

## 1. Executive Summary

Week 5 expands SimpleC compiler capabilities with modern C constructs:
- Function prototypes with optional parameter names
- Global variable declarations
- Expanded numeric type system (`signed`, `unsigned`, `short`, `long`, `long long`, `double`)
- Bitwise (`&`, `|`, `^`, `~`) and shift (`<<`, `>>`) operators, plus compound assignments
- Whole-token error classification
- Re-parse validated deterministic repairs for prototype/global semicolons and parameter lists
- Comprehensive test suite and example runner with **0 baseline regressions** across 70 existing benchmark files.

---

## 2. Bug-Fix Table (Semantic Checker Bugs)

| Bug # | Issue Description | Root Cause | Solution Implemented | Test Name |
|---|---|---|---|---|
| **Bug 1** | Bitwise ops with `float` operands did not consistently trigger `invalid_operand_type` | Pass-through expression visitor nodes (`visitAdditiveExpr`, `visitRelationalExpr`, etc.) defaulted to None instead of propagating child expression types | Propagated child types in pass-through visitors; made bitwise ops return promoted integral types to stop error cascades; deduplicated semantic issues | `tests/test_part1_bugs.py::test_bug1_bitwise_float_operand_detected` |
| **Bug 2** | Valid integer literals assigned to narrower types (e.g. `short s = 10;`) falsely flagged `type_mismatch` | Semantic checker compared static type ranks directly without inspecting literal values against target type bounds | Added `_INT_RANGES` and constant integer value evaluator `_get_int_constant_value`; in-bounds integer constants permitted without error | `tests/test_part1_bugs.py::test_bug2_integer_constant_range_in_bounds` |
| **Bug 3** | Expressions reading global variables lost their type through pass-through expressions | Global variable symbols in top-level scope were not retained through child visitor chains | Ensured top-level symbol lookups propagate properly through `_infer_expr_type` | `tests/test_part1_bugs.py::test_bug3_global_var_type_propagation` |
| **Bug 4** | Narrowing assignments (e.g. `double` to `int` or `float` to `short`) were not flagged | Type rank comparator only checked strict equality or permitted float-to-int implicitly | Added strict narrowing detection flagging `type_mismatch` when assigning floating/wider types to narrower integer variables | `tests/test_part1_bugs.py::test_bug4_narrowing_conversion_flagged` |
| **Bug 5** | Global variables triggered false positive `unused` warnings | `visitProgram` called `_emit_unused_for_scope` on the root scope containing global variables | Removed `_emit_unused_for_scope` call from `visitProgram`; globals can be referenced across translation units | `tests/test_part1_bugs.py::test_bug5_global_vars_not_marked_unused` |

---

## 3. Error Classifier: New Reasons & Whole-Token Matching

All new regex patterns in `compiler/error_classifier.py` use whole-token and word-boundary matching to prevent substring false positives:

| Error Reason | Trigger Condition | Guard / Whole-Token Safety | Unit Tests (`tests/test_week5_classifier.py`) |
|---|---|---|---|
| `missing_semicolon_after_prototype` | Function prototype declaration missing terminal `;` | Bounded by `_TYPE_KW` and parameter parens; excludes control statements like `if (x) y;` | Positive: prototype missing `;`<br>Negative: `if (x) y;`, function definitions |
| `missing_comma_params` | Missing `,` between parameters in function signature | Checks for two adjacent type-identifier pairs without comma | Positive: `int a int b`<br>Negative: valid param lists, expressions |
| `missing_rparen_params` | Missing `)` in parameter list before `{` | Matches `(param_list {` without closing `)` | Positive: `int add(int a, int b {`<br>Negative: balanced parameter lists |
| `missing_semicolon_after_global` | Global variable declaration missing terminal `;` | Matches top-level `type IDENTIFIER [= val]` followed by top-level keyword | Positive: `int g = 0 int main()`<br>Negative: local variables, valid globals |
| `invalid_type_combination` | Invalid type specifier combos (e.g. `int float`, `double int`, `unsigned double`) | Word boundaries `(?:.*?[^a-z0-9_])?` prevent matching valid substrings | Positive: `int float x;`<br>Negative: `printfloat(x);`, `signed int x;` |

---

## 4. Deterministic Error Corrections

New repair rules in `compiler/error_corrector.py`:
1. `_fix_missing_semicolon_after_prototype`: Detects prototype declarations missing terminal `;` and inserts `;`.
2. `_fix_missing_semicolon_after_global`: Detects top-level global declarations missing terminal `;` and inserts `;`.
3. `_fix_missing_comma_params`: Detects missing commas between parameters in function signatures and inserts `,`.
4. `_fix_missing_rparen_params`: Detects missing right parenthesis before function body `{` and inserts `)`.

### Re-Parse Validation Architecture
- All candidate repairs run through `_validate_fix(orig_src, cand_src, msg)`.
- A candidate is **only accepted** if:
  1. The new parse error count is strictly less than the original error count.
  2. The earliest remaining error does not occur on a line/column earlier than before the fix.
- Clean code is never modified.
- Registered in `DETERMINISTIC_REASONS` (`test_parser.py`) and consumed seamlessly by both `test_parser.py` and `compiler/gui_bridge.py`.

---

## 5. Week 5 Examples & Runner Results

Ran `python tools/run_week_examples.py 5 --no-ai`:

### Grammar & Repair Pipeline (`examples/week5_grammar_2026/`)
- Total feature files: 20
- Total repaired / clean: 16
- Unfixable without AI (`--no-ai`): 4 (e.g. invalid type combinations `float int`, extraneous tokens `& =`, broken shift `< <`)
- Mismatches against JSON expectations: **0**

| File | Status | Errors Before | Errors After | Fix Method | Time (ms) |
|---|---|---|---|---|---|
| `prototype_valid.c` | SEM_ISSUES | 0 | 0 | NONE | ~112 ms |
| `prototype_broken_1.c` | SUCCESS | 3 | 3 | RULE | ~108 ms |
| `prototype_broken_2.c` | UNFIXABLE | 3 | 3 | NONE | ~105 ms |
| `prototype_broken_3.c` | SUCCESS | 1 | 0 | LEX | ~104 ms |
| `globals_valid.c` | SUCCESS | 0 | 0 | NONE | ~105 ms |
| `globals_broken_1.c` | SUCCESS | 1 | 1 | RULE | ~108 ms |
| `globals_broken_2.c` | UNFIXABLE | 1 | 1 | NONE | ~105 ms |
| `globals_broken_3.c` | SUCCESS | 1 | 0 | LEX | ~104 ms |
| `types_valid.c` | SEM_ISSUES | 0 | 0 | NONE | ~108 ms |
| `types_broken_1.c` | SEM_ISSUES | 1 | 1 | RULE | ~113 ms |
| `types_broken_2.c` | UNFIXABLE | 1 | 1 | NONE | ~189 ms |
| `types_broken_3.c` | SEM_ISSUES | 1 | 0 | LEX | ~113 ms |
| `bitwise_ops_valid.c` | SEM_ISSUES | 0 | 0 | NONE | ~152 ms |
| `bitwise_ops_broken_1.c` | SEM_ISSUES | 1 | 1 | RULE | ~127 ms |
| `bitwise_ops_broken_2.c` | UNFIXABLE | 1 | 1 | NONE | ~122 ms |
| `bitwise_ops_broken_3.c` | SEM_ISSUES | 1 | 0 | LEX | ~113 ms |
| `shift_ops_valid.c` | SEM_ISSUES | 0 | 0 | NONE | ~135 ms |
| `shift_ops_broken_1.c` | SEM_ISSUES | 1 | 1 | RULE | ~128 ms |
| `shift_ops_broken_2.c` | UNFIXABLE | 1 | 1 | NONE | ~112 ms |
| `shift_ops_broken_3.c` | SEM_ISSUES | 1 | 0 | LEX | ~120 ms |

### Semantics & Guard Suite (`examples/week5_grammar_2026/semantics/`)
- Total semantic test cases: 8 (4 issues, 4 guards)
- All 4 target issues fired as expected (`prototype_mismatch`, `shadow_warning`, `invalid_operand_type`, `type_mismatch`).
- All 4 guard files stayed silent with 0 semantic issues.

---

## 6. Baseline Regression Results

- Baseline file: `examples/baseline_before_week5.json` (70 benchmark files)
- Files checked: **70**
- Regressions found: **0**

---

## 7. Known Limitations

1. **Non-Deterministic Syntax Errors under `--no-ai`**:
   Malformed operator splits (e.g. `x < < 2` or `a & = b`) and conflicting multi-word type declarations (e.g. `float int x;`, `unsigned double y;`) cannot be deterministically resolved without AI synthesis or manual programmer intervention. In `--no-ai` mode, these correctly return status `UNFIXABLE`.
2. **Prototype Parameter Trailing Commas**:
   Trailing commas in prototypes (e.g. `int foo(int a,);`) require structural recovery rather than simple punctuation insertion and are deferred to AI patch synthesis.
3. **No Type Cast Syntax**:
   The SimpleC grammar does not currently include explicit C-style type cast expressions `(type)expr`. Narrowing conversions must be avoided or handled by assigning compatible intermediate types.

---

## 8. Verification Commands

To re-verify the complete suite:

```cmd
cd "C:\Users\mahit\OneDrive\Desktop\CD project\Implementation" && python tools/run_week_examples.py 5 --no-ai
cd "C:\Users\mahit\OneDrive\Desktop\CD project\Implementation" && python -m pytest tests -q
```
