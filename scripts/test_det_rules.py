# scripts/test_det_rules.py
import sys, os
sys.path.insert(0, os.getcwd())
import time
from compiler.repair_planner import RepairPlanner

print("Creating RepairPlanner...")
t0 = time.time()
planner = RepairPlanner()
print(f"Created planner in {time.time()-t0:.2f}s")

with open('examples/week8_2026/clean_guard.c', 'r') as f:
    src = f.read()

print("Applying deterministic rules...")
t1 = time.time()
cand, steps = planner._apply_deterministic_rules(src, filename='clean_guard.c', language='c')
print(f"Applied rules in {time.time()-t1:.2f}s")
print("Steps:", steps)
print("Cand top lines:", cand.splitlines()[:5])
