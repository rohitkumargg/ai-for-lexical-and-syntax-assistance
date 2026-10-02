# SimpleC Semantic Benchmark Report

### Main Benchmark Table (examples/ excluding examples/semantic/)

- **Files scanned**: 104
- **Runtime**: 14.54s
- **Note**: Only 9 of 31 kinds appear in original examples. The fault-injected set (Stage 3) will be the main per-kind measure.

| Issue Kind | Detected | Standalone Fixed | Standalone Accepted | Pipeline Fixed | Pipeline Accepted | Accept Rate (Pipe) | Top Rejection Reason |
|---|---|---|---|---|---|---|---|
| `invalid_dereference` | 2 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `invalid_operand_type` | 6 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `pointer_assignment_warning` | 2 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `prototype_mismatch` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `redeclared` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `shadow_warning` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `type_mismatch` | 2 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `undeclared` | 65 | 21 | 21 | 21 | 21 | 32.3% | N/A |
| `unused` | 54 | 52 | 52 | 43 | 43 | 79.6% | N/A |

### Rule-Trigger Programs (examples/semantic/)

- **Files scanned**: 8
- **Runtime**: 0.07s
- **Note**: Isolated synthetic tests targeting specific rules.

| Issue Kind | Detected | Standalone Fixed | Standalone Accepted | Pipeline Fixed | Pipeline Accepted | Accept Rate (Pipe) | Top Rejection Reason |
|---|---|---|---|---|---|---|---|
| `arrow_on_value` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `call_arity_mismatch` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `case_outside_switch` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `dot_on_pointer` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `duplicate_member` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `redeclared_struct` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `return_type_mismatch` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `too_many_initializers` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `type_mismatch` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `undeclared` | 1 | 1 | 0 | 0 | 0 | 0.0% | Issue count did not decrease (1 -> 1) |
| `unknown_struct_type` | 2 | 0 | 0 | 0 | 0 | 0.0% | N/A |

### Unused Variable Reconciled Accounting (Main Examples)

- **Detected**: 54
- **Accepted**: 52
- **Rejected**: 0
- **Unfixed**:  2
- **Checksum**: 54 == 52 + 0 + 2 -> **MATCH (detected == accepted + rejected + unfixed)**

#### Rejected Cases (0)
*(None)*

#### Unfixed Cases (3)
- `examples\week5_grammar_2026\semantics\prototype_mismatch_err.c:3` (`b`) -> Fixer produced no edit (declaration pattern not matched)
- `examples\week6_grammar_2026\pointer_errors.c:3` (`pointer`) -> Fixer produced no edit (declaration pattern not matched)