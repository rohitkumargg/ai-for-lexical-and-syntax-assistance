import pytest
from app import app
from compiler.repair_planner import RepairPlanner
from compiler.pipeline_logger import (
    PipelineEvent,
    PipelineRunLogger,
    StageStatus,
    get_pipeline_run,
    register_pipeline_run,
)
from compiler.improvement_advisor import candidate_registry


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_pipeline_event_structure():
    logger = PipelineRunLogger(run_id="test_run_001")
    ev = logger.record_stage(
        stage_id="source_received",
        stage_name="1. Source Code Received",
        status=StageStatus.PASSED,
        description="Received test source file.",
        duration_ms=1.25,
        findings_count=0,
        diagnostics={"lines": 10},
    )
    assert ev.run_id == "test_run_001"
    assert ev.stage_id == "source_received"
    assert ev.status == "PASSED"
    assert ev.duration_ms == 1.25
    assert ev.timestamp_iso is not None
    assert ev.timestamp_display is not None
    assert ev.diagnostics["lines"] == 10

    d = ev.to_dict()
    assert d["event_id"].startswith("evt_")
    assert d["stage_name"] == "1. Source Code Received"
    assert d["status"] == "PASSED"


def test_pipeline_all_stages_clean_program():
    planner = RepairPlanner()
    clean_code = """int main() {
    int a = 10;
    int b = 20;
    int c = a + b;
    return c;
}"""
    result = planner.plan_and_repair(clean_code, filename="clean.c")
    assert result["status"] == "CLEAN"
    assert "run_id" in result
    assert "pipeline_events" in result
    events = result["pipeline_events"]
    assert len(events) >= 10

    stage_ids = [e["stage_id"] for e in events]
    assert "source_received" in stage_ids
    assert "lexical_analysis" in stage_ids
    assert "syntax_analysis" in stage_ids
    assert "semantic_analysis" in stage_ids
    assert "security_analysis" in stage_ids
    assert "green_metrics" in stage_ids
    assert "patch_validation" in stage_ids

    # For clean program, repair models must be SKIPPED
    qwen_ev = next(e for e in events if e["stage_id"] == "qwen_ollama")
    assert qwen_ev["status"] == "SKIPPED"

    val_ev = next(e for e in events if e["stage_id"] == "patch_validation")
    assert val_ev["status"] == "PASSED"


def test_syntax_failure_skips_semantic_analysis():
    planner = RepairPlanner()
    # Fatal syntax error: invalid syntax structure
    bad_syntax = """int main() {
    int x = ;;;
    return 0
"""
    result = planner.plan_and_repair(bad_syntax, filename="syntax_err.c")
    events = result["pipeline_events"]

    syn_ev = next(e for e in events if e["stage_id"] == "syntax_analysis")
    assert syn_ev["status"] == "FAILED"
    assert syn_ev["findings_count"] > 0

    sem_ev = next(e for e in events if e["stage_id"] == "semantic_analysis")
    # If blocked by syntax, semantic analysis must NOT claim PASSED
    assert sem_ev["status"] in ["SKIPPED", "FAILED"]
    if sem_ev["status"] == "SKIPPED":
        assert "earlier syntax" in sem_ev["description"].lower() or "syntax" in str(sem_ev["failure_reason"]).lower()


def test_lexical_failure_detection():
    planner = RepairPlanner()
    bad_lex = """int main() {
    retrun 0;
}"""
    result = planner.plan_and_repair(bad_lex, filename="lex_err.c")
    events = result["pipeline_events"]
    lex_ev = next(e for e in events if e["stage_id"] == "lexical_analysis")
    assert lex_ev["status"] == "FAILED"
    assert lex_ev["findings_count"] > 0


def test_semantic_undeclared_identifier():
    planner = RepairPlanner()
    bad_sem = """int main() {
    undeclared_var = 100;
    return 0;
}"""
    result = planner.plan_and_repair(bad_sem, filename="sem_err.c")
    events = result["pipeline_events"]
    sem_ev = next(e for e in events if e["stage_id"] == "semantic_analysis")
    assert sem_ev["status"] == "FAILED"
    assert sem_ev["findings_count"] > 0


def test_security_vulnerability_detection():
    planner = RepairPlanner()
    overflow_code = """int main() {
    int x = 2147483647 + 1;
    return 0;
}"""
    result = planner.plan_and_repair(overflow_code, filename="overflow.c")
    events = result["pipeline_events"]
    sec_ev = next(e for e in events if e["stage_id"] == "security_analysis")
    assert sec_ev["status"] == "FAILED"
    assert sec_ev["findings_count"] > 0

    # Green Metrics event check
    green_ev = next(e for e in events if e["stage_id"] == "green_metrics")
    assert green_ev["status"] == "PASSED"
    assert green_ev["duration_ms"] >= 0.0
    assert "total_runtime_ms" in green_ev["diagnostics"]
    assert "peak_memory_mb" in green_ev["diagnostics"]


def test_api_pipeline_endpoints(client):
    code = """int main() {
    int x = 10;
    return x;
}"""
    # 1. Trigger analysis and plan
    res = client.post("/api/coordinator/analyze_and_plan", json={"code": code, "filename": "api_test.c"})
    assert res.status_code == 200
    data = res.get_json()
    assert "run_id" in data
    assert "pipeline_events" in data
    run_id = data["run_id"]
    events = data["pipeline_events"]
    assert len(events) > 0

    # 2. Query /api/pipeline/latest
    res_latest = client.get("/api/pipeline/latest")
    assert res_latest.status_code == 200
    latest_data = res_latest.get_json()
    assert latest_data["run_id"] == run_id
    assert len(latest_data["events"]) == len(events)

    # 3. Query /api/pipeline/run/<run_id>
    res_run = client.get(f"/api/pipeline/run/{run_id}")
    assert res_run.status_code == 200
    run_data = res_run.get_json()
    assert run_data["run_id"] == run_id
    assert len(run_data["events"]) == len(events)


def test_user_approval_pipeline_stage_update(client):
    planner = RepairPlanner()
    code = """int main() {
    int x = 2147483647 + 1;
    return 0;
}"""
    res = client.post("/api/coordinator/analyze_and_plan", json={"code": code, "filename": "test_appr.c"})
    data = res.get_json()
    cand_id = data.get("candidate_id")

    if cand_id:
        # Check Stage 12 is initially PENDING
        events_before = data["pipeline_events"]
        st12_before = next(e for e in events_before if e["stage_id"] == "user_approval_apply")
        assert st12_before["status"] == "PENDING"

        # Apply candidate
        apply_res = client.post(f"/api/improvement/candidate/{cand_id}/apply", json={"current_code": code})
        if apply_res.status_code == 200:
            apply_data = apply_res.get_json()
            assert apply_data["success"] is True
            assert "pipeline_events" in apply_data
            st12_after = next(e for e in apply_data["pipeline_events"] if e["stage_id"] == "user_approval_apply")
            assert st12_after["status"] == "PASSED"
