"""Program Execution Engine for Antigravity Compiler IDE.

Compiles and executes user C (and Python) programs in an isolated,
resource-limited sandbox environment with stdin support, strict timeouts,
output byte truncation, and pre-execution security verification.

Principles:
1. Sandboxed Isolation: Never executes directly inside web worker process.
   Always executes within isolated temporary directory with cleaned environment.
2. Safe Arguments: Strictly avoids shell=True and shell-injection risks.
3. Pre-execution Security: Verifies source code against PreExecutionSecurityGate
   and dangerous system-level functions (system, popen, exec, etc.).
4. Resource Limits: Enforces execution timeout, maximum output bytes, and process termination.
5. Honest Feedback: Distinguishes compilation failures, runtime errors, timeouts,
   and security blocks.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from compiler.job_sandbox import WindowsJobSandbox


class ExecutionStatus(str, Enum):
    READY = "Ready"
    COMPILING = "Compiling"
    RUNNING = "Running"
    COMPLETED = "Completed"
    COMPILATION_FAILED = "Compilation Failed"
    RUNTIME_ERROR = "Runtime Error"
    TIMED_OUT = "Timed Out"
    SECURITY_BLOCKED = "Security Blocked"
    ENV_UNAVAILABLE = "Environment Unavailable"


@dataclass
class ProgramExecutionResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    execution_time_ms: float = 0.0
    compilation_error: Optional[str] = None
    stdin_used: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        is_ref = (self.status == "Refused (Sandbox Unverified)" or bool(self.details.get("is_refused")))
        return {
            "success": self.status == ExecutionStatus.COMPLETED.value,
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms,
            "compilation_error": self.compilation_error,
            "stdin_used": self.stdin_used,
            "refused": is_ref,
            "is_refused": is_ref,
            "details": dict(self.details),
        }


class ProgramExecutor:
    """Executes C programs safely in an isolated sandbox with resource controls."""

    MAX_SOURCE_BYTES = 256 * 1024         # 256 KB max source code
    MAX_OUTPUT_BYTES = 64 * 1024          # 64 KB max stdout/stderr capture
    MAX_MEMORY_BYTES = 128 * 1024 * 1024  # 128 MB RAM limit
    DEFAULT_TIMEOUT_SEC = 4.0             # 4.0s execution timeout
    MAX_TIMEOUT_SEC = 10.0                # 10.0s max permitted timeout
    COMPILER_TIMEOUT_SEC = 6.0           # 6.0s compilation timeout

    # Dangerous functions that must not be executed
    DANGEROUS_CALLS = {
        "system",
        "popen",
        "execl",
        "execle",
        "execlp",
        "execv",
        "execve",
        "execvp",
        "fork",
        "WinExec",
        "ShellExecute",
        "CreateProcess",
    }

    def __init__(self, compiler_path: Optional[str] = None):
        self.compiler_path = compiler_path or self._discover_compiler()

    @staticmethod
    def _discover_compiler() -> Optional[str]:
        """Locate native GCC or Clang executable."""
        # 1. Search PATH
        gcc = shutil.which("gcc")
        if gcc:
            return gcc
        clang = shutil.which("clang")
        if clang:
            return clang

        # 2. Known Windows paths (MinGW / MSYS2 / LLVM)
        candidates = [
            r"C:\MinGW\bin\gcc.exe",
            r"C:\Program Files\mingw-w64\bin\gcc.exe",
            r"C:\msys64\ucrt64\bin\gcc.exe",
            r"C:\msys64\mingw64\bin\gcc.exe",
            r"C:\LLVM\bin\clang.exe",
            r"C:\Program Files\LLVM\bin\clang.exe",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    def is_compiler_available(self) -> bool:
        return self.compiler_path is not None and os.path.exists(self.compiler_path)

    def _check_pre_execution_security(
        self, source_code: str, filename: str = "main.c", language: str = "c"
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Screen submission using PreExecutionSecurityGate and dangerous function inspection.
        Returns: (is_safe, error_message, details_dict)
        """
        # 1. Size check
        if len(source_code.encode("utf-8")) > self.MAX_SOURCE_BYTES:
            return (
                False,
                f"Source code exceeds maximum permitted size of {self.MAX_SOURCE_BYTES // 1024} KB.",
                {"reason": "PAYLOAD_TOO_LARGE"},
            )

        # 2. PreExecutionSecurityGate check
        try:
            from compiler.security_gate import PreExecutionSecurityGate
            verdict = PreExecutionSecurityGate.check_submission(
                source_code, filename=filename, language=language, action="run_program"
            )
            if verdict.is_blocked:
                return (
                    False,
                    f"Security Gate blocked execution: {verdict.message} ({verdict.reason_code})",
                    verdict.to_dict(),
                )
        except Exception:
            pass

        # 3. Malicious Code Precheck
        try:
            from compiler.malicious_precheck import MaliciousCodePrecheck
            precheck_rep = MaliciousCodePrecheck.analyze(source_code, filename=filename, language=language)
            if precheck_rep.blocks_execution:
                blocked_findings = [f for f in precheck_rep.findings if f.blocks_execution]
                first_f = blocked_findings[0] if blocked_findings else precheck_rep.findings[0]
                return (
                    False,
                    f"Execution blocked by Malicious Code Precheck: {first_f.explanation} (Rule: {first_f.rule_id}, Risk: {first_f.risk_level.value})",
                    precheck_rep.to_dict(),
                )
        except Exception:
            pass

        # 4. Dangerous OS/shell execution calls in C
        if language in ("c", "cpp"):
            from compiler.call_extractor import strip_c_comments_and_strings
            clean_code = strip_c_comments_and_strings(source_code)
            for func_name in self.DANGEROUS_CALLS:
                import re
                pattern = rf"\b{func_name}\s*\("
                if re.search(pattern, clean_code):
                    return (
                        False,
                        f"Execution blocked: Program contains unauthorized system/shell invocation '{func_name}()'.",
                        {"dangerous_call": func_name},
                    )

        return True, None, None

    def execute_c(
        self,
        source_code: str,
        stdin_input: str = "",
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        filename: str = "main.c",
        approval_token: Optional[str] = None,
        gate_already_verified: bool = False,
    ) -> ProgramExecutionResult:
        """
        Compile and execute a C program safely in a temporary sandbox.
        Enforces mandatory Security Decision Gate and User Approval.
        """
        timeout_sec = max(0.5, min(float(timeout_sec), self.MAX_TIMEOUT_SEC))

        # Phase 1: Security Decision Gate & Prechecks
        if not gate_already_verified:
            from compiler.security_approval_gate import SecurityDecisionGate
            permitted, gate_verdict = SecurityDecisionGate.evaluate_and_verify(
                source_code=source_code,
                filename=filename,
                language="c",
                operation="execute",
                approval_token=approval_token,
            )
            if not permitted:
                sec_err = gate_verdict.summary
                if gate_verdict.policy_reason and gate_verdict.policy_reason != gate_verdict.summary:
                    sec_err = f"{gate_verdict.summary}\n{gate_verdict.policy_reason}"
                return ProgramExecutionResult(
                    status=ExecutionStatus.SECURITY_BLOCKED.value,
                    stdout="",
                    stderr=sec_err,
                    exit_code=None,
                    execution_time_ms=0.0,
                    compilation_error=None,
                    stdin_used=bool(stdin_input),
                    details=gate_verdict.to_dict(),
                )

        # Phase 2.5: Sandbox Backend Verification & Interim Guard
        from compiler.sandbox.interim_guard import evaluate_interim_guard
        guard_verdict = evaluate_interim_guard(source_code, filename=filename, language="c")
        if guard_verdict.is_refused:
            return ProgramExecutionResult(
                status="Refused (Sandbox Unverified)",
                stdout="",
                stderr=(
                    f"[SANDBOX REFUSAL] Program compilation and execution refused on host machine.\n\n"
                    f"Reason: {guard_verdict.reason}\n\n"
                    f"Policy: Until an isolated container sandbox (Docker Desktop with WSL2) is verified, "
                    f"the compiler fails closed and strictly refuses to execute risky code on the host.\n"
                    f"No host fallback is permitted."
                ),
                exit_code=None,
                execution_time_ms=0.0,
                compilation_error="",
                stdin_used=bool(stdin_input),
                details={
                    "is_refused": True,
                    "refusal_reason": guard_verdict.reason,
                    "risk_factors": guard_verdict.risk_factors,
                    "highest_severity": guard_verdict.highest_severity,
                },
            )

        # Phase 2: Compiler Availability Check
        if not self.is_compiler_available():
            return ProgramExecutionResult(
                status=ExecutionStatus.ENV_UNAVAILABLE.value,
                stdout="",
                stderr="Native C compiler (GCC/Clang) is not available on this host environment.",
                exit_code=None,
                execution_time_ms=0.0,
                compilation_error="No native C compiler detected.",
                stdin_used=bool(stdin_input),
            )

        # Phase 3: Sandboxed Compilation & Execution in temporary directory
        with tempfile.TemporaryDirectory(prefix="antigravity_exec_", ignore_cleanup_errors=True) as sandbox_dir:
            src_file = os.path.join(sandbox_dir, "program.c")
            exe_ext = ".exe" if os.name == "nt" else ""
            exe_file = os.path.join(sandbox_dir, f"program{exe_ext}")

            try:
                with open(src_file, "w", encoding="utf-8") as f:
                    f.write(source_code)
            except Exception as e:
                return ProgramExecutionResult(
                    status=ExecutionStatus.COMPILATION_FAILED.value,
                    stdout="",
                    stderr=f"Failed to prepare source file: {str(e)}",
                    exit_code=-1,
                )

            # Strip host environment of secrets, API keys, credentials
            compiler_dir = os.path.dirname(self.compiler_path) if self.compiler_path else ""
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            safe_path = compiler_dir
            if os.name == "nt":
                safe_path = (
                    f"{compiler_dir}{os.pathsep}"
                    f"{os.path.join(system_root, 'System32')}{os.pathsep}"
                    f"{system_root}"
                )
            else:
                safe_path = "/usr/bin:/bin:/usr/local/bin"

            safe_env = {
                "PATH": safe_path,
                "SystemRoot": system_root,
                "TMP": sandbox_dir,
                "TEMP": sandbox_dir,
            }

            compile_cmd = [
                self.compiler_path,
                "-O0",
                "-Wall",
                "-Werror=implicit-function-declaration",
                src_file,
                "-o",
                exe_file,
            ]

            # Run Compiler
            try:
                comp_proc = subprocess.run(
                    compile_cmd,
                    cwd=sandbox_dir,
                    env=safe_env,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=self.COMPILER_TIMEOUT_SEC,
                )
            except subprocess.TimeoutExpired:
                return ProgramExecutionResult(
                    status=ExecutionStatus.COMPILATION_FAILED.value,
                    stdout="",
                    stderr=f"Compilation timed out after {self.COMPILER_TIMEOUT_SEC}s.",
                    exit_code=-1,
                    compilation_error="Compilation timed out.",
                )
            except Exception as e:
                return ProgramExecutionResult(
                    status=ExecutionStatus.COMPILATION_FAILED.value,
                    stdout="",
                    stderr=f"Compilation failed to start: {str(e)}",
                    exit_code=-1,
                    compilation_error=str(e),
                )

            if comp_proc.returncode != 0:
                raw_err = comp_proc.stderr or comp_proc.stdout or "Compilation failed."
                # Redact temp dir path for clean display
                clean_err = raw_err.replace(sandbox_dir + os.sep, "").replace(sandbox_dir, "")
                return ProgramExecutionResult(
                    status=ExecutionStatus.COMPILATION_FAILED.value,
                    stdout="",
                    stderr=clean_err.strip(),
                    exit_code=comp_proc.returncode,
                    compilation_error=clean_err.strip(),
                )

            # Phase 4: Execute Compiled Binary in Isolated Subprocess
            if not os.path.isfile(exe_file):
                return ProgramExecutionResult(
                    status=ExecutionStatus.COMPILATION_FAILED.value,
                    stdout="",
                    stderr="Compilation succeeded but binary executable was not created.",
                    exit_code=-1,
                    compilation_error="Binary executable missing.",
                )

            run_cmd = [exe_file]
            start_time = time.perf_counter()

            # On Windows, suppress crash dialog boxes (WER) so segfaults exit immediately
            creationflags = 0
            if os.name == "nt":
                try:
                    import ctypes
                    # SEM_FAILCRITICALERRORS (0x0001) | SEM_NOGPFAULTERRORBOX (0x0002)
                    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
                except Exception:
                    pass
                creationflags = 0x08000000  # CREATE_NO_WINDOW

            try:
                with WindowsJobSandbox(memory_limit_bytes=self.MAX_MEMORY_BYTES) as job:
                    proc = subprocess.Popen(
                        run_cmd,
                        cwd=sandbox_dir,
                        env=safe_env,
                        shell=False,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        creationflags=creationflags,
                    )
                    job.assign_process(proc)

                    try:
                        stdout_raw, stderr_raw = proc.communicate(
                            input=stdin_input if stdin_input else None,
                            timeout=timeout_sec,
                        )
                    except subprocess.TimeoutExpired:
                        # Terminate/kill timed out process
                        try:
                            proc.kill()
                            if os.name == "nt":
                                # Terminate any spawned child processes on Windows
                                subprocess.run(
                                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                    capture_output=True,
                                    timeout=2.0,
                                )
                        except Exception:
                            pass

                        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                        return ProgramExecutionResult(
                            status=ExecutionStatus.TIMED_OUT.value,
                            stdout="",
                            stderr=f"Execution timed out: Program exceeded time limit of {timeout_sec:.1f}s and was terminated.",
                            exit_code=None,
                            execution_time_ms=elapsed_ms,
                            stdin_used=bool(stdin_input),
                        )

                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                stdout_str = (stdout_raw or "").strip()
                stderr_str = (stderr_raw or "").strip()

                # Clean up sandbox paths from runtime stderr if any
                stderr_str = stderr_str.replace(sandbox_dir + os.sep, "").replace(sandbox_dir, "")

                # Truncate excessive outputs safely to prevent browser / memory lockup
                if len(stdout_str) > self.MAX_OUTPUT_BYTES:
                    stdout_str = (
                        stdout_str[: self.MAX_OUTPUT_BYTES]
                        + f"\n\n[Stdout truncated: exceeded maximum {self.MAX_OUTPUT_BYTES // 1024} KB limit]"
                    )
                if len(stderr_str) > self.MAX_OUTPUT_BYTES:
                    stderr_str = (
                        stderr_str[: self.MAX_OUTPUT_BYTES]
                        + f"\n\n[Stderr truncated: exceeded maximum {self.MAX_OUTPUT_BYTES // 1024} KB limit]"
                    )

                status = (
                    ExecutionStatus.COMPLETED.value
                    if proc.returncode == 0
                    else ExecutionStatus.RUNTIME_ERROR.value
                )

                return ProgramExecutionResult(
                    status=status,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    exit_code=proc.returncode,
                    execution_time_ms=elapsed_ms,
                    stdin_used=bool(stdin_input),
                )

            except Exception as e:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                return ProgramExecutionResult(
                    status=ExecutionStatus.RUNTIME_ERROR.value,
                    stdout="",
                    stderr=f"Execution exception: {str(e)}",
                    exit_code=-1,
                    execution_time_ms=elapsed_ms,
                    stdin_used=bool(stdin_input),
                )

    def execute_python(
        self,
        source_code: str,
        stdin_input: str = "",
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        filename: str = "main.py",
        approval_token: Optional[str] = None,
        gate_already_verified: bool = False,
    ) -> ProgramExecutionResult:
        """Execute a Python program safely in an isolated sandbox with resource controls."""
        timeout_sec = max(0.5, min(float(timeout_sec), self.MAX_TIMEOUT_SEC))

        if not gate_already_verified:
            from compiler.security_approval_gate import SecurityDecisionGate

            permitted, gate_verdict = SecurityDecisionGate.evaluate_and_verify(
                source_code=source_code,
                filename=filename,
                language="python",
                operation="execute",
                approval_token=approval_token,
            )
            if not permitted:
                sec_err = gate_verdict.summary
                if gate_verdict.policy_reason and gate_verdict.policy_reason != gate_verdict.summary:
                    sec_err = f"{gate_verdict.summary}\n{gate_verdict.policy_reason}"
                return ProgramExecutionResult(
                    status=ExecutionStatus.SECURITY_BLOCKED.value,
                    stdout="",
                    stderr=sec_err,
                    exit_code=None,
                    execution_time_ms=0.0,
                    stdin_used=bool(stdin_input),
                    details=gate_verdict.to_dict(),
                )

        # Check syntax ahead of time for fast, accurate error reporting
        try:
            compile(source_code, filename, "exec")
        except SyntaxError as se:
            err_line_info = f'File "{filename}", line {se.lineno}'
            clean_err = f"{err_line_info}\n    {(se.text or '').strip()}\nSyntaxError: {se.msg}"
            return ProgramExecutionResult(
                status=ExecutionStatus.COMPILATION_FAILED.value,
                stdout="",
                stderr=clean_err,
                exit_code=1,
                execution_time_ms=0.0,
                compilation_error=clean_err,
                stdin_used=bool(stdin_input),
            )

        # Phase 2.5: Sandbox Backend Verification & Interim Guard
        from compiler.sandbox.interim_guard import evaluate_interim_guard
        guard_verdict = evaluate_interim_guard(source_code, filename=filename, language="python")
        if guard_verdict.is_refused:
            return ProgramExecutionResult(
                status="Refused (Sandbox Unverified)",
                stdout="",
                stderr=(
                    f"[SANDBOX REFUSAL] Program compilation and execution refused on host machine.\n\n"
                    f"Reason: {guard_verdict.reason}\n\n"
                    f"Policy: Until an isolated container sandbox (Docker Desktop with WSL2) is verified, "
                    f"the compiler fails closed and strictly refuses to execute risky code on the host.\n"
                    f"No host fallback is permitted."
                ),
                exit_code=None,
                execution_time_ms=0.0,
                compilation_error="",
                stdin_used=bool(stdin_input),
                details={
                    "is_refused": True,
                    "refusal_reason": guard_verdict.reason,
                    "risk_factors": guard_verdict.risk_factors,
                    "highest_severity": guard_verdict.highest_severity,
                },
            )

        with tempfile.TemporaryDirectory(prefix="antigravity_pyexec_", ignore_cleanup_errors=True) as sandbox_dir:
            src_file = os.path.join(sandbox_dir, "script.py")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write(source_code)

            safe_env = {
                "PATH": os.environ.get("PATH", ""),
                "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
                "PYTHONUNBUFFERED": "1",
                "TMP": sandbox_dir,
                "TEMP": sandbox_dir,
            }

            cmd = [sys.executable, "-u", "-B", src_file]
            start_time = time.perf_counter()

            try:
                with WindowsJobSandbox(memory_limit_bytes=self.MAX_MEMORY_BYTES) as job:
                    proc = subprocess.Popen(
                        cmd,
                        cwd=sandbox_dir,
                        env=safe_env,
                        shell=False,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    job.assign_process(proc)

                    try:
                        stdout_raw, stderr_raw = proc.communicate(
                            input=stdin_input if stdin_input else None,
                            timeout=timeout_sec,
                        )
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                        return ProgramExecutionResult(
                            status=ExecutionStatus.TIMED_OUT.value,
                            stdout="",
                            stderr=f"Execution timed out after {timeout_sec:.1f}s.",
                            exit_code=None,
                            execution_time_ms=elapsed_ms,
                            stdin_used=bool(stdin_input),
                        )

                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                stdout_str = (stdout_raw or "").strip()
                stderr_str = (stderr_raw or "").strip()

                if len(stdout_str) > self.MAX_OUTPUT_BYTES:
                    stdout_str = stdout_str[: self.MAX_OUTPUT_BYTES] + "\n[Stdout truncated]"
                if len(stderr_str) > self.MAX_OUTPUT_BYTES:
                    stderr_str = stderr_str[: self.MAX_OUTPUT_BYTES] + "\n[Stderr truncated]"

                status = (
                    ExecutionStatus.COMPLETED.value
                    if proc.returncode == 0
                    else ExecutionStatus.RUNTIME_ERROR.value
                )

                return ProgramExecutionResult(
                    status=status,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    exit_code=proc.returncode,
                    execution_time_ms=elapsed_ms,
                    stdin_used=bool(stdin_input),
                )
            except Exception as e:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                return ProgramExecutionResult(
                    status=ExecutionStatus.RUNTIME_ERROR.value,
                    stdout="",
                    stderr=f"Execution error: {str(e)}",
                    exit_code=-1,
                    execution_time_ms=elapsed_ms,
                )

    def execute_program(
        self,
        source_code: str,
        language: str = "c",
        stdin_input: str = "",
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        filename: str = "main.c",
        approval_token: Optional[str] = None,
        gate_already_verified: bool = False,
    ) -> ProgramExecutionResult:
        """Route execution to language-specific executor."""
        lang_norm = (language or "c").strip().lower()
        if lang_norm in ("python", "py"):
            return self.execute_python(
                source_code=source_code,
                stdin_input=stdin_input,
                timeout_sec=timeout_sec,
                filename=filename or "main.py",
                approval_token=approval_token,
                gate_already_verified=gate_already_verified,
            )
        else:
            return self.execute_c(
                source_code=source_code,
                stdin_input=stdin_input,
                timeout_sec=timeout_sec,
                filename=filename or "main.c",
                approval_token=approval_token,
                gate_already_verified=gate_already_verified,
            )
