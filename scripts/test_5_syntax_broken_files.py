import os
import sys
import time
import json

sys.path.insert(0, os.getcwd())

from compiler.repair_job_manager import get_repair_job_manager
from compiler.patch_validator import SandboxedCompiler
from compiler.agents import SyntaxAgent

compiler = SandboxedCompiler()
agent = SyntaxAgent()
mgr = get_repair_job_manager()

TEST_CASES = [
    {
        "filename": "test_missing_semicolon.c",
        "code": """#include <stdio.h>
int calculate_sum(int a, int b) {
    int res = a + b
    return res;
}
int main(void) {
    printf("%d\\n", calculate_sum(5, 10));
    return 0;
}
"""
    },
    {
        "filename": "test_typo_keyword.c",
        "code": """#include <stdio.h>
int countdown(int start) {
    whlie (start > 0) {
        start--;
    }
    return start;
}
int main(void) {
    return countdown(5);
}
"""
    },
    {
        "filename": "test_missing_paren.c",
        "code": """#include <stdio.h>
int check_positive(int n) {
    if (n > 0 {
        return 1;
    }
    return 0;
}
int main(void) {
    return check_positive(10);
}
"""
    },
    {
        "filename": "test_typo_type.c",
        "code": """#include <stdio.h>
viod print_greeting(const char *msg) {
    printf("Greeting: %s\\n", msg);
}
int main(void) {
    print_greeting("Hello World");
    return 0;
}
"""
    },
    {
        "filename": "test_missing_closing_brace.c",
        "code": """#include <stdio.h>
int find_max(int a, int b) {
    if (a > b) {
        return a;
    else {
        return b;
    }
}
int main(void) {
    return find_max(3, 7);
}
"""
    }
]

def run_tests():
    print("\n=== REQUIREMENT 6: 5 SYNTAX-BROKEN C FILES EVALUATION TABLE ===")
    results = []

    for tc in TEST_CASES:
        fname = tc["filename"]
        code = tc["code"]
        
        # 1. Before stats
        init_compiles, init_out, _ = compiler.compile_check(code)
        init_fnds = agent.analyze(code, filename=fname)
        fnds_before_count = len(init_fnds)

        # 2. Run Job
        t0 = time.perf_counter()
        job = mgr.create_job(code=code, filename=fname, language="c")
        mgr.start_job(job)

        while job.state in ("PENDING", "RUNNING"):
            time.sleep(0.1)

        elapsed = time.perf_counter() - t0
        repaired_code = job.current_code

        # 3. After stats
        final_compiles, final_out, _ = compiler.compile_check(repaired_code)
        final_fnds = agent.analyze(repaired_code, filename=fname)
        fnds_after_count = len(final_fnds)

        tiers = getattr(job, "windows_by_tier", {"rules": 0, "codet5": 0, "qwen": 0})
        tier_str = f"rules:{tiers.get('rules', 0)}, codet5:{tiers.get('codet5', 0)}, qwen:{tiers.get('qwen', 0)}"

        results.append({
            "file": fname,
            "before_fnds": fnds_before_count,
            "after_fnds": fnds_after_count,
            "compiles_before": "YES" if init_compiles else "NO",
            "compiles_after": "YES" if final_compiles else "NO",
            "windows_by_tier": tier_str,
            "seconds": round(elapsed, 2)
        })

    # Print Table
    print(f"| {'File':<30} | {'Findings Before':<16} | {'Findings After':<15} | {'Compiles Before':<16} | {'Compiles After':<15} | {'Windows by Tier':<35} | {'Seconds':<8} |")
    print(f"|{'-'*32}|{'-'*18}|{'-'*17}|{'-'*18}|{'-'*17}|{'-'*37}|{'-'*10}|")
    for r in results:
        print(f"| {r['file']:<30} | {r['before_fnds']:<16} | {r['after_fnds']:<15} | {r['compiles_before']:<16} | {r['compiles_after']:<15} | {r['windows_by_tier']:<35} | {r['seconds']:<8.2f} |")

if __name__ == "__main__":
    run_tests()
