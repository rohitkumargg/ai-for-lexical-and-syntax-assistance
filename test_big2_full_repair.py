import re
from compiler.lexical_corrector import fix_common_lexical_issues
from compiler.repair_job_manager import _fix_unambiguous_syntax_delimiters
from compiler.security_auto_fixer import SecurityAutoFixer
from compiler.patch_validator import SandboxedCompiler

with open("examples/big2.c", "r", encoding="utf-8") as f:
    code = f.read()

print("Original lines:", len(code.splitlines()))

# 1. Lexical
c1, lex_steps = fix_common_lexical_issues(code)
print("Lexical fixes applied:", len(lex_steps))

# 2. Syntax delimiters (brackets, semicolons, commas)
c2, delim_steps = _fix_unambiguous_syntax_delimiters(c1)
print("Delimiter fixes applied:", len(delim_steps))

# 3. Semantic pointer access (ptr.x -> ptr->x)
lines = c2.splitlines()
sem_fixes = 0
for idx, line in enumerate(lines):
    if "ptr.x" in line:
        lines[idx] = line.replace("ptr.x", "ptr->x")
        sem_fixes += 1
    if "ptr.y" in line:
        lines[idx] = line.replace("ptr.y", "ptr->y")
        sem_fixes += 1
c3 = "\n".join(lines)
print("Semantic pointer dot fixes applied:", sem_fixes)

# 4. Security fixes (gets, scanf, sprintf)
fixer = SecurityAutoFixer()
res = fixer.apply_fixes(c3)
c4 = res.source
print("Security fixes applied:", len(res.applied_steps))

# Check with GCC!
comp = SandboxedCompiler()
ok, out, code_exit = comp.compile_check(c4)
print("GCC compile check ok:", ok)
if not ok:
    err_lines = [line for line in out.splitlines() if "error:" in line]
    print(f"GCC error count: {len(err_lines)}")
    for e in err_lines[:10]:
        print(" ", e)
else:
    print("ALL 2030 LINES COMPILED WITH ZERO ERRORS!")

