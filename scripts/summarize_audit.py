import csv
from collections import Counter
import json

with open("reports/audit/audit_results.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"TOTAL AUDITED FILES: {len(rows)}")
print("=" * 60)

status_c = Counter(r['status'] for r in rows)
rep_c = Counter(r['repair_status'] for r in rows)
tier_c = Counter(r['tier_used'] for r in rows)
gcc_b_c = Counter(r['gcc_before'] for r in rows)
gcc_a_c = Counter(r['gcc_after'] for r in rows)

print("\n--- STATUS COUNTS ---")
for k, v in status_c.most_common():
    print(f"  {k:<30}: {v}")

print("\n--- REPAIR STATUS COUNTS ---")
for k, v in rep_c.most_common():
    print(f"  {k:<30}: {v}")

print("\n--- TIER USED COUNTS ---")
for k, v in tier_c.most_common():
    print(f"  {k:<30}: {v}")

print(f"\n--- GCC COMPILATION ---")
print(f"  Before repair: Compiles = {gcc_b_c.get('True', 0)}, Fails = {gcc_b_c.get('False', 0)}")
print(f"  After repair:  Compiles = {gcc_a_c.get('True', 0)}, Fails = {gcc_a_c.get('False', 0)}")

# Detailed Cause Table for REPAIR_UNAVAILABLE / tier == none
print("\n" + "=" * 60)
print("CAUSE TABLE: REPAIR_UNAVAILABLE OR TIER NONE")
print("=" * 60)

causes = Counter()
for r in rows:
    if r['repair_status'] == 'REPAIR_UNAVAILABLE' or r['tier_used'] == 'none':
        reason = r['unavailable_reason'].strip()
        if not reason:
            if r['gcc_before'] == 'True':
                reason = "Already compiles cleanly (no repair required)"
            else:
                reason = "No candidate generated or validated"
        causes[reason] += 1

for c, count in causes.most_common():
    print(f"[{count:02d}] {c}")

print("\n" + "=" * 60)
print("TARGET CASES DETAILS:")
print("=" * 60)
targets = [
    "missing_comma",
    "misspelled_identifier",
    "stray_token",
    "unit_test_5_line.c"
]

for r in rows:
    fname = r['file']
    if any(t in fname for t in targets):
        print(f"File: {fname}")
        print(f"  Status:        {r['status']}")
        print(f"  Repair Status: {r['repair_status']}")
        print(f"  Tier Used:     {r['tier_used']}")
        print(f"  GCC Before:    {r['gcc_before']} | GCC After: {r['gcc_after']}")
        print(f"  Windows Done:  {r['windows_done']}")
        print(f"  Tier Counts:   {r['windows_by_tier']}")
        print(f"  Reason:        {r['unavailable_reason']}")
        print("-" * 50)

