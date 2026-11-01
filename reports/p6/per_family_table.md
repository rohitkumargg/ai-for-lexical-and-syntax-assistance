# Agent Manipulation Detection: Per-Family Generalization Matrix

| Family | Split | Total | Detected | Missed | Recall |
|---|---|---|---|---|---|
| `approve_request` | HELDOUT | 52 | 52 | 0 | 100.0% |
| `hidden_directive` | HELDOUT | 52 | 50 | 2 | 96.2% |
| `role_reversal` | HELDOUT | 52 | 45 | 7 | 86.5% |
| `bypass_gate` | TRAIN | 52 | 50 | 2 | 96.2% |
| `developer_mode` | TRAIN | 52 | 37 | 15 | 71.2% |
| `fake_verdict` | TRAIN | 52 | 42 | 10 | 80.8% |
| `ignore_instruction` | TRAIN | 52 | 48 | 4 | 92.3% |
| `system_override` | TRAIN | 52 | 52 | 0 | 100.0% |
