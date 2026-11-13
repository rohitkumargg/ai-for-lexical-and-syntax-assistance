import csv
import sys
from collections import Counter
from pathlib import Path

csv_path = Path("reports/corpus/results.csv")
if not csv_path.exists():
    print("results.csv does not exist.")
    sys.exit(0)

with open(csv_path, "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

total = len(rows)
passed = sum(1 for r in rows if r.get("passed") == "True")
failed = sum(1 for r in rows if r.get("passed") != "True")

print(f"=== Results Summary: {total} total, {passed} passed ({passed/total*100:.1f}%), {failed} failed ({failed/total*100:.1f}%) ===")

# Group by status
by_status = Counter(r.get("status", "UNKNOWN") for r in rows)
print("\nBy Status:")
for st, cnt in by_status.most_common():
    print(f"  {st}: {cnt}")

# Group by category
by_cat = Counter(r.get("category", "UNKNOWN") for r in rows)
print("\nBy Category (Total / Pass / Fail):")
for cat in sorted(by_cat.keys()):
    cat_rows = [r for r in rows if r.get("category") == cat]
    cat_pass = sum(1 for r in cat_rows if r.get("passed") == "True")
    cat_fail = sum(1 for r in cat_rows if r.get("passed") != "True")
    print(f"  {cat}: {len(cat_rows)} total, {cat_pass} passed, {cat_fail} failed")

# Failures detail
fails = [r for r in rows if r.get("passed") != "True"]
if fails:
    print(f"\nDetailed Failures ({len(fails)}):")
    for idx, r in enumerate(fails, 1):
        fc = r.get("failure_cause", "")
        if len(fc) > 90:
            fc = fc[:90] + "..."
        print(f"  {idx:2d}. {r.get('file')} [{r.get('category')}/{r.get('subcat')}] status={r.get('status')} tier={r.get('tier')}")
        print(f"      cause: {fc}")
