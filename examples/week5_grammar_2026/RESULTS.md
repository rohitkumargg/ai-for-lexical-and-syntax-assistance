# Week 5 Verification Results

- Mode: `--no-ai=True`
- Timestamp: 2026-10-02 03:37:01
- Total feature files: 16
- Total semantic checks: 8
- Baseline regressions: 0
- Overall Status: FAIL

## Grammar & Repair Results

| File | Status | Errors Before | Errors After | Fix Method | Time (ms) |
|---|---|---|---|---|---|
| `prototype_valid.c` | SUCCESS | 0 | 0 | SEM | 124.83 |
| `prototype_broken_1.c` | SUCCESS | 3 | 0 | RULE | 113.89 |
| `prototype_broken_3.c` | SUCCESS | 1 | 0 | LEX | 106.70 |
| `globals_valid.c` | SUCCESS | 0 | 0 | NONE | 108.51 |
| `globals_broken_1.c` | SUCCESS | 1 | 0 | RULE | 114.56 |
| `globals_broken_3.c` | SUCCESS | 1 | 0 | LEX | 107.30 |
| `types_valid.c` | SEM_ISSUES | 0 | 0 | SEM | 125.52 |
| `types_broken_1.c` | SUCCESS | 1 | 0 | RULE | 108.79 |
| `types_broken_3.c` | SUCCESS | 1 | 0 | LEX | 108.76 |
| `bitwise_ops_valid.c` | SUCCESS | 0 | 0 | SEM | 134.57 |
| `bitwise_ops_broken_2.c` | SUCCESS | 1 | 0 | RULE | 116.91 |
| `bitwise_ops_broken_3.c` | SUCCESS | 1 | 0 | LEX | 109.94 |
| `shift_ops_valid.c` | SUCCESS | 0 | 0 | SEM | 121.80 |
| `shift_ops_broken_1.c` | SUCCESS | 1 | 0 | RULE | 122.52 |
| `shift_ops_broken_2.c` | SUCCESS | 1 | 0 | RULE | 114.16 |
| `shift_ops_broken_3.c` | SUCCESS | 1 | 0 | LEX | 111.91 |

## Semantics & Guard Results

| File | Target Issue | Expected To Fire | Found Issues | Result |
|---|---|---|---|---|
| `semantics/prototype_mismatch_err.c` | `prototype_mismatch` | True | 2 (['prototype_mismatch', 'unused']) | **PASS** |
| `semantics/prototype_mismatch_guard.c` | `prototype_mismatch` | False | 0 ([]) | **PASS** |
| `semantics/shadow_warning_err.c` | `shadow_warning` | True | 1 (['shadow_warning']) | **PASS** |
| `semantics/shadow_warning_guard.c` | `shadow_warning` | False | 0 ([]) | **PASS** |
| `semantics/invalid_operand_type_err.c` | `invalid_operand_type` | True | 12 (['invalid_operand_type', 'invalid_operand_type', 'invalid_operand_type', 'invalid_operand_type', 'invalid_operand_type', 'invalid_operand_type', 'unused', 'unused', 'unused', 'unused', 'unused', 'unused']) | **PASS** |
| `semantics/invalid_operand_type_guard.c` | `invalid_operand_type` | False | 0 ([]) | **PASS** |
| `semantics/narrowing_err.c` | `type_mismatch` | True | 4 (['type_mismatch', 'type_mismatch', 'unused', 'unused']) | **PASS** |
| `semantics/narrowing_guard.c` | `type_mismatch` | False | 0 ([]) | **PASS** |

## Baseline Results

70 files checked from `examples/baseline_before_week5.json`: **0 regressions found**.
