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


@app.route("/api/languages")
def languages():
    return jsonify(LANGUAGES)


def _resolve_lang_and_filename(data, default_name_fn=None):
    req_lang = data.get("language")
    filename = data.get("filename")

    if req_lang:
        lang_id = req_lang.strip().lower()
        if not get_language(lang_id):
            return None, None, (jsonify({"error": f"Unknown language: {req_lang}"}), 400)
    else:
        lang_id = detect_language(filename)

    if not filename and default_name_fn:
        filename = default_name_fn(lang_id)
    elif not filename:
        lang_obj = get_language(lang_id)
        filename = lang_obj["default_name"] if lang_obj else "main.c"

    if not extension_ok(lang_id, filename):
        return None, None, (jsonify({"error": f"Filename '{filename}' does not match language '{lang_id}'"}), 400)

    return lang_id, filename, None


@app.route("/api/repair", methods=["POST"])
def repair():
    data = request.json or {}
    code = data.get("code") or data.get("source_code", "")
    approval_token = data.get("approval_token")
    lang_id, filename, err_resp = _resolve_lang_and_filename(data)
    if err_resp:
        return err_resp

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=code,
        filename=filename,
        language=lang_id,
        operation="repair",
        approval_token=approval_token,
    )
    if not permitted:
        return jsonify(warning_payload), gate_status

    from compiler.gui_bridge import repair_source_for_gui
    result = repair_source_for_gui(code, filename, language=lang_id)
    if "analysis_mode" not in result:
        from compiler.call_extractor import get_extraction_mode
        result["analysis_mode"] = get_extraction_mode(code) if lang_id == "c" else "AST"
    return jsonify(result)


@app.route("/api/repair/job", methods=["POST"])
def repair_job_start():
    data = request.json or {}
    code = data.get("code") or data.get("source_code", "")
    approval_token = data.get("approval_token")
    lang_id, filename, err_resp = _resolve_lang_and_filename(data)
    if err_resp:
        return err_resp

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=code,
        filename=filename,
        language=lang_id,
        operation="repair",
        approval_token=approval_token,
    )
    if not permitted:
        return jsonify(warning_payload), gate_status

    from compiler.repair_job_manager import get_repair_job_manager
    job_mgr = get_repair_job_manager()
    job = job_mgr.create_job(
        code=code,
        filename=filename,
        language=lang_id,
        operation="repair",
        approval_token=approval_token,
    )
    job_mgr.start_job(job)
    return jsonify({"job_id": job.job_id, "state": job.state}), 202


@app.route("/api/repair/job/<path:job_id>", methods=["GET"])
def repair_job_status(job_id):
    import re
    if not re.fullmatch(r'^[a-f0-9]{32}$', job_id):
        return jsonify({"error": f"Invalid job_id: '{job_id}'. Must match ^[a-f0-9]{{32}}$"}), 400
    from compiler.repair_job_manager import get_repair_job_manager
    job = get_repair_job_manager().get_job(job_id)
    if not job:
        return jsonify({"error": f"Job {job_id} not found"}), 404
    return jsonify(job.to_status_dict())


@app.route("/api/repair/job/<path:job_id>/cancel", methods=["POST"])
def repair_job_cancel(job_id):
    import re
    if not re.fullmatch(r'^[a-f0-9]{32}$', job_id):
        return jsonify({"error": f"Invalid job_id: '{job_id}'. Must match ^[a-f0-9]{{32}}$"}), 400
    from compiler.repair_job_manager import get_repair_job_manager
    cancelled = get_repair_job_manager().cancel_job(job_id)
    if not cancelled:
        return jsonify({"error": f"Job {job_id} not found", "cancelled": False}), 404
    return jsonify({"job_id": job_id, "status": "cancelled", "state": "CANCELLED", "cancelled": True})


@app.route("/api/repair/job/<path:job_id>", methods=["DELETE"])
def repair_job_delete(job_id):
    import re
    if not re.fullmatch(r'^[a-f0-9]{32}$', job_id):
        return jsonify({"error": f"Invalid job_id: '{job_id}'. Must match ^[a-f0-9]{{32}}$"}), 400
    from compiler.repair_job_manager import get_repair_job_manager
    try:
        deleted = get_repair_job_manager().delete_job(job_id)
        if not deleted:
            return jsonify({"error": f"Job {job_id} not found"}), 404
        return jsonify({"job_id": job_id, "deleted": True, "message": "Job deleted successfully"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400



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


@app.route("/api/testcase", methods=["POST"])
def testcase():
    data = request.json or {}
    code = data.get("code") or data.get("source_code", "")

    def default_test_name(lid):
        return "test_case.py" if lid == "python" else "test_case.c"

    lang_id, filename, err_resp = _resolve_lang_and_filename(data, default_name_fn=default_test_name)
    if err_resp:
        return err_resp

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=code,
        filename=filename,
        language=lang_id,
        operation="execute",
        approval_token=data.get("approval_token"),
    )
    if not permitted:
        return jsonify(warning_payload), gate_status

    from compiler.gui_bridge import repair_source_for_gui
    result = repair_source_for_gui(code, filename, language=lang_id)
    return jsonify(result)


@app.route("/api/program/run", methods=["POST"])
@app.route("/api/run", methods=["POST"])
@app.route("/run", methods=["POST"])
@app.route("/execute", methods=["POST"])
@app.route("/api/execute", methods=["POST"])
def run_program():
    """
    Dedicated program execution endpoint.
    Compiles and executes C (or Python) source code in an isolated sandbox.
    Completely decoupled from CodeT5 / Qwen AI repair workflows and metric computations.
    Enforces mandatory Security Decision Gate and User Approval.
    """
    data = request.json or {}
    code = data.get("code") or data.get("source_code", "")
    stdin_data = data.get("stdin", "")
    timeout_sec = data.get("timeout", 4.0)
    approval_token = data.get("approval_token")

    lang_id, filename, err_resp = _resolve_lang_and_filename(data)
    if err_resp:
        lang_id = data.get("language", "c").strip().lower()
        filename = data.get("filename", "main.c")

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=code,
        filename=filename,
        language=lang_id,
        operation="execute",
        approval_token=approval_token,
    )
    if not permitted:
        return jsonify(warning_payload), gate_status

    from compiler.program_executor import ProgramExecutor
    executor = ProgramExecutor()
    res = executor.execute_program(
        source_code=code,
        language=lang_id,
        stdin_input=stdin_data,
        timeout_sec=timeout_sec,
        filename=filename,
        approval_token=approval_token,
        gate_already_verified=True,
    )
    res_dict = res.to_dict()
    status_code = 423 if res_dict.get("is_refused") else 200
    return jsonify(res_dict), status_code


@app.route("/api/security/prescan", methods=["POST"])
def security_prescan():
    """
    Pre-scan endpoint: performs full static security analysis BEFORE repair or execution.
    Returns HTTP 409 with warning payload if security findings exist and no valid approval token is provided.
    Returns HTTP 200 if clean or if approved with a valid one-time token.
    """
    data = request.json or {}
    code = data.get("code") or data.get("source_code", "")
    filename = data.get("filename", "main.c")
    language = data.get("language", "c")
    operation = data.get("operation", "prescan")
    approval_token = data.get("approval_token")

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=code,
        filename=filename,
        language=language,
        operation=operation,
        approval_token=approval_token,
    )
    if not permitted:
        return jsonify(warning_payload), gate_status

    import hashlib
    return jsonify({
        "status": "PASSED",
        "requires_approval": False,
        "can_override": True,
        "is_prohibited": False,
        "overall_risk": "NONE",
        "heading": "Security Gate Passed",
        "summary": "Program passed all security checks. Compilation and execution permitted.",
        "explanation": "No security issues detected. Code is safe for compilation and execution.",
        "findings_by_severity": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
        "security_checks_completed": True,
        "findings": [],
        "findings_count": 0,
        "source_hash": hashlib.sha256(code.encode("utf-8")).hexdigest(),
        "filename": filename,
        "operation": operation,
    }), 200


@app.route("/api/security/approval/check", methods=["POST"])
def security_approval_check():
    data = request.json or {}
    code = data.get("code") or data.get("source_code", "")
    filename = data.get("filename", "main.c")
    language = data.get("language", "c")
    operation = data.get("operation", "execute")

    from compiler.security_approval_gate import SecurityDecisionGate
    verdict = SecurityDecisionGate.evaluate(
        source_code=code,
        filename=filename,
        language=language,
        operation=operation,
    )
    return jsonify(verdict.to_dict())


@app.route("/api/security/approval/approve", methods=["POST"])
def security_approval_approve():
    data = request.json or {}
    code = data.get("code") or data.get("source_code", "")
    filename = data.get("filename", "main.c")
    language = data.get("language", "c")
    operation = data.get("operation", "execute")
    force = bool(data.get("force", False))

    from compiler.security_approval_gate import SecurityApprovalManager
    success, token, msg = SecurityApprovalManager.create_one_time_approval(
        source_code=code,
        filename=filename,
        language=language,
        operation=operation,
        force=force,
    )
    if not success:
        return jsonify({"success": False, "error": msg, "can_override": False}), 403

    return jsonify({
        "success": True,
        "approval_token": token,
        "message": msg,
        "expires_in_sec": SecurityApprovalManager.DEFAULT_TTL_SEC,
    })


@app.route("/api/security/approval/cancel", methods=["POST"])
def security_approval_cancel():
    data = request.json or {}
    code = data.get("code") or data.get("source_code", "")
    filename = data.get("filename", "main.c")
    operation = data.get("operation", "execute")

    from compiler.security_approval_gate import SecurityApprovalManager
    SecurityApprovalManager.record_cancellation(
        source_code=code,
        filename=filename,
        operation=operation,
    )
    return jsonify({
        "success": True,
        "message": "Compilation/execution cancelled. Program remains uncompiled and unexecuted."
    })


@app.route("/api/examples")
def examples():
    lang_id = request.args.get("language", "c").strip().lower()
    lang_obj = get_language(lang_id)
    if not lang_obj:
        return jsonify({"error": f"Unknown language: {lang_id}"}), 400

    valid_exts = tuple(lang_obj["extensions"])
    example_root = "examples"
    files = []

    if os.path.exists(example_root):
        for root, dirs, filenames in os.walk(example_root):
            dirs[:] = [d for d in dirs if not d.startswith((".", "_")) and d != "__pycache__"]
            for f in filenames:
                if f.startswith((".", "_")):
                    continue
                if f.lower().endswith(valid_exts):
                    if "_fixed." in f.lower():
                        continue
                    rel_path = os.path.relpath(os.path.join(root, f), example_root)
                    parts = rel_path.replace("\\", "/").split("/")
                    if any(p.startswith((".", "_")) or p == "__pycache__" for p in parts):
                        continue
                    files.append("/".join(parts))

    files.sort()
    return jsonify(files)


@app.route("/api/example/<path:name>")
def load_example(name):
    lang_id = request.args.get("language")
    if lang_id:
        lang_id = lang_id.strip().lower()
        if not get_language(lang_id):
            return jsonify({"error": f"Unknown language: {lang_id}"}), 404

    root = os.path.realpath("examples")
    full = os.path.realpath(os.path.join(root, name))

    try:
        common = os.path.commonpath([root, full])
    except ValueError:
        return jsonify({"error": "Invalid path"}), 404

    if common != root or full == root or not os.path.isfile(full):
        return jsonify({"error": "Example not found"}), 404

    rel = os.path.relpath(full, root)
    parts = rel.replace("\\", "/").split("/")
    if any(p.startswith((".", "_")) or p == "__pycache__" for p in parts):
        return jsonify({"error": "Example not found"}), 404

    if lang_id:
        if not extension_ok(lang_id, full):
            return jsonify({"error": "Extension does not match language"}), 404
    else:
        detected = detect_language(full)
        if not extension_ok(detected, full):
            return jsonify({"error": "Extension not recognized"}), 404

    with open(full, "r", encoding="utf-8") as f:
        code = f.read()

    return jsonify({"code": code, "filename": "/".join(parts)})


@app.route("/api/file/create", methods=["POST"])
def create_file():
    data = request.json or {}
    filename = data.get("filename", "").strip()
    code = data.get("code", "")
    folder = data.get("folder", "user_tests").strip()

    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    from compiler.security_gate import PreExecutionSecurityGate
    f_verdict = PreExecutionSecurityGate.check_file_operation(filename, operation="create")
    if f_verdict.is_blocked:
        return jsonify(f_verdict.to_dict()), 403

    if not filename.endswith(".c") and not filename.endswith(".py"):
        filename += ".c"

    filename = os.path.basename(filename)

    if folder:
        safe_folder = os.path.normpath(folder).replace("..", "").strip("/\\")
        target_dir = os.path.join("examples", safe_folder)
    else:
        target_dir = os.path.join("examples", "user_tests")

    default_template = """int main() {
    // Write your C code here
    return 0;
}
"""
    file_content = code if code is not None and code != "" else default_template

    # Content precheck: file can be created without hard blocking

    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, filename)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(file_content)

    rel_name = os.path.relpath(full_path, "examples").replace("\\", "/")
    return jsonify({
        "success": True,
        "filename": rel_name,
        "code": file_content,
        "message": f"Created {rel_name}"
    })


@app.route("/api/file/save", methods=["POST"])
def save_file():
    data = request.json or {}
    filename = data.get("filename", "").strip()
    code = data.get("code", "")

    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    clean_filename = filename.replace("\\", "/").strip("/")
    if clean_filename.startswith("examples/"):
        clean_filename = clean_filename[len("examples/"):]

    safe_rel = os.path.normpath(clean_filename).replace("..", "").strip("/\\")

    # Mandatory security gate on target file and content
    from compiler.security_gate import PreExecutionSecurityGate
    f_verdict = PreExecutionSecurityGate.check_file_operation(safe_rel, operation="save")
    if f_verdict.is_blocked:
        return jsonify(f_verdict.to_dict()), 403

    # Content precheck warning: code can be saved in editor without hard blocking

    full_path = os.path.join("examples", safe_rel)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(code)

    # Strictly limit root sync to only default demo entry points (main.c, main.py)
    # NEVER allow arbitrary files to be written into workspace root.
    if safe_rel in ("main.c", "main.py"):
        try:
            with open(safe_rel, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception:
            pass

    return jsonify({"success": True, "message": f"Saved {safe_rel}", "filename": safe_rel})


@app.route("/api/models/status")
def models_status():
    """Inspect local model readiness (CodeT5 adapters, Ollama daemon, VRAM)."""
    try:
        from compiler.local_models import LocalModelPipeline
        pipeline = LocalModelPipeline()
        status = pipeline.get_system_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e), "offline_enforced": True}), 500


@app.route("/api/models/unload", methods=["POST"])
def models_unload():
    """Trigger memory cleanup: unload CodeT5 and signal Ollama to release VRAM."""
    try:
        from compiler.local_models import LocalModelPipeline
        pipeline = LocalModelPipeline()
        pipeline.codet5.unload()
        ollama_ok = pipeline.ollama.unload_model()
        return jsonify({
            "success": True,
            "message": "Models unloaded from memory",
            "codet5_unloaded": True,
            "ollama_unloaded": ollama_ok,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Global patch validation history manager (Never apply AI patch without explicit approval)
from compiler.patch_validator import PatchValidator, PatchHistoryManager
patch_history = PatchHistoryManager()
patch_validator = PatchValidator()


@app.route("/api/patch/validate", methods=["POST"])
def validate_patch():
    """Validate a candidate patch across syntax, compilation, semantic, and security stages."""
    import uuid
    data = request.json or {}
    orig_code = data.get("original_code", "")
    cand_code = data.get("candidate_code", "")
    filename = data.get("filename", "main.c")
    explanation = data.get("explanation", "Proposed candidate repair")
    assumptions = data.get("assumptions", [])
    expected_effects = data.get("expected_effects", [])

    if not cand_code:
        return jsonify({"error": "Candidate code is required"}), 400

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=cand_code,
        filename=filename,
        language=detect_language(filename),
        operation="validate",
        approval_token=data.get("approval_token"),
    )
    if not permitted:
        return jsonify(warning_payload), gate_status

    report = patch_validator.validate_patch(
        original_code=orig_code,
        candidate_code=cand_code,
        filename=filename,
    )

    patch_id = f"PATCH-{uuid.uuid4().hex[:8]}"
    item = patch_history.register_candidate_patch(
        patch_id=patch_id,
        file_path=filename,
        original_code=orig_code,
        patched_code=cand_code,
        explanation=explanation,
        report=report,
        assumptions=assumptions,
        expected_effects=expected_effects,
    )

    return jsonify(item.to_dict())


@app.route("/api/patch/apply", methods=["POST"])
def apply_patch():
    """
    Explicit user approval endpoint.
    NEVER apply an AI patch without explicit approval from this endpoint.
    """
    data = request.json or {}
    patch_id = data.get("patch_id", "")
    if not patch_id:
        return jsonify({"error": "patch_id is required"}), 400

    current_code = data.get("current_code") or data.get("current_source_code")
    if current_code:
        from compiler.security_approval_gate import enforce_security_gate_for_request
        permitted, warning_payload, gate_status = enforce_security_gate_for_request(
            source_code=current_code,
            filename=data.get("filename", "main.c"),
            language=detect_language(data.get("filename", "main.c")),
            operation="apply_patch",
            approval_token=data.get("approval_token"),
        )
        if not permitted:
            return jsonify(warning_payload), gate_status

    success, msg, item = patch_history.approve_and_apply(patch_id, current_source=current_code)
    if not success or not item:
        if "ineligible" in msg or "validation failed" in msg or "tampered" in msg.lower() or "modified" in msg.lower():
            status_code = 400
        elif "Stale" in msg or "already" in msg:
            status_code = 409
        elif "not found" in msg.lower():
            status_code = 404
        else:
            status_code = 400
        return jsonify({"error": msg, "success": False}), status_code

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=item.patched_code,
        filename=item.file_path,
        language=detect_language(item.file_path),
        operation="apply_patch",
        approval_token=data.get("approval_token"),
    )
    if not permitted:
        return jsonify(warning_payload), gate_status

    # Run verification analysis on newly applied code
    from compiler.orchestrator import AgentOrchestrator
    orchestrator = AgentOrchestrator()
    analysis = orchestrator.run_analysis(item.patched_code, filename=item.file_path)

    return jsonify({
        "success": True,
        "message": msg,
        "patch_id": patch_id,
        "applied_code": item.patched_code,
        "user_decision": "APPROVED",
        "analysis_after": analysis.to_dict(),
        "revert_available": len(patch_history.applied_history) > 0,
    })


@app.route("/api/patch/reject", methods=["POST"])
def reject_patch():
    """User explicitly rejects a candidate patch."""
    data = request.json or {}
    patch_id = data.get("patch_id", "")
    reason = data.get("reason", "Rejected by user")
    if not patch_id:
        return jsonify({"error": "patch_id is required"}), 400

    success, msg = patch_history.reject(patch_id, reason=reason)
    if not success:
        return jsonify({"error": msg}), 404

    return jsonify({"success": True, "message": msg, "patch_id": patch_id, "user_decision": "REJECTED"})


@app.route("/api/patch/revert", methods=["POST"])
def revert_patch():
    """Revert the most recently applied patch to its preserved original source."""
    success, msg, orig_code = patch_history.revert_last()
    if not success or orig_code is None:
        return jsonify({"error": msg}), 400

    return jsonify({
        "success": True,
        "message": msg,
        "restored_code": orig_code,
        "revert_available": len(patch_history.applied_history) > 0,
    })


@app.route("/api/security/report", methods=["POST"])
def security_report():
    """Run comprehensive security vulnerability analysis on source code."""
    data = request.json or {}
    code = data.get("code") or data.get("source_code", "")
    filename = data.get("filename", "main.c")

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=code,
        filename=filename,
        language=detect_language(filename),
        operation="report",
        approval_token=data.get("approval_token"),
    )
    if not permitted:
        return jsonify(warning_payload), gate_status

    from compiler.security_reporter import SecurityReporter
    reporter = SecurityReporter()
    report = reporter.analyze_source(code, filename=filename)
    return jsonify(report.to_dict())


@app.route("/api/security/compare", methods=["POST"])
def security_compare():
    """Compare security vulnerabilities before and after a patch (delta analysis)."""
    data = request.json or {}
    original_code = data.get("original_code", "")
    patched_code = data.get("patched_code", "")
    filename = data.get("filename", "main.c")

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=original_code,
        filename=filename,
        language=detect_language(filename),
        operation="compare",
        approval_token=data.get("approval_token"),
    )
    if not permitted:
        return jsonify(warning_payload), gate_status

    permitted2, warning_payload2, gate_status2 = enforce_security_gate_for_request(
        source_code=patched_code,
        filename=filename,
        language=detect_language(filename),
        operation="compare",
        approval_token=data.get("approval_token"),
    )
    if not permitted2:
        return jsonify(warning_payload2), gate_status2

    from compiler.security_reporter import SecurityReporter
    reporter = SecurityReporter()
    delta = reporter.compare_patches(original_code, patched_code, filename=filename)
    return jsonify(delta.to_dict())


@app.route("/api/security/benchmark", methods=["GET"])
def security_benchmark():
    """Evaluate security analyzer against ground-truth labeled benchmark suite."""
    from compiler.security_reporter import SecurityBenchmarkEvaluator
    benchmark_dir = request.args.get("dir", "examples/security_fix_2026")
    if not os.path.exists(benchmark_dir):
        return jsonify({"error": f"Benchmark directory not found: {benchmark_dir}"}), 404

    evaluator = SecurityBenchmarkEvaluator()
    res = evaluator.evaluate_directory(benchmark_dir)
    return jsonify(res.to_dict())


@app.route("/api/security/remediation", methods=["POST"])
def security_remediation():
    """
    Generate general remediation recommendations and code fix proposals
    for all detected security vulnerabilities in source code.
    """
    data = request.get_json(silent=True) or {}
    code = data.get("code") or data.get("source_code") or ""
    filename = data.get("filename", "main.c")
    req_lang = data.get("language")

    lang_id, resolved_filename, err_resp = _resolve_lang_and_filename(data)
    if not lang_id:
        lang_id = detect_language(filename, req_lang)
    if not resolved_filename:
        resolved_filename = "main.py" if lang_id == "python" else (filename or "main.c")

    from compiler.security_remediation import SecurityRemediationEngine, EPISTEMIC_DISCLAIMER
    engine = SecurityRemediationEngine()
    recs = engine.generate_recommendations(
        source_code=code,
        filename=resolved_filename,
        language=lang_id,
        findings=data.get("findings"),
    )
    return jsonify({
        "status": "SUCCESS",
        "recommendations": [r.to_dict() for r in recs],
        "count": len(recs),
        "epistemic_disclaimer": EPISTEMIC_DISCLAIMER,
    })


@app.route("/api/security/apply", methods=["POST"])
def security_apply():
    """
    Explicitly apply an accepted security remediation proposal to the program.
    Does NOT modify source code before explicit user approval.
    """
    data = request.get_json(silent=True) or {}
    candidate_id = data.get("candidate_id")
    proposed_code = data.get("proposed_code")
    original_code = data.get("original_code") or data.get("code") or ""
    filename = data.get("filename", "main.c")
    language = data.get("language", "c")

    from compiler.improvement_advisor import candidate_registry
    cand_obj = candidate_registry.get(candidate_id) if candidate_id else None

    if cand_obj:
        if cand_obj.original_source_hash and original_code:
            current_h = hashlib.sha256(original_code.encode("utf-8")).hexdigest()
            if current_h != cand_obj.original_source_hash:
                return jsonify({
                    "success": False,
                    "error": "Stale candidate proposal: Source code has changed since the candidate was generated. Please re-run analysis to generate a current proposal.",
                    "is_stale": True,
                }), 409
        if not proposed_code:
            proposed_code = cand_obj.proposed_code
        if not original_code:
            original_code = cand_obj.original_code

    if not proposed_code:
        return jsonify({"success": False, "error": "No proposed code available to apply"}), 400

    try:
        p_item = patch_history.register_candidate_patch(
            patch_id=f"PATCH-SEC-{uuid.uuid4().hex[:8]}",
            file_path=filename,
            original_code=original_code,
            patched_code=proposed_code,
            explanation=f"Security Remediation Apply: {candidate_id or 'explicit'}",
        )
        patch_history.approve_and_apply(p_item.patch_id, current_source=original_code)
    except Exception:
        pass

    from compiler.patch_validator import PatchValidator
    validator = PatchValidator()
    val_report = validator.validate_patch(
        original_code=original_code,
        candidate_code=proposed_code,
        filename=filename,
        language=language,
    )

    if not val_report.is_valid:
        return jsonify({
            "success": False,
            "error": f"Candidate rejected: validation failed ({val_report.verdict.value}): {val_report.explanation}",
            "applied_code": None,
            "validation_report": val_report.to_dict(),
            "is_valid": False,
            "candidate_id": candidate_id,
        }), 400

    return jsonify({
        "success": True,
        "applied_code": proposed_code,
        "validation_report": val_report.to_dict(),
        "is_valid": True,
        "candidate_id": candidate_id,
    })


@app.route("/api/rules/candidates", methods=["GET"])
def get_candidate_rules():
    """List all proposed candidate rules with test and validation reports."""
    from compiler.rule_repository import RuleRepositoryManager
    repo = RuleRepositoryManager()
    return jsonify({
        "candidates": [c.to_dict() for c in repo.candidates.values()],
        "count": len(repo.candidates),
    })


@app.route("/api/rules/propose", methods=["POST"])
def propose_rule():
    """Propose a new candidate rule into the separate candidate-rule repository."""
    data = request.get_json(silent=True) or {}
    from compiler.rule_repository import RuleRepositoryManager, RuleTestCase
    repo = RuleRepositoryManager()

    name = data.get("name", "Candidate Rule")
    category = data.get("category", "syntax")
    error_reason = data.get("error_reason", "generic")
    triggering_conditions = data.get("triggering_conditions", {})
    applicable_context = data.get("applicable_context", "")
    transformation = data.get("transformation", {})
    assumptions = data.get("assumptions", [])
    pos_tests = [RuleTestCase.from_dict(t) for t in data.get("positive_tests", [])]
    neg_tests = [RuleTestCase.from_dict(t) for t in data.get("negative_tests", [])]
    amb_tests = [RuleTestCase.from_dict(t) for t in data.get("ambiguous_cases", [])]
    proposer = data.get("source_model") or data.get("proposer", "human_user")

    cand = repo.propose_candidate(
        name=name,
        category=category,
        error_reason=error_reason,
        triggering_conditions=triggering_conditions,
        applicable_context=applicable_context,
        transformation=transformation,
        assumptions=assumptions,
        positive_tests=pos_tests,
        negative_tests=neg_tests,
        ambiguous_cases=amb_tests,
        proposer=proposer,
        source_model=proposer,
    )
    cand_dict = cand.to_dict()
    return jsonify({"success": True, "candidate": cand_dict, **cand_dict}), 201


@app.route("/api/rules/candidate/<rule_id>/validate", methods=["POST"])
def validate_rule(rule_id):
    """Run regression tests and security checks against a candidate rule."""
    from compiler.rule_repository import RuleRepositoryManager
    repo = RuleRepositoryManager()
    rep = repo.validate_candidate(rule_id)
    if not rep:
        return jsonify({"error": f"Candidate rule '{rule_id}' not found", "success": False}), 404
    rep_dict = rep.to_dict()
    return jsonify({"success": True, "report": rep_dict, **rep_dict})


@app.route("/api/rules/candidate/<rule_id>/approve", methods=["POST"])
def approve_rule(rule_id):
    """
    Explicit human review and approval gate to activate a candidate rule.
    Models are strictly blocked from self-promotion.
    """
    data = request.get_json(silent=True) or {}
    reviewer = data.get("reviewer_name") or data.get("reviewer", "")
    comments = data.get("approval_notes") or data.get("comments", "")
    from compiler.rule_repository import RuleRepositoryManager
    repo = RuleRepositoryManager()
    try:
        active = repo.approve_and_activate(rule_id, reviewer_name=reviewer, comments=comments)
        active_dict = active.to_dict()
        return jsonify({
            "success": True,
            "message": f"Rule '{rule_id}' approved and activated.",
            "rule": active_dict,
            "active_rule": active_dict,
        })
    except PermissionError as pe:
        return jsonify({"error": str(pe), "success": False}), 403
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 400


@app.route("/api/rules/candidate/<rule_id>/reject", methods=["POST"])
def reject_rule(rule_id):
    """Human rejection of a candidate rule."""
    data = request.get_json(silent=True) or {}
    reviewer = data.get("reviewer_name") or data.get("reviewer", "human_reviewer")
    reason = data.get("reason", "Rejected during human review")
    from compiler.rule_repository import RuleRepositoryManager
    repo = RuleRepositoryManager()
    ok, msg = repo.reject_candidate(rule_id, reviewer_name=reviewer, reason=reason)
    if not ok:
        return jsonify({"error": msg, "success": False}), 404
    return jsonify({"success": True, "message": msg})


@app.route("/api/rules/active", methods=["GET"])
def get_active_rules():
    """List active deterministic rules with versions, status, and history."""
    from compiler.rule_repository import RuleRepositoryManager
    repo = RuleRepositoryManager()
    rules_list = [r.to_dict() for r in repo.active_rules.values()]
    return jsonify({
        "success": True,
        "rules": rules_list,
        "active_rules": rules_list,
        "count": len(repo.active_rules),
    })


@app.route("/api/rules/active/<rule_id>/disable", methods=["POST"])
def disable_active_rule(rule_id):
    """Disable an active rule to prevent regressions."""
    data = request.get_json(silent=True) or {}
    reviewer = data.get("reviewer_name") or data.get("reviewer", "human_reviewer")
    reason = data.get("reason", "Disabled due to suspected regression")
    from compiler.rule_repository import RuleRepositoryManager
    repo = RuleRepositoryManager()
    try:
        active = repo.disable_rule(rule_id, reviewer_name=reviewer, reason=reason)
        active_dict = active.to_dict()
        return jsonify({"success": True, "rule": active_dict, "active_rule": active_dict})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 404


@app.route("/api/rules/active/<rule_id>/enable", methods=["POST"])
def enable_active_rule(rule_id):
    """Re-enable a previously disabled active rule."""
    data = request.get_json(silent=True) or {}
    reviewer = data.get("reviewer_name") or data.get("reviewer", "human_reviewer")
    from compiler.rule_repository import RuleRepositoryManager
    repo = RuleRepositoryManager()
    try:
        active = repo.enable_rule(rule_id, reviewer_name=reviewer)
        active_dict = active.to_dict()
        return jsonify({"success": True, "rule": active_dict, "active_rule": active_dict})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 404


@app.route("/api/rules/active/<rule_id>/rollback", methods=["POST"])
def rollback_active_rule(rule_id):
    """Roll back an active rule to a specified prior version."""
    data = request.get_json(silent=True) or {}
    target_version = data.get("target_version", "")
    reviewer = data.get("reviewer_name") or data.get("reviewer", "human_reviewer")
    from compiler.rule_repository import RuleRepositoryManager
    repo = RuleRepositoryManager()
    try:
        active = repo.rollback_rule(rule_id, target_version=target_version, reviewer_name=reviewer)
        active_dict = active.to_dict()
        return jsonify({"success": True, "rule": active_dict, "active_rule": active_dict})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 400


@app.route("/api/rules/history", methods=["GET"])
def get_rule_history():
    """Audit log of rule activations, disables, and rollbacks."""
    from compiler.rule_repository import RuleRepositoryManager
    repo = RuleRepositoryManager()
    return jsonify({"history": repo.history, "count": len(repo.history)})


@app.route("/api/quality/score", methods=["POST", "GET"])
def calculate_quality_score():
    """
    Calculates the Code Quality Score (0-100) across 5 documented dimensions:
    Correctness, Maintainability, Compliance, Complexity, Efficiency.
    Distinguishes measured properties from heuristic estimates.
    Returns INSUFFICIENT_INFORMATION when source is empty or fragmented.
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    code = data.get("code", "")
    filename = data.get("filename", "main.c")
    cfg_dict = data.get("config")

    from compiler.code_quality import CodeQualityScorer, QualityConfig

    cfg = QualityConfig(**cfg_dict) if isinstance(cfg_dict, dict) else QualityConfig()
    scorer = CodeQualityScorer(cfg)
    report = scorer.analyze_source(source_code=code, filename=filename)
    return jsonify(report.to_dict())


@app.route("/api/quality/config", methods=["GET"])
def get_quality_config():
    """Returns the documented quality dimensions, weights, and scoring thresholds."""
    from compiler.code_quality import QualityConfig, QUALITY_DISCLAIMER
    cfg = QualityConfig()
    return jsonify({
        "config": cfg.to_dict(),
        "disclaimer": QUALITY_DISCLAIMER,
        "dimensions": [
            {
                "name": "correctness",
                "weight": cfg.weight_correctness,
                "type": "MEASURED",
                "description": "Deterministic syntax errors, semantic diagnostics, and confirmed security vulnerabilities.",
            },
            {
                "name": "compliance",
                "weight": cfg.weight_compliance,
                "type": "HYBRID",
                "description": "Canonical main signatures, header includes, and consistent indentation discipline.",
            },
            {
                "name": "maintainability",
                "weight": cfg.weight_maintainability,
                "type": "HEURISTIC",
                "description": "Function length, comment-to-code ratio, line length limits, and identifier clarity.",
            },
            {
                "name": "complexity",
                "weight": cfg.weight_complexity,
                "type": "MEASURED",
                "description": "Cyclomatic decision point complexity and control-flow block nesting depth.",
            },
            {
                "name": "efficiency",
                "weight": cfg.weight_efficiency,
                "type": "HYBRID",
                "description": "Nested loop complexity, quadratic string patterns, and Green Compiler runtime profile.",
            },
        ],
    })


@app.route("/api/optimization/potential", methods=["POST", "GET"])
def get_optimization_potential():
    """
    Computes Optimization Potential (%) estimating remaining improvement opportunity.
    Explicitly distinguishes STATIC_ESTIMATE from MEASURED_BENCHMARK.
    Returns INSUFFICIENT_INFORMATION when source is empty or brief.
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    code = data.get("code", "")
    filename = data.get("filename", "main.c")
    weights = data.get("weights")
    green_metrics = data.get("green_metrics")

    from compiler.optimization_potential import OptimizationPotentialAnalyzer

    analyzer = OptimizationPotentialAnalyzer(weights=weights if isinstance(weights, dict) else None)
    report = analyzer.analyze(source_code=code, filename=filename, green_metrics=green_metrics)
    return jsonify(report.to_dict())


@app.route("/api/optimization/config", methods=["GET"])
def get_optimization_config():
    """Returns documented optimization categories, default weights, and epistemological disclaimer."""
    from compiler.optimization_potential import OPTIMIZATION_DISCLAIMER, OpportunityCategory, EstimateType

    return jsonify({
        "disclaimer": OPTIMIZATION_DISCLAIMER,
        "estimate_types": [e.value for e in EstimateType],
        "categories": [
            {
                "category": OpportunityCategory.ALGORITHMIC_COMPLEXITY.value,
                "weight": 0.30,
                "description": "Polynomial and cubic loop nesting (O(N^2), O(N^3)) and linear search bottlenecks.",
            },
            {
                "category": OpportunityCategory.AVOIDABLE_COMPUTATION.value,
                "weight": 0.25,
                "description": "Loop-invariant calculations, un-cached strlen() in conditions, heavy math calls.",
            },
            {
                "category": OpportunityCategory.UNNECESSARY_ALLOCATIONS.value,
                "weight": 0.20,
                "description": "Repeated dynamic heap allocations (malloc/calloc) inside loops and heap churn.",
            },
            {
                "category": OpportunityCategory.REDUNDANT_OPERATIONS.value,
                "weight": 0.15,
                "description": "Dead stores, duplicate variable assignments, redundant identity arithmetic.",
            },
            {
                "category": OpportunityCategory.INEFFICIENT_IO_MEMORY.value,
                "weight": 0.10,
                "description": "Unbuffered single-char I/O in loops, quadratic string concatenation (strcat).",
            },
        ],
    })


@app.route("/api/security/risk", methods=["POST", "GET"])
def get_security_risk():
    """
    Computes normalized Security Risk Score (%) from supported findings and exposure factors.
    Returns INCOMPLETE_ASSESSMENT when source is empty or brief.
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    code = data.get("code", "")
    filename = data.get("filename", "main.c")
    findings = data.get("findings")

    from compiler.security_risk import SecurityRiskScorer

    if findings is None or (isinstance(findings, list) and len(findings) == 0 and len(code.strip()) >= 15):
        # Run security reporter if findings not pre-provided or if empty list sent on non-empty code
        from compiler.security_reporter import SecurityReporter
        sec_rep = SecurityReporter().analyze_source(code, filename)
        findings = sec_rep.findings

    scorer = SecurityRiskScorer()
    report = scorer.assess(findings=findings, source_code=code, filename=filename)
    return jsonify(report.to_dict())


@app.route("/api/security/risk/delta", methods=["POST"])
def get_security_risk_delta():
    """
    Recalculates Security Risk Score across proposed or approved fixes,
    preserving before-and-after results and risk delta.
    """
    data = request.get_json(silent=True) or {}
    before_code = data.get("before_code", "")
    after_code = data.get("after_code", "")
    filename = data.get("filename", "main.c")

    from compiler.security_reporter import SecurityReporter
    from compiler.security_risk import SecurityRiskScorer

    sec_reporter = SecurityReporter()
    before_findings = data.get("before_findings")
    if before_findings is None or (isinstance(before_findings, list) and len(before_findings) == 0 and len(before_code.strip()) >= 15):
        before_findings = sec_reporter.analyze_source(before_code, filename).findings

    after_findings = data.get("after_findings")
    if after_findings is None or (isinstance(after_findings, list) and len(after_findings) == 0 and len(after_code.strip()) >= 15):
        after_findings = sec_reporter.analyze_source(after_code, filename).findings

    scorer = SecurityRiskScorer()
    delta_rep = scorer.assess_delta(
        before_findings=before_findings,
        after_findings=after_findings,
        before_code=before_code,
        after_code=after_code,
        filename=filename,
    )
    return jsonify(delta_rep.to_dict())


@app.route("/api/security/risk/config", methods=["GET"])
def get_security_risk_config():
    """Returns documented formula weights, factor scales, and epistemological disclaimer."""
    from compiler.security_risk import SECURITY_RISK_DISCLAIMER, SecurityRiskScorer

    return jsonify({
        "disclaimer": SECURITY_RISK_DISCLAIMER,
        "severity_weights": SecurityRiskScorer.SEVERITY_WEIGHTS,
        "formula": {
            "description": "Contribution(f) = BaseWeight(Severity) * Exploitability * Exposure * Confidence",
            "saturation_function": "Risk = 100 * (1 - exp(-TotalRawPoints / 40.0))",
            "scale_constant": 40.0,
        },
        "factors": [
            {
                "name": "exploitability",
                "range": [0.4, 1.0],
                "description": "Direct memory execution/control (1.0), pointer corruption (0.85), arithmetic wrap (0.75), dangerous API (0.60), disclosure (0.55).",
            },
            {
                "name": "exposure",
                "range": [0.5, 1.0],
                "description": "External untrusted I/O input boundary (1.0), main entry path (0.85), internal static scope (0.65).",
            },
            {
                "name": "confidence",
                "range": [0.5, 1.0],
                "description": "Confirmed deterministic rule (1.0), heuristic analysis (0.70), speculation (0.50).",
            },
        ],
    })


@app.route("/api/green/config", methods=["GET"])
def get_green_config():
    """
    Returns documented Green Metrics Score formula, baseline targets,
    measurement methodology, assumptions, and epistemological limitations.
    """
    from compiler.green_engine import (
        GREEN_METRICS_DISCLAIMER,
        GreenBaseline,
        GreenScoreConfig,
        MeasurementType,
    )

    baseline = GreenBaseline()
    config = GreenScoreConfig()

    return jsonify({
        "disclaimer": GREEN_METRICS_DISCLAIMER,
        "scoring_weights": config.to_dict(),
        "baseline": baseline.to_dict(),
        "measurement_types": [m.value for m in MeasurementType],
        "methodology": {
            "directly_measured": [
                "Total elapsed wall-clock latency (ms) and per-stage timings via perf_counter",
                "Process Peak Resident Set Size (RSS memory in MB) via OS process inspection",
                "Host process CPU utilization percentage (%) via psutil",
                "GPU VRAM peak allocated memory (MB) via PyTorch/CUDA runtime when present",
                "Model calls, retry counts, prompt/completion token quantities",
            ],
            "statistically_estimated": [
                "Energy consumption in Joules (J) and Watt-hours (Wh) via hardware linear TDP power model",
                "CO2-equivalent emissions (g and kg) via regional grid carbon intensity (475 g CO2/kWh)",
                "Energy and latency amortized per successfully validated repair",
            ],
            "linear_power_model": "P_total = P_idle + (TDP_cpu - P_idle)*(cpu%/100) + 3W*(RAM_GB) + P_gpu*(gpu%/100)",
            "hardware_assumptions": {
                "system_idle_w": 15.0,
                "cpu_tdp_w": 45.0,
                "gpu_tdp_w": 35.0,
                "grid_carbon_intensity_g_kwh": 475.0,
            },
            "safety_integrity_policy": (
                "Validation rigor, compiler checks, regression testing, and security analysis "
                "are NEVER bypassed, truncated, or weakened to artificially inflate the Green Metrics Score."
            ),
        },
    })


@app.route("/api/green/measure", methods=["POST", "GET"])
def measure_green():
    """
    Evaluates Green Metrics and Score for given execution metrics or ad-hoc run.
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    from compiler.green_engine import LocalGreenMetricsEngine, ModelResourceMetrics

    engine = LocalGreenMetricsEngine()
    total_ms = float(data.get("total_runtime_ms", 120.0))
    stage_ms = data.get("phase_ms", {"syntax": 40.0, "semantic": 50.0, "security": 30.0})
    m_data = data.get("model_metrics", {})
    model_metrics = ModelResourceMetrics(
        model_calls=int(m_data.get("model_calls", data.get("ai_fixes", 0))),
        model_name=m_data.get("model_name"),
        retries_count=int(m_data.get("retries_count", data.get("retries_count", 0))),
        prompt_tokens=int(m_data.get("prompt_tokens", 0)),
        completion_tokens=int(m_data.get("completion_tokens", 0)),
        total_tokens=int(m_data.get("total_tokens", 0)),
    )
    validated_repairs = int(data.get("validated_repairs_count", 1))
    repair_success = bool(data.get("repair_success", True))
    stages_passed = int(data.get("validation_stages_passed", 4))
    rule_fixes = int(data.get("rule_fixes_count", data.get("rule_fixes", 0)))
    ai_fixes = int(data.get("ai_fixes_count", data.get("ai_fixes", 0)))

    report = engine.build_report(
        total_runtime_ms=total_ms,
        stage_ms=stage_ms,
        model_metrics=model_metrics,
        validated_repairs_count=validated_repairs,
        repair_success=repair_success,
        validation_stages_passed=stages_passed,
        rule_fixes_count=rule_fixes,
        ai_fixes_count=ai_fixes,
    )
    return jsonify(report.to_dict())


@app.route("/api/green/history", methods=["GET"])
def get_green_history():
    """
    Returns recent historical green metrics audit records.
    """
    limit = int(request.args.get("limit", 30))
    from compiler.green_logger import GreenLogger
    logger = GreenLogger()
    records = logger.get_recent(limit=limit)
    return jsonify({"count": len(records), "records": records})


@app.route("/api/benchmark/status", methods=["GET"])
def get_benchmark_status():
    """
    Returns latest benchmark evaluation report or UNBENCHMARKED status.
    Ensures zero fabricated scores; status is unbenchmarked until actual run.
    """
    from compiler.benchmark_engine import ModelEvaluationEngine
    engine = ModelEvaluationEngine()
    return jsonify(engine.get_status())


@app.route("/api/benchmark/dataset", methods=["GET"])
def get_benchmark_dataset():
    """
    Returns the fixed, labelled benchmark dataset metadata, categories, and cases.
    """
    from compiler.benchmark_engine import BENCHMARK_DATASET, BenchmarkCategory, BENCHMARK_DEFINITIONS, BENCHMARK_DISCLAIMER
    return jsonify({
        "size": len(BENCHMARK_DATASET),
        "categories": [c.value for c in BenchmarkCategory],
        "cases": [c.to_dict() for c in BENCHMARK_DATASET],
        "definitions": BENCHMARK_DEFINITIONS,
        "disclaimer": BENCHMARK_DISCLAIMER,
    })


@app.route("/api/benchmark/definitions", methods=["GET"])
def get_benchmark_definitions():
    """
    Returns documented metric definitions, formulas, denominators, exclusions, and disclaimers.
    """
    from compiler.benchmark_engine import BENCHMARK_DEFINITIONS, BENCHMARK_DISCLAIMER
    return jsonify({
        "definitions": BENCHMARK_DEFINITIONS,
        "disclaimer": BENCHMARK_DISCLAIMER,
    })


@app.route("/api/benchmark/run", methods=["POST"])
def run_benchmark():
    """
    Executes actual empirical benchmark evaluation across all 5 configurations
    against the fixed labelled benchmark dataset.
    """
    data = request.get_json(silent=True) or {}
    configs_req = data.get("configurations")
    cases_req = data.get("cases_subset")

    from compiler.benchmark_engine import ModelEvaluationEngine, ConfigurationType

    engine = ModelEvaluationEngine()
    configs = None
    if configs_req and isinstance(configs_req, list):
        configs = []
        for c in configs_req:
            try:
                configs.append(ConfigurationType(c))
            except Exception:
                pass

    report = engine.run_benchmark(configurations=configs, cases_subset=cases_req)
    return jsonify(report.to_dict())


@app.route("/api/dashboard/before_after", methods=["POST"])
def get_dashboard_before_after():
    """
    Computes before-and-after comparisons across live session metrics for approved fixes:
    - Code Quality Score (%) & Delta
    - Security Risk Score (%) & Delta
    - Optimization Potential (%) & Delta
    - Resolved vs Remaining Compiler and Security Issues
    - Resource Overhead Expended (Time, Energy Joules, Carbon, Peak Memory, Model Tokens)
    """
    data = request.get_json(silent=True) or {}
    before_code = data.get("before_code", "")
    after_code = data.get("after_code", "")
    filename = data.get("filename", "main.c")
    green_report = data.get("green_report") or {}
    applied_steps = data.get("applied_steps") or []

    from compiler.code_quality import CodeQualityScorer
    from compiler.optimization_potential import OptimizationPotentialAnalyzer
    from compiler.security_reporter import SecurityReporter
    from compiler.security_risk import SecurityRiskScorer

    # 1. Quality Scores
    quality_scorer = CodeQualityScorer()
    q_before = quality_scorer.analyze_source(source_code=before_code, filename=filename)
    q_after = quality_scorer.analyze_source(source_code=after_code, filename=filename)

    # 2. Optimization Potential
    opt_analyzer = OptimizationPotentialAnalyzer()
    opt_before = opt_analyzer.analyze(source_code=before_code, filename=filename)
    opt_after = opt_analyzer.analyze(source_code=after_code, filename=filename)

    # 3. Security Risk & Delta
    sec_reporter = SecurityReporter()
    sec_before = sec_reporter.analyze_source(before_code, filename)
    sec_after = sec_reporter.analyze_source(after_code, filename)
    sec_delta = sec_reporter.compare_patches(
        original_source=before_code,
        patched_source=after_code,
        filename=filename,
    )

    sec_scorer = SecurityRiskScorer()
    risk_before = sec_scorer.assess(findings=sec_before.findings, source_code=before_code, filename=filename)
    risk_after = sec_scorer.assess(findings=sec_after.findings, source_code=after_code, filename=filename)

    # Calculate Deltas and 4 Code Quality Metrics
    from compiler.code_quality import calculate_code_quality_metrics
    cq_before = calculate_code_quality_metrics(
        q=q_before.overall_score if q_before.can_score else None,
        o=opt_before.optimization_potential if opt_before.can_score else None,
        v=risk_before.risk_score if risk_before.can_score else None,
    )
    cq_after = calculate_code_quality_metrics(
        q=q_after.overall_score if q_after.can_score else None,
        o=opt_after.optimization_potential if opt_after.can_score else None,
        v=risk_after.risk_score if risk_after.can_score else None,
    )

    q_before_val = q_before.overall_score if q_before.can_score else None
    q_after_val = q_after.overall_score if q_after.can_score else None
    q_delta = round(q_after_val - q_before_val, 1) if (q_before_val is not None and q_after_val is not None) else None

    opt_before_val = opt_before.optimization_potential if opt_before.can_score else None
    opt_after_val = opt_after.optimization_potential if opt_after.can_score else None
    opt_delta = round(opt_after_val - opt_before_val, 1) if (opt_before_val is not None and opt_after_val is not None) else None

    risk_before_val = risk_before.risk_score if risk_before.can_score else None
    risk_after_val = risk_after.risk_score if risk_after.can_score else None
    risk_delta_val = round(risk_after_val - risk_before_val, 1) if (risk_before_val is not None and risk_after_val is not None) else None

    ov_before = cq_before["overall_code_quality"]
    ov_after = cq_after["overall_code_quality"]
    ov_delta = round(ov_after - ov_before, 1) if (ov_before is not None and ov_after is not None) else None

    opt_code_before = cq_before["optimal_code"]
    opt_code_after = cq_after["optimal_code"]
    opt_code_delta = round(opt_code_after - opt_code_before, 1) if (opt_code_before is not None and opt_code_after is not None) else None

    poor_before = cq_before["poor_code"]
    poor_after = cq_after["poor_code"]
    poor_delta = round(poor_after - poor_before, 1) if (poor_before is not None and poor_after is not None) else None

    vuln_before = cq_before["vulnerability_risk"]
    vuln_after = cq_after["vulnerability_risk"]
    vuln_delta = round(vuln_after - vuln_before, 1) if (vuln_before is not None and vuln_after is not None) else None

    # Error Counts from analysis
    before_errors = (len(q_before.diagnostics.get("syntax", [])) if hasattr(q_before, "diagnostics") and isinstance(q_before.diagnostics, dict) else 0)
    after_errors = (len(q_after.diagnostics.get("syntax", [])) if hasattr(q_after, "diagnostics") and isinstance(q_after.diagnostics, dict) else 0)

    from compiler.repair_planner import calculate_six_metrics, build_six_metrics_comparison
    before_six_metrics = calculate_six_metrics(source_code=before_code, filename=filename, findings=sec_before.findings)
    after_six_metrics = calculate_six_metrics(source_code=after_code, filename=filename, findings=sec_after.findings)
    metrics_comparison = build_six_metrics_comparison(before_six_metrics, after_six_metrics)

    return jsonify({
        "success": True,
        "before_six_metrics": before_six_metrics,
        "after_six_metrics": after_six_metrics,
        "metrics_comparison": metrics_comparison,
        "before": {
            "overall_code_quality": ov_before,
            "optimal_code": opt_code_before,
            "poor_code": poor_before,
            "vulnerability_risk": vuln_before,
            "quality_score": q_before_val,
            "quality_status": q_before.status.value,
            "optimization_potential": opt_before_val,
            "optimization_status": opt_before.status.value,
            "security_risk_score": risk_before_val,
            "security_status": risk_before.status.value,
            "security_finding_counts": {
                "critical": risk_before.critical_count,
                "high": risk_before.high_count,
                "medium": risk_before.medium_count,
                "low": risk_before.low_count,
            },
            "syntax_errors_count": before_errors,
        },
        "after": {
            "overall_code_quality": ov_after,
            "optimal_code": opt_code_after,
            "poor_code": poor_after,
            "vulnerability_risk": vuln_after,
            "quality_score": q_after_val,
            "quality_status": q_after.status.value,
            "optimization_potential": opt_after_val,
            "optimization_status": opt_after.status.value,
            "security_risk_score": risk_after_val,
            "security_status": risk_after.status.value,
            "security_finding_counts": {
                "critical": risk_after.critical_count,
                "high": risk_after.high_count,
                "medium": risk_after.medium_count,
                "low": risk_after.low_count,
            },
            "syntax_errors_count": after_errors,
        },
        "delta": {
            "overall_code_quality_delta": ov_delta,
            "optimal_code_delta": opt_code_delta,
            "poor_code_delta": poor_delta,
            "vulnerability_risk_delta": vuln_delta,
            "quality_score_delta": q_delta,
            "optimization_potential_delta": opt_delta,
            "security_risk_delta": risk_delta_val,
            "resolved_vulnerabilities_count": len(sec_delta.resolved_vulnerabilities),
            "remaining_vulnerabilities_count": len(sec_delta.remaining_vulnerabilities),
            "introduced_vulnerabilities_count": len(sec_delta.introduced_vulnerabilities),
            "resolved_errors_count": max(0, before_errors - after_errors),
            "applied_steps": applied_steps,
        },
        "resource_overhead": {
            "runtime_ms": green_report.get("total_runtime_ms", 0),
            "estimated_joules": green_report.get("energy_metrics", {}).get("estimated_joules", 0.0),
            "estimated_carbon_mg": green_report.get("energy_metrics", {}).get("estimated_co2_mg", 0.0),
            "peak_memory_mb": green_report.get("system_metrics", {}).get("peak_memory_mb", 0.0),
            "model_tokens": green_report.get("model_metrics", {}).get("total_tokens", 0),
            "measurement_mode": green_report.get("energy_metrics", {}).get("measurement_mode", "HARDWARE_TDP_LINEAR_POWER_MODEL"),
        },
        "epistemic_badges": {
            "quality": "LIVE SESSION: MEASURED",
            "optimization": "STATIC HEURISTIC ESTIMATE",
            "security_risk": "LIVE SESSION: RISK INDEX",
            "green_metrics": "HARDWARE POWER MODEL: ESTIMATED",
            "benchmark": "FIXED BENCHMARK DATASET",
        }
    })


# -------------------------------------------------------------
# COORDINATED REPAIR PLANNER ENDPOINT (QWEN2.5-CODER AGENT)
# -------------------------------------------------------------
from compiler.pipeline_logger import get_pipeline_run, StageStatus, _PIPELINE_RUNS_CACHE

_ACTIVE_REPAIR_EVENTS = {}



@app.route("/api/coordinator/cancel", methods=["POST"])
def coordinator_cancel():
    data = request.get_json(silent=True) or {}
    run_id = data.get("run_id") or data.get("request_id")
    cancelled = False
    if run_id and run_id in _ACTIVE_REPAIR_EVENTS:
        _ACTIVE_REPAIR_EVENTS[run_id].set()
        cancelled = True
    elif _ACTIVE_REPAIR_EVENTS:
        for evt in _ACTIVE_REPAIR_EVENTS.values():
            evt.set()
        cancelled = True

    if run_id:
        try:
            from compiler.repair_job_manager import get_repair_job_manager
            if get_repair_job_manager().cancel_job(run_id):
                cancelled = True
        except Exception:
            pass

    try:
        from compiler.local_models import OllamaClient
        OllamaClient().unload_model()
    except Exception:
        pass

    if cancelled:
        return jsonify({"status": "CANCELLED", "run_id": run_id, "message": "Repair run cancelled successfully."})
    return jsonify({"status": "NOT_FOUND", "message": f"Run ID '{run_id}' not found or already completed."}), 404


@app.route("/api/coordinator/analyze_and_plan", methods=["POST"])
def coordinator_analyze_and_plan():
    """
    Coordinates specialized analyzers, executes Qwen2.5-Coder reasoning agent,
    runs whole-program validation, and computes before-and-after score deltas.
    """
    data = request.get_json(silent=True) or {}
    code = data.get("code") if data.get("code") is not None else data.get("source_code", "")
    filename = data.get("filename")
    req_lang = data.get("language")
    run_id = data.get("run_id")

    lang_id, resolved_filename, _ = _resolve_lang_and_filename(data)
    if not lang_id:
        lang_id = detect_language(filename=filename, requested=req_lang)
    if not resolved_filename:
        resolved_filename = "main.py" if lang_id == "python" else (filename or "main.c")

    continuation_id = data.get("continuation_id")
    approval_token = data.get("approval_token")

    if continuation_id:
        from compiler.continuation_manager import ContinuationManager
        session = ContinuationManager.get_session(continuation_id)
        if session and session.token_rebind_error and not approval_token:
            return jsonify({
                "status": "SECURITY_WARNING",
                "http_status": 409,
                "message": session.token_rebind_error,
                "error": session.token_rebind_error,
                "policy_reason": session.token_rebind_error,
                "reapproval_required": True,
            }), 409

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=code,
        filename=resolved_filename,
        language=lang_id,
        operation=data.get("operation") or "repair",
        approval_token=approval_token,
    )
    if not permitted:
        return jsonify(warning_payload), gate_status

    request_id = run_id or f"req_{uuid.uuid4().hex[:12]}"
    cancel_event = threading.Event()
    _ACTIVE_REPAIR_EVENTS[request_id] = cancel_event
    lines_count = len(code.splitlines())
    calc_budget = min(900.0, 300.0 + 0.5 * lines_count)
    env_budget = os.environ.get("SERVER_TIME_BUDGET_SECONDS")
    if env_budget:
        try:
            time_budget_s = float(env_budget)
        except Exception:
            time_budget_s = calc_budget
    else:
        time_budget_s = calc_budget

    import logging
    coord_logger = logging.getLogger("Coordinator")
    coord_logger.info(f"[{request_id}] ROUTING DECISION: filename='{resolved_filename}', detected_lang='{lang_id}', requested_lang='{req_lang}', time_budget_s={time_budget_s}")
    try:
        from compiler.repair_planner import RepairPlanner
        planner = RepairPlanner()
        op_name = data.get("operation") or "repair"
        # Round system deactivated: repairs complete in one pass.
        # Ignore round and continuation_id from client; keep underlying logic intact.
        result = planner.plan_and_repair(
            code,
            filename=resolved_filename,
            language=lang_id,
            run_id=request_id,
            time_budget_s=time_budget_s,
            approval_token=approval_token,
            operation=op_name,
            continuation_id=None,
            round=1,
            cancel_event=cancel_event,
        )
        result["can_continue_repair"] = False
        result["round"] = 1
        if "candidate" in result and isinstance(result["candidate"], dict):
            result["candidate"]["can_continue_repair"] = False
            result["candidate"]["round"] = 1
        for evt in result.get("pipeline_events", []):
            coord_logger.info(
                f"[{request_id}] STAGE TIMING: stage='{evt.get('stage_id')}' status='{evt.get('status')}' duration_ms={evt.get('duration_ms')}"
            )
        from compiler.call_extractor import get_extraction_mode
        if "analysis_mode" not in result:
            result["analysis_mode"] = get_extraction_mode(code) if lang_id == "c" else "AST"
        return jsonify(result)
    except Exception as e:
        import traceback
        import time
        tb_str = traceback.format_exc()
        os.makedirs("logs", exist_ok=True)
        with open("logs/server_errors.log", "a", encoding="utf-8") as err_log:
            err_log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] REQUEST_ID: {request_id} FILENAME: {resolved_filename} LANG: {lang_id}\n{tb_str}\n")

        failing_stage = "repair_planner"
        if "extract_call_sites" in str(e):
            failing_stage = "candidate_assessment"
        elif "compile" in str(e).lower() or "gcc" in str(e).lower():
            failing_stage = "validation_compilation"
        elif "ollama" in str(e).lower() or "generate" in str(e).lower():
            failing_stage = "qwen_ollama"
        elif "syntax" in str(e).lower() or "parse" in str(e).lower():
            failing_stage = "syntax_analysis"

        clean_msg = str(e).replace(os.path.abspath("."), "<WORKSPACE_ROOT>")
        return jsonify({
            "request_id": request_id,
            "status": "ERROR",
            "failing_stage": failing_stage,
            "exception_type": type(e).__name__,
            "error_message": clean_msg,
            "message": clean_msg,
            "filename": resolved_filename,
            "language": lang_id
        }), 500
    finally:
        _ACTIVE_REPAIR_EVENTS.pop(request_id, None)


@app.route("/api/repair/post_apply", methods=["POST"])
def repair_post_apply():
    """
    User applied a proposal: runs fresh re-analysis on editor source without restarting CodeT5.
    If issues remain, escalates conditionally to Qwen.
    """
    try:
        data = request.get_json(silent=True) or {}
        editor_source = data.get("source_code") or data.get("code") or ""
        filename = data.get("filename") or "main.c"
        req_lang = data.get("language")
        applied_from_state = data.get("applied_from_state", "QWEN_PROPOSAL_READY")
        original_source_hash = data.get("original_source_hash")
        applied_source_hash = data.get("applied_source_hash")
        initial_findings = data.get("initial_findings", [])
        retry_count = int(data.get("retry_count", 0))
        history_hashes = data.get("history_hashes", [])
        run_id = data.get("run_id")
        escalate_to_qwen = bool(data.get("escalate_to_qwen", False))

        lang_id, resolved_filename, _ = _resolve_lang_and_filename(data)
        if not lang_id:
            lang_id = detect_language(filename=filename, requested=req_lang)
        if not resolved_filename:
            resolved_filename = "main.py" if lang_id == "python" else (filename or "main.c")

        from compiler.repair_planner import RepairPlanner
        planner = RepairPlanner()
        result = planner.post_apply_reanalyze_and_escalate(
            editor_source=editor_source,
            filename=resolved_filename,
            language=lang_id,
            applied_from_state=applied_from_state,
            original_source_hash=original_source_hash,
            applied_source_hash=applied_source_hash,
            initial_findings=initial_findings,
            retry_count=retry_count,
            history_hashes=history_hashes,
            run_id=run_id,
            escalate_to_qwen=escalate_to_qwen,
        )
        return jsonify(result)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "ERROR",
            "workflow_state": "VALIDATION_INCOMPLETE",
            "message": f"Post-apply re-analysis failed: {str(exc)}",
            "error": str(exc),
        }), 500


@app.route("/api/pipeline/latest", methods=["GET"])
def get_latest_pipeline_run():
    """Returns the most recent pipeline execution run events."""
    if not _PIPELINE_RUNS_CACHE:
        return jsonify({"run_id": None, "events": []})
    latest_run_id = next(reversed(_PIPELINE_RUNS_CACHE))
    logger = _PIPELINE_RUNS_CACHE[latest_run_id]
    return jsonify(logger.to_dict())


@app.route("/api/pipeline/run/<run_id>", methods=["GET"])
def get_pipeline_run_by_id(run_id):
    """Returns pipeline execution events for a specific run ID."""
    logger = get_pipeline_run(run_id)
    if not logger:
        return jsonify({"error": f"Pipeline run '{run_id}' not found", "events": []}), 404
    return jsonify(logger.to_dict())


# -------------------------------------------------------------
# POST-REPAIR IMPROVEMENT ADVISOR ENDPOINTS
# -------------------------------------------------------------
from compiler.improvement_advisor import ImprovementAdvisor, candidate_registry


@app.route("/api/improvement/advise", methods=["POST"])
def get_improvement_advisories():
    """
    Analyzes clean or repaired program source and produces actionable,
    evidence-backed improvement candidates with reviewable diffs.
    """
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    filename = data.get("filename", "main.c")
    green_report = data.get("green_report")

    from compiler.security_approval_gate import enforce_security_gate_for_request
    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
        source_code=code,
        filename=filename,
        language=detect_language(filename),
        operation="improvement_advise",
        approval_token=data.get("approval_token"),
    )
    if not permitted:
        return jsonify(warning_payload), gate_status

    advisor = ImprovementAdvisor()
    report = advisor.analyze_and_advise(code, filename=filename, green_report=green_report)

    return jsonify(report.to_dict())


@app.route("/api/improvement/candidate/<candidate_id>/apply", methods=["POST"])
def apply_improvement_candidate(candidate_id):
    """
    Explicit user approval and application gate for an improvement candidate.
    Enforces validation eligibility, baseline freshness, and target file consistency before applying.
    """
    data = request.get_json(silent=True) or {}
    current_code = data.get("current_code")
    if current_code is None:
        current_code = data.get("current_source_code")
    req_filename = data.get("filename")

    cand = candidate_registry.get(candidate_id)
    if not cand:
        return jsonify({"error": f"Candidate '{candidate_id}' not found", "success": False}), 404

    # Enforce current source presence for baseline freshness verification
    if current_code is None:
        return jsonify({
            "error": "Current editor source code is required to verify freshness before applying patch.",
            "success": False,
            "candidate_id": candidate_id,
        }), 400

    # Enforce target file/tab match
    if req_filename and cand.filename and req_filename != cand.filename:
        def _clean_fname(fn):
            return (fn or "").replace("\\", "/").strip().lstrip("/").replace("examples/", "")
        c_req = _clean_fname(req_filename)
        c_cand = _clean_fname(cand.filename)
        base_match = os.path.basename(c_req) == os.path.basename(c_cand)
        path_match = (c_req == c_cand) or c_req.endswith(c_cand) or c_cand.endswith(c_req)
        if not (base_match or path_match):
            return jsonify({
                "error": f"Target file mismatch: candidate is for '{cand.filename}', but request targeted '{req_filename}'.",
                "success": False,
                "candidate_id": candidate_id,
                "expected_filename": cand.filename,
                "actual_filename": req_filename,
            }), 400

    success, msg, cand = candidate_registry.verify_and_apply(candidate_id, current_source=current_code)
    if not cand:
        return jsonify({"error": msg, "success": False}), 404

    if not success:
        status_code = 409 if ("Stale" in msg or "already" in msg) else 422
        return jsonify({
            "error": msg,
            "success": False,
            "candidate_id": candidate_id,
            "validation_state": cand.validation_state,
            "is_eligible": cand.is_eligible_for_application,
            "user_decision": cand.user_decision_state,
        }), status_code

    # Register with patch_history so revert endpoint (/api/patch/revert) works smoothly
    try:
        p_item = patch_history.register_candidate_patch(
            patch_id=f"IMP-{cand.id}",
            file_path=cand.filename,
            original_code=cand.original_code,
            patched_code=cand.proposed_code,
            explanation=cand.explanation,
        )
        patch_history.approve_and_apply(p_item.patch_id, current_source=current_code)
    except Exception:
        pass

    # Log user approval and patch application in the genuine pipeline run
    pipeline_events = []
    run_id = cand.run_id or (next(reversed(_PIPELINE_RUNS_CACHE)) if _PIPELINE_RUNS_CACHE else None)
    if run_id:
        p_logger = get_pipeline_run(run_id)
        if p_logger:
            p_logger.record_stage(
                stage_id="user_approval_apply",
                stage_name="12. User Approval & Patch Application",
                status=StageStatus.PASSED,
                description=f"User explicitly approved candidate '{cand.id}' and applied patch to editor.",
                duration_ms=0.1,
                diagnostics={"candidate_id": cand.id, "applied_at": cand.applied_at},
            )
            pipeline_events = [e.to_dict() for e in p_logger.ordered_events]

    return jsonify({
        "success": True,
        "candidate_id": candidate_id,
        "run_id": run_id,
        "applied_code": cand.proposed_code,
        "filename": cand.filename,
        "original_source_hash": cand.original_source_hash,
        "proposed_source_hash": cand.proposed_source_hash,
        "strategy": cand.strategy.value,
        "title": cand.title,
        "user_decision": "APPLIED",
        "target": "editor",
        "message": msg,
        "pipeline_events": pipeline_events,
    })


@app.route("/api/improvement/candidate/<candidate_id>/rollback", methods=["POST"])
@app.route("/api/improvement/candidate/<candidate_id>/apply_failed", methods=["POST"])
def rollback_improvement_candidate(candidate_id):
    """
    Rolls back an applied candidate to AWAITING_USER_DECISION if the frontend
    editor application encountered an error or failed to complete.
    """
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "Editor update failed")
    success, msg, cand = candidate_registry.rollback_apply(candidate_id, reason=reason)
    if not cand:
        return jsonify({"error": msg, "success": False}), 404
    if not success:
        return jsonify({"error": msg, "success": False}), 400

    return jsonify({
        "success": True,
        "candidate_id": candidate_id,
        "user_decision": cand.user_decision_state,
        "message": msg,
    })


@app.route("/api/improvement/candidate/<candidate_id>/reject", methods=["POST"])
def reject_improvement_candidate(candidate_id):
    """Explicit user rejection of an improvement candidate."""
    success, msg, cand = candidate_registry.reject(candidate_id)
    if not cand:
        return jsonify({"error": msg, "success": False}), 404

    return jsonify({
        "success": True,
        "candidate_id": candidate_id,
        "user_decision": "USER_REJECTED",
        "message": msg,
    })


def open_browser():

    webbrowser.open_new("http://127.0.0.1:5000")




if __name__ == "__main__":
    import logging
    logger = logging.getLogger(__name__)
    print("Initializing server startup...", flush=True)
    # Requirement 3: Move resume_unfinished_jobs() to application startup only (not on import, not in test mode); log errors instead of pass
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