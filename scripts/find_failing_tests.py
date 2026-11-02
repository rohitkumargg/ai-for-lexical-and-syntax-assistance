import subprocess
import re
import json

print("Running pytest to find all failures...")
p = subprocess.run(["pytest", "--tb=line", "-q"], capture_output=True, text=True)
stdout = p.stdout
stderr = p.stderr

failures = []
# Lines look like:
# FAIL tests/foo.py::test_bar - AssertionError: ...
# or in summary:
# FAILED tests/foo.py::test_bar - AssertionError: ...
for line in stdout.splitlines():
    if line.startswith("FAILED "):
        parts = line[7:].split(" - ", 1)
        test_id = parts[0].strip()
        cause = parts[1].strip() if len(parts) > 1 else "Unknown"
        failures.append({"test_id": test_id, "cause": cause})

print(f"Total failures found: {len(failures)}")
with open("scratch/failing_tests.json", "w") as f:
    json.dump(failures, f, indent=2)

for idx, f in enumerate(failures, 1):
    print(f"[{idx:02d}] {f['test_id']} -> {f['cause']}")

