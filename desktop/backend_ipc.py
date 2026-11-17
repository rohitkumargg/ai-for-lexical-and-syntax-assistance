"""
Electron IPC Bridge for SimpleC Desktop Application.
Communicates via stdin/stdout newline-delimited JSON.
NO TCP or network socket is bound or listened on.
"""

import sys
import os
import json
import traceback
import re

# Ensure workspace root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import backend_logic

# Map route names to handler functions
ROUTE_HANDLERS = {
    # Group 1: System & Files
    "languages": lambda args: backend_logic.handle_languages(),
    "examples": lambda args: backend_logic.handle_examples(args.get("language", "c")),
    "load_example": lambda args: backend_logic.handle_load_example(args.get("name"), args.get("language")),
    "create_file": lambda args: backend_logic.handle_create_file(args),
    "save_file": lambda args: backend_logic.handle_save_file(args),
    "models_status": lambda args: backend_logic.handle_models_status(),
    "models_unload": lambda args: backend_logic.handle_models_unload(),

    # Group 2: Security & Analysis
    "quality_score": lambda args: backend_logic.handle_quality_score(args),
    "quality_config": lambda args: backend_logic.handle_quality_config(),
    "optimization_potential": lambda args: backend_logic.handle_optimization_potential(args),
    "optimization_config": lambda args: backend_logic.handle_optimization_config(),
    "security_risk": lambda args: backend_logic.handle_security_risk(args),
    "security_risk_delta": lambda args: backend_logic.handle_security_risk_delta(args),
    "security_risk_config": lambda args: backend_logic.handle_security_risk_config(),
    "security_report": lambda args: backend_logic.handle_security_report(args),
    "security_compare": lambda args: backend_logic.handle_security_compare(args),
    "security_benchmark": lambda args: backend_logic.handle_security_benchmark(args.get("dir")),
    "security_remediation": lambda args: backend_logic.handle_security_remediation(args),
    "security_apply": lambda args: backend_logic.handle_security_apply(args),
    "security_prescan": lambda args: backend_logic.handle_security_prescan(args),
    "security_approval_check": lambda args: backend_logic.handle_security_approval_check(args),
    "security_approval_approve": lambda args: backend_logic.handle_security_approval_approve(args),
    "security_approval_cancel": lambda args: backend_logic.handle_security_approval_cancel(args),

    # Group 3: Execution, Repair & Jobs
    "run_program": lambda args: backend_logic.handle_run_program(args),
    "testcase": lambda args: backend_logic.handle_testcase(args),
    "repair": lambda args: backend_logic.handle_repair(args),
    "repair_job_start": lambda args: backend_logic.handle_repair_job_start(args),
    "repair_job_status": lambda args: backend_logic.handle_repair_job_status(args.get("job_id")),
    "repair_job_cancel": lambda args: backend_logic.handle_repair_job_cancel(args.get("job_id")),
    "repair_job_delete": lambda args: backend_logic.handle_repair_job_delete(args.get("job_id")),
    "coordinator_cancel": lambda args: backend_logic.handle_coordinator_cancel(args),
    "coordinator_analyze_and_plan": lambda args: backend_logic.handle_coordinator_analyze_and_plan(args),
    "repair_post_apply": lambda args: backend_logic.handle_repair_post_apply(args),
    "pipeline_latest": lambda args: backend_logic.handle_latest_pipeline_run(),
    "pipeline_run": lambda args: backend_logic.handle_pipeline_run_by_id(args.get("run_id")),

    # Group 4: Patch & Diff
    "validate_patch": lambda args: backend_logic.handle_validate_patch(args),
    "apply_patch": lambda args: backend_logic.handle_apply_patch(args),
    "reject_patch": lambda args: backend_logic.handle_reject_patch(args),
    "revert_patch": lambda args: backend_logic.handle_revert_patch(),
    "dashboard_before_after": lambda args: backend_logic.handle_dashboard_before_after(args),

    # Group 5: Improvement & Rules
    "improvement_advise": lambda args: backend_logic.handle_improvement_advisories(args),
    "improvement_candidate_apply": lambda args: backend_logic.handle_apply_improvement_candidate(args.get("candidate_id"), args),
    "improvement_candidate_rollback": lambda args: backend_logic.handle_rollback_improvement_candidate(args.get("candidate_id"), args),
    "improvement_candidate_reject": lambda args: backend_logic.handle_reject_improvement_candidate(args.get("candidate_id")),
    "rules_candidates": lambda args: backend_logic.handle_candidate_rules(),
    "rules_propose": lambda args: backend_logic.handle_propose_rule(args),
    "rules_candidate_validate": lambda args: backend_logic.handle_validate_rule(args.get("rule_id")),
    "rules_candidate_approve": lambda args: backend_logic.handle_approve_rule(args.get("rule_id"), args),
    "rules_candidate_reject": lambda args: backend_logic.handle_reject_rule(args.get("rule_id"), args),
    "rules_active": lambda args: backend_logic.handle_active_rules(),
    "rules_active_disable": lambda args: backend_logic.handle_disable_active_rule(args.get("rule_id"), args),
    "rules_active_enable": lambda args: backend_logic.handle_enable_active_rule(args.get("rule_id"), args),
    "rules_active_rollback": lambda args: backend_logic.handle_rollback_active_rule(args.get("rule_id"), args),
    "rules_history": lambda args: backend_logic.handle_rule_history(),

    # Group 6: Benchmark & Green
    "green_config": lambda args: backend_logic.handle_green_config(),
    "green_measure": lambda args: backend_logic.handle_measure_green(args),
    "green_history": lambda args: backend_logic.handle_green_history(args.get("limit", 30)),
    "benchmark_status": lambda args: backend_logic.handle_benchmark_status(),
    "benchmark_dataset": lambda args: backend_logic.handle_benchmark_dataset(),
    "benchmark_definitions": lambda args: backend_logic.handle_benchmark_definitions(),
    "benchmark_run": lambda args: backend_logic.handle_run_benchmark(args),
}


def dispatch_by_url(url, args=None):
    """
    Optional URL resolver allowing direct resolution of HTTP paths like
    /api/languages or /api/repair/job/<job_id>
    """
    args = args or {}
    clean_url = url.split("?")[0]
    # parse query params if present
    if "?" in url:
        query_part = url.split("?", 1)[1]
        for pair in query_part.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                import urllib.parse
                args.setdefault(k, urllib.parse.unquote(v))

    if clean_url == "/api/languages":
        return ROUTE_HANDLERS["languages"](args)
    if clean_url == "/api/file/save":
        return ROUTE_HANDLERS["save_file"](args)
    if clean_url == "/api/file/create":
        return ROUTE_HANDLERS["create_file"](args)
    if clean_url == "/api/examples":
        return ROUTE_HANDLERS["examples"](args)
    if clean_url.startswith("/api/example/"):
        name = clean_url[len("/api/example/"):]
        import urllib.parse
        args["name"] = urllib.parse.unquote(name)
        return ROUTE_HANDLERS["load_example"](args)
    if clean_url == "/api/models/status":
        return ROUTE_HANDLERS["models_status"](args)
    if clean_url == "/api/models/unload":
        return ROUTE_HANDLERS["models_unload"](args)
    if clean_url == "/api/quality/score":
        return ROUTE_HANDLERS["quality_score"](args)
    if clean_url == "/api/quality/config":
        return ROUTE_HANDLERS["quality_config"](args)
    if clean_url == "/api/optimization/potential":
        return ROUTE_HANDLERS["optimization_potential"](args)
    if clean_url == "/api/optimization/config":
        return ROUTE_HANDLERS["optimization_config"](args)
    if clean_url == "/api/security/risk":
        return ROUTE_HANDLERS["security_risk"](args)
    if clean_url == "/api/security/risk/delta":
        return ROUTE_HANDLERS["security_risk_delta"](args)
    if clean_url == "/api/security/risk/config":
        return ROUTE_HANDLERS["security_risk_config"](args)
    if clean_url == "/api/security/report":
        return ROUTE_HANDLERS["security_report"](args)
    if clean_url == "/api/security/compare":
        return ROUTE_HANDLERS["security_compare"](args)
    if clean_url == "/api/security/benchmark":
        return ROUTE_HANDLERS["security_benchmark"](args)
    if clean_url == "/api/security/remediation":
        return ROUTE_HANDLERS["security_remediation"](args)
    if clean_url == "/api/security/apply":
        return ROUTE_HANDLERS["security_apply"](args)
    if clean_url == "/api/security/prescan":
        return ROUTE_HANDLERS["security_prescan"](args)
    if clean_url == "/api/security/approval/check":
        return ROUTE_HANDLERS["security_approval_check"](args)
    if clean_url == "/api/security/approval/approve":
        return ROUTE_HANDLERS["security_approval_approve"](args)
    if clean_url == "/api/security/approval/cancel":
        return ROUTE_HANDLERS["security_approval_cancel"](args)
    if clean_url in ("/api/program/run", "/api/run", "/run", "/execute", "/api/execute"):
        return ROUTE_HANDLERS["run_program"](args)
    if clean_url == "/api/testcase":
        return ROUTE_HANDLERS["testcase"](args)
    if clean_url == "/api/repair":
        return ROUTE_HANDLERS["repair"](args)
    if clean_url == "/api/repair/job":
        return ROUTE_HANDLERS["repair_job_start"](args)
    
    m_job_cancel = re.match(r"^/api/repair/job/([^/]+)/cancel$", clean_url)
    if m_job_cancel:
        args["job_id"] = m_job_cancel.group(1)
        return ROUTE_HANDLERS["repair_job_cancel"](args)

    m_job_status = re.match(r"^/api/repair/job/([^/]+)$", clean_url)
    if m_job_status:
        args["job_id"] = m_job_status.group(1)
        return ROUTE_HANDLERS["repair_job_status"](args)

    if clean_url == "/api/coordinator/cancel":
        return ROUTE_HANDLERS["coordinator_cancel"](args)
    if clean_url == "/api/coordinator/analyze_and_plan":
        return ROUTE_HANDLERS["coordinator_analyze_and_plan"](args)
    if clean_url == "/api/repair/post_apply":
        return ROUTE_HANDLERS["repair_post_apply"](args)
    if clean_url == "/api/pipeline/latest":
        return ROUTE_HANDLERS["pipeline_latest"](args)
    
    m_pipe = re.match(r"^/api/pipeline/run/([^/]+)$", clean_url)
    if m_pipe:
        args["run_id"] = m_pipe.group(1)
        return ROUTE_HANDLERS["pipeline_run"](args)

    if clean_url == "/api/patch/validate":
        return ROUTE_HANDLERS["validate_patch"](args)
    if clean_url == "/api/patch/apply":
        return ROUTE_HANDLERS["apply_patch"](args)
    if clean_url == "/api/patch/reject":
        return ROUTE_HANDLERS["reject_patch"](args)
    if clean_url == "/api/patch/revert":
        return ROUTE_HANDLERS["revert_patch"](args)
    if clean_url == "/api/dashboard/before_after":
        return ROUTE_HANDLERS["dashboard_before_after"](args)
    if clean_url == "/api/improvement/advise":
        return ROUTE_HANDLERS["improvement_advise"](args)

    m_imp_apply = re.match(r"^/api/improvement/candidate/([^/]+)/apply$", clean_url)
    if m_imp_apply:
        import urllib.parse
        args["candidate_id"] = urllib.parse.unquote(m_imp_apply.group(1))
        return ROUTE_HANDLERS["improvement_candidate_apply"](args)

    m_imp_rollback = re.match(r"^/api/improvement/candidate/([^/]+)/(rollback|apply_failed)$", clean_url)
    if m_imp_rollback:
        import urllib.parse
        args["candidate_id"] = urllib.parse.unquote(m_imp_rollback.group(1))
        return ROUTE_HANDLERS["improvement_candidate_rollback"](args)

    m_imp_reject = re.match(r"^/api/improvement/candidate/([^/]+)/reject$", clean_url)
    if m_imp_reject:
        import urllib.parse
        args["candidate_id"] = urllib.parse.unquote(m_imp_reject.group(1))
        return ROUTE_HANDLERS["improvement_candidate_reject"](args)

    if clean_url == "/api/rules/candidates":
        return ROUTE_HANDLERS["rules_candidates"](args)
    if clean_url == "/api/rules/propose":
        return ROUTE_HANDLERS["rules_propose"](args)

    m_rule_val = re.match(r"^/api/rules/candidate/([^/]+)/validate$", clean_url)
    if m_rule_val:
        import urllib.parse
        args["rule_id"] = urllib.parse.unquote(m_rule_val.group(1))
        return ROUTE_HANDLERS["rules_candidate_validate"](args)

    m_rule_app = re.match(r"^/api/rules/candidate/([^/]+)/approve$", clean_url)
    if m_rule_app:
        import urllib.parse
        args["rule_id"] = urllib.parse.unquote(m_rule_app.group(1))
        return ROUTE_HANDLERS["rules_candidate_approve"](args)

    m_rule_rej = re.match(r"^/api/rules/candidate/([^/]+)/reject$", clean_url)
    if m_rule_rej:
        import urllib.parse
        args["rule_id"] = urllib.parse.unquote(m_rule_rej.group(1))
        return ROUTE_HANDLERS["rules_candidate_reject"](args)

    if clean_url == "/api/rules/active":
        return ROUTE_HANDLERS["rules_active"](args)

    m_rule_dis = re.match(r"^/api/rules/active/([^/]+)/disable$", clean_url)
    if m_rule_dis:
        import urllib.parse
        args["rule_id"] = urllib.parse.unquote(m_rule_dis.group(1))
        return ROUTE_HANDLERS["rules_active_disable"](args)

    m_rule_en = re.match(r"^/api/rules/active/([^/]+)/enable$", clean_url)
    if m_rule_en:
        import urllib.parse
        args["rule_id"] = urllib.parse.unquote(m_rule_en.group(1))
        return ROUTE_HANDLERS["rules_active_enable"](args)

    m_rule_rb = re.match(r"^/api/rules/active/([^/]+)/rollback$", clean_url)
    if m_rule_rb:
        import urllib.parse
        args["rule_id"] = urllib.parse.unquote(m_rule_rb.group(1))
        return ROUTE_HANDLERS["rules_active_rollback"](args)

    if clean_url == "/api/rules/history":
        return ROUTE_HANDLERS["rules_history"](args)
    if clean_url == "/api/green/config":
        return ROUTE_HANDLERS["green_config"](args)
    if clean_url == "/api/green/measure":
        return ROUTE_HANDLERS["green_measure"](args)
    if clean_url == "/api/green/history":
        return ROUTE_HANDLERS["green_history"](args)
    if clean_url == "/api/benchmark/status":
        return ROUTE_HANDLERS["benchmark_status"](args)
    if clean_url == "/api/benchmark/dataset":
        return ROUTE_HANDLERS["benchmark_dataset"](args)
    if clean_url == "/api/benchmark/definitions":
        return ROUTE_HANDLERS["benchmark_definitions"](args)
    if clean_url == "/api/benchmark/run":
        return ROUTE_HANDLERS["benchmark_run"](args)

    return {"error": f"Route not found: {clean_url}"}, 404


def handle_request(req):
    req_id = req.get("id")
    route = req.get("route", "")
    args = req.get("args") or {}

    try:
        if route in ROUTE_HANDLERS:
            data, status = ROUTE_HANDLERS[route](args)
        elif route.startswith("/") or route.startswith("http"):
            data, status = dispatch_by_url(route, args)
        else:
            data = {"error": f"Unknown route: {route}"}
            status = 404
        return {
            "id": req_id,
            "status": status,
            "data": data,
            "error": None
        }
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return {
            "id": req_id,
            "status": 500,
            "data": {"error": str(exc)},
            "error": str(exc)
        }


def main():
    # Set stdin and stdout to utf-8
    sys.stdin.reconfigure(encoding="utf-8")
    
    # Save the real stdout stream specifically for JSON IPC responses
    real_stdout = sys.stdout
    real_stdout.reconfigure(encoding="utf-8")

    # Redirect sys.stdout to sys.stderr so any compiler/parser/model print statements
    # do NOT pollute the newline-delimited JSON IPC protocol on real_stdout!
    sys.stdout = sys.stderr

    # Send ready signal on stderr
    sys.stderr.write("BACKEND_IPC_READY\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            res = {"id": None, "status": 400, "error": f"Invalid JSON: {str(e)}"}
            real_stdout.write(json.dumps(res) + "\n")
            real_stdout.flush()
            continue

        res = handle_request(req)
        real_stdout.write(json.dumps(res) + "\n")
        real_stdout.flush()


if __name__ == "__main__":
    main()
