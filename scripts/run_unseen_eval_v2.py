# scripts/run_unseen_eval_v2.py
import sys
import os
import time
from collections import defaultdict

sys.path.insert(0, os.getcwd())

from scripts.held_out_evaluation_v2 import generate_programs_v2, ERROR_CLASSES
from compiler.repair_job_manager import RepairJobManager, check_c_syntax_errors, split_top_level_functions
from compiler.repair_planner import RepairPlanner
from compiler.patch_validator import SandboxedCompiler, PatchIntegrityInspector
from compiler.security_approval_gate import SecurityApprovalManager

def evaluate_unseen():
    progs = generate_programs_v2()
    unseen_progs = [p for p in progs if p["split"] == "unseen"]
    print(f"Running fresh evaluation on {len(unseen_progs)} UNSEEN programs (Seed 4242)...")
    print("=" * 70)

    planner = RepairPlanner()
    compiler = SandboxedCompiler()

    results_by_class = defaultdict(lambda: {"fixed": 0, "not_fixed": 0, "tiers": []})

    for idx, p in enumerate(unseen_progs, 1):
        pid = p["id"]
        e_class = p["error_class"]
        code = p["code"]
        clean_base = p["clean_base"]

        # GCC before
        gcc_before, errs_before = check_c_syntax_errors(code)
        assert not gcc_before, f"Expected {pid} to fail GCC compilation before repair"

        t0 = time.perf_counter()
        
        # UI execution path
        ok_tok, tok, _ = SecurityApprovalManager.create_one_time_approval(code, f"{pid}.c", "c")
        res = planner.plan_and_repair(code, filename=f"{pid}.c", language="c", operation="repair", approval_token=tok)
        cand_dict = res.get("candidate") or {}
        patched_code = cand_dict.get("proposed_code", code)
        tier_p = cand_dict.get("repair_provider", "none")
        if tier_p in ("deterministic_rules", "deterministic"):
            tier_used = "rules"
        elif tier_p == "codet5":
            tier_used = "codet5"
        elif tier_p == "qwen":
            tier_used = "qwen"
        else:
            tier_used = "none"

        gcc_after, errs_after = check_c_syntax_errors(patched_code)
        
        # Verify scope guard
        scope_ok = False
        if patched_code != code:
            scope_ok, _ = PatchIntegrityInspector.inspect(code, patched_code, original_findings=res.get("findings", []), filename=f"{pid}.c")

        # Success requires: compiles, scope guard passed, no new findings
        is_fixed = gcc_after and scope_ok

        elapsed = round(time.perf_counter() - t0, 2)
        print(f"[{idx:02d}/{len(unseen_progs):02d}] {pid} ({e_class:<22}) | GCC: {'OK' if gcc_after else 'FAIL':<4} | Scope: {'OK' if scope_ok else 'FAIL':<4} | Tier: {tier_used:<6} | {elapsed}s")

        if is_fixed:
            results_by_class[e_class]["fixed"] += 1
        else:
            results_by_class[e_class]["not_fixed"] += 1
        results_by_class[e_class]["tiers"].append(tier_used)

    print("\n" + "=" * 70)
    print("UNSEEN EVALUATION RESULTS (SEED 4242)")
    print("=" * 70)
    print(f"{'Error Class':<24} | {'Total':<6} | {'Fixed':<6} | {'Not Fixed':<10} | {'Tiers Used'}")
    print("-" * 70)
    total_unseen = len(unseen_progs)
    total_fixed = 0
    for e_class in ERROR_CLASSES:
        stats = results_by_class[e_class]
        tot = stats["fixed"] + stats["not_fixed"]
        total_fixed += stats["fixed"]
        tiers_str = ", ".join(f"{k}:{v}" for k, v in Counter(stats["tiers"]).items()) if stats["tiers"] else "none"
        print(f"{e_class:<24} | {tot:<6} | {stats['fixed']:<6} | {stats['not_fixed']:<10} | {tiers_str}")
    print("-" * 70)
    print(f"{'TOTAL':<24} | {total_unseen:<6} | {total_fixed:<6} | {total_unseen - total_fixed:<10} | Success Rate: {round(total_fixed / total_unseen * 100, 1)}%")
    print("=" * 70)

if __name__ == "__main__":
    from collections import Counter
    evaluate_unseen()

