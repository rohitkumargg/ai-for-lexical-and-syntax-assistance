import os, sys
sys.path.insert(0, os.getcwd())
from compiler.repair_job_manager import check_c_syntax_errors

exs = [
    ('const', 'const int MAX_LIMIT = 100;\nint main(void) { const char *msg = "hello"; return 0; }'),
    ('volatile', 'volatile int reg_flag = 1;\nint main(void) { volatile int local_reg = 0; return local_reg; }'),
    ('static', 'static int counter = 0;\nstatic void inc(void) { static int loc = 0; loc++; }\nint main(void) { inc(); return 0; }'),
    ('extern', 'extern int global_buffer;\nextern void ext_worker(int code);\nint main(void) { return 0; }')
]

for name, code in exs:
    is_valid, errors = check_c_syntax_errors(code)
    print(f"=== Specifier: {name} ===")
    print("Code:\n" + code)
    print(f"ANTLR is_valid: {is_valid}")
    print(f"ANTLR error count: {len(errors)}")
    print(f"Errors list: {errors}")
    print("-" * 40)
