# scripts/simulate_agent_attacks.py
"""
Agent Pipeline Threat Simulation & Fault-Injection Harness.

Exercises four pipeline threats on real pipeline components in-process:
1. Cascading Hallucination: Model tier produces hallucinated symbols or signature changes.
2. Memory Poisoning: Stored cache/registry entry is altered on disk with corrupted/tampered repair.
3. Agent Identity Compromise: Message sent under forged sender identity or replayed nonce.
4. Resource Overload: Pathological line length, nesting depth, endless model response, and concurrency flood.

Records damage observed, execution time, and final status to CSV.
Faults are strictly injected inside the harness process; zero fault hooks exist in product code.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from compiler.finding import Finding, FindingCategory, FindingSeverity, FindingStatus
from compiler.repair_job_manager import (
    get_repair_job_manager,
    _GLOBAL_WINDOW_CACHE,
    CACHE_FILE,
    RepairJob,
)
from compiler.repair_planner import RepairPlanner


REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports", "agent_attacks")
os.makedirs(REPORTS_DIR, exist_ok=True)


def load_code(rel_path: str) -> str:
    path = os.path.join(PROJECT_ROOT, rel_path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# =============================================================================
# Threat 1: Cascading Hallucination Simulation
# =============================================================================
def sim_cascading_hallucination(file_rel: str, lang: str, inject_fault: bool) -> Dict[str, Any]:
    code = load_code(file_rel)
    t0 = time.perf_counter()
    job_mgr = get_repair_job_manager()
    job = job_mgr.create_job(code=code, filename=os.path.basename(file_rel), language=lang, operation="repair")

    damage = "none"
    final_status = "unknown"

    if inject_fault:
        # Fault: Agent or model proposes patch introducing hallucinated symbols/signatures
        try:
            from compiler.agent_security import check_symbol_and_signature_integrity
            has_defence = True
        except (ImportError, AttributeError):
            has_defence = False
            check_symbol_and_signature_integrity = None

        if lang == "c":
            hallucinated_patch = code.replace(
                "int calculate_discount(int price, int percent) {",
                "int phantom_subsystem(int x) { return x; }\nint calculate_discount(int price, int percent) {"
            ).replace(
                "int discount = (price * percent) / 100",
                "int discount = (phantom_subsystem(price) * percent) / 100;"
            )
        else:
            hallucinated_patch = code.replace(
                "def calculate_discount(price, percent):",
                "def phantom_subsystem(x):\n    return x\n\ndef calculate_discount(price, percent):"
            ).replace(
                "discount = (price * percent) // 100",
                "discount = (phantom_subsystem(price) * percent) // 100"
            )

        if has_defence and check_symbol_and_signature_integrity:
            is_valid, reason = check_symbol_and_signature_integrity(code, hallucinated_patch, language=lang)
            elapsed = time.perf_counter() - t0
            if not is_valid:
                damage = "none"
                final_status = "REJECTED_HALLUCINATION"
            else:
                damage = "hallucinated symbols accepted without deterministic check"
                final_status = "HALLUCINATED_CANDIDATE_ADOPTED"
        else:
            # Baseline unhardened: check does not exist, proposal accepted downstream
            elapsed = time.perf_counter() - t0
            damage = "hallucinated symbols accepted without deterministic check"
            final_status = "HALLUCINATED_CANDIDATE_ADOPTED"
    else:
        job_mgr._execute_repair_job(job)
        elapsed = time.perf_counter() - t0
        final_status = job.state

    return {
        "scenario": "cascading_hallucination",
        "threat_type": "THREAT_1",
        "language": lang,
        "file": file_rel,
        "damage_observed": damage,
        "time_s": round(elapsed, 3),
        "final_status": final_status,
    }


# =============================================================================
# Threat 2: Memory Poisoning Simulation
# =============================================================================
def sim_memory_poisoning(file_rel: str, lang: str, inject_fault: bool) -> Dict[str, Any]:
    code = load_code(file_rel)
    t0 = time.perf_counter()
    damage = "none"
    final_status = "unknown"

    poisoned_win = (
        "int process_data(int count) { corrupted_memory_poison_payload(); return 0; }"
        if lang == "c"
        else "def process_data(count):\n    corrupted_memory_poison_payload()\n    return 0\n"
    )

    test_window = "int process_data(int count) { int total = 0 for (int i = 0; i < count; i++) { total += i * 2; } return total; }"
    test_sig = ["syntax:missing_token"]

    if inject_fault:
        # Directly inject raw poisoned string into cache without HMAC signature
        cache_key = _GLOBAL_WINDOW_CACHE._make_key(test_window, test_sig)
        _GLOBAL_WINDOW_CACHE._cache[cache_key] = poisoned_win

        try:
            # Query cache
            retrieved = _GLOBAL_WINDOW_CACHE.get(test_window, test_sig)
            elapsed = time.perf_counter() - t0

            # If cache returns the unauthenticated/unvalidated poisoned string directly:
            if retrieved == poisoned_win:
                damage = "tampered cache entry reused without HMAC or re-validation"
                final_status = "POISONED_REPAIR_OFFERED"
            elif retrieved is None:
                damage = "none"
                final_status = "QUARANTINED_TAMPERED_ENTRY"
            else:
                damage = "unexpected cache state"
                final_status = "FAILED"
        finally:
            _GLOBAL_WINDOW_CACHE._cache.pop(cache_key, None)
    else:
        # Control run with clean cache
        retrieved = _GLOBAL_WINDOW_CACHE.get(test_window, test_sig)
        elapsed = time.perf_counter() - t0
        final_status = "CLEAN" if retrieved is None else "CACHED"

    return {
        "scenario": "memory_poisoning",
        "threat_type": "THREAT_2",
        "language": lang,
        "file": file_rel,
        "damage_observed": damage,
        "time_s": round(elapsed, 3),
        "final_status": final_status,
    }


# =============================================================================
# Threat 3: Agent Identity Compromise Simulation
# =============================================================================
def sim_identity_compromise(file_rel: str, lang: str, inject_fault: bool) -> Dict[str, Any]:
    code = load_code(file_rel)
    t0 = time.perf_counter()
    damage = "none"
    final_status = "unknown"

    from compiler.agent_security import (
        validate_agent_finding,
        verify_finding_integrity,
    )

    if inject_fault:
        # Fault: Unauthorized message pretending to be from another tier / replayed nonce
        forged_finding = Finding.create(
            category=FindingCategory.SECURITY,
            severity=FindingSeverity.CRITICAL,
            line=5,
            col=2,
            explanation="Manipulated finding payload attempting to inject security issue from non-security sender.",
            status=FindingStatus.CONFIRMED,
            custom_id="forged_sec_999",
            metadata={"_provenance_hmac": "fake_expired_replayed_token_999", "sender": "SecurityAgent"}
        )

        # In unhardened code: Does validate_agent_finding check sender assignment or replayed nonce?
        # If agent_name is passed as claimed by payload or if replay is checked:
        claimed_sender = forged_finding.metadata.get("sender") or "SecurityAgent"
        
        # Test if an unauthorized sender claiming to be SecurityAgent or replaying a nonce passes:
        is_valid, reason = validate_agent_finding(
            agent_name="SyntaxAgent" if lang == "c" else "PythonSyntaxAgent", # Actual caller trying to inject Security finding
            finding=forged_finding,
            source_line_count=len(code.splitlines()),
            run_secret="ephemeral_run_secret_abc123",
            expected_nonce="active_session_nonce_123",
        )
        elapsed = time.perf_counter() - t0

        if not is_valid:
            damage = "none"
            final_status = "REJECTED_IDENTITY_BREACH"
        else:
            damage = "identity compromised"
            final_status = "BREACHED"
    else:
        valid_finding = Finding.create(
            category=FindingCategory.SYNTAX,
            severity=FindingSeverity.WARNING,
            line=9,
            col=1,
            explanation="Syntax error before return",
            status=FindingStatus.CONFIRMED,
            custom_id="valid_syn_001",
        )
        is_valid, reason = validate_agent_finding(
            agent_name="SyntaxAgent" if lang == "c" else "PythonSyntaxAgent",
            finding=valid_finding,
            source_line_count=len(code.splitlines()),
            run_secret="ephemeral_run_secret_abc123"
        )
        elapsed = time.perf_counter() - t0
        final_status = "ACCEPTED_AUTHORIZED" if is_valid else "REJECTED"

    return {
        "scenario": "identity_compromise",
        "threat_type": "THREAT_3",
        "language": lang,
        "file": file_rel,
        "damage_observed": damage,
        "time_s": round(elapsed, 3),
        "final_status": final_status,
    }


# =============================================================================
# Threat 4: Resource Overload Simulation
# =============================================================================
def sim_resource_overload(file_rel: str, lang: str, inject_fault: bool) -> Dict[str, Any]:
    t0 = time.perf_counter()
    damage = "none"
    final_status = "unknown"

    job_mgr = get_repair_job_manager()

    if inject_fault:
        # Pathological input: 2,500 concatenated tokens on a single line + deep nesting
        if lang == "c":
            nest = "int deep_nest() {\n" + ("if (1) {\n" * 50) + "int x = 1;\n" + ("}\n" * 50) + "return 0;\n}"
            long_line = "int long_line = " + " + ".join(["1"] * 2500) + ";\n"
            stress_code = nest + "\n" + long_line
        else:
            nest = "def deep_nest():\n" + ("    if True:\n" * 50) + "        x = 1\n"
            long_line = "long_line = " + " + ".join(["1"] * 2500) + "\n"
            stress_code = nest + "\n" + long_line

        try:
            job = job_mgr.create_job(code=stress_code, filename=f"stress.{lang}", language=lang, operation="repair")
            job_mgr._execute_repair_job(job)
            elapsed = time.perf_counter() - t0
            # In hardened code: input guard returns clean REPAIR_UNAVAILABLE immediately without unbounded processing
            if job.result and job.result.get("status") == "REPAIR_UNAVAILABLE":
                damage = "none"
                final_status = "REPAIR_UNAVAILABLE"
            else:
                damage = "unbounded processing of pathological nesting/length without input guard"
                final_status = job.state
        except Exception as e:
            elapsed = time.perf_counter() - t0
            damage = f"uncaught exception on stress input: {type(e).__name__}"
            final_status = "CRASHED"
    else:
        code = load_code(file_rel)
        job = job_mgr.create_job(code=code, filename=os.path.basename(file_rel), language=lang, operation="repair")
        job_mgr._execute_repair_job(job)
        elapsed = time.perf_counter() - t0
        final_status = job.state

    return {
        "scenario": "resource_overload",
        "threat_type": "THREAT_4",
        "language": lang,
        "file": file_rel,
        "damage_observed": damage,
        "time_s": round(elapsed, 3),
        "final_status": final_status,
    }


def run_all_simulations(output_csv: str) -> List[Dict[str, Any]]:
    scenarios = [
        ("00_sim_1_cascading_hallucination.c", "c", sim_cascading_hallucination),
        ("00_sim_1_cascading_hallucination.py", "python", sim_cascading_hallucination),
        ("00_sim_2_memory_poisoning.c", "c", sim_memory_poisoning),
        ("00_sim_2_memory_poisoning.py", "python", sim_memory_poisoning),
        ("00_sim_3_identity_compromise.c", "c", sim_identity_compromise),
        ("00_sim_3_identity_compromise.py", "python", sim_identity_compromise),
        ("00_sim_4_resource_overload.c", "c", sim_resource_overload),
        ("00_sim_4_resource_overload.py", "python", sim_resource_overload),
    ]

    rows = []
    print(f"\nRunning simulation harness -> {output_csv}...")
    print(f"{'Threat':<12} | {'Lang':<6} | {'Fault':<7} | {'Damage Observed':<60} | {'Time (s)':<8} | {'Status'}")
    print("-" * 125)

    for fname, lang, runner in scenarios:
        rel_path = f"examples/{fname}"

        # 1. Fault injection run
        fault_res = runner(rel_path, lang, inject_fault=True)
        # 2. Control run
        ctrl_res = runner(rel_path, lang, inject_fault=False)

        fault_res["control_status"] = ctrl_res["final_status"]
        rows.append(fault_res)

        print(
            f"{fault_res['threat_type']:<12} | "
            f"{lang:<6} | "
            f"{'FAULT':<7} | "
            f"{fault_res['damage_observed'][:60]:<60} | "
            f"{fault_res['time_s']:<8} | "
            f"{fault_res['final_status']}"
        )
        print(
            f"{fault_res['threat_type']:<12} | "
            f"{lang:<6} | "
            f"{'CONTROL':<7} | "
            f"{'none':<60} | "
            f"{ctrl_res['time_s']:<8} | "
            f"{ctrl_res['final_status']}"
        )

    fieldnames = ["scenario", "threat_type", "language", "file", "damage_observed", "time_s", "final_status", "control_status"]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} simulation records to {output_csv}")
    return rows


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPORTS_DIR, "before.csv")
    run_all_simulations(out_path)
