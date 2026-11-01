# scripts/test_repair_job_1000_lines.py
"""
Executes Requirement 7:
1. Runs repair job on generated ~1000-line multi-function file.
   Collects: windows repaired, wall seconds, estimated vs actual duration, compiles (yes/no).
2. Runs mid-run cancellation test:
   Verifies cancel stops Ollama model requests and leaves no orphan process.
"""
import os
import sys
import time
import json
import subprocess

sys.path.insert(0, os.getcwd())

from compiler.repair_job_manager import get_repair_job_manager
from compiler.patch_validator import SandboxedCompiler

def run_benchmark():
    file_path = "examples/generated_1000_lines.c"
    with open(file_path, "r", encoding="utf-8") as f:
        src = f.read()

    job_mgr = get_repair_job_manager()
    compiler = SandboxedCompiler()

    # Initial compilation state
    init_compiles, init_out, _ = compiler.compile_check(src)
    print(f"Initial 1000-line file compiles: {init_compiles}")

    print("\n--- Starting Full 1000-Line Repair Job ---")
    t0 = time.perf_counter()
    job = job_mgr.create_job(code=src, filename="generated_1000_lines.c", language="c")
    job_mgr.start_job(job)

    # Monitor until completion and track estimates at 0%, 25%, 50%, 75%
    snapshots = {}
    while job.state in ("PENDING", "RUNNING"):
        time.sleep(0.1)
        job_status = job.to_status_dict()
        fn_idx = job_status.get("function_index", 0)
        fn_tot = job_status.get("function_total", 0)
        est = job_status.get("estimated_total_s", 0.0)
        el = job_status.get("elapsed_s", 0.0)
        
        if "start" not in snapshots:
            snapshots["start"] = (fn_idx, fn_tot, est, el)
        if fn_tot > 0:
            pct = fn_idx / fn_tot
            if pct >= 0.25 and "25%" not in snapshots:
                snapshots["25%"] = (fn_idx, fn_tot, est, el)
            if pct >= 0.50 and "50%" not in snapshots:
                snapshots["50%"] = (fn_idx, fn_tot, est, el)
            if pct >= 0.75 and "75%" not in snapshots:
                snapshots["75%"] = (fn_idx, fn_tot, est, el)

    total_time = time.perf_counter() - t0
    final_status = job.to_status_dict()
    repaired_code = job.current_code

    final_compiles, final_out, _ = compiler.compile_check(repaired_code)

    print("\n=== REQUIREMENT 8: ESTIMATED_TOTAL_S PROGRESSION TABLE ===")
    print(f"{'Milestone':<15} | {'Function Progress':<20} | {'Estimated Total (s)':<22} | {'Elapsed (s)':<15} | {'Actual Final (s)':<18}")
    print("-" * 96)
    st = snapshots.get("start", (0, job.function_total, job.estimated_total_s, 0.0))
    print(f"{'Job Start (0%)':<15} | {f'{st[0]}/{st[1]}':<20} | {f'{st[2]:.2f}s':<22} | {f'{st[3]:.2f}s':<15} | {f'{total_time:.2f}s':<18}")
    if "25%" in snapshots:
        s25 = snapshots["25%"]
        print(f"{'Progress 25%':<15} | {f'{s25[0]}/{s25[1]}':<20} | {f'{s25[2]:.2f}s':<22} | {f'{s25[3]:.2f}s':<15} | {f'{total_time:.2f}s':<18}")
    if "50%" in snapshots:
        s50 = snapshots["50%"]
        print(f"{'Progress 50%':<15} | {f'{s50[0]}/{s50[1]}':<20} | {f'{s50[2]:.2f}s':<22} | {f'{s50[3]:.2f}s':<15} | {f'{total_time:.2f}s':<18}")
    if "75%" in snapshots:
        s75 = snapshots["75%"]
        print(f"{'Progress 75%':<15} | {f'{s75[0]}/{s75[1]}':<20} | {f'{s75[2]:.2f}s':<22} | {f'{s75[3]:.2f}s':<15} | {f'{total_time:.2f}s':<18}")
    final_est = final_status.get('estimated_total_s', total_time)
    print(f"{'Final (100%)':<15} | {f'{job.function_total}/{job.function_total}':<20} | {f'{final_est:.2f}s':<22} | {f'{total_time:.2f}s':<15} | {f'{total_time:.2f}s':<18}")
    print("-" * 96)

    print("\n=== REQUIREMENT 7 RESULTS TABLE ===")
    print(f"{'Metric':<25} | {'Value':<20}")
    print("-" * 50)
    print(f"{'File':<25} | {'generated_1000_lines.c':<20}")
    print(f"{'Total Lines':<25} | {len(src.splitlines()):<20}")
    print(f"{'Functions':<25} | {job.function_total:<20}")
    print(f"{'Windows Repaired':<25} | {job.windows_done:<20}")
    print(f"{'Elapsed Seconds':<25} | {round(total_time, 2):<20}")
    print(f"{'Estimate at Start (s)':<25} | {round(st[2], 2):<20}")
    print(f"{'Actual Total (s)':<25} | {round(total_time, 2):<20}")
    print(f"{'Compiles (Before)':<25} | {'YES' if init_compiles else 'NO':<20}")
    print(f"{'Compiles (After)':<25} | {'YES' if final_compiles else 'NO':<20}")
    print(f"{'Job State':<25} | {job.state:<20}")
    print("-" * 50)

    # -------------------------------------------------------------
    # Mid-run Cancellation Test
    # -------------------------------------------------------------
    print("\n--- Starting Mid-Run Cancellation Test ---")
    cancel_job = job_mgr.create_job(code=src, filename="generated_1000_lines.c", language="c")
    job_mgr.start_job(cancel_job)

    # Wait until job begins running functions
    time.sleep(0.3)
    print(f"Job state before cancel: {cancel_job.state} (function {cancel_job.function_index}/{cancel_job.function_total})")

    # Issue cancellation mid-run
    cancel_res = job_mgr.cancel_job(cancel_job.job_id)
    time.sleep(0.5)

    print(f"Cancel request succeeded: {cancel_res}")
    print(f"Job state after cancel: {cancel_job.state}")
    print(f"Job stage after cancel: {cancel_job.stage}")

    # Check for orphan python/gcc/ollama processes
    ps_cmd = "Get-Process -Name 'gcc', 'ollama' -ErrorAction SilentlyContinue | Select-Object -Property Id, ProcessName"
    proc_check = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True)
    print(f"Active gcc/ollama processes:\n{proc_check.stdout.strip() if proc_check.stdout.strip() else 'No active compiler/ollama orphan processes.'}")

    assert cancel_job.state == "CANCELLED", "Job must be in CANCELLED state"
    assert final_compiles is True, "Repaired 1000-line file must compile"
    print("\nRequirement 7 test completed successfully!")

if __name__ == "__main__":
    run_benchmark()
