# scripts/patch_rjm.py
with open('compiler/repair_job_manager.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = 'CACHE_FILE = os.path.join(CACHE_DIR, "window_cache.json")'

helper_code = '''CACHE_FILE = os.path.join(CACHE_DIR, "window_cache.json")


def _lightweight_check(code_str: str, language: str = "c", filename: str = "main.c") -> Tuple[bool, List[int], str]:
    """Lightweight check: runs compiler check (gcc -fsyntax-only) or syntax agent."""
    import re
    if language in ("c", "cpp", "c++"):
        try:
            c_comp = SandboxedCompiler()
            if c_comp.is_available():
                ok, out, _ = c_comp.compile_check(code_str)
                err_lines = [int(m) for m in re.findall(r":(\\d+):(?:\\d+:)? (?:fatal )?error:", out)]
                return ok, sorted(list(dict.fromkeys(err_lines))), out
        except Exception:
            pass
    from compiler.agents import SyntaxAgent, PythonSyntaxAgent
    agent = PythonSyntaxAgent() if language == "python" else SyntaxAgent()
    findings = agent.analyze(code_str, filename=filename)
    ok = len(findings) == 0
    errs = [f.location.line for f in findings if hasattr(f, "location") and f.location and f.location.line]
    return ok, sorted(list(dict.fromkeys(errs))), ""
'''

text = text.replace(target, helper_code, 1)
with open('compiler/repair_job_manager.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Patched successfully!")
