import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_api_languages(client):
    res = client.get("/api/languages")
    assert res.status_code == 200
    data = res.get_json()
    ids = [item["id"] for item in data]
    assert "c" in ids
    assert "python" in ids

def test_api_examples_language_filter(client):
    res_py = client.get("/api/examples?language=python")
    assert res_py.status_code == 200
    py_files = res_py.get_json()
    assert len(py_files) > 0
    assert all(f.endswith(".py") for f in py_files)
    assert not any(f.endswith(".c") for f in py_files)

    res_c = client.get("/api/examples?language=c")
    assert res_c.status_code == 200
    c_files = res_c.get_json()
    assert len(c_files) > 0
    assert all(f.endswith(".c") for f in c_files)
    assert not any(f.endswith(".py") for f in c_files)

def test_api_example_path_traversal(client):
    res1 = client.get("/api/example/..%2Fapp.py")
    assert res1.status_code == 404

    res2 = client.get("/api/example/../app.py")
    assert res2.status_code == 404

def test_api_example_extension_language_mismatch(client):
    # A .c file requested with language=python must return 404
    res = client.get("/api/example/block_scope.c?language=python")
    assert res.status_code == 404

def test_api_repair_mismatch_extension_returns_400(client):
    payload = {
        "code": "int main() { return 0; }",
        "filename": "x.c",
        "language": "python",
    }
    res = client.post("/api/repair", json=payload)
    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data

def test_api_repair_python_payload_structure(client):
    payload = {
        "code": "x = 5\nif x > 3\n    print(x)\n",
        "filename": "test.py",
        "language": "python",
    }
    res = client.post("/api/repair", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    facts_keys = [
        "success",
        "status",
        "filename",
        "corrected_code",
        "applied_steps",
        "logs",
        "errors",
        "semantic_issues",
        "security_warnings",
        "changed_lines",
        "security_changed_lines",
        "stats",
        "green_report",
        "total_applied_steps",
    ]
    for k in facts_keys:
        assert k in data, f"Missing key in response: {k}"

    assert data["language"] == "python"
    assert data["success"] is True
    assert data["status"] in ("SUCCESS", "SUCCESS_WITH_WARNINGS")
    assert "if x > 3:" in data["corrected_code"]
