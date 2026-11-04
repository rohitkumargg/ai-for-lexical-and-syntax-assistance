import time
import os
import difflib

with open("examples/big2.c", "r", encoding="utf-8") as f:
    code = f.read()

print(f"Loaded big2.c: {len(code.splitlines())} lines, {len(code)} bytes", flush=True)

from compiler.repair_planner import RepairPlanner, calculate_six_metrics
from compiler.malicious_precheck import MaliciousCodePrecheck
planner = RepairPlanner()

t0 = time.perf_counter()
print("\n--- Step 1: Precheck ---", flush=True)
t = time.perf_counter()
precheck_rep = MaliciousCodePrecheck.analyze(code)
print(f"Precheck took {round(time.perf_counter() - t, 3)}s, findings: {len(precheck_rep.findings)}", flush=True)

print("\n--- Step 2: analyze_program (original) ---", flush=True)
t = time.perf_counter()
findings, scores = planner.analyze_program(code, "big2.c", "c")
print(f"analyze_program took {round(time.perf_counter() - t, 3)}s, findings: {len(findings)}", flush=True)

print("\n--- Step 3: _apply_deterministic_rules ---", flush=True)
t = time.perf_counter()
det_cand, det_steps = planner._apply_deterministic_rules(code, "big2.c", "c", findings=findings, deadline=time.perf_counter() + 30.0)
print(f"_apply_deterministic_rules took {round(time.perf_counter() - t, 3)}s, steps: {len(det_steps)}", flush=True)

print("\n--- Step 4: calculate_six_metrics (original) ---", flush=True)
t = time.perf_counter()
six_orig = calculate_six_metrics(code, "big2.c", "c", findings=findings)
print(f"calculate_six_metrics took {round(time.perf_counter() - t, 3)}s", flush=True)

cand = det_cand if det_cand else code

print("\n--- Step 5: analyze_program (candidate) ---", flush=True)
t = time.perf_counter()
cand_findings, cand_scores = planner.analyze_program(cand, "big2.c", "c", is_reanalysis=True)
print(f"analyze_program (cand) took {round(time.perf_counter() - t, 3)}s, cand_findings: {len(cand_findings)}", flush=True)

print("\n--- Step 6: calculate_six_metrics (candidate) ---", flush=True)
t = time.perf_counter()
six_cand = calculate_six_metrics(cand, "big2.c", "c", findings=cand_findings)
print(f"calculate_six_metrics (cand) took {round(time.perf_counter() - t, 3)}s", flush=True)

print("\n--- Step 7: validator.validate_patch ---", flush=True)
t = time.perf_counter()
val_rep = planner.validator.validate_patch(
    original_code=code,
    candidate_code=cand,
    filename="big2.c",
    language="c",
    original_findings=findings,
)
print(f"validate_patch took {round(time.perf_counter() - t, 3)}s, is_valid: {val_rep.is_valid}", flush=True)

print(f"\nTotal elapsed: {round(time.perf_counter() - t0, 3)}s", flush=True)
