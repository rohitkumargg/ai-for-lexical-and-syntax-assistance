import json

data = json.load(open('reports/diagnostics/step1_diagnosis.json'))
print('| File | Lang | Sec Detected | Proposal Gen | Tier | Qwen Called | Qwen Rejection (raw) | Status | Metrics On | Time | Failure Details |')
print('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
for r in data:
    f = r['file'].replace('examples/', '')
    lang = r['language']
    sec = r['security_finding_detected']
    prop = r['repair_proposal_generated']
    tier = r['repair_tier']
    qw = r['qwen_called']
    qwr = r['qwen_rejected_raw'].replace('\n', ' ')
    if len(qwr) > 25:
        qwr = qwr[:22] + '...'
    st = r['final_status']
    m_comp = 'repaired' if prop == 'YES' else 'original'
    t = f"{r['time_s']:.2f}s"
    fail = r['failure_details'].replace('\n', ' ')
    if len(fail) > 40:
        fail = fail[:37] + '...'
    print(f"| `{f}` | {lang} | {sec} | {prop} | {tier} | {qw} | {qwr} | {st} | {m_comp} | {t} | {fail} |")
