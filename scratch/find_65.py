import glob, os
from compiler.semantic_checker import SemanticChecker

files = sorted(glob.glob('examples/**/*.c', recursive=True))
main_files = [f for f in files if not f.replace('\\', '/').startswith('examples/semantic/')]

sem_issues = []
for path in main_files:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        checker = SemanticChecker()
        issues = checker.check_code(code)
        for iss in issues:
            if iss.get('kind') == 'undeclared':
                sem_issues.append((path, iss))
    except Exception as e:
        pass

print(f'Total SemanticChecker undeclared issues: {len(sem_issues)}')
for path, iss in sem_issues:
    print(f"{path}:{iss.get('line')}:{iss.get('col')} -> {iss.get('detail')}")
