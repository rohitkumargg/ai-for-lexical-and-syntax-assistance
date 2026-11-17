import json

data = json.load(open('reports/diagnostics/step1_diagnosis.json'))
print(f'Checking metrics across {len(data)} files:')
missing_count = 0
for r in data:
    f = r['file'].replace('examples/', '')
    m = r['metrics']
    for k, v in m.items():
        if v['value'] == '--%':
            missing_count += 1
            print(f'BLANK in {f}: {k}')

if missing_count == 0:
    print('ALL METRICS ARE FULLY COMPUTED! Zero --% blanks across all 23 files!')
else:
    print(f'Total blanks found: {missing_count}')
