import sys, os, csv
sys.path.insert(0, os.getcwd())
from scripts.audit_suite import audit_file, CSV_PATH
from scripts.held_out_evaluation import generate_programs

fieldnames = [
    "file", "lines", "status", "repair_status", "tier_used",
    "windows_done", "windows_by_tier", "gcc_before", "gcc_after",
    "findings_by_severity", "score_metrics", "unavailable_reason"
]

held_out_map = {f"held_out/{p['id']}_{p['error_class']}.c": p["code"] for p in generate_programs()}

with open(CSV_PATH, 'r', newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

updated = 0
for r in rows:
    if r['status'] == 'ERROR':
        fname = r['file']
        if fname in held_out_map:
            code = held_out_map[fname]
        elif os.path.exists(fname):
            with open(fname, 'r', encoding='utf-8', errors='ignore') as fp:
                code = fp.read()
        else:
            print(f"Skipping {fname}: file not found")
            continue
        try:
            new_row = audit_file(fname, code)
            r.update({k: str(new_row[k]) for k in fieldnames})
            updated += 1
            print(f"Updated {fname}: status={r['status']}, tier={r['tier_used']}, gcc_a={r['gcc_after']}")
            # Flush periodically
            with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f_out:
                writer = csv.DictWriter(f_out, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        except Exception as ex:
            print(f"Error on {fname}: {ex}")

print(f"Done updating {updated} rows.")
