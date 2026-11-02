# scripts/debug_det_rules.py
import sys, os
sys.path.insert(0, os.getcwd())
import time
from compiler.repair_planner import RepairPlanner

print("Instantiating RepairPlanner...", flush=True)
p = RepairPlanner()
print("Reading clean_guard.c...", flush=True)
with open('examples/week8_2026/clean_guard.c', 'r') as f:
    src = f.read()

print("Calling _apply_deterministic_rules...", flush=True)
cand, steps = p._apply_deterministic_rules(src, filename="clean_guard.c", language="c")
print("Steps:", steps, flush=True)
print("Top 5 lines:\n" + "\n".join(cand.splitlines()[:5]), flush=True)

