import pytest
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def test_forced_analyzer_exception_returns_incomplete_or_error(monkeypatch):
    from compiler.repair_planner import RepairPlanner
    from compiler.security_reporter import SecurityReporter

    def mock_broken_analyze(*args, **kwargs):
        raise RuntimeError("Simulated analyzer crash")

    monkeypatch.setattr(SecurityReporter, "analyze_source", mock_broken_analyze)

    planner = RepairPlanner()
    code = "int main() { return 0; }"
    
    findings, scores = planner.analyze_program(code, filename="test.c", language="c")
    # A failed analyzer must NOT report a clean success status
    status = scores.get("security_assessment_status", "")
    assert status in ("INCOMPLETE", "ERROR", "INCONCLUSIVE", "FAILED"), f"Expected incomplete status, got: {status}"

    # Verify plan_and_repair gives status INCOMPLETE
    plan_res = planner.plan_and_repair(code, filename="test.c", language="c")
    assert plan_res.get("status") == "INCOMPLETE", f"Expected plan status INCOMPLETE, got: {plan_res.get('status')}"
    assert "Simulated analyzer crash" in plan_res.get("message", "")

def test_forced_analyzer_exception_api_endpoint(monkeypatch):
    from app import app
    from compiler.security_reporter import SecurityReporter

    def mock_broken_analyze(*args, **kwargs):
        raise RuntimeError("Simulated analyzer crash")

    monkeypatch.setattr(SecurityReporter, "analyze_source", mock_broken_analyze)

    client = app.test_client()
    res = client.post("/api/coordinator/analyze_and_plan", json={
        "code": "int main() { return 0; }",
        "filename": "test_crash.c",
        "language": "c",
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data.get("status") == "INCOMPLETE"
    assert "Simulated analyzer crash" in data.get("message", "")


def test_forced_analyzer_exception_dashboard_field(monkeypatch):
    """
    D3 verification: Verify that INCOMPLETE status appears in the dashboard-facing
    field the UI reads ('security_status' and 'security_assessment_status').
    """
    from app import app
    from compiler.security_reporter import SecurityReporter

    def mock_broken_analyze(*args, **kwargs):
        raise RuntimeError("Simulated analyzer crash")

    monkeypatch.setattr(SecurityReporter, "analyze_source", mock_broken_analyze)

    client = app.test_client()
    res = client.post("/api/coordinator/analyze_and_plan", json={
        "code": "int main() { return 0; }",
        "filename": "test_dashboard_crash.c",
        "language": "c",
    })
    assert res.status_code == 200
    data = res.get_json()
    # Dashboard-facing fields read by the UI:
    assert data.get("security_status") == "INCOMPLETE", f"Expected security_status 'INCOMPLETE', got {data.get('security_status')}"
    assert data.get("security_assessment_status") == "INCOMPLETE", f"Expected security_assessment_status 'INCOMPLETE', got {data.get('security_assessment_status')}"
    assert data.get("workflow_state") == "ANALYSIS_INCOMPLETE"

