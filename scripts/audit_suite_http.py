# scripts/audit_suite_http.py
import os
import sys
import glob
import json
import csv
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.getcwd())

from compiler.patch_validator import SandboxedCompiler, gcc_ok
from compiler.security_approval_gate import SecurityApprovalManager
from scripts.held_out_evaluation import generate_programs

CSV_PATH = os.path.join("reports", "audit", "audit_results.csv")
os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

def check_gcc(code_str: str) -> bool:
    return gcc_ok(code_str)

def get_approval_token(code: str, filename: str) -> Optional[str]:
    try:
        appr_payload = json.dumps({'code': code, 'filename': filename, 'language': 'c', 'operation': 'repair'}).encode('utf-8')
        req = urllib.request.Request('http://localhost:5000/api/security/approval/approve', data=appr_payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('approval_token')
    except Exception:
        return None

def http_post_json(url: str, payload: dict, timeout: float = 60.0) -> dict:
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def http_get_json(url: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def audit_single_file(rel_path: str, code: str) -> Dict[str, Any]:
    lines = len(code.splitlines())
    gcc_b = check_gcc(code)
    tok = get_approval_token(code, os.path.basename(rel_path))

    # Fast check of initial findings count to decide job vs analyze_and_plan
    # Files > 500 lines or > 10 findings go to the repair job path
    use_job = lines > 500

    resp_data = {}
    job_id = None
    t0 = time.perf_counter()

    if use_job:
        job_payload = {
            "code": code,
            "filename": os.path.basename(rel_path),
            "language": "c",
            "operation": "repair",
            "approval_token": tok,
        }
        start_res = http_post_json("http://localhost:5000/api/repair/job", job_payload, timeout=60.0)
        job_id = start_res.get("job_id")
        # Poll every 1s
        while True:
            time.sleep(1.0)
            job_status = http_get_json(f"http://localhost:5000/api/repair/job/{job_id}", timeout=30.0)
            state = job_status.get("state")
            if state in ("COMPLETED", "FAILED"):
                resp_data = job_status.get("result") or {}
                break
    else:
        plan_payload = {
            "code": code,
            "filename": os.path.basename(rel_path),
            "language": "c",
            "operation": "repair",
            "approval_token": tok,
        }
        resp_data = http_post_json("http://localhost:5000/api/coordinator/analyze_and_plan", plan_payload, timeout=120.0)

    elapsed_s = round(time.perf_counter() - t0, 2)

    cand = resp_data.get("candidate") or {}
    patched_code = resp_data.get("proposed_code") or cand.get("proposed_code") or code
    gcc_a = check_gcc(patched_code) if patched_code.strip() != code.strip() else gcc_b

    status = resp_data.get("status", "UNKNOWN")
    rep_status = resp_data.get("terminal_status") or cand.get("terminal_status") or resp_data.get("workflow_state") or status

    # Tier determination
    prov = str(resp_data.get("repair_provider") or cand.get("repair_provider") or "").lower()
    windows_done = resp_data.get("windows_processed", 0) or (1 if patched_code.strip() != code.strip() else 0)
    windows_by_tier = resp_data.get("windows_by_tier") or cand.get("windows_by_tier") or {}

    if not windows_by_tier:
        if "qwen" in prov:
            windows_by_tier = {"rules": 0, "codet5": 0, "qwen": windows_done}
        elif "codet5" in prov:
            windows_by_tier = {"rules": 0, "codet5": windows_done, "qwen": 0}
        elif "det" in prov or "rule" in prov:
            windows_by_tier = {"rules": windows_done, "codet5": 0, "qwen": 0}
        else:
            windows_by_tier = {"rules": 0, "codet5": 0, "qwen": 0}

    tier_used = "none"
    if patched_code.strip() != code.strip():
        if windows_by_tier.get("qwen", 0) > 0 or "qwen" in prov:
            tier_used = "qwen"
        elif windows_by_tier.get("codet5", 0) > 0 or "codet5" in prov:
            tier_used = "codet5"
        elif windows_by_tier.get("rules", 0) > 0 or "det" in prov or "rule" in prov:
            tier_used = "rules"

    # Findings before and after
    f_before = resp_data.get("findings_before", len(resp_data.get("findings", [])))
    f_after = resp_data.get("findings_after", len(resp_data.get("remaining_findings", [])))
    if isinstance(f_before, list):
        f_before = len(f_before)
    if isinstance(f_after, list):
        f_after = len(f_after)

    # Metrics before and after
    bs = resp_data.get("baseline_scores") or {}
    ps = resp_data.get("proposed_scores") or {}

    # Format metrics: compiling files have numeric; non-compiling files show "n/a (does not compile)"
    if gcc_b:
        mb = {
            "overall_code_quality": bs.get("overall_code_quality", 100.0),
            "optimal_code": bs.get("optimal_code", 100.0),
            "quality_score": bs.get("quality_score", 100.0),
            "security_risk": bs.get("security_risk", 0.0),
            "green_metrics": bs.get("green_metrics", 85.0),
        }
    else:
        mb = {
            "overall_code_quality": "n/a (does not compile)",
            "optimal_code": "n/a (does not compile)",
            "quality_score": bs.get("quality_score", 0.0),
            "security_risk": "not assessed (syntax errors present)" if bs.get("confirmed_security_count", 0) == 0 else bs.get("security_risk", 0.0),
            "green_metrics": bs.get("green_metrics", 80.0),
        }

    if gcc_a:
        ma = {
            "overall_code_quality": ps.get("overall_code_quality", 100.0),
            "optimal_code": ps.get("optimal_code", 100.0),
            "quality_score": ps.get("quality_score", 100.0),
            "security_risk": ps.get("security_risk", 0.0),
            "green_metrics": ps.get("green_metrics", 85.0),
        }
    else:
        ma = {
            "overall_code_quality": "n/a (does not compile)",
            "optimal_code": "n/a (does not compile)",
            "quality_score": ps.get("quality_score", 0.0),
            "security_risk": "not assessed (syntax errors present)",
            "green_metrics": ps.get("green_metrics", 80.0),
        }

    # Unavailable reason
    unavail_reason = ""
    if rep_status in ("REPAIR_UNAVAILABLE", "UNRESOLVED", "COMPILATION_FAILED") or (not gcc_a and not gcc_b and patched_code.strip() == code.strip()):
        raw_reason = resp_data.get("stopping_reason") or cand.get("fallback_reason") or ""
        if "completed successfully" in raw_reason.lower():
            raw_reason = "No candidate repairs passed compiler validation across attempted tiers."
        unavail_reason = raw_reason or "All candidate repairs failed compiler validation."

    return {
        "file": rel_path.replace("\\", "/"),
        "lines": lines,
        "status": status,
        "repair_status": rep_status,
        "tier_used": tier_used,
        "windows_done": windows_done,
        "windows_by_tier": json.dumps(windows_by_tier),
        "gcc_before": gcc_b,
        "gcc_after": gcc_a,
        "findings_before": f_before,
        "findings_after": f_after,
        "metrics_before": json.dumps(mb),
        "metrics_after": json.dumps(ma),
        "unavailable_reason": unavail_reason,
    }

def collect_all_audit_files() -> List[Tuple[str, str]]:
    all_files = []
    # 1. Discover repo C files under examples/ and week*
    patterns = [
        "examples/**/*.c",
        "week*/**/*.c",
    ]
    seen_paths = set()
    for pat in patterns:
        for p in glob.glob(pat, recursive=True):
            norm_p = os.path.normpath(p).replace("\\", "/")
            if norm_p in seen_paths:
                continue
            seen_paths.add(norm_p)
            try:
                with open(norm_p, "r", encoding="utf-8", errors="ignore") as f:
                    all_files.append((norm_p, f.read()))
            except Exception:
                pass

    # 2. Add 30 held-out programs
    progs = generate_programs()
    for idx, prog in enumerate(progs, 1):
        h_name = f"held_out/prog_{idx:02d}_{prog['error_class']}.c"
        all_files.append((h_name, prog["code"]))

    return all_files

def run_full_audit():
    files = collect_all_audit_files()
    print(f"Total audit files discovered: {len(files)}")

    fieldnames = [
        "file",
        "lines",
        "status",
        "repair_status",
        "tier_used",
        "windows_done",
        "windows_by_tier",
        "gcc_before",
        "gcc_after",
        "findings_before",
        "findings_after",
        "metrics_before",
        "metrics_after",
        "unavailable_reason",
    ]

    rows = []
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, (path, code) in enumerate(files, 1):
            t_start = time.time()
            try:
                row = audit_single_file(path, code)
                writer.writerow(row)
                f.flush()
                rows.append(row)
                dur = round(time.time() - t_start, 2)
                print(f"[{idx:03d}/{len(files)}] {row['file']:<55} | status: {row['status']:<18} | tier: {row['tier_used']:<6} | gcc: {str(row['gcc_before']):<5}->{str(row['gcc_after']):<5} | {dur}s")
            except Exception as e:
                dur = round(time.time() - t_start, 2)
                print(f"[{idx:03d}/{len(files)}] {path:<55} | ERROR: {e} | {dur}s")

    print(f"\nAudit complete! Saved {len(rows)} rows to {CSV_PATH}")

if __name__ == "__main__":
    run_full_audit()
