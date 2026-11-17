import os
import threading
import webbrowser
import json
import uuid
import hashlib

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from compiler.week5_repair_helpers import print_parser_check
from compiler.languages import (
    LANGUAGES,
    get_language,
    detect_language,
    extension_ok,
)

import backend_logic
from backend_logic import (
    patch_history,
    patch_validator,
    _ACTIVE_REPAIR_EVENTS,
)

# Startup check for parser freshness
print_parser_check()

app = Flask(
    __name__,
    template_folder="gui/templates",
    static_folder="gui/static"
)


def _get_static_hash(filename: str) -> str:
    path = os.path.join(app.static_folder or "gui/static", filename)
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:10]
    except Exception:
        return "1"


@app.context_processor
def inject_static_hashes():
    return {
        "app_js_hash": _get_static_hash("app.js"),
        "style_css_hash": _get_static_hash("style.css"),
    }


@app.after_request
def add_cache_control_headers(response):
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    return render_template("index.html")


def _resolve_lang_and_filename(data, default_name_fn=None):
    lid, fname, err, code = backend_logic.resolve_lang_and_filename(data, default_name_fn)
    if err:
        return None, None, (jsonify(err), code)
    return lid, fname, None


# -------------------------------------------------------------
# GROUP 1: SYSTEM & FILE ROUTES
# -------------------------------------------------------------

@app.route("/api/languages")
def languages():
    data, code = backend_logic.handle_languages()
    return jsonify(data), code


@app.route("/api/examples")
def examples():
    lang_id = request.args.get("language", "c")
    data, code = backend_logic.handle_examples(lang_id)
    return jsonify(data), code


@app.route("/api/example/<path:name>")
def load_example(name):
    lang_id = request.args.get("language")
    data, code = backend_logic.handle_load_example(name, lang_id)
    return jsonify(data), code


@app.route("/api/file/create", methods=["POST"])
def create_file():
    data, code = backend_logic.handle_create_file(request.json or {})
    return jsonify(data), code


@app.route("/api/file/save", methods=["POST"])
def save_file():
    data, code = backend_logic.handle_save_file(request.json or {})
    return jsonify(data), code


@app.route("/api/models/status")
def models_status():
    data, code = backend_logic.handle_models_status()
    return jsonify(data), code


@app.route("/api/models/unload", methods=["POST"])
def models_unload():
    data, code = backend_logic.handle_models_unload()
    return jsonify(data), code


# -------------------------------------------------------------
# GROUP 2: SECURITY & ANALYSIS ROUTES
# -------------------------------------------------------------

@app.route("/api/quality/score", methods=["POST", "GET"])
def calculate_quality_score():
    data_in = request.get_json(silent=True) if request.method == "POST" else request.args
    data, code = backend_logic.handle_quality_score(data_in or {})
    return jsonify(data), code


@app.route("/api/quality/config", methods=["GET"])
def get_quality_config():
    data, code = backend_logic.handle_quality_config()
    return jsonify(data), code


@app.route("/api/optimization/potential", methods=["POST", "GET"])
def get_optimization_potential():
    data_in = request.get_json(silent=True) if request.method == "POST" else request.args
    data, code = backend_logic.handle_optimization_potential(data_in or {})
    return jsonify(data), code


@app.route("/api/optimization/config", methods=["GET"])
def get_optimization_config():
    data, code = backend_logic.handle_optimization_config()
    return jsonify(data), code


@app.route("/api/security/risk", methods=["POST", "GET"])
def get_security_risk():
    data_in = request.get_json(silent=True) if request.method == "POST" else request.args
    data, code = backend_logic.handle_security_risk(data_in or {})
    return jsonify(data), code


@app.route("/api/security/risk/delta", methods=["POST"])
def get_security_risk_delta():
    data, code = backend_logic.handle_security_risk_delta(request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/security/risk/config", methods=["GET"])
def get_security_risk_config():
    data, code = backend_logic.handle_security_risk_config()
    return jsonify(data), code


@app.route("/api/security/report", methods=["POST"])
def security_report():
    data, code = backend_logic.handle_security_report(request.json or {})
    return jsonify(data), code


@app.route("/api/security/compare", methods=["POST"])
def security_compare():
    data, code = backend_logic.handle_security_compare(request.json or {})
    return jsonify(data), code


@app.route("/api/security/benchmark", methods=["GET"])
def security_benchmark():
    benchmark_dir = request.args.get("dir", "examples/security_fix_2026")
    data, code = backend_logic.handle_security_benchmark(benchmark_dir)
    return jsonify(data), code


@app.route("/api/security/remediation", methods=["POST"])
def security_remediation():
    data, code = backend_logic.handle_security_remediation(request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/security/apply", methods=["POST"])
def security_apply():
    data, code = backend_logic.handle_security_apply(request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/security/prescan", methods=["POST"])
def security_prescan():
    data, code = backend_logic.handle_security_prescan(request.json or {})
    return jsonify(data), code


@app.route("/api/security/approval/check", methods=["POST"])
def security_approval_check():
    data, code = backend_logic.handle_security_approval_check(request.json or {})
    return jsonify(data), code


@app.route("/api/security/approval/approve", methods=["POST"])
def security_approval_approve():
    data, code = backend_logic.handle_security_approval_approve(request.json or {})
    return jsonify(data), code


@app.route("/api/security/approval/cancel", methods=["POST"])
def security_approval_cancel():
    data, code = backend_logic.handle_security_approval_cancel(request.json or {})
    return jsonify(data), code


# -------------------------------------------------------------
# GROUP 3: EXECUTION, REPAIR & JOB ROUTES
# -------------------------------------------------------------

@app.route("/api/program/run", methods=["POST"])
@app.route("/api/run", methods=["POST"])
@app.route("/run", methods=["POST"])
@app.route("/execute", methods=["POST"])
@app.route("/api/execute", methods=["POST"])
def run_program():
    data, code = backend_logic.handle_run_program(request.json or {})
    return jsonify(data), code


@app.route("/api/testcase", methods=["POST"])
def testcase():
    data, code = backend_logic.handle_testcase(request.json or {})
    return jsonify(data), code


@app.route("/api/repair", methods=["POST"])
def repair():
    data, code = backend_logic.handle_repair(request.json or {})
    return jsonify(data), code


@app.route("/api/repair/job", methods=["POST"])
def repair_job_start():
    data, code = backend_logic.handle_repair_job_start(request.json or {})
    return jsonify(data), code


@app.route("/api/repair/job/<path:job_id>", methods=["GET"])
def repair_job_status(job_id):
    data, code = backend_logic.handle_repair_job_status(job_id)
    return jsonify(data), code


@app.route("/api/repair/job/<path:job_id>/cancel", methods=["POST"])
def repair_job_cancel(job_id):
    data, code = backend_logic.handle_repair_job_cancel(job_id)
    return jsonify(data), code


@app.route("/api/repair/job/<path:job_id>", methods=["DELETE"])
def repair_job_delete(job_id):
    data, code = backend_logic.handle_repair_job_delete(job_id)
    return jsonify(data), code


@app.route("/api/repair_stream", methods=["POST"])
def repair_stream():
    data = request.json or {}
    code = data.get("code") or data.get("source_code", "")
    lang_id, filename, err_resp = _resolve_lang_and_filename(data)
    if err_resp:
        return err_resp

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=code,
        filename=filename,
        language=lang_id,
        operation="repair",
        approval_token=data.get("approval_token"),
    )
    if not permitted:
        @stream_with_context
        def generate_blocked():
            yield f"data: {json.dumps(warning_payload)}\n\n"
        return Response(generate_blocked(), status=gate_status, mimetype="text/event-stream")

    @stream_with_context
    def generate():
        from compiler.gui_bridge import repair_source_for_gui_stream
        for event in repair_source_for_gui_stream(code, filename, language=lang_id):
            yield f"data: {json.dumps(event)}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/coordinator/cancel", methods=["POST"])
def coordinator_cancel():
    data, code = backend_logic.handle_coordinator_cancel(request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/coordinator/analyze_and_plan", methods=["POST"])
def coordinator_analyze_and_plan():
    data, code = backend_logic.handle_coordinator_analyze_and_plan(request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/repair/post_apply", methods=["POST"])
def repair_post_apply():
    data, code = backend_logic.handle_repair_post_apply(request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/pipeline/latest", methods=["GET"])
def get_latest_pipeline_run():
    data, code = backend_logic.handle_latest_pipeline_run()
    return jsonify(data), code


@app.route("/api/pipeline/run/<run_id>", methods=["GET"])
def get_pipeline_run_by_id(run_id):
    data, code = backend_logic.handle_pipeline_run_by_id(run_id)
    return jsonify(data), code


# -------------------------------------------------------------
# GROUP 4: PATCH & DIFF ROUTES
# -------------------------------------------------------------

@app.route("/api/patch/validate", methods=["POST"])
def validate_patch():
    data, code = backend_logic.handle_validate_patch(request.json or {})
    return jsonify(data), code


@app.route("/api/patch/apply", methods=["POST"])
def apply_patch():
    data, code = backend_logic.handle_apply_patch(request.json or {})
    return jsonify(data), code


@app.route("/api/patch/reject", methods=["POST"])
def reject_patch():
    data, code = backend_logic.handle_reject_patch(request.json or {})
    return jsonify(data), code


@app.route("/api/patch/revert", methods=["POST"])
def revert_patch():
    data, code = backend_logic.handle_revert_patch()
    return jsonify(data), code


@app.route("/api/dashboard/before_after", methods=["POST"])
def get_dashboard_before_after():
    data, code = backend_logic.handle_dashboard_before_after(request.get_json(silent=True) or {})
    return jsonify(data), code


# -------------------------------------------------------------
# GROUP 5: IMPROVEMENT & RULES ROUTES
# -------------------------------------------------------------

@app.route("/api/improvement/advise", methods=["POST"])
def get_improvement_advisories():
    data, code = backend_logic.handle_improvement_advisories(request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/improvement/candidate/<candidate_id>/apply", methods=["POST"])
def apply_improvement_candidate(candidate_id):
    data, code = backend_logic.handle_apply_improvement_candidate(candidate_id, request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/improvement/candidate/<candidate_id>/rollback", methods=["POST"])
@app.route("/api/improvement/candidate/<candidate_id>/apply_failed", methods=["POST"])
def rollback_improvement_candidate(candidate_id):
    data, code = backend_logic.handle_rollback_improvement_candidate(candidate_id, request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/improvement/candidate/<candidate_id>/reject", methods=["POST"])
def reject_improvement_candidate(candidate_id):
    data, code = backend_logic.handle_reject_improvement_candidate(candidate_id)
    return jsonify(data), code


@app.route("/api/rules/candidates", methods=["GET"])
def get_candidate_rules():
    data, code = backend_logic.handle_candidate_rules()
    return jsonify(data), code


@app.route("/api/rules/propose", methods=["POST"])
def propose_rule():
    data, code = backend_logic.handle_propose_rule(request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/rules/candidate/<rule_id>/validate", methods=["POST"])
def validate_rule(rule_id):
    data, code = backend_logic.handle_validate_rule(rule_id)
    return jsonify(data), code


@app.route("/api/rules/candidate/<rule_id>/approve", methods=["POST"])
def approve_rule(rule_id):
    data, code = backend_logic.handle_approve_rule(rule_id, request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/rules/candidate/<rule_id>/reject", methods=["POST"])
def reject_rule(rule_id):
    data, code = backend_logic.handle_reject_rule(rule_id, request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/rules/active", methods=["GET"])
def get_active_rules():
    data, code = backend_logic.handle_active_rules()
    return jsonify(data), code


@app.route("/api/rules/active/<rule_id>/disable", methods=["POST"])
def disable_active_rule(rule_id):
    data, code = backend_logic.handle_disable_active_rule(rule_id, request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/rules/active/<rule_id>/enable", methods=["POST"])
def enable_active_rule(rule_id):
    data, code = backend_logic.handle_enable_active_rule(rule_id, request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/rules/active/<rule_id>/rollback", methods=["POST"])
def rollback_active_rule(rule_id):
    data, code = backend_logic.handle_rollback_active_rule(rule_id, request.get_json(silent=True) or {})
    return jsonify(data), code


@app.route("/api/rules/history", methods=["GET"])
def get_rule_history():
    data, code = backend_logic.handle_rule_history()
    return jsonify(data), code


# -------------------------------------------------------------
# GROUP 6: BENCHMARK & GREEN ROUTES
# -------------------------------------------------------------

@app.route("/api/green/config", methods=["GET"])
def get_green_config():
    data, code = backend_logic.handle_green_config()
    return jsonify(data), code


@app.route("/api/green/measure", methods=["POST", "GET"])
def measure_green():
    data_in = request.get_json(silent=True) if request.method == "POST" else request.args
    data, code = backend_logic.handle_measure_green(data_in or {})
    return jsonify(data), code


@app.route("/api/green/history", methods=["GET"])
def get_green_history():
    limit = int(request.args.get("limit", 30))
    data, code = backend_logic.handle_green_history(limit)
    return jsonify(data), code


@app.route("/api/benchmark/status", methods=["GET"])
def get_benchmark_status():
    data, code = backend_logic.handle_benchmark_status()
    return jsonify(data), code


@app.route("/api/benchmark/dataset", methods=["GET"])
def get_benchmark_dataset():
    data, code = backend_logic.handle_benchmark_dataset()
    return jsonify(data), code


@app.route("/api/benchmark/definitions", methods=["GET"])
def get_benchmark_definitions():
    data, code = backend_logic.handle_benchmark_definitions()
    return jsonify(data), code


@app.route("/api/benchmark/run", methods=["POST"])
def run_benchmark():
    data, code = backend_logic.handle_run_benchmark(request.get_json(silent=True) or {})
    return jsonify(data), code


def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")


if __name__ == "__main__":
    import logging
    logger = logging.getLogger(__name__)
    print("Initializing server startup...", flush=True)
    if not app.testing and not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            from compiler.repair_job_manager import get_repair_job_manager
            resumed_count = get_repair_job_manager().resume_unfinished_jobs()
            print(f"Resumed {resumed_count} unfinished repair jobs.", flush=True)
        except Exception as exc:
            logger.error("Failed to resume unfinished repair jobs on startup: %s", exc, exc_info=True)
    print("Starting Flask web server on http://127.0.0.1:5000 ...", flush=True)
    threading.Timer(1.0, open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
