# scripts/format_failures_table.py
import json
import os
import subprocess

curr_lf = json.load(open(".pytest_cache/v/cache/lastfailed"))
base_lf = json.load(open("../wt_checkpoint/.pytest_cache/v/cache/lastfailed")) if os.path.exists("../wt_checkpoint/.pytest_cache/v/cache/lastfailed") else {}

# Filter out non-test files if any (e.g. .txt files)
curr_tests = [k for k in curr_lf if "::" in k]
base_set = set(base_lf.keys())

print(f"Total test IDs in lastfailed: {len(curr_tests)}")
print(f"Total test IDs in baseline lastfailed: {len(base_lf)}")

# Collapse the 25 garbage input variants into 1 row for readability or list all
rows = []
for test_id in sorted(curr_tests):
    also_in_base = test_id in base_set
    rows.append((test_id, also_in_base))

print(f"\n{'#':<4} {'Test ID':<85} {'Fails on f16d73e?'}")
print("-" * 110)
for idx, (tid, in_base) in enumerate(rows, 1):
    display_id = tid if len(tid) <= 85 else tid[:82] + "..."
    print(f"[{idx:02d}] {display_id:<85} {'YES' if in_base else 'NO'}")

