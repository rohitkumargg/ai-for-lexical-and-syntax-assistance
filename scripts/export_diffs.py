import os
import subprocess
import hashlib

os.makedirs("reports/diffs", exist_ok=True)

CHANGED_FILES = [
    "app.py",
    "compiler/repair_job_manager.py",
    "compiler/repair_planner.py",
    "compiler/security_approval_gate.py",
    "compiler/error_corrector.py",
    "gui/static/app.js",
    "docs/DATA_RETENTION.md",
    "tests/test_repair_job.py",
    "scripts/held_out_evaluation.py",
]

print("=== EXPORTING DIFFS TO reports/diffs/ ===")
print(f"{'File':<35} | {'Diff Path':<35} | {'Diff Size (bytes)':<18} | {'SHA256 of Diff'}")
print("-" * 140)

for fpath in CHANGED_FILES:
    sanitized = fpath.replace("/", "_").replace("\\", "_") + ".diff"
    diff_target = os.path.join("reports", "diffs", sanitized)

    cmd = ["git", "diff", "-U3", fpath]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    diff_bytes = res.stdout

    with open(diff_target, "wb") as f:
        f.write(diff_bytes)

    h = hashlib.sha256(diff_bytes).hexdigest()
    sz = len(diff_bytes)
    print(f"{fpath:<35} | {diff_target:<35} | {sz:<18} | {h}")

print("\n=== GIT DIFF --STAT FOR CHANGED FILES ===")
cmd_stat = ["git", "diff", "--stat"] + CHANGED_FILES
res_stat = subprocess.run(cmd_stat, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
print(res_stat.stdout)

