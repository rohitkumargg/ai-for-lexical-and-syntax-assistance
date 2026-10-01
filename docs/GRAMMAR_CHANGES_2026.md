# SimpleC Grammar Changes and Architecture (2026 Evolution)

## 1. ANTLR Regeneration Command

The ANTLR tool jar is located at:
`grammar/antlr-4.13.2-complete.jar` (v4.13.2)

Because ANTLR 4.13.2 requires Java 11+ (class file version 55.0+), the Java runtime packaged with the IDE / system extensions is used:
`C:\Users\rohit\.antigravity-ide\extensions\redhat.java-1.56.0-win32-x64\jre\21.0.12.1-win32-x86_64\bin\java.exe` (Java 21)

### Exact Windows Command to Regenerate Parser:
```powershell
& "C:\Users\rohit\.antigravity-ide\extensions\redhat.java-1.56.0-win32-x64\jre\21.0.12.1-win32-x86_64\bin\java.exe" -jar grammar/antlr-4.13.2-complete.jar -Dlanguage=Python3 -visitor -listener -o generated grammar/SimpleC.g4
```

---

## 2. Parse Error Flow Summary

A parse error in the system flows through the following stages:

1. **Input Ingestion & Tokenization**:
   - The user provides C source code via CLI (`test_parser.py`) or Flask GUI (`compiler/gui_bridge.py`).
   - `parse_source(source_text)` feeds `source_text` to `InputStream`, `SimpleCLexer`, `CommonTokenStream`, and `SimpleCParser`.
   - Two instances of `CollectingErrorListener` are attached: one for stage `LEX` on `SimpleCLexer`, and one for stage `PARSE` on `SimpleCParser`.

2. **Phase 1: Lexical Cleanup (`compiler/lexical_corrector.py`)**:
   - Runs before AST construction.
   - Normalizes unicode copy/paste punctuation (e.g. curly quotes, em-dashes, full-width semicolons/commas/parentheses).
   - Normalizes malformed compound tokens (e.g. `=<=` -> `<=`).
   - Performs conservative dictionary-based keyword typo fixes (e.g. `itn` -> `int`, `whlie` -> `while`, `viod` -> `void`, `contniue` -> `continue`).
   - Strictly ignores single-letter identifiers (e.g. `i`) to avoid destructive changes.

3. **Phase 2: Syntax Error Classification & Repair Loop**:
   - The code is parsed with `SimpleCParser.program()`.
   - If `has_any_errors(listeners)` is True:
     - `get_first_error_object(listeners)` extracts the earliest error (`stage`, `line`, `column`, `msg`, `offending`).
     - `classify_error_message(msg)` in `compiler/error_classifier.py` inspects the message and categorizes it into an `ErrorClassification` with reasons such as `missing_semicolon`, `missing_rbrace`, `missing_lparen`, `missing_rparen`, `missing_rhs`, `extraneous_token`, `mismatched_token`, etc.
     - **Identifier Typo Correction**: If the offending symbol is an identifier, `fix_identifier_typo_at` checks Levenshtein distance against known symbols in the symbol table (`build_symbols(tree)`).
     - **Deterministic Correction**: If the error matches a known deterministic repair rule, `apply_correction(...)` in `compiler/error_corrector.py` inserts missing semicolons, balances braces/parentheses, cleans dangling declarations, or repairs missing RHS.
     - **AI Fallback**: If the error is not deterministically fixable or if it is a `LEX` stage error, `ai_generate_patch_candidates` in `compiler/ai_error_corrector.py` invokes CodeT5+LoRA to generate candidate source patches. The candidate that reduces parse error count most cleanly is selected.
     - The repair loop continues until parsing is error-free or until iteration/repetition limits are reached.

4. **Phase 3: Semantic Analysis (`compiler/semantic_checker.py`)**:
   - Once the AST parses cleanly, `SemanticChecker` (a visitor over `SimpleCVisitor`) traverses the AST.
   - Maintains a scoped symbol table stack (`_scopes`), function signatures (`_funcs`), loop nesting depth (`_loop_depth`), and tracks variable usage.
   - Verifies:
     - Undeclared identifier uses
     - Redeclarations in the same scope
     - Use before declaration
     - Unused variables
     - Type compatibility & narrowing checks in assignments and initializers
     - Function return type compatibility (and void returns)
     - Function call arity and argument types
     - `break` / `continue` outside of loops
   - Automatic fixes for simple semantic issues (`unused` variable removal, `undeclared` identifier typo fix) are applied iteratively.

5. **Phase 4: Security Analysis (`compiler/security_checker.py`, `taint_checker.py`, `string_flow_checker.py`)**:
   - Audits source code for dangerous APIs (`system`, `popen`, `gets`, `strcpy`, `sprintf`), tainted user input flows, and buffer overflow risks.
   - `SecurityAutoFixer` rewrites unsafe functions to safer equivalents (`gets` -> `fgets`, `strcpy` -> `strncpy`, `sprintf` -> `snprintf`).

6. **Phase 5: Metrics and Green Reporting (`compiler/green_metrics.py`, `green_scorer.py`)**:
   - Collects runtime phase latencies, repair counts (lex, rule, AI, sem), energy/CPU usage, and computes an overall Green Score.

---

## 3. Week 5: Grammar & Semantic Additions

### Features Implemented:
1. **Function Prototypes**:
   - Top-level function declarations ending with `;`:
     `int add(int a, int b);`
     `int multiply(int, int);`
     `void run(void);`
   - Parameter names are optional in prototypes.
   - Prototypes are registered in the symbol table so calls before definition are legal.
   - Definitions following prototypes are verified for matching return type, parameter count, and parameter types (`prototype_mismatch`).
2. **Global Variable Declarations**:
   - Top-level variable declarations (with and without initializers):
     `int global_counter = 0;`
     `float scale_factor;`
   - Scoped at the top-level / global scope, visible to all functions.
   - Local declarations inside functions may shadow globals (shadowing warning / tracked).
3. **Additional Primitive Types**:
   - `unsigned`, `signed`, `short`, `long`, `long long`, `double`, `unsigned int`, `unsigned short`, `unsigned long`, `unsigned long long`, `signed int`, `signed short`, `signed long`, `signed long long`.
   - Updated type ranking, promotion, and narrowing checks in `semantic_checker.py`.
4. **Bitwise, Shift, and Compound Assignment Operators**:
   - Bitwise unary: `~` (bitwise NOT) at unary precedence.
   - Shift operators: `<<`, `>>` placed between additive and relational expressions.
   - Bitwise AND: `&` placed between equality and bitwise XOR.
   - Bitwise XOR: `^` placed between bitwise AND and bitwise OR.
   - Bitwise OR: `|` placed between bitwise XOR and logical AND.
   - Compound assignments: `&=`, `|=`, `^=`, `<<=`, `>>=`, `%=`.
   - Semantic validation: Operands of bitwise (`&`, `|`, `^`, `~`) and shift (`<<`, `>>`) expressions must be integral types (flagged as `invalid_operand_type`).

---

## 4. Decisions and Limitations

- **Prototype vs Function Definition**: In ANTLR, a top-level unit can be either a function definition (`functionDef`) or a top-level declaration (`topLevelDeclaration`). To avoid ambiguities, `functionDeclaration` (prototype) is explicitly specified as `typeSpecifier IDENTIFIER LPAREN prototypeParamList? RPAREN SEMI`.
- **Prototype Parameters**: Parameter names in prototypes are optional (e.g. `int foo(int, float);` as well as `int foo(int a, float b);`, and `void foo(void);`).
- **Integral Check for Bitwise/Shift Operators**: Types `char`, `short`, `int`, `long`, `long long` (and their `unsigned`/`signed` variants) are integral. `float` and `double` are non-integral; using bitwise or shift operations on `float`/`double` raises `invalid_operand_type`.
- **Top-Level Ordering**: Declarations and function definitions can be freely interleaved at the top level.

---

## 5. Week 5 Completion Summary

### Completed Milestones
1. **Semantic Bug Fixes**:
   - **Bug 1 (Bitwise operand propagation)**: Pass-through expressions (`additiveExpr`, `relationalExpr`, etc.) now propagate child types so bitwise operations on float operands consistently trigger `invalid_operand_type`. Bitwise operators return promoted integral types to stop cascade errors, and issues are deduplicated.
   - **Bug 2 (Integer constant ranges)**: Added `_INT_RANGES` and constant integer value extraction; in-range integer literals assigned to narrower integral types (e.g. `short s = 10;`) do not emit false positive `type_mismatch`.
   - **Bug 3 (Global variable propagation)**: Expressions reading global variables correctly preserve the variable's type through pass-through expressions.
   - **Bug 4 (Narrowing conversions)**: Assignments from `double`/`float` or wider integer types to narrower integer types without cast correctly flag `type_mismatch`.
   - **Bug 5 (Global unused suppression)**: Global variables are excluded from the `unused` variable warning since globals can be accessed externally or in other compilation units.

2. **Whole-Token Error Classifier (`compiler/error_classifier.py`)**:
   - 5 reasons added: `missing_semicolon_after_prototype`, `missing_comma_params`, `missing_rparen_params`, `missing_semicolon_after_global`, `invalid_type_combination`.
   - Word boundaries and token patterns ensure no false positives: `printfloat` does not trigger `invalid_type_combination`; `if (x) y;` does not trigger `missing_semicolon_after_prototype`.

3. **Deterministic Error Repair (`compiler/error_corrector.py`)**:
   - Deterministic repairs implemented for:
     - Missing semicolon after function prototype
     - Missing semicolon after global variable declaration
     - Missing comma between parameters in function headers
     - Missing right parenthesis in parameter lists
   - Re-parse validation ensures a repair candidate is accepted only if the total parse error count decreases and no new earlier error is introduced. Clean code remains untouched.
   - All 4 reasons registered in `DETERMINISTIC_REASONS` (`test_parser.py`) shared directly with `compiler/gui_bridge.py`.

4. **Examples and Runner**:
   - Complete test suite in `examples/week5_grammar_2026/` covering 5 features (`prototype`, `globals`, `types`, `bitwise_ops`, `shift_ops`) with valid files, broken files (missing token, extraneous token, typo), and expected JSONs.
   - `semantics/` subfolder covering `prototype_mismatch`, `shadow_warning`, `invalid_operand_type` (&, |, ^, ~, <<, >>), and narrowing, with false-positive guard files for each.
   - `tools/run_week_examples.py` runs files through GUI bridge repair, validates against JSON expectations, checks semantics rules and guards, and verifies 0 baseline regressions.

