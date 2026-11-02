import os
import sys
sys.path.insert(0, os.getcwd())

from compiler.repair_job_manager import RepairJobManager
import json

code = """int system(char *command);
int main() {
    char cmd[50];
    scanf("%49s", cmd);
    system(cmd);
}"""

mgr = RepairJobManager()
job = mgr.create_job(code=code, filename="tainted_6line.c", language="c")
mgr._execute_repair_job(job)
res = job.result

print("=== 6-LINE PROGRAM REPAIR JOB RESULT ===")
print("Status:", res.get("status"))
print("Stopping Reason:", res.get("stopping_reason"))
print("Compiles:", res.get("compiles"))
print("\n=== FINDINGS (UI PANEL FIELDS) ===")
findings = res.get("findings", [])
print(f"Total findings: {len(findings)}")
for idx, f in enumerate(findings, 1):
    print(f"\n--- Finding #{idx} ---")
    print("Raw finding:", json.dumps(f, indent=2, default=str))
