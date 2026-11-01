import os
import shutil
import subprocess
import pytest

INDEX_PATH = os.path.join("gui", "templates", "index.html")
APP_JS_PATH = os.path.join("gui", "static", "app.js")

def test_index_html_contains_language_switch():
    assert os.path.exists(INDEX_PATH), "index.html not found"
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    assert 'id="language-switch"' in html, "index.html missing id='language-switch'"

def test_app_js_new_file_no_location_reload():
    assert os.path.exists(APP_JS_PATH), "app.js not found"
    with open(APP_JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    assert "location.reload()" not in js, "app.js should not contain location.reload()"
    assert "function newFile" in js, "app.js must define newFile function"

def test_app_js_no_hardcoded_test_case_c():
    with open(APP_JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    assert '"test_case.c"' not in js and "'test_case.c'" not in js, "app.js contains hardcoded test_case.c"

def test_app_js_sends_language_field():
    with open(APP_JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    assert "language: currentLanguageId" in js, "app.js must send language in API payload"

def test_node_check_app_js():
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed; skipping node --check gui/static/app.js")

    res = subprocess.run([node_exe, "--check", APP_JS_PATH], capture_output=True, text=True)
    assert res.returncode == 0, f"node --check failed: {res.stderr}"
