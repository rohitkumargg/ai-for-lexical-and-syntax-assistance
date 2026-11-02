import csv, json, math

with open("reports/audit/audit_results.csv", "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

violations = []

for r in rows:
    fname = r["file"]
    status = r["status"]
    rep_status = r["repair_status"]
    gcc_b = r["gcc_before"] == "True"
    gcc_a = r["gcc_after"] == "True"
    
    # 1. Metric bounds and NaN
    scores = json.loads(r["score_metrics"]) if r["score_metrics"] else {}
    for m, val in scores.items():
        if val is not None:
            if math.isnan(val):
                violations.append((fname, f"Metric {m} is NaN"))
            elif not (0.0 <= float(val) <= 100.0):
                violations.append((fname, f"Metric {m}={val} out of [0, 100]"))

    # 2. Findings vs CLEAN
    fnds = json.loads(r["findings_by_severity"]) if r["findings_by_severity"] else {}
    crit = fnds.get("critical", 0)
    high = fnds.get("high", 0)
    if (crit > 0 or high > 0) and (status == "CLEAN" or rep_status == "CLEAN"):
        violations.append((fname, f"CLEAN status but has {crit} critical, {high} high findings"))

    # 3. Security Risk vs Findings
    sec_risk = scores.get("security_risk")
    if (crit > 0 or high > 0) and sec_risk == 0.0:
        violations.append((fname, f"security_risk is 0.0% but has {crit} critical, {high} high findings"))

    # 4. GCC before vs CLEAN
    if not gcc_b and status == "CLEAN":
        violations.append((fname, f"status=CLEAN but gcc_before=False (GCC failed to compile original)"))

print(f"Total audit invariant violations found: {len(violations)}")
for fname, v in violations:
    print(f"  {fname}: {v}")

