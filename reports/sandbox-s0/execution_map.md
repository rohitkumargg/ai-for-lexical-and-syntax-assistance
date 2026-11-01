# Execution and Compilation Path Audit (S0)

| Subsystem | Exact Command | Working Directory | Environment | Timeouts | User-Visible Output |
|---|---|---|---|---|---|
| `compiler/patch_validator.py` (`PatchValidator._run_syntax_check`) | `["gcc", "-fsyntax-only", "-Wall", "-Werror=implicit-function-declaration", "candidate.c"]` | Temp dir `antigravity_sandbox_*` | Scraped `PATH` (MinGW + System32), `TMP`/`TEMP` | 5.0 s | Redacted compiler syntax error text |
| `compiler/program_executor.py` (`ProgramExecutor.run_c_program` compile phase) | `["gcc", "-O0", "-Wall", "-Werror=implicit-function-declaration", "program.c", "-o", "program.exe"]` | Temp dir `antigravity_sandbox_*` | Scraped `PATH`, `SystemRoot`, `TMP`, `TEMP` | 5.0 s | Redacted compiler error in terminal |
| `compiler/program_executor.py` (`ProgramExecutor.run_c_program` run phase) | `["<temp_dir>\\program.exe"]` | Temp dir `antigravity_sandbox_*` | Scraped `PATH`, `SystemRoot`, `TMP`, `TEMP` | 4.0 s (max 10.0 s) | `stdout`, `stderr`, exit code |
| `compiler/program_executor.py` (`ProgramExecutor.run_python_program`) | `["python.exe", "-u", "-B", "program.py"]` | Temp dir `antigravity_sandbox_*` | Scraped `PATH`, `SystemRoot`, `PYTHONUNBUFFERED=1`, `TMP`, `TEMP` | 4.0 s (max 10.0 s) | `stdout`, `stderr`, exit code |
| `compiler/benchmark_engine.py` | Calls `RepairWorkflow` -> `PatchValidator._run_syntax_check` | Temp dir | Scraped `safe_env` | 5.0 s | Benchmark pass/fail status |
| `compiler/green_engine.py` | Profiling wrappers around `RepairWorkflow` & `ProgramExecutor` | Host cwd | Host env | Inherited | Latency, joules, and green score |
| `tools/run_matrix_evaluator.py` | Direct host `gcc` and `python` oracle runs | Host temp dir | Host env | 5.0 s | CSV matrix and stdout |
| `tools/inventory_programs.py` | Syntax-only `gcc -fsyntax-only` & AST parsing | Host cwd | Host env | 10.0 s | Inventory CSV |

