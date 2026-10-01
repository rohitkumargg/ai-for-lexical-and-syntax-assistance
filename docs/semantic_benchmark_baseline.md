# Baseline Semantic Benchmark Table (Stage 1)

- **Total C files scanned**: 112
- **Total runtime**: 30.09s
- **Note**: Only 9 of 31 kinds appear in `examples/`, so the fault-injected set (Stage 3) will be the main per-kind measure.

| Issue Kind | Detected | Standalone Fixed | Standalone Accepted | Pipeline Fixed | Pipeline Accepted | Accept Rate (Pipe) | Top Rejection Reason |
|---|---|---|---|---|---|---|---|
| `arrow_on_value` | 1 | 1 | 1 | 1 | 1 | 100.0% | N/A |
| `call_arity_mismatch` | 1 | 1 | 1 | 1 | 1 | 100.0% | N/A |
| `case_outside_switch` | 1 | 1 | 1 | 1 | 1 | 100.0% | N/A |
| `dot_on_pointer` | 1 | 1 | 1 | 1 | 1 | 100.0% | N/A |
| `duplicate_member` | 1 | 1 | 1 | 1 | 1 | 100.0% | N/A |
| `invalid_dereference` | 2 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `invalid_operand_type` | 6 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `pointer_assignment_warning` | 2 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `prototype_mismatch` | 1 | 1 | 1 | 1 | 1 | 100.0% | N/A |
| `redeclared` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `redeclared_struct` | 1 | 1 | 1 | 1 | 1 | 100.0% | N/A |
| `return_type_mismatch` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `shadow_warning` | 1 | 1 | 1 | 1 | 1 | 100.0% | N/A |
| `too_many_initializers` | 1 | 1 | 1 | 1 | 1 | 100.0% | N/A |
| `type_mismatch` | 3 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `undeclared` | 66 | 0 | 0 | 1 | 1 | 1.5% | N/A |
| `unknown_struct_type` | 2 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `unused` | 54 | 50 | 31 | 30 | 30 | 55.6% | Target issue remained after fix |