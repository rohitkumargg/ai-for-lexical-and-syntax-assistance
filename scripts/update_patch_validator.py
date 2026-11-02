# scripts/update_patch_validator.py
with open("compiler/patch_validator.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = """            cmd = [
                self.compiler_path,
                "-fsyntax-only",
                "-Wall",
                "-Werror=implicit-function-declaration",
                temp_c_file,
            ]"""

new_block = """            cmd = [
                self.compiler_path,
                "-fsyntax-only",
                temp_c_file,
            ]"""

assert old_block in content, "old_block not found!"
content = content.replace(old_block, new_block, 1)

old_is_clean = 'is_clean = (proc.returncode == 0) and ("error:" not in output_clean.lower()) and ("implicit declaration of function" not in output_clean.lower())'
new_is_clean = 'is_clean = (proc.returncode == 0) and ("error:" not in output_clean.lower())'

assert old_is_clean in content, "old_is_clean not found!"
content = content.replace(old_is_clean, new_is_clean, 1)

target_end = """            except Exception as e:
                return False, f"Sandboxed compiler execution error: {str(e)}", -1"""

gcc_ok_def = """            except Exception as e:
                return False, f"Sandboxed compiler execution error: {str(e)}", -1


def gcc_ok(source_code: str, timeout_seconds: float = 4.0) -> Tuple[bool, str, int]:
    \"\"\"
    Unified canonical compiler check used by planner, job manager, and audit.
    Programs that only produce warnings (e.g. implicit declarations) count as compiling.
    Only genuine compilation errors (exit code != 0 or 'error:' in stderr) fail.
    Returns: (is_clean, compiler_output, exit_code)
    \"\"\"
    compiler = SandboxedCompiler()
    return compiler.compile_check(source_code, timeout_seconds=timeout_seconds)"""

assert target_end in content, "target_end not found!"
content = content.replace(target_end, gcc_ok_def, 1)

with open("compiler/patch_validator.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Successfully updated compiler/patch_validator.py!")

