import json
from app import app
from compiler.security_approval_gate import SecurityApprovalManager

client = app.test_client()
code = 'int system(char *command); int main(){ char cmd[50]; scanf("%49s", cmd); system(cmd); }'

# 1. Prescan / gate check
pre_res = client.post('/api/security/prescan', json={'code': code, 'filename': 'main.c', 'language': 'c', 'operation': 'repair'})
print('=== 1. SECURITY PRESCAN RESPONSE (/api/security/prescan) ===')
print('HTTP Status Code:', pre_res.status_code)
pre_data = pre_res.get_json() or {}
print(json.dumps(pre_data, indent=2))

# 2. Gate approval
ok, token, msg = SecurityApprovalManager.create_one_time_approval(source_code=code, filename='main.c', language='c', operation='repair')

# 3. Analyze / Coordinator API output (/api/coordinator/analyze_and_plan)
ana_res = client.post('/api/coordinator/analyze_and_plan', json={'code': code, 'filename': 'main.c', 'language': 'c', 'approval_token': token})
print('\n=== 2. COORDINATOR ANALYZE RESPONSE (/api/coordinator/analyze_and_plan) ===')
print('HTTP Status Code:', ana_res.status_code)
data = ana_res.get_json() or {}
print('Program Status:', data.get('status'))
print('Terminal Status:', data.get('terminal_status'))
print('Banner Status Label:', data.get('banner_label') or (data.get('original_assessment') or {}).get('status_label'))
print('Original Assessment:', json.dumps(data.get('original_assessment'), indent=2))
print('Total Findings in List:', len(data.get('findings', [])))
print('Findings:', json.dumps(data.get('findings'), indent=2))
