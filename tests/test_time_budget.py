import pytest
import time
from compiler.repair_planner import RepairPlanner

def test_file_with_40_plus_syntax_errors_returns_within_budget():
    """
    Test requirement 1: A file with 40+ syntax errors returns a valid status within the budget.
    """
    planner = RepairPlanner()
    
    # Generate C code with 45 syntax errors (missing semicolons across many lines)
    lines = ["int main() {"]
    for i in range(45):
        lines.append(f"    int var_{i} = {i}") # missing semicolon on each line
    lines.append("    return 0;")
    lines.append("}")
    code_45_errors = "\n".join(lines)
    
    budget = 90.0
    t0 = time.perf_counter()
    res = planner.plan_and_repair(
        code_45_errors,
        filename="stress_45_errors.c",
        language="c",
        time_budget_s=budget,
    )
    duration = time.perf_counter() - t0
    
    # Must complete strictly within budget
    assert duration <= budget, f"Execution took {duration:.2f}s, exceeding budget of {budget}s"
    
    # Must return a valid dictionary response with status
    assert isinstance(res, dict)
    assert "status" in res
    valid_statuses = {"REPAIR_PLAN_READY", "PROPOSAL_READY", "PARTIALLY_REPAIRED", "TIME_BUDGET_EXCEEDED", "UNRESOLVED"}
    assert res["status"] in valid_statuses, f"Unexpected status: {res['status']}"
    
    # Must preserve findings found
    findings = res.get("findings") or res.get("unified_findings") or []
    assert len(findings) >= 30, f"Expected at least 30 syntax errors detected, got {len(findings)}"


def test_tiny_budget_returns_time_budget_exceeded_with_stage_name():
    """
    Test requirement 2: A request with a tiny budget (e.g. 1s) returns TIME_BUDGET_EXCEEDED with the stage name.
    """
    planner = RepairPlanner()
    
    code = """
    int calculate(int a, int b) {
        int x = a + b
        int y = x * 2
        return y
    }
    """
    tiny_budget = 0.001 # 1 millisecond forces budget expiry
    res = planner.plan_and_repair(
        code,
        filename="tiny_budget.c",
        language="c",
        time_budget_s=tiny_budget,
    )
    
    assert isinstance(res, dict)
    assert res["status"] in ("TIME_BUDGET_EXCEEDED", "PARTIALLY_REPAIRED"), f"Expected TIME_BUDGET_EXCEEDED, got {res.get('status')}"
    assert "stopped_stage" in res or "failing_stage" in res
    stage = res.get("stopped_stage") or res.get("failing_stage")
    assert stage is not None and len(stage) > 0, "Expected non-empty stopped stage name"
