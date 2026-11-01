# Security Fix 2026 Benchmark Results

| Case Name | Before Status | After Status | Fixed | Code Match | Idempotent | Result |
|:---|:---|:---|:---:|:---:|:---:|:---:|
| `e02_scanf_widths` | `SUCCESS` | `SUCCESS` | True | False | True | **FAIL** |
| `e03_gets` | `BLOCKED_SECURITY` | `SUCCESS` | True | True | True | **PASS** |
| `e04_strcpy` | `SUCCESS_WITH_WARNINGS` | `SUCCESS` | True | False | True | **FAIL** |
| `e05_strcat` | `SUCCESS_WITH_WARNINGS` | `SUCCESS` | True | True | True | **PASS** |
| `e06_sprintf` | `SUCCESS_WITH_WARNINGS` | `SUCCESS` | True | True | True | **PASS** |
| `e07_printf_user` | `SUCCESS_WITH_WARNINGS` | `SUCCESS` | True | True | True | **PASS** |
| `e08_pointer_destination` | `SUCCESS_WITH_WARNINGS` | `SUCCESS_WITH_WARNINGS` | False | True | True | **PASS** |
| `e09_taint_scope` | `SUCCESS_WITH_WARNINGS` | `SUCCESS_WITH_WARNINGS` | False | True | True | **PASS** |
| `e10_prototype_only` | `SUCCESS` | `SUCCESS` | False | True | True | **PASS** |
| `e11_allowlist_guard` | `SUCCESS` | `SUCCESS` | False | True | True | **PASS** |

## Summary

4 failures encountered:

- e01_cmd_injection: broken file examples\security_fix_2026\e01_cmd_injection_broken.c does not exist
- e02_scanf_widths: before status mismatch: expected SUCCESS_WITH_WARNINGS, got SUCCESS
- e02_scanf_widths: corrected code does not match expected fix
- e04_strcpy: corrected code does not match expected fix
