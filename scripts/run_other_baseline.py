import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler.repair_planner import RepairPlanner

files = [
    'examples/main.c',
    'examples/untitled1.c',
    'examples/week5_grammar_2026/bitwise_ops_broken_2.c',
    'examples/week5_grammar_2026/globals_broken_1.c',
    'examples/week5_grammar_2026/types_broken_1.c',
    'examples/week10_security/unsafe_gets.c'
]

planner = RepairPlanner()
results = {}

for fpath in files:
    with open(fpath, 'r', encoding='utf-8') as f:
        code = f.read()
    fname = os.path.basename(fpath)
    res = planner.plan_and_repair(code, filename=fname)
    
    # Extract findings from original_assessment
    findings_list = []
    cf = (res.get('original_assessment') or {}).get('classified_findings') or {}
    for stage_findings in cf.values():
        if isinstance(stage_findings, list):
            for item in stage_findings:
                findings_list.append({
                    'category': item.get('category'),
                    'severity': item.get('severity'),
                    'title': item.get('title'),
                    'rule_id': item.get('rule_id')
                })

    risk_pct = (res.get('baseline_scores') or {}).get('vulnerability_risk')
    status = res.get('terminal_status') or res.get('status')

    results[fpath] = {
        'filename': fname,
        'status': status,
        'risk_pct': risk_pct,
        'findings': findings_list,
        'has_candidate': bool(res.get('candidate'))
    }

output_path = 'other_examples_baseline.json'
with open(output_path, 'w', encoding='utf-8') as out:
    json.dump(results, out, indent=2)

print(f"Captured {len(results)} files to {output_path}:")
for k, v in results.items():
    print(f"  {k}: status={v['status']}, risk_pct={v['risk_pct']}, findings={len(v['findings'])}")
