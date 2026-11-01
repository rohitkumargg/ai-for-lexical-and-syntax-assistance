# compiler/job_sandbox.py
"""Windows Job Object isolation sandbox for executing untrusted binaries and scripts with memory and process limits."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Optional, Tuple

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    JobObjectExtendedLimitInformation = 9
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x0200
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x0008
    JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x0400

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]


class WindowsJobSandbox:
    """Manages a Windows Job Object with strict resource limits for a sandboxed process."""

    def __init__(self, memory_limit_bytes: int = 128 * 1024 * 1024, max_processes: int = 1):
        self.memory_limit_bytes = memory_limit_bytes
        self.max_processes = max_processes
        self.h_job: Optional[Any] = None

    def __enter__(self) -> "WindowsJobSandbox":
        if os.name == "nt":
            self.h_job = ctypes.windll.kernel32.CreateJobObjectW(None, None)
            if self.h_job:
                info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                info.BasicLimitInformation.LimitFlags = (
                    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
                    JOB_OBJECT_LIMIT_JOB_MEMORY |
                    JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
                    JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
                )
                info.BasicLimitInformation.ActiveProcessLimit = self.max_processes
                info.JobMemoryLimit = self.memory_limit_bytes
                ctypes.windll.kernel32.SetInformationJobObject(
                    self.h_job,
                    JobObjectExtendedLimitInformation,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                )
        return self

    def assign_process(self, proc: subprocess.Popen) -> bool:
        """Assigns the spawned process to the job object."""
        if os.name == "nt" and self.h_job and hasattr(proc, "_handle"):
            try:
                ret = ctypes.windll.kernel32.AssignProcessToJobObject(self.h_job, int(proc._handle))
                return bool(ret)
            except Exception:
                return False
        return False

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.name == "nt" and self.h_job:
            try:
                ctypes.windll.kernel32.CloseHandle(self.h_job)
            except Exception:
                pass
            self.h_job = None

