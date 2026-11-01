# Security Analysis & Auto-Fix Architecture (2026 Update)

## 1. Six Root Causes Addressed

1. **Unrepaired Command Injections in SecurityAutoFixer**  
   Previously, `SecurityAutoFixer` had detection rules for `system(cmd)` but never generated an auto-repair patch. Any input tainted by external sources (e.g. `scanf`, `gets`) remained vulnerable and blocked compilation without a fix path.

2. **Flawed Security Status Aggregation & Prototype Penalties**  
   `_status_from_security` previously returned `BLOCKED_SECURITY` if the sum of security scores was $\ge 6$, or if any critical issue remained. Furthermore, `compiler/security_checker.py` scored prototype declarations like `int system(char *command);` as dangerous calls with non-constant inputs (3 points) and `system("literal")` as 2 points, causing even safe, clean code to remain blocked. The status logic now blocks exclusively on unresolved `[CRITICAL]` findings; `[WARNING]` or `[HIGH]` produces `SUCCESS_WITH_WARNINGS`; and benign fixed calls produce `[INFO]` (score=0).

3. **Global Unscoped Regex in Taint Checker**  
   `compiler/taint_checker.py` previously executed a single regex across the entire file without function-level scoping, did not recognize sanitizers (allowlist validation guards), and treated numeric `scanf` targets (`%d`, `%f`) as tainted. It is now scoped per function, sanitizes names guarded by `strcmp` checks, and restricts taint strictly to character buffers.

4. **Unvalidated Model Patch Acceptance**  
   `SecurityAutoFixer._apply_ai_security_fixes` blindly accepted any `REPLACE_LINE` from the model as long as the line changed text, resulting in hallucinations such as undeclared buffers (`scanf("%11s", arr)`), wrong destination types (`scanf("%11s", a)` with `int a`), or size mismatches (`%11s` into `char[10]`). All candidate patches now pass through an accept-only-if-safer verifier.

5. **Fragile Deterministic Fixes**  
   Deterministic rules previously used hardcoded bounds like `scanf("%99s")` regardless of array length, generated non-null-terminated `strncpy(dst, src, sizeof(dst))`, and produced incorrect bounds in `strncat`. Deterministic fixes now dynamically calculate buffer lengths ($N - 1$ for `char[N]`), use `snprintf`, and compute proper `strncat` bounds (`sizeof(dst) - strlen(dst) - 1`).

6. **Semantic Analyzer False Positives on Standard C Constructs**  
   The semantic analyzer produced false positives on valid library symbols (`strcmp`, `strlen`, `strcpy`, etc.), reported `call_type_mismatch` due to missing array-to-pointer decay on `char *` arguments, and reported `type_mismatch` on string initialization of character arrays (`char cmd[40] = "ls";`). Built-in library signatures and proper pointer conversions are now registered.

---

## 2. Allowlist Dispatch Architecture & Behavior Change

When a variable $v$ tainted by untrusted input reaches a command-execution sink (such as `system(v)`):
- Rather than leaving the code vulnerable or attempting unstructured string replacement, the fixer generates an explicit allowlist dispatch block:
  ```c
  if (strcmp(v, "ls") == 0) {
      system("ls");
  } else if (strcmp(v, "date") == 0) {
      system("date");
  } else {
      printf("command not allowed\n");
  }
  ```
- **Allowlist Extraction**: The allowed literals default to `["ls", "date"]`, or if the source file already contains fixed calls `system("literal")`, those literal strings are reused in order of appearance.
- **Behavior Change**: An unvalidated user command string is converted into a strictly validated token dispatch where only predefined constant string literals can ever be executed by the host operating system.

---

## 3. Honest Limitations

1. **Command Allowlist Defaults are a Starting Point**  
   The fallback allowlist `["ls", "date"]` provides a secure, compiling template for safe dispatch. Production code must tailor allowlists to application-specific commands and arguments.

2. **Intra-Function Taint Scope Only**  
   Taint tracking is scoped to the enclosing function. Taint propagation across function parameters, global state, heap allocations, or struct member indirections across translation units is not analyzed.

3. **Statically Sized Character Arrays Only**  
   Buffer bound fixes ($N - 1$) and `sizeof` conversions require local or global statically declared character arrays (`char buf[N]`). Pointer parameters, dynamically allocated memory (`malloc`), and pointer variables without known bound declarations remain unedited with an explicit diagnostic (`destination size unknown`) rather than risking unsafe assumptions.
