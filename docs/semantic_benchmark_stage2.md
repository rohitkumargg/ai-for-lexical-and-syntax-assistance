# Baseline Semantic Benchmark Table (Stage 1)

- **Total C files scanned**: 104
- **Total runtime**: 23.68s
- **Note**: Only 9 of 31 kinds appear in `examples/`, so the fault-injected set (Stage 3) will be the main per-kind measure.

| Issue Kind | Detected | Standalone Fixed | Standalone Accepted | Pipeline Fixed | Pipeline Accepted | Accept Rate (Pipe) | Top Rejection Reason |
|---|---|---|---|---|---|---|---|
| `invalid_dereference` | 2 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `invalid_operand_type` | 6 | 6 | 1 | 6 | 6 | 100.0% | Fixer phase is not idempotent (re-applied change) |
| `pointer_assignment_warning` | 2 | 2 | 2 | 2 | 2 | 100.0% | N/A |
| `prototype_mismatch` | 1 | 1 | 1 | 1 | 1 | 100.0% | N/A |
| `redeclared` | 1 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `shadow_warning` | 1 | 1 | 1 | 1 | 1 | 100.0% | N/A |
| `type_mismatch` | 2 | 0 | 0 | 2 | 2 | 100.0% | N/A |
| `undeclared` | 65 | 0 | 0 | 0 | 0 | 0.0% | N/A |
| `unused` | 54 | 50 | 35 | 39 | 39 | 72.2% | Target issue remained after fix |