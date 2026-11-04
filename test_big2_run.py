import time
from compiler.repair_planner import RepairPlanner

with open("examples/big2.c", "r", encoding="utf-8") as f:
    code = f.read()

planner = RepairPlanner()
t0 = time.perf_counter()
print("Starting full autonomous plan_and_repair of big2.c (2030 lines)...")
res = planner.plan_and_repair(code, filename="big2.c", language="c")
dur = round(time.perf_counter() - t0, 2)
print(f"Done in {dur}s!")
print("Status:", res.get("status"))
print("Workflow state:", res.get("workflow_state"))
print("Has candidate:", res.get("has_candidate"))
cand = res.get("candidate")
if cand:
    print("Provider:", cand.get("repair_provider"))
    print("Strategy:", cand.get("repair_strategy"))
    print("Title:", cand.get("title"))
    print("Proposed code lines:", len(cand.get("proposed_code", "").splitlines()))
print("Findings count:", len(res.get("findings", [])))
print("Pipeline events count:", len(res.get("pipeline_events", [])))
for ev in res.get("pipeline_events", []):
    print(f"  {ev.get('stage_name')}: {ev.get('status')} ({ev.get('duration_ms')} ms)")

