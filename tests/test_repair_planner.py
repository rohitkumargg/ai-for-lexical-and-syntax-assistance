import pytest
from app import app
from compiler.repair_planner import RepairPlanner
from compiler.improvement_advisor import candidate_registry


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_repair_planner_analyze_program():
    planner = RepairPlanner()
    code = """int main() {
    int x = 2147483647 + 1;
    return 0;
}"""
    findings, metrics = planner.analyze_program(code, "test_overflow.c")
    assert len(findings) > 0

    # Verify structured plain-language fields
    found_overflow = False
    for f in findings:
        assert f.title is not None
        assert f.explanation is not None
        assert f.consequence is not None
        assert f.how_to_fix is not None
        assert f.status in ["CONFIRMED", "POSSIBLE", "HEURISTIC"]
        if "overflow" in f.title.lower() or "overflow" in f.explanation.lower() or (f.cwe_id and "190" in f.cwe_id):
            found_overflow = True
            assert len(f.consequence) > 0
            assert len(f.how_to_fix) > 0

    assert found_overflow, "Expected integer overflow finding to be detected and explained"

    # Verify honest metrics from underlying scorers
    assert "quality_score" in metrics
    assert "security_risk_score" in metrics
    assert "optimization_potential" in metrics
    assert "green_metrics" in metrics
    assert metrics["security_risk_score"] > 0, "Security risk should be elevated due to integer overflow"


def test_repair_planner_validation_safety():
    planner = RepairPlanner()
    code = """int main() {
    int x = 10;
    return 0;
}"""
    # Candidate with syntax error (missing semicolon)
    invalid_candidate = """int main() {
    int x = 10
    return 0;
}"""
    val_result = planner.validate_candidate(code, invalid_candidate, "test_valid.c")
    assert not val_result.is_valid
    assert not val_result.syntax_passed
    assert val_result.verdict.value.startswith("FAILED_")


def test_api_coordinator_analyze_and_plan(client):
    code = """int main() {
    int x = 2147483647 + 1;
    return 0;
}"""
    payload = {
        "source_code": code,
        "filename": "overflow_test.c",
        "generate_repair": True
    }
    res = client.post("/api/coordinator/analyze_and_plan", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    assert "unified_findings" in data
    assert "before_metrics" in data
    assert "summary" in data

    # Verify candidate structure if generated
    if data.get("candidate"):
        cand = data["candidate"]
        assert "id" in cand
        assert "proposed_code" in cand
        assert "diff" in cand
        assert "validation" in cand
        assert "user_decision_state" in cand
        assert cand["user_decision_state"] == "PENDING_REVIEW"
        assert "after_metrics" in data

        cand_id = cand["id"]
        # Candidate must exist in candidate_registry
        reg_entry = candidate_registry.get(cand_id)
        assert reg_entry is not None
        assert reg_entry.original_source_hash is not None


def test_candidate_apply_and_reject_lifecycle(client):
    code = """int main() {
    int a = 1;
    return 0;
}"""
    payload = {
        "source_code": code,
        "filename": "lifecycle.c",
        "generate_repair": True
    }
    res = client.post("/api/coordinator/analyze_and_plan", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    if data.get("candidate"):
        cand_id = data["candidate"]["id"]

        # Reject candidate
        rej_res = client.post(f"/api/improvement/candidate/{cand_id}/reject")
        assert rej_res.status_code == 200
        rej_data = rej_res.get_json()
        assert rej_data["success"] is True
        assert rej_data["user_decision"] == "USER_REJECTED"

        # Applying a rejected candidate should fail
        apply_res = client.post(
            f"/api/improvement/candidate/{cand_id}/apply",
            json={"current_source_code": code}
        )
        assert apply_res.status_code in [400, 422]
        apply_data = apply_res.get_json()
        assert apply_data["success"] is False


def test_candidate_stale_source_conflict(client):
    code = """int main() {
    int a = 1;
    return 0;
}"""
    payload = {
        "source_code": code,
        "filename": "stale.c",
        "generate_repair": True
    }
    res = client.post("/api/coordinator/analyze_and_plan", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    if data.get("candidate"):
        cand_id = data["candidate"]["id"]

        # Attempt to apply with modified/stale code
        stale_code = """int main() {
    int a = 999; /* modified in editor */
    return 0;
}"""
        apply_res = client.post(
            f"/api/improvement/candidate/{cand_id}/apply",
            json={"current_source_code": stale_code}
        )
        assert apply_res.status_code == 409
        apply_data = apply_res.get_json()
        assert apply_data["success"] is False
        assert "stale" in apply_data["error"].lower() or "conflict" in apply_data["error"].lower() or "modified" in apply_data["error"].lower()
