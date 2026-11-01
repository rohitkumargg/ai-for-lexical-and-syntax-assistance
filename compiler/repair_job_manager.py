# compiler/repair_job_manager.py
"""
Background repair job management, tolerant function partitioning,
per-function independent repair, window caching, and automatic crash-recovery.
"""
from __future__ import annotations

import os
import sys
import time
import json
import uuid
import re
import hashlib
import threading
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor

from compiler.windowed_repair import get_window_for_finding, splice_window_into_source
from compiler.patch_validator import SandboxedCompiler, PatchIntegrityInspector, ensure_c_libc_headers
from compiler.finding import Finding, FindingCategory, FindingSeverity, FindingStatus, SourceLocation
from compiler.pipeline_logger import StageStatus

logger = logging.getLogger("RepairJobManager")

JOBS_DIR = os.path.join(os.getcwd(), "data", "repair_jobs")
CACHE_DIR = os.path.join(os.getcwd(), "data", "repair_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "window_cache.json")


# ---------------------------------------------------------------------------
# Requirement 2: Tolerant Function Splitting with Brace Matching
# ---------------------------------------------------------------------------

FN_HEADER_RE = re.compile(
    r'^[ \t]*(?:(?:static|inline|extern|const|viod|void|int|char|cahr|float|double|long|unsigned|short|bool|struct\s+\w+)\s+)+[* \t]*([a-zA-Z_]\w*)\s*\([^;]*?\)\s*\{?',
    re.MULTILINE
)


def split_top_level_functions(source_code: str, language: str = "c") -> Tuple[str, List[Dict[str, Any]]]:
    """
    Splits C/C++ source code into top-level functions using tolerant brace matching.
    Works reliably on broken code with mismatched braces or syntax defects.
    
    Returns:
        (preamble, functions_list)
        Each function dict contains:
            name: function identifier
            start_line: 1-indexed start line
            end_line: 1-indexed end line
            code: source text of the function
            trailing: blank lines / comments between this function and next
            index: 0-indexed position
    """
    if not source_code:
        return "", []

    lines = source_code.splitlines(keepends=True)
    total_lines = len(lines)
    if total_lines == 0:
        return "", []

    if language.lower() not in ("c", "cpp", "c++"):
        # For non-C code (e.g. Python), return whole file as single function
        return "", [{
            "name": "main_module",
            "start_line": 1,
            "end_line": total_lines,
            "code": source_code,
            "trailing": "",
            "index": 0
        }]

    fn_starts: List[Tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = FN_HEADER_RE.match(line)
        if m and not line.strip().endswith(';'):
            fn_name = m.group(1)
            if fn_name not in ('if', 'for', 'while', 'switch', 'catch'):
                fn_starts.append((i, fn_name))

    if not fn_starts:
        return "", [{
            "name": "whole_file",
            "start_line": 1,
            "end_line": total_lines,
            "code": source_code,
            "trailing": "",
            "index": 0
        }]

    first_fn_idx = fn_starts[0][0]
    global_preamble = "".join(lines[:first_fn_idx])

    functions: List[Dict[str, Any]] = []
    for k, (start_idx, fn_name) in enumerate(fn_starts):
        next_start_idx = fn_starts[k + 1][0] if k + 1 < len(fn_starts) else total_lines

        depth = 0
        end_idx = start_idx
        found_brace = False

        for curr in range(start_idx, next_start_idx):
            line = lines[curr]
            stripped = re.sub(r'//.*$', '', line)
            stripped = re.sub(r'".*?"', '""', stripped)
            stripped = re.sub(r"'.*?'", "''", stripped)

            o = stripped.count('{')
            c = stripped.count('}')
            if o > 0:
                found_brace = True
            depth += (o - c)

            if found_brace and depth <= 0:
                end_idx = curr
                break
        else:
            # Tolerant matching: depth never returned to 0 before next function start or EOF.
            # Close the function at next_start_idx - 1 so it doesn't swallow later functions.
            end_idx = max(start_idx, next_start_idx - 1)
            while end_idx > start_idx and not lines[end_idx].strip():
                end_idx -= 1

        fn_code = "".join(lines[start_idx : end_idx + 1])
        trailing = "".join(lines[end_idx + 1 : next_start_idx])

        functions.append({
            "name": fn_name,
            "start_line": start_idx + 1,
            "end_line": end_idx + 1,
            "code": fn_code,
            "trailing": trailing,
            "index": k,
        })

    return global_preamble, functions


def assemble_functions(preamble: str, functions: List[Dict[str, Any]]) -> str:
    """Assembles preamble and function chunks back into a unified source string."""
    return preamble + "".join(f["code"] + f.get("trailing", "") for f in functions)


# ---------------------------------------------------------------------------
# Requirement 5: Window Repair Cache (hash of window text + finding list)
# ---------------------------------------------------------------------------

class WindowRepairCache:
    """Persistent cache for successfully repaired windows by hash(window_text, finding_list)."""

    def __init__(self, cache_file: str = CACHE_FILE):
        self.cache_file = cache_file
        self._lock = threading.Lock()
        self._cache: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if os.path.isfile(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load window cache: {e}")
                self._cache = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            tmp = f"{self.cache_file}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._cache, f)
            os.replace(tmp, self.cache_file)
        except Exception as e:
            logger.warning(f"Could not save window cache: {e}")

    @staticmethod
    def _make_key(window_text: str, finding_sigs: List[str]) -> str:
        norm_txt = "\n".join(l.strip() for l in window_text.splitlines() if l.strip())
        sorted_sigs = ",".join(sorted(finding_sigs))
        payload = f"{norm_txt}:::{sorted_sigs}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, window_text: str, finding_sigs: List[str]) -> Optional[str]:
        with self._lock:
            key = self._make_key(window_text, finding_sigs)
            return self._cache.get(key)

    def set(self, window_text: str, finding_sigs: List[str], repaired_window: str) -> None:
        with self._lock:
            key = self._make_key(window_text, finding_sigs)
            self._cache[key] = repaired_window
            self._save()


_GLOBAL_WINDOW_CACHE = WindowRepairCache()


# ---------------------------------------------------------------------------
# Requirement 1 & 4: Repair Job Definition & Persistence
# ---------------------------------------------------------------------------

JOB_ID_REGEX = re.compile(r'^[a-f0-9]{32}$')


def is_valid_job_id(job_id: Any) -> bool:
    if not isinstance(job_id, str):
        return False
    return bool(JOB_ID_REGEX.fullmatch(job_id))


@dataclass
class RepairJob:
    job_id: str
    state: str                          # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    stage: str
    function_index: int
    function_total: int
    elapsed_s: float
    estimated_total_s: float
    windows_done: int
    skipped_windows: List[Dict[str, Any]] = field(default_factory=list)
    windows_by_tier: Dict[str, int] = field(default_factory=lambda: {"rules": 0, "codet5": 0, "qwen": 0})
    current_code: str = ""
    original_code: str = ""
    filename: str = "main.c"
    language: str = "c"
    operation: str = "repair"
    approval_token: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    start_time: float = field(default_factory=time.perf_counter)
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    speedup: Optional[float] = None

    def to_status_dict(self) -> Dict[str, Any]:
        """Returns the public status payload expected by GET /api/repair/job/<id>."""
        return {
            "job_id": self.job_id,
            "state": self.state,
            "stage": self.stage,
            "function_index": self.function_index,
            "function_total": self.function_total,
            "elapsed_s": round(self.elapsed_s, 2),
            "estimated_total_s": round(self.estimated_total_s, 2),
            "windows_done": self.windows_done,
            "windows_by_tier": self.windows_by_tier,
            "skipped_windows": self.skipped_windows,
            "speedup": self.speedup,
            "error": self.error_message,
            "result": self.result,
        }

    def to_persist_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "state": self.state,
            "stage": self.stage,
            "function_index": self.function_index,
            "function_total": self.function_total,
            "elapsed_s": self.elapsed_s,
            "estimated_total_s": self.estimated_total_s,
            "windows_done": self.windows_done,
            "windows_by_tier": self.windows_by_tier,
            "skipped_windows": self.skipped_windows,
            "current_code": self.current_code,
            "original_code": self.original_code,
            "filename": self.filename,
            "language": self.language,
            "operation": self.operation,
            # Requirement 2: Do NOT persist approval tokens in job files on disk
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error_message": self.error_message,
            "result": self.result,
            "speedup": self.speedup,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RepairJob:
        return cls(
            job_id=data["job_id"],
            state=data.get("state", "PENDING"),
            stage=data.get("stage", "Pending"),
            function_index=data.get("function_index", 0),
            function_total=data.get("function_total", 0),
            elapsed_s=data.get("elapsed_s", 0.0),
            estimated_total_s=data.get("estimated_total_s", 0.0),
            windows_done=data.get("windows_done", 0),
            windows_by_tier=data.get("windows_by_tier", {"rules": 0, "codet5": 0, "qwen": 0}),
            skipped_windows=data.get("skipped_windows", []),
            current_code=data.get("current_code", ""),
            original_code=data.get("original_code", ""),
            filename=data.get("filename", "main.c"),
            language=data.get("language", "c"),
            operation=data.get("operation", "repair"),
            approval_token=None,  # Never restored from disk (Requirement 2)
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            start_time=time.perf_counter() - data.get("elapsed_s", 0.0),
            error_message=data.get("error_message"),
            result=data.get("result"),
            speedup=data.get("speedup"),
        )


def _fix_unambiguous_syntax_delimiters(src: str) -> Tuple[str, List[str]]:
    fixes = []
    lines = src.splitlines(keepends=True)
    new_lines = []
    for i, line in enumerate(lines):
        l = line
        # Missing bracket in array dimension: int arr[5; -> int arr[5];
        l2 = re.sub(r'(\[\s*\d+)\s*;', r'\1];', l)
        if l2 != l:
            fixes.append("Closed array dimension with missing ']'")
            l = l2
        # Missing comma in parameter list: int a int b -> int a, int b
        l2 = re.sub(r'(\b(?:int|char|float|double|void|long|short)\s+[a-zA-Z_]\w*)\s+((?:int|char|float|double|long|short)\s+[a-zA-Z_]\w*)', r'\1, \2', l)
        if l2 != l:
            fixes.append("Inserted missing comma between parameter declarations")
            l = l2
        # Missing semicolon in for header: for (i = 0; i < 5 i = i + 1)
        l2 = re.sub(r'(for\s*\([^;]+;[^;]+?)(\s+[a-zA-Z_]\w*\s*=)', r'\1;\2', l)
        l2 = re.sub(r'(for\s*\([^;]+?)(\s+[a-zA-Z_]\w*\s*[<>=!])', r'\1;\2', l2)
        if l2 != l:
            fixes.append("Inserted missing semicolon in for-loop header")
            l = l2
        # Missing semicolon on lone break / continue
        l2 = re.sub(r'^\s*(break|continue)\s*$', r'\g<0>;', l)
        if l2 != l:
            fixes.append("Inserted missing semicolon after control keyword")
            l = l2
        # Missing ( after if/while/for
        if l.strip().startswith(('if ', 'while ', 'for ', 'switch ')) and l.count(')') > l.count('('):
            l2 = re.sub(r'(\b(?:if|while|for|switch)\s+)', r'\1(', l)
            if l2 != l:
                fixes.append("Inserted missing '(' after control statement")
                l = l2
        # Missing ) before { on if/while/for
        if l.strip().startswith(('if ', 'while ', 'for ', 'switch ')) and l.count('(') > l.count(')'):
            diff = l.count('(') - l.count(')')
            l2 = re.sub(r'\s*\{\s*$', ')' * diff + ' {\n', l)
            if l2 != l:
                fixes.append("Inserted missing ')' before statement block")
                l = l2
        # Missing ) before ; on function calls / expressions
        if not l.strip().startswith(('if', 'while', 'for', 'switch')) and l.count('(') > l.count(')') and l.rstrip().endswith(';'):
            diff = l.count('(') - l.count(')')
            l2 = re.sub(r';\s*$', ')' * diff + ';\n', l)
            if l2 != l:
                fixes.append("Inserted missing ')' before statement terminator")
                l = l2
        # Missing semicolon on statement before next statement/return
        if i + 1 < len(lines):
            next_l = lines[i+1].strip()
            if (next_l.startswith(('int ', 'char ', 'float ', 'double ', 'return', '}', 'if ', 'while ', 'for ')) and 
                not l.strip().endswith((';', '{', '}')) and l.strip() and not l.strip().startswith(('if', 'while', 'for', 'else', '#'))):
                l = l.rstrip('\r\n') + ';\n'
                fixes.append("Inserted missing semicolon at end of statement")
        new_lines.append(l)
    return "".join(new_lines), fixes


class RepairJobManager:
    """Singleton manager controlling job lifecycles, persistence, background execution, and cancellation."""

    def __init__(self, jobs_dir: str = JOBS_DIR):
        self.jobs_dir = jobs_dir
        os.makedirs(self.jobs_dir, exist_ok=True)
        self._jobs: Dict[str, RepairJob] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._load_persisted_jobs()

    def _load_persisted_jobs(self) -> None:
        try:
            for fname in os.listdir(self.jobs_dir):
                if fname.endswith(".json"):
                    path = os.path.join(self.jobs_dir, fname)
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        job = RepairJob.from_dict(data)
                        self._jobs[job.job_id] = job
                        self._cancel_events[job.job_id] = threading.Event()
        except Exception as e:
            logger.warning(f"Error loading persisted repair jobs: {e}")

    def save_job(self, job: RepairJob) -> None:
        """Persists job state to disk atomically."""
        if not is_valid_job_id(job.job_id):
            raise ValueError(f"Security: Invalid job_id format for filesystem persistence: {job.job_id}")
        try:
            job.updated_at = time.time()
            path = os.path.join(self.jobs_dir, f"{job.job_id}.json")
            # Extra safety check: canonical path must strictly reside within jobs_dir
            canonical = os.path.realpath(path)
            jobs_dir_real = os.path.realpath(self.jobs_dir)
            if not canonical.startswith(jobs_dir_real):
                raise ValueError(f"Security: Path traversal attempt blocked: {job.job_id}")
            os.makedirs(self.jobs_dir, exist_ok=True)
            tmp = f"{path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(job.to_persist_dict(), f)
            # Windows file locking retry loop
            replaced = False
            for attempt in range(6):
                try:
                    os.replace(tmp, path)
                    replaced = True
                    break
                except (PermissionError, OSError):
                    time.sleep(0.05 * (attempt + 1))
            if not replaced:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(job.to_persist_dict(), f)
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception as fallback_err:
                    logger.warning(f"save_job fallback write warning: {fallback_err}")
        except Exception as e:
            logger.error(f"Failed to persist repair job {job.job_id}: {e}")
            raise

    def create_job(
        self,
        code: str = "",
        filename: str = "main.c",
        language: str = "c",
        operation: str = "repair",
        approval_token: Optional[str] = None,
        job_id: Optional[str] = None,  # IGNORED: Server generates uuid4 hex only
        source_code: Optional[str] = None,
    ) -> RepairJob:
        if not code and source_code:
            code = source_code
        with self._lock:
            # Requirement 1: Ignore client-supplied job_id; generate server-side (uuid4 hex)
            jid = uuid.uuid4().hex

            # Requirement 7: estimated_total_s must have a value at job start (defects x per-tier average)
            initial_defects = 0
            if code:
                try:
                    from compiler.agents import SyntaxAgent
                    fnds = SyntaxAgent().analyze(code, filename=filename)
                    initial_defects = len(fnds)
                except Exception:
                    initial_defects = max(1, len(code.splitlines()) // 30)
            if initial_defects == 0 and code:
                initial_defects = max(1, len(code.splitlines()) // 40)
            # Weighted average per defect: deterministic rules (~0.15s), CodeT5 (~3s), Qwen (~8s) -> blended ~1.8s
            init_estimate = round(max(initial_defects, 1) * 1.8 + 4.0, 2)

            job = RepairJob(
                job_id=jid,
                state="PENDING",
                stage="Job initialized; preparing function partitioning...",
                function_index=0,
                function_total=0,
                elapsed_s=0.0,
                estimated_total_s=init_estimate,
                windows_done=0,
                windows_by_tier={"rules": 0, "codet5": 0, "qwen": 0},
                current_code=code,
                original_code=code,
                filename=filename,
                language=language,
                operation=operation,
                approval_token=approval_token,
            )
            self._jobs[jid] = job
            self._cancel_events[jid] = threading.Event()
            self.save_job(job)
            return job

    def get_job(self, job_id: str) -> Optional[RepairJob]:
        if not is_valid_job_id(job_id):
            return None
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        if not is_valid_job_id(job_id):
            return False
        with self._lock:
            job = self._jobs.get(job_id)
            evt = self._cancel_events.get(job_id)
            if not job:
                return False

            if evt:
                evt.set()

            # Stop Ollama requests & leave no orphan process
            try:
                from compiler.local_models import OllamaClient
                OllamaClient().unload_model()
            except Exception:
                pass

            job.state = "CANCELLED"
            job.stage = "Cancelled by user"
            job.error_message = "Repair job was cancelled."
            self.save_job(job)
            return True

    def delete_job(self, job_id: str) -> bool:
        """Requirement 2: Delete job files (and their cached code) on user request."""
        if not is_valid_job_id(job_id):
            raise ValueError(f"Security: Invalid job_id format: {job_id}")
        with self._lock:
            job = self._jobs.pop(job_id, None)
            self._cancel_events.pop(job_id, None)
            path = os.path.join(self.jobs_dir, f"{job_id}.json")
            canonical = os.path.realpath(path)
            jobs_dir_real = os.path.realpath(self.jobs_dir)
            if not canonical.startswith(jobs_dir_real):
                raise ValueError(f"Security: Path traversal attempt blocked: {job_id}")
            deleted = False
            if os.path.isfile(path):
                try:
                    os.remove(path)
                    deleted = True
                except Exception as e:
                    logger.error(f"Failed to delete job file {path}: {e}")
            return (job is not None) or deleted

    def cleanup_expired_jobs(self, max_age_s: float = 86400.0) -> int:
        """Requirement 2: Delete job files (and their cached code) after 24 h (86,400s)."""
        now = time.time()
        deleted = 0
        with self._lock:
            expired_ids = [
                jid for jid, job in self._jobs.items()
                if (now - getattr(job, "updated_at", job.created_at)) > max_age_s
            ]
            for jid in expired_ids:
                try:
                    self.delete_job(jid)
                    deleted += 1
                except Exception:
                    pass
            if os.path.isdir(self.jobs_dir):
                for fname in os.listdir(self.jobs_dir):
                    if fname.endswith(".json"):
                        jid = fname[:-5]
                        if is_valid_job_id(jid):
                            fpath = os.path.join(self.jobs_dir, fname)
                            try:
                                if (now - os.path.getmtime(fpath)) > max_age_s:
                                    os.remove(fpath)
                                    deleted += 1
                            except Exception:
                                pass
        return deleted

    def start_job(self, job: RepairJob) -> None:
        """Launches the job in a background daemon thread."""
        thread = threading.Thread(
            target=self._execute_repair_job,
            args=(job,),
            name=f"RepairJobThread_{job.job_id}",
            daemon=True
        )
        thread.start()

    def resume_unfinished_jobs(self) -> int:
        """
        Requirement 2 & 4: Resume unfinished jobs on server startup.
        Resume MUST re-check the security gate for the stored source code.
        """
        resumed = 0
        # Clean up expired jobs first
        self.cleanup_expired_jobs()
        from compiler.security_approval_gate import enforce_security_gate_for_request
        with self._lock:
            for job in list(self._jobs.values()):
                if job.state in ("PENDING", "RUNNING"):
                    # Security gate re-check on resume: approval_token is None because tokens are not persisted
                    permitted, warning_payload, gate_status = enforce_security_gate_for_request(
                        source_code=job.original_code,
                        filename=job.filename,
                        language=job.language,
                        operation="repair",
                        approval_token=None,  # No token persisted
                    )
                    if not permitted:
                        err_msg = warning_payload.get("error", "Security violation detected upon job resume.")
                        logger.warning(f"Job {job.job_id} resume blocked by security gate: {err_msg}")
                        job.state = "FAILED"
                        job.stage = f"Security gate check failed on resume: {err_msg}"
                        job.error_message = err_msg
                        self.save_job(job)
                        continue

                    logger.info(f"Resuming unfinished repair job: {job.job_id} at function {job.function_index}/{job.function_total}")
                    job.stage = f"Resumed on server restart: resuming from function {job.function_index}..."
                    self.start_job(job)
                    resumed += 1
        return resumed

    def _safe_save_job(self, job: RepairJob) -> None:
        try:
            self.save_job(job)
        except Exception as e:
            logger.warning(f"Could not persist intermediate job state: {e}")

    # -----------------------------------------------------------------------
    # Requirement 2 & 3: Per-Function Repair Pipeline & Limits
    # -----------------------------------------------------------------------

    def _execute_repair_job(self, job: RepairJob) -> None:
        from compiler.repair_planner import RepairPlanner, _get_finding_sig, _classify_program_status
        planner = RepairPlanner()
        cancel_evt = self._cancel_events.get(job.job_id, threading.Event())

        t_job_start = time.perf_counter() - job.elapsed_s
        job.state = "RUNNING"
        self._safe_save_job(job)

        # Requirement 3: Limits
        PER_WINDOW_CAP_S = float(os.environ.get("PER_WINDOW_TIMEOUT_S", 20.0))
        STALL_THRESHOLD = 3
        OVERALL_CEILING_S = float(os.environ.get("REPAIR_JOB_OVERALL_CEILING_S", 1800.0)) # 30 min default
        PARALLEL_WORKERS = int(os.environ.get("OLLAMA_NUM_PARALLEL", "1"))

        c_comp = SandboxedCompiler()

        def _lightweight_check(code_str: str) -> Tuple[bool, List[int], str]:
            if job.language == "c" and c_comp.is_available():
                ok, out, _ = c_comp.compile_check(code_str)
                err_lines = [int(m) for m in re.findall(r":(\d+):(?:\d+:)? (?:fatal )?error:", out)]
                return ok, sorted(list(dict.fromkeys(err_lines))), out
            else:
                from compiler.agents import SyntaxAgent, PythonSyntaxAgent
                agent = PythonSyntaxAgent() if job.language == "python" else SyntaxAgent()
                findings = agent.analyze(code_str, filename=job.filename)
                ok = len(findings) == 0
                errs = [f.location.line for f in findings if hasattr(f, "location") and f.location and f.location.line]
                return ok, sorted(list(dict.fromkeys(errs))), ""

        try:
            # 1. Tolerant Function Splitting
            preamble, functions = split_top_level_functions(job.original_code, language=job.language)
            job.function_total = len(functions)
            job.stage = f"Partitioned {len(functions)} top-level functions; starting independent repair pass..."
            self._safe_save_job(job)

            # Generate prototypes for context-aware single function testing
            clean_prototypes = []
            for fn in functions:
                lines = fn["code"].splitlines()
                if lines:
                    first_line = lines[0].strip()
                    fixed_header, _ = planner._apply_deterministic_rules(first_line, filename=job.filename, language=job.language)
                    first_line = fixed_header.strip()
                    if "{" in first_line:
                        first_line = first_line.split("{")[0].strip()
                    if not first_line.endswith(";"):
                        first_line += ";"
                    if re.match(r'^[ \t]*(?:void|int|char|float|double|long|unsigned|short|bool|struct\s+\w+)\b[a-zA-Z0-9_\s\*]+\([a-zA-Z0-9_,\s\*]*\)\s*;', first_line):
                        clean_prototypes.append(first_line)
            prototypes_str = "\n".join(clean_prototypes)
            fn_context_header = ensure_c_libc_headers(preamble + "\n" + prototypes_str) + "\n"
            if job.language == "c" and c_comp.is_available():
                h_ok, _, _ = c_comp.compile_check(fn_context_header)
                if not h_ok:
                    fn_context_header = ensure_c_libc_headers(preamble) + "\n"
            fn_ctx_offset = len(fn_context_header.splitlines())

            def _check_fn(fn_code_str: str) -> Tuple[bool, List[int], str]:
                if job.language == "c" and c_comp.is_available():
                    test_source = fn_context_header + fn_code_str
                    ok, out, _ = c_comp.compile_check(test_source)
                    all_errs = [int(m) for m in re.findall(r":(\d+):(?:\d+:)? (?:fatal )?error:", out)]
                    fn_lines_cnt = len(fn_code_str.splitlines())
                    fn_errs = [err - fn_ctx_offset for err in all_errs if 1 <= (err - fn_ctx_offset) <= fn_lines_cnt]
                    if not ok and not fn_errs:
                        from compiler.agents import SyntaxAgent
                        agent = SyntaxAgent()
                        findings = agent.analyze(fn_code_str, filename=job.filename)
                        fn_errs = [f.location.line for f in findings if hasattr(f, "location") and f.location and f.location.line]
                    is_ok = ok and (len(fn_errs) == 0)
                    return is_ok, sorted(list(dict.fromkeys(fn_errs))), out
                else:
                    return _lightweight_check(fn_code_str)

            # Start from resumed function_index if resuming from disk
            start_fn_idx = max(0, job.function_index - 1) if job.function_index > 0 else 0

            # Helper to repair a single function independently
            def _repair_single_function(fn_dict: Dict[str, Any]) -> Tuple[Dict[str, Any], int, List[Dict[str, Any]], Dict[str, int]]:
                fn_name = fn_dict["name"]
                fn_src = fn_dict["code"]
                fn_windows_done = 0
                fn_skipped_windows = []
                fn_tier_counts = {"rules": 0, "codet5": 0, "qwen": 0}

                # Context-aware lightweight check on function
                fn_ok, fn_err_lines, _ = _check_fn(fn_src)
                if fn_ok or len(fn_err_lines) == 0:
                    return fn_dict, 0, [], fn_tier_counts

                current_fn_code = fn_src
                consecutive_no_progress = 0
                current_err_count = len(fn_err_lines)

                # Tier 1: Deterministic rules on function
                det_fn, det_steps = planner._apply_deterministic_rules(
                    current_fn_code, filename=job.filename, language=job.language
                )
                if det_fn and det_fn.strip() != current_fn_code.strip():
                    fnd_list = [
                        Finding(
                            id=f"det_{fn_name}_{el}",
                            category=FindingCategory.SYNTAX,
                            location=SourceLocation(line=el, col=1, file_path=job.filename),
                            explanation=f"Deterministic repair for {fn_name} at line {el}",
                            evidence="",
                            severity=FindingSeverity.HIGH,
                            confidence=1.0,
                            status=FindingStatus.CONFIRMED,
                        )
                        for el in (fn_err_lines or [1])
                    ]
                    scope_ok, _ = PatchIntegrityInspector.inspect(current_fn_code, det_fn, original_findings=fnd_list, filename=job.filename)
                    if scope_ok:
                        d_ok, d_errs, _ = _check_fn(det_fn)
                        if d_ok or len(d_errs) < current_err_count:
                            current_fn_code = det_fn
                            current_err_count = len(d_errs)
                            steps_count = len(det_steps) if det_steps else 1
                            fn_windows_done += steps_count
                            fn_tier_counts["rules"] += steps_count

                if job.language == "c":
                    delim_fn, delim_steps = _fix_unambiguous_syntax_delimiters(current_fn_code)
                    if delim_fn and delim_fn.strip() != current_fn_code.strip():
                        s_ok, s_errs, _ = _check_fn(delim_fn)
                        if s_ok or len(s_errs) < current_err_count:
                            current_fn_code = delim_fn
                            current_err_count = len(s_errs)
                            steps_count = len(delim_steps) if delim_steps else 1
                            fn_windows_done += steps_count
                            fn_tier_counts["rules"] += steps_count

                # Windowed repair loop for remaining errors in this function
                f_ok, f_err_lines, _ = _check_fn(current_fn_code)
                attempted_err_lines: set[int] = set()

                while f_err_lines and not f_ok:
                    if cancel_evt.is_set():
                        break

                    # Overall ceiling check
                    if (time.perf_counter() - t_job_start) >= OVERALL_CEILING_S:
                        break

                    eligible = [el for el in f_err_lines if el not in attempted_err_lines]
                    if not eligible:
                        break

                    target_err_line = eligible[0]
                    win_src, win_start, win_end, win_rel = get_window_for_finding(
                        current_fn_code, target_err_line, radius=12, max_lines=35
                    )

                    t_win_start = time.perf_counter()
                    cand_win_text = None
                    cand_win_tier = "rules"
                    win_finding_sig = [f"syntax_error:line_{target_err_line}"]

                    # Requirement 5: Check Window Cache
                    cached_win = _GLOBAL_WINDOW_CACHE.get(win_src, win_finding_sig)
                    if cached_win:
                        cand_win_text = cached_win
                        cand_win_tier = "rules"
                    else:
                        dummy_f = Finding(
                            id=f"win_err_{target_err_line}",
                            category=FindingCategory.SYNTAX,
                            location=SourceLocation(line=win_rel, col=1, file_path=job.filename),
                            explanation=f"Syntax defect at relative line {win_rel}",
                            evidence="",
                            severity=FindingSeverity.HIGH,
                            confidence=1.0,
                            status=FindingStatus.CONFIRMED,
                        )

                        # Tier 2: CodeT5 (capped at 6 s)
                        if planner.codet5_enabled and planner.codet5.is_available() and job.language == "c":
                            try:
                                t_c5 = time.perf_counter()
                                raw_c5, _ = planner.codet5.generate_patch(
                                    source_text=win_src,
                                    reason="syntax_error",
                                    line=win_rel,
                                    col=0
                                )
                                if (time.perf_counter() - t_c5) <= 6.0 and raw_c5 and raw_c5.strip() != win_src.strip():
                                    s_ok, _ = PatchIntegrityInspector.inspect(win_src, raw_c5, original_findings=[dummy_f], filename=job.filename)
                                    if s_ok:
                                        cand_win_text = raw_c5
                                        cand_win_tier = "codet5"
                            except Exception:
                                pass

                        # Tier 3: Qwen Ollama (capped at PER_WINDOW_CAP_S, default 20 s)
                        if not cand_win_text and planner.ollama.is_available():
                            win_lines = win_src.splitlines()
                            rel_idx = win_rel - 1
                            ev_line = win_lines[rel_idx].strip() if 0 <= rel_idx < len(win_lines) else ""
                            dummy_f.evidence = ev_line

                            # Execute Qwen repair with per-window timeout
                            q_res = planner.ollama.generate_repair(
                                win_src, dummy_f, model_name=getattr(planner.ollama, "default_model", "qwen2.5-coder:3b"), language=job.language
                            )
                            q_raw = q_res[0] if isinstance(q_res, tuple) else q_res
                            win_elapsed = time.perf_counter() - t_win_start

                            # Requirement 3: Per-window cap (20 s) check
                            if win_elapsed > PER_WINDOW_CAP_S:
                                fn_skipped_windows.append({
                                    "function": fn_name,
                                    "target_line": target_err_line,
                                    "elapsed_s": round(win_elapsed, 2),
                                    "reason": f"window_timeout_exceeded_{PER_WINDOW_CAP_S}s"
                                })
                                attempted_err_lines.add(target_err_line)
                                consecutive_no_progress += 1
                                if consecutive_no_progress >= STALL_THRESHOLD:
                                    break
                                continue

                            if q_raw and isinstance(q_raw, str) and q_raw.strip() != win_src.strip():
                                if job.language == "c":
                                    q_raw = re.sub(r'\b([0-9]+)[uU]?[lL]{1,2}\b', r'(long long)\1', q_raw)
                                s_ok, _ = PatchIntegrityInspector.inspect(win_src, q_raw, original_findings=[dummy_f], filename=job.filename)
                                if s_ok:
                                    cand_win_text = q_raw
                                    cand_win_tier = "qwen"

                    if cand_win_text:
                        spliced = splice_window_into_source(current_fn_code, cand_win_text, win_start, win_end)
                        sp_ok, sp_errs, _ = _check_fn(spliced)
                        if sp_ok or (len(sp_errs) < current_err_count and all(e in f_err_lines for e in sp_errs)):
                            if sp_ok:
                                # Cache the accepted window (Requirement 5)
                                _GLOBAL_WINDOW_CACHE.set(win_src, win_finding_sig, cand_win_text)
                            current_fn_code = spliced
                            current_err_count = len(sp_errs)
                            f_err_lines = sp_errs
                            f_ok = sp_ok
                            fn_windows_done += 1
                            fn_tier_counts[cand_win_tier] = fn_tier_counts.get(cand_win_tier, 0) + 1
                            consecutive_no_progress = 0
                            attempted_err_lines.clear()
                            if sp_ok:
                                break
                            continue

                    attempted_err_lines.add(target_err_line)
                    consecutive_no_progress += 1
                    # Requirement 3: Stall rule (3 consecutive windows with no progress)
                    if consecutive_no_progress >= STALL_THRESHOLD:
                        break

                new_fn_dict = dict(fn_dict)
                new_fn_dict["code"] = current_fn_code
                return new_fn_dict, fn_windows_done, fn_skipped_windows, fn_tier_counts

            # Execute function repairs (sequential or optional parallel)
            repaired_functions = list(functions)
            total_fns = len(functions)

            t_seq_start = time.perf_counter()

            if PARALLEL_WORKERS > 1:
                # Requirement 6: OLLAMA_NUM_PARALLEL > 1
                logger.info(f"Executing parallel function repair with OLLAMA_NUM_PARALLEL={PARALLEL_WORKERS}")
                with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
                    futures = [executor.submit(_repair_single_function, fn) for fn in functions]
                    for idx, fut in enumerate(futures):
                        if cancel_evt.is_set():
                            break
                        res_fn, win_cnt, sk_wins, t_counts = fut.result()
                        repaired_functions[idx] = res_fn
                        job.windows_done += win_cnt
                        job.skipped_windows.extend(sk_wins)
                        for tk, tv in t_counts.items():
                            job.windows_by_tier[tk] = job.windows_by_tier.get(tk, 0) + tv
                        job.function_index = idx + 1
                        job.elapsed_s = time.perf_counter() - t_job_start
                        if job.function_index > 0:
                            job.estimated_total_s = round((job.elapsed_s / job.function_index) * total_fns, 2)
                        job.stage = f"Repaired function {idx + 1}/{total_fns} ({res_fn['name']}) [Parallel]"
                        self._safe_save_job(job)
                job.speedup = None  # Requirement 9: removed synthetic 1.8x claim
            else:
                for idx in range(start_fn_idx, total_fns):
                    if cancel_evt.is_set():
                        job.state = "CANCELLED"
                        job.stage = "Repair cancelled by user signal."
                        self._safe_save_job(job)
                        return

                    # Overall ceiling check (Requirement 3: default 30 min)
                    if (time.perf_counter() - t_job_start) >= OVERALL_CEILING_S:
                        job.stage = f"Overall time ceiling ({round(OVERALL_CEILING_S)}s) reached."
                        break

                    fn = repaired_functions[idx]
                    job.stage = f"Repairing function {idx + 1}/{total_fns} ({fn['name']})..."
                    res_fn, win_cnt, sk_wins, t_counts = _repair_single_function(fn)
                    repaired_functions[idx] = res_fn
                    job.windows_done += win_cnt
                    job.skipped_windows.extend(sk_wins)
                    for tk, tv in t_counts.items():
                        job.windows_by_tier[tk] = job.windows_by_tier.get(tk, 0) + tv
                    job.function_index = idx + 1
                    job.elapsed_s = time.perf_counter() - t_job_start
                    if job.function_index > 0:
                        job.estimated_total_s = round((job.elapsed_s / job.function_index) * total_fns, 2)
                    job.current_code = assemble_functions(preamble, repaired_functions)

                    # Requirement 4: Persist job state to disk after each function
                    self._safe_save_job(job)

            if cancel_evt.is_set():
                job.state = "CANCELLED"
                job.stage = "Repair cancelled by user signal."
                self._safe_save_job(job)
                return

            # ---------------------------------------------------------------
            # Requirement 2: Whole-File Lightweight Check & Splicing
            # ---------------------------------------------------------------
            job.stage = "Performing whole-file lightweight verification (parse + gcc -fsyntax-only)..."
            self._safe_save_job(job)

            whole_candidate = assemble_functions(preamble, repaired_functions)
            if job.language == "c":
                whole_candidate = ensure_c_libc_headers(whole_candidate, job.original_code)

            orig_ok, orig_errs, _ = _lightweight_check(job.original_code)
            w_ok, w_errs, _ = _lightweight_check(whole_candidate)

            final_adopted_code = whole_candidate

            if not w_ok:
                det_whole, _ = planner._apply_deterministic_rules(final_adopted_code, filename=job.filename, language=job.language)
                dw_ok, dw_errs, _ = _lightweight_check(det_whole)
                if dw_ok or len(dw_errs) <= len(w_errs):
                    final_adopted_code = det_whole
                    w_ok = dw_ok
                    w_errs = dw_errs

            # If whole-file check showed regression or new errors, fall back function by function
            if not w_ok and len(w_errs) > len(orig_errs):
                logger.info("Whole-file check detected regressions; executing function-by-function rollback fallback.")
                adopted_fns = list(functions) # original functions
                curr_assembled = job.original_code
                best_err_count = len(orig_errs)

                for k, rep_fn in enumerate(repaired_functions):
                    if rep_fn["code"] != functions[k]["code"]:
                        test_fns = list(adopted_fns)
                        test_fns[k] = rep_fn
                        test_code = assemble_functions(preamble, test_fns)
                        t_ok, t_errs, _ = _lightweight_check(test_code)
                        if t_ok or len(t_errs) <= best_err_count:
                            adopted_fns[k] = rep_fn
                            best_err_count = len(t_errs)
                            curr_assembled = test_code

                final_adopted_code = curr_assembled

            # ---------------------------------------------------------------
            # Final Analysis & Plan Packaging
            # ---------------------------------------------------------------
            job.stage = "Running final orchestrator & quality analysis..."
            self._safe_save_job(job)

            # Produce complete final response using standard RepairPlanner
            plan_res = planner.plan_and_repair(
                source_code=job.original_code,
                filename=job.filename,
                language=job.language,
                run_id=job.job_id,
                time_budget_s=15.0, # floor already prepared
                approval_token=job.approval_token,
                operation=job.operation,
                is_job_subtask=True,
            )

            # Update proposed candidate with the verified multi-function result
            if final_adopted_code.strip() != job.original_code.strip():
                final_ok, final_errs, _ = _lightweight_check(final_adopted_code)
                plan_res["proposed_code"] = final_adopted_code
                plan_res["candidate_code"] = final_adopted_code
                plan_res["diff"] = planner._generate_diff(job.original_code, final_adopted_code, job.filename) if hasattr(planner, "_generate_diff") else ""
                plan_res["compiles"] = final_ok
                remaining_findings = plan_res.get("security_findings", []) or plan_res.get("findings", [])
                try:
                    from agents.security_agent import SecurityAgent
                    sec_rep = SecurityAgent().analyze(final_adopted_code, filename=job.filename)
                    remaining_findings = sec_rep.get("findings", []) if isinstance(sec_rep, dict) else (getattr(sec_rep, "findings", []) or remaining_findings)
                except Exception:
                    pass
                stat, lbl, msg = _classify_program_status(final_adopted_code, remaining_findings, lang_id=job.language)
                if stat == "CLEAN" and job.windows_done > 0:
                    stat = "FULLY_REPAIRED"
                plan_res["status"] = stat
                plan_res["workflow_state"] = stat
                plan_res["terminal_status"] = stat
                plan_res["windows_processed"] = job.windows_done
                plan_res["skipped_windows"] = job.skipped_windows
                if "candidate" in plan_res and isinstance(plan_res["candidate"], dict):
                    plan_res["candidate"]["proposed_code"] = final_adopted_code
                    plan_res["candidate"]["compiles"] = final_ok
                    plan_res["candidate"]["diff"] = plan_res["diff"]

            plan_res["can_continue_repair"] = False
            plan_res["round"] = 1
            plan_res["job_id"] = job.job_id
            plan_res["skipped_windows"] = job.skipped_windows
            plan_res["total_wall_time_s"] = round(time.perf_counter() - t_job_start, 2)
            plan_res["stopping_reason"] = "completed" if job.windows_done > 0 else "clean_or_unmodified"
            if not plan_res.get("proposed_code"):
                plan_res["proposed_code"] = final_adopted_code

            job.result = plan_res
            job.current_code = final_adopted_code
            job.state = "COMPLETED"
            job.stage = "Repair job completed successfully."
            job.elapsed_s = time.perf_counter() - t_job_start
            job.estimated_total_s = job.elapsed_s
            self._safe_save_job(job)
            logger.info(f"Repair job {job.job_id} completed in {round(job.elapsed_s, 2)}s with {job.windows_done} windows repaired.")

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Error executing repair job {job.job_id}: {e}\n{tb}")
            job.state = "FAILED"
            job.stage = f"Error: {str(e)}"
            job.error_message = str(e)
            job.elapsed_s = time.perf_counter() - t_job_start
            self.save_job(job)


# Global singleton instance
_GLOBAL_JOB_MANAGER: Optional[RepairJobManager] = None

def get_repair_job_manager() -> RepairJobManager:
    global _GLOBAL_JOB_MANAGER
    if _GLOBAL_JOB_MANAGER is None:
        _GLOBAL_JOB_MANAGER = RepairJobManager()
    return _GLOBAL_JOB_MANAGER
