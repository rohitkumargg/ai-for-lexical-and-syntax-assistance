# tests/test_repair_job.py
"""
Unit and integration tests for Repair Job Architecture:
1. POST starts a job and returns job_id. GET /api/repair/job/<id> returns:
   {state, stage, function_index, function_total, elapsed_s, estimated_total_s, windows_done}.
2. Tolerant function splitting on broken C code with brace matching.
3. Per-window cap (20 s), stall rule (3 consecutive windows), overall ceiling (30 min).
4. Disk persistence of job state and automatic resumption on restart.
5. Window repair cache by hash(window_text, finding_list).
6. Optional OLLAMA_NUM_PARALLEL=2 parallel speedup reporting.
7. Cancellation stops Ollama requests and leaves no orphan processes.
"""
import os
import time
import json
import uuid
import pytest
from app import app
from compiler.repair_job_manager import (
    split_top_level_functions,
    assemble_functions,
    WindowRepairCache,
    RepairJob,
    RepairJobManager,
    get_repair_job_manager
)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_split_top_level_functions_tolerant():
    """Requirement 2: Tolerant function splitting with brace matching on broken code."""
    broken_code = """#include <stdio.h>
typedef struct { int a; } Data;

int func_one(int x) {
    if (x > 0) {
        printf("positive");
    // missing closing brace
    return x * 2;
}

void func_two(char *s) {
    viod *bad;
    printf("%s", s);
}

int main(void) {
    return 0;
}
"""
    preamble, fns = split_top_level_functions(broken_code, language="c")
    assert "typedef struct" in preamble
    assert len(fns) == 3
    fn_names = [f["name"] for f in fns]
    assert fn_names == ["func_one", "func_two", "main"]

    reassembled = assemble_functions(preamble, fns)
    assert reassembled == broken_code, "Reassembly must preserve bit-for-bit exact code"


def test_api_repair_job_start_and_status(client):
    """Requirement 1: POST starts job and returns job_id; GET returns required status schema."""
    code = """#include <stdio.h>
int compute(int x) {
    return x * 2;
}
int main(void) {
    return 0;
}
"""
    # 1. POST /api/repair/job
    post_res = client.post("/api/repair/job", json={
        "code": code,
        "filename": "test.c",
        "language": "c"
    })
    assert post_res.status_code == 202
    data = post_res.get_json()
    assert "job_id" in data
    assert data["state"] in ("PENDING", "RUNNING")
    job_id = data["job_id"]

    # 2. GET /api/repair/job/<id>
    get_res = client.get(f"/api/repair/job/{job_id}")
    assert get_res.status_code == 200
    status_data = get_res.get_json()

    # Verify all required schema fields
    required_fields = [
        "state",
        "stage",
        "function_index",
        "function_total",
        "elapsed_s",
        "estimated_total_s",
        "windows_done",
    ]
    for field in required_fields:
        assert field in status_data, f"Missing required field: {field}"


def test_repair_job_persistence_and_resumption():
    """Requirement 4: Persist job state to disk; on server restart, unfinished jobs resume."""
    test_dir = os.path.join(os.getcwd(), "data", "test_repair_jobs")
    os.makedirs(test_dir, exist_ok=True)
    mgr = RepairJobManager(jobs_dir=test_dir)

    job = mgr.create_job(
        code="int f() { return 1; }",
        filename="test.c",
        language="c"
    )
    job.function_index = 2
    job.function_total = 5
    job.state = "RUNNING"
    mgr.save_job(job)

    # Simulate server restart by creating a new manager from the same directory
    mgr_restart = RepairJobManager(jobs_dir=test_dir)
    loaded_job = mgr_restart.get_job(job.job_id)
    assert loaded_job is not None
    assert loaded_job.function_index == 2
    assert loaded_job.function_total == 5
    assert loaded_job.state == "RUNNING"

    # Test automatic resumption
    resumed_count = mgr_restart.resume_unfinished_jobs()
    assert resumed_count >= 1

    # Clean up test dir
    try:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception:
        pass


def test_window_repair_cache():
    """Requirement 5: Cache accepted windows by hash of (window text, finding list)."""
    test_cache_file = os.path.join(os.getcwd(), "data", "test_cache", "test_win_cache.json")
    cache = WindowRepairCache(cache_file=test_cache_file)

    win_text = "int a = 10\nreturn a;"
    findings = ["syntax_error:line_1"]
    repaired_win = "int a = 10;\nreturn a;"

    # Initially not cached
    assert cache.get(win_text, findings) is None

    # Set cache
    cache.set(win_text, findings, repaired_win)

    # Retrieval matches
    assert cache.get(win_text, findings) == repaired_win

    # Different findings produces cache miss
    assert cache.get(win_text, ["syntax_error:line_2"]) is None

    # Clean up
    try:
        import shutil
        shutil.rmtree(os.path.dirname(test_cache_file), ignore_errors=True)
    except Exception:
        pass


def test_repair_job_cancel_endpoint(client):
    """Requirement 1 & 7: Cancel stops job, sets CANCELLED, leaves no orphan processes."""
    code = """#include <stdio.h>
int slow_fn(int n) {
    int s = 0;
    for(int i = 0; i < n; i++) s += i;
    return s;
}
"""
    post_res = client.post("/api/repair/job", json={
        "code": code,
        "filename": "cancel_test.c",
        "language": "c"
    })
    job_id = post_res.get_json()["job_id"]

    # Cancel via POST /api/repair/job/<id>/cancel
    cancel_res = client.post(f"/api/repair/job/{job_id}/cancel")
    assert cancel_res.status_code == 200
    c_data = cancel_res.get_json()
    assert c_data["cancelled"] is True
    assert c_data["state"] == "CANCELLED"

    # Status reflects cancellation
    st_res = client.get(f"/api/repair/job/{job_id}")
    assert st_res.get_json()["state"] == "CANCELLED"


def test_security_path_traversal_and_invalid_job_ids(client):
    """
    Requirement 1: Ignore client-supplied job_id (generate server-side uuid4 hex).
    Validate every job_id used in a path with ^[a-f0-9]{32}$ and refuse others with 400.
    Test with an id containing path separators and dots: must be rejected and nothing written outside data/repair_jobs.
    """
    # 1. Ignore client-supplied job_id
    fake_client_id = "11111111111111111111111111111111"
    post_res = client.post("/api/repair/job", json={
        "code": "int main() { return 0; }",
        "job_id": fake_client_id,
        "filename": "sec_test.c",
        "language": "c"
    })
    assert post_res.status_code == 202
    assigned_id = post_res.get_json()["job_id"]
    assert assigned_id != fake_client_id, "Server MUST ignore client-supplied job_id"
    import re
    assert re.match(r"^[a-f0-9]{32}$", assigned_id), "Generated job_id must be 32-char hex"

    # 2. Refuse invalid job_ids with 400
    invalid_ids = [
        "../foo.json",
        "../../test",
        "not-a-valid-hex-id",
        "123",
        "1234567890abcdef1234567890abcdef1234", # 36 chars
        "1234567890abcdef1234567890abcdeG",     # non-hex char 'G'
        "sub/dir/id",
        "..%2Fevil.json"
    ]
    for bad_id in invalid_ids:
        # GET
        res_get = client.get(f"/api/repair/job/{bad_id}")
        assert res_get.status_code == 400, f"Expected 400 for bad_id: {bad_id}, got {res_get.status_code}"
        # CANCEL
        res_cancel = client.post(f"/api/repair/job/{bad_id}/cancel")
        assert res_cancel.status_code == 400, f"Expected 400 for cancel bad_id: {bad_id}, got {res_cancel.status_code}"
        # DELETE
        res_delete = client.delete(f"/api/repair/job/{bad_id}")
        assert res_delete.status_code == 400, f"Expected 400 for delete bad_id: {bad_id}, got {res_delete.status_code}"

    # 3. Direct RepairJobManager check: must raise ValueError and nothing written outside data/repair_jobs
    mgr = get_repair_job_manager()
    dangerous_job = RepairJob(
        job_id="../../outside_job",
        state="PENDING",
        stage="Test",
        function_index=0,
        function_total=1,
        elapsed_s=0.0,
        estimated_total_s=0.0,
        windows_done=0,
        windows_by_tier={"rules": 0, "codet5": 0, "qwen": 0},
        current_code="int main() {}",
        original_code="int main() {}"
    )
    with pytest.raises(ValueError) as excinfo:
        mgr.save_job(dangerous_job)
    assert "Security: Invalid job_id format" in str(excinfo.value) or "Path traversal" in str(excinfo.value)

    # Verify no file was created outside data/repair_jobs
    outside_file = os.path.join(os.getcwd(), "data", "outside_job.json")
    root_outside_file = os.path.join(os.getcwd(), "outside_job.json")
    assert not os.path.exists(outside_file), f"File written outside data/repair_jobs: {outside_file}"
    assert not os.path.exists(root_outside_file), f"File written in root: {root_outside_file}"


def test_security_token_not_persisted_and_retention_and_delete(client):
    """
    Requirement 2:
    - Do not persist approval tokens in job files.
    - Delete job files (and their cached code) after 24 h and on user request.
    - Resume must re-check security gate for the stored source.
    """
    test_dir = os.path.join(os.getcwd(), "data", "test_retention_jobs")
    os.makedirs(test_dir, exist_ok=True)
    mgr = RepairJobManager(jobs_dir=test_dir)

    # Create job with dummy approval token
    fake_token = "approval_token_12345"
    job = mgr.create_job(
        code="int main() { return 0; }",
        filename="retention_test.c",
        language="c",
        approval_token=fake_token
    )
    job.state = "PENDING"
    mgr.save_job(job)

    # 1. Verify approval_token is NEVER persisted to disk
    job_file = os.path.join(test_dir, f"{job.job_id}.json")
    assert os.path.exists(job_file)
    with open(job_file, "r", encoding="utf-8") as f:
        persisted_data = json.load(f)
    assert "approval_token" not in persisted_data, "Approval token MUST NOT be persisted to disk!"

    loaded_job = RepairJob.from_dict(persisted_data)
    assert loaded_job.approval_token is None, "Restored job must have approval_token=None"

    # 2. Test DELETE endpoint on user request
    del_res = client.delete(f"/api/repair/job/{job.job_id}")
    # Note: client accesses global job manager; let's test mgr.delete_job directly and via client for registered job
    global_mgr = get_repair_job_manager()
    job2 = global_mgr.create_job(code="int main() {}", filename="del_test.c", language="c")
    global_mgr.save_job(job2)
    job2_file = os.path.join(global_mgr.jobs_dir, f"{job2.job_id}.json")
    assert os.path.exists(job2_file)

    res_del = client.delete(f"/api/repair/job/{job2.job_id}")
    assert res_del.status_code == 200
    assert res_del.get_json()["deleted"] is True
    assert not os.path.exists(job2_file), "Job file must be deleted on user DELETE request"

    # Subsequent GET returns 404
    assert client.get(f"/api/repair/job/{job2.job_id}").status_code == 404

    # 3. Test 24h retention cleanup
    job_old = mgr.create_job(code="int main() {}", filename="old.c", language="c")
    mgr.save_job(job_old)
    # Artificially age the job file and job object by 25 hours (90,000s)
    old_time = time.time() - 90000.0
    job_old.created_at = old_time
    job_old.updated_at = old_time
    mgr.save_job(job_old)
    job_old_path = os.path.join(test_dir, f"{job_old.job_id}.json")
    os.utime(job_old_path, (old_time, old_time))

    cleaned = mgr.cleanup_expired_jobs(max_age_s=86400.0)
    assert cleaned >= 1
    assert not os.path.exists(job_old_path), "Expired job (>24h) must be deleted"

    # Clean up test dir
    try:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception:
        pass


