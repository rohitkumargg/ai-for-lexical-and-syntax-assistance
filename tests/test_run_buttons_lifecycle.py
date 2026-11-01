import os
import re

def test_app_js_defines_set_all_run_buttons_disabled():
    app_js_path = os.path.join("gui", "static", "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "function setAllRunButtonsDisabled(disabled)" in content, "Missing setAllRunButtonsDisabled definition"
    for btn_id in ["btn-run", "btn-run-program", "btn-editor-run-program", "btn-dock-run"]:
        assert btn_id in content, f"Missing target button {btn_id}"

def test_run_repair_lifecycle_restores_all_run_buttons():
    app_js_path = os.path.join("gui", "static", "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Ensure _runRepairAfterPrescan finally block calls setAllRunButtonsDisabled(false)
    assert re.search(r"function\s+_runRepairAfterPrescan[\s\S]*?finally\s*\{[\s\S]*?setAllRunButtonsDisabled\(false\)", content)

def test_apply_recommended_plan_restores_all_run_buttons():
    app_js_path = os.path.join("gui", "static", "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Ensure applyRecommendedPlan post-apply finally block calls setAllRunButtonsDisabled(false)
    assert re.search(r"async\s+function\s+applyRecommendedPlan[\s\S]*?setAllRunButtonsDisabled\(false\)", content)

def test_security_gate_on_continue_and_cancel_restores_all_run_buttons():
    app_js_path = os.path.join("gui", "static", "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # onCancel must restore buttons
    assert re.search(r"onCancel:\s*async\s*\(\)\s*=>\s*\{[\s\S]*?setAllRunButtonsDisabled\(false\)", content)

