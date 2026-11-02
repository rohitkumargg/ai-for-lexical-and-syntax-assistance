# tests/test_ui_metrics_invariants.py
import pytest
import math
from compiler.code_quality import calculate_code_quality_metrics, CodeQualityScorer, QualityConfig
from compiler.repair_planner import RepairPlanner

def test_metrics_range_and_not_nan():
    # Test varying values of Q, O, V
    test_cases = [
        (100.0, 0.0, 0.0),
        (0.0, 100.0, 100.0),
        (50.0, 50.0, 50.0),
        (85.5, 12.3, 24.1),
        (None, 10.0, 0.0),
        (90.0, None, 0.0),
        (90.0, 0.0, None),
    ]
    for q, o, v in test_cases:
        res = calculate_code_quality_metrics(q=q, o=o, v=v)
        for key in ["overall_code_quality", "optimal_code", "poor_code", "vulnerability_risk"]:
            val = res[key]
            if val is not None:
                assert not math.isnan(val), f"{key} is NaN for ({q}, {o}, {v})"
                assert 0.0 <= val <= 100.0, f"{key}={val} outside [0, 100] for ({q}, {o}, {v})"

def test_overall_code_quality_formula():
    q, o, v = 80.0, 20.0, 10.0
    # Formula: 0.50 * 80 + 0.25 * (100 - 20) + 0.25 * (100 - 10) = 40 + 20 + 22.5 = 82.5
    res = calculate_code_quality_metrics(q=q, o=o, v=v)
    assert res["overall_code_quality"] == 82.5
    assert res["optimal_code"] == 80.0
    assert res["poor_code"] == 20.0
    assert res["vulnerability_risk"] == 10.0

def test_security_findings_never_clean_or_zero_risk():
    from compiler.repair_planner import _classify_program_status
    from compiler.orchestrator import Finding, FindingCategory, FindingSeverity
    sec_finding = Finding(
        id="SEC-01",
        category=FindingCategory.SECURITY,
        severity=FindingSeverity.HIGH,
        explanation="Command injection vulnerability: system(cmd)",
        evidence="system(cmd);",
        location=None,
    )
    status, label, msg = _classify_program_status(
        "int main() { system(\"ls\"); }", [sec_finding], lang_id="c"
    )
    assert status != "CLEAN", f"Expected non-CLEAN status for command injection, got {status}"
    assert status == "VALID_WITH_SECURITY_ISSUES"

def test_audit_csv_metrics_invariants():
    import csv, os, json
    csv_path = os.path.join("reports", "audit", "audit_results.csv")
    if not os.path.exists(csv_path):
        pytest.skip("Audit CSV does not exist yet")
    
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    
    for r in rows:
        fname = r["file"]
        # Skip error rows if any
        if r["status"] == "ERROR":
            continue
        
        # 1. Check GCC vs CLEAN status
        gcc_b = r["gcc_before"] == "True"
        status = r["status"]
        if not gcc_b:
            assert status != "CLEAN", f"File {fname} has gcc_before=False but status=CLEAN"
            
        # 2. Check findings vs CLEAN status
        crit = 0
        high = 0
        if r.get("findings_by_severity"):
            fnds = json.loads(r["findings_by_severity"])
            crit = fnds.get("critical", 0)
            high = fnds.get("high", 0)
        elif r.get("findings_before"):
            try:
                cnt = int(r["findings_before"])
                if cnt > 0 and not gcc_b:
                    assert status != "CLEAN"
            except Exception:
                pass
        if crit > 0 or high > 0:
            assert status != "CLEAN", f"File {fname} has {crit} critical / {high} high findings but status=CLEAN"
            
        # 3. Check metrics bounds
        raw_scores = r.get("metrics_before") or r.get("score_metrics") or "{}"
        scores = json.loads(raw_scores) if raw_scores else {}
        for metric_name, val in scores.items():
            if isinstance(val, (int, float)):
                assert not math.isnan(val), f"{fname}: {metric_name} is NaN"
                assert 0.0 <= val <= 100.0, f"{fname}: {metric_name}={val} out of bounds"

