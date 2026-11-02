# compiler/security_approval_gate.py
"""
Mandatory Security Approval Gate Before Compilation and Execution.

Implements the user-controlled workflow:
Source Code → Malicious Code Precheck → Lexical Analysis → Syntax Analysis
→ Semantic Analysis → Security Analysis → Security Decision Gate → User Approval → Compilation / Execution

Core Principles:
1. Compilation & execution cannot start until the security decision gate permits them.
2. The gate evaluates the latest analysis results for the exact source being compiled.
3. Prohibited threats (host destructive commands, credential exfiltration, prompt-injection
   gate bypass) can NEVER be overridden.
4. Reviewable security vulnerabilities require explicit, one-time, cryptographically bound
   user approval scoped to the exact source hash and operation.
5. Inconclusive or skipped assessments fail closed.
6. Comments and string literals are distinguished from executable code.
7. Decisions are logged in the existing audit log without exposing sensitive secrets.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple

from compiler.call_extractor import strip_c_comments_and_strings
from compiler.security_gate import (
    PreExecutionSecurityGate,
    SecurityGateVerdict,
    SecurityThreatCategory,
    GateReasonCode,
)
from compiler.repair_logger import RepairLogger, RepairLogEvent, _utc_now_iso


# ──────────────────────────────────────────────────────────────────────────────
# C system functions that must not execute without security review
# ──────────────────────────────────────────────────────────────────────────────
DANGEROUS_SYSTEM_CALLS = {
    "system": ("Executes arbitrary OS shell command", "CWE-78"),
    "popen": ("Opens a bidirectional process pipe to system shell", "CWE-78"),
    "gets": ("Reads unbounded input from stdin into buffer", "CWE-120"),
    "strcpy": ("Unbounded string copy into destination buffer", "CWE-120"),
    "strcat": ("Unbounded string concatenation into destination buffer", "CWE-120"),
    "sprintf": ("Unbounded formatted string write into destination buffer", "CWE-134"),
    "execl": ("Replaces process image with arbitrary executable", "CWE-78"),
    "execle": ("Replaces process image with arbitrary executable and environment", "CWE-78"),
    "execlp": ("Replaces process image searching PATH", "CWE-78"),
    "execv": ("Executes process image with argument vector", "CWE-78"),
    "execve": ("Executes process image with environment vector", "CWE-78"),
    "execvp": ("Executes process image searching PATH", "CWE-78"),
    "fork": ("Forks host process table", "CWE-400"),
    "WinExec": ("Executes Windows application directly", "CWE-78"),
    "ShellExecute": ("Windows ShellExecute arbitrary command invocation", "CWE-78"),
    "CreateProcess": ("Windows CreateProcess native process instantiation", "CWE-78"),
}

# ──────────────────────────────────────────────────────────────────────────────
# Python dangerous functions that must not execute without security review
# ──────────────────────────────────────────────────────────────────────────────
DANGEROUS_PYTHON_CALLS: Dict[str, Tuple[str, str, str, List[str]]] = {
    # key: (description, cwe, severity, future_risks)
    "os.system": (
        "Executes arbitrary OS shell command via Python os.system()",
        "CWE-78",
        "HIGH",
        [
            "An attacker who controls the argument can execute arbitrary commands on the host OS",
            "Untrusted input allows attackers to chain and execute arbitrary shell commands",
            "Could lead to full system compromise, data exfiltration, or ransomware deployment",
            "os.system() returns only the exit code — stderr/stdout are not captured, hiding malicious output",
        ],
    ),
    "os.popen": (
        "Opens a pipe to an OS shell command via Python os.popen()",
        "CWE-78",
        "HIGH",
        [
            "Allows reading or writing to a shell command pipe — attacker can inject commands",
            "Deprecated since Python 3.0 in favor of subprocess module",
            "Output can be intercepted, enabling data exfiltration via shell redirection",
        ],
    ),
    "subprocess.call": (
        "Executes external process via subprocess.call() — waits for completion",
        "CWE-78",
        "HIGH",
        [
            "When shell=True, allows arbitrary command injection through string arguments",
            "Even with shell=False, untrusted arguments can cause path traversal or binary substitution",
            "Blocking call — can be used for denial-of-service by invoking long-running processes",
        ],
    ),
    "subprocess.run": (
        "Executes external process via subprocess.run()",
        "CWE-78",
        "HIGH",
        [
            "With shell=True and unsanitized input, enables full shell command injection",
            "capture_output=True can leak sensitive data from command output",
            "check=False (default) silently ignores process failures, masking attack indicators",
        ],
    ),
    "subprocess.Popen": (
        "Creates a new OS process via subprocess.Popen()",
        "CWE-78",
        "HIGH",
        [
            "Most powerful subprocess API — allows full control over stdin/stdout/stderr pipes",
            "shell=True with unsanitized input enables arbitrary command injection",
            "Dangling Popen objects can leak file descriptors and zombie processes",
            "Can be used to establish persistent reverse shells or C2 channels",
        ],
    ),
    "eval": (
        "Evaluates arbitrary Python expression from string via eval()",
        "CWE-95",
        "CRITICAL",
        [
            "eval() executes ANY Python expression — including __import__('os').system('rm -rf /')",
            "Cannot be safely sandboxed — even restricted builtins can be bypassed",
            "User input passed to eval() grants full code execution to an attacker",
            "Commonly exploited in web applications for Remote Code Execution (RCE)",
        ],
    ),
    "exec": (
        "Executes arbitrary Python code block from string via exec()",
        "CWE-95",
        "CRITICAL",
        [
            "exec() can run multi-line arbitrary Python code including imports and system calls",
            "Grants full access to the Python runtime — can modify variables, classes, and modules",
            "Cannot be sandboxed safely — even 'restricted' execution modes are bypassable",
            "If attacker controls input, this is equivalent to arbitrary code execution on the server",
        ],
    ),
    "compile": (
        "Compiles Python source into code object via compile() — often paired with exec()/eval()",
        "CWE-95",
        "HIGH",
        [
            "compile() creates executable code objects that can be passed to exec() or eval()",
            "Obfuscation vector — code can be built dynamically to evade static detection",
            "When combined with exec(), enables deferred arbitrary code execution",
        ],
    ),
    "pickle.loads": (
        "Deserializes Python object from untrusted bytes via pickle.loads()",
        "CWE-502",
        "CRITICAL",
        [
            "Pickle deserialization can execute arbitrary Python code during object reconstruction",
            "Attackers craft malicious pickled payloads that run __reduce__() hooks on load",
            "Common attack vector for Remote Code Execution in web APIs accepting pickled data",
            "Never unpickle data received from untrusted or unauthenticated sources",
        ],
    ),
    "pickle.load": (
        "Deserializes Python object from untrusted file/stream via pickle.load()",
        "CWE-502",
        "CRITICAL",
        [
            "Same risks as pickle.loads() — arbitrary code execution during deserialization",
            "Loading a pickle file from an untrusted source is equivalent to running arbitrary code",
            "Malicious pickle payloads are trivial to craft and widely documented",
        ],
    ),
    "__import__": (
        "Dynamic module import via __import__() — can load arbitrary modules at runtime",
        "CWE-95",
        "HIGH",
        [
            "Enables loading os, subprocess, or socket modules dynamically to bypass static checks",
            "Common obfuscation technique: __import__('os').system('malicious_cmd')",
            "Can be used inside eval() or exec() to hide dangerous imports from code review",
        ],
    ),
    "importlib.import_module": (
        "Dynamic module import via importlib — can load arbitrary modules at runtime",
        "CWE-95",
        "MEDIUM",
        [
            "Enables runtime loading of dangerous modules (os, subprocess, ctypes)",
            "Can circumvent static import analysis by constructing module names dynamically",
        ],
    ),
    "ctypes.CDLL": (
        "Loads native shared library via ctypes — enables calling arbitrary C functions",
        "CWE-426",
        "HIGH",
        [
            "Loading arbitrary .so/.dll files can execute native code outside Python sandbox",
            "Untrusted library paths can be exploited for DLL hijacking / preloading attacks",
            "Native code has no Python-level safety constraints — can corrupt memory, call system APIs",
        ],
    ),
    "shutil.rmtree": (
        "Recursively deletes entire directory tree via shutil.rmtree()",
        "CWE-73",
        "HIGH",
        [
            "If path is controlled by user input, attacker can delete arbitrary directories",
            "No confirmation prompt — deletion is immediate and typically irreversible",
            "Symlink attacks: a symlink placed inside the tree can redirect deletion to other filesystem locations",
        ],
    ),
}

# ──────────────────────────────────────────────────────────────────────────────
# Detailed future risk database for C dangerous functions
# ──────────────────────────────────────────────────────────────────────────────
PYTHON_RULE_DETAILS: Dict[str, Dict[str, Any]] = {
    "PY-SEC-01": {
        "cwe": "CWE-502",
        "severity": "HIGH",
        "reason_dangerous": "yaml.load() without a safe Loader can construct arbitrary Python objects from untrusted input.",
        "potential_threat": "An attacker can supply malicious YAML tags (e.g. !!python/object/apply) to achieve Remote Code Execution.",
        "future_risks": [
            "Full host operating system compromise through deserialization payloads",
            "Arbitrary execution of system commands and reverse shells",
            "Exfiltration of local files, credentials, and environment variables"
        ],
        "recommended_fix": "Replace yaml.load() with yaml.safe_load() or specify Loader=yaml.SafeLoader.",
    },
    "PY-SEC-02": {
        "cwe": "CWE-327",
        "severity": "HIGH",
        "reason_dangerous": "MD5 and SHA-1 cryptographic hash algorithms are collision-prone and broken.",
        "potential_threat": "An attacker can forge hash collisions to bypass signature checks, token validations, or integrity verifications.",
        "future_risks": [
            "Credential forgery and credential stuffing attacks",
            "Collision attacks allowing forged digital signatures",
            "Non-compliance with security standards (PCI-DSS, NIST, FIPS)"
        ],
        "recommended_fix": "Use hashlib.sha256() or stronger hash functions (or bcrypt/argon2 for passwords).",
    },
    "PY-SEC-03": {
        "cwe": "CWE-95",
        "severity": "HIGH",
        "reason_dangerous": "eval() evaluates arbitrary Python expressions dynamically from untrusted strings.",
        "potential_threat": "An attacker providing input to eval() can execute arbitrary Python statements including OS commands.",
        "future_risks": [
            "Remote Code Execution (RCE) on the server or developer workstation",
            "Bypass of all application logic, permissions, and database constraints",
            "Unauthorized execution of operating system commands"
        ],
        "recommended_fix": "Use ast.literal_eval() for safely parsing Python literals, or avoid dynamic evaluation.",
    },
    "PY-SEC-04": {
        "cwe": "CWE-78",
        "severity": "HIGH",
        "reason_dangerous": "subprocess call with shell=True executes commands through the system shell interpreter.",
        "potential_threat": "Untrusted command arguments allow attackers to execute arbitrary shell commands.",
        "future_risks": [
            "Command injection enabling unauthorized file reads, modifications, or deletions",
            "Spawning background backdoors or reverse shell connections",
            "Privilege escalation under the web server's user account"
        ],
        "recommended_fix": "Pass command and arguments as a list with shell=False (default).",
    },
    "PY-SEC-05": {
        "cwe": "CWE-295",
        "severity": "HIGH",
        "reason_dangerous": "Disabling TLS certificate verification (verify=False) permits unencrypted or spoofed traffic.",
        "potential_threat": "An attacker on the local network can perform a Man-in-the-Middle (MitM) attack to intercept or modify API requests.",
        "future_risks": [
            "Interception of bearer tokens, API credentials, and sensitive user data",
            "Injection of spoofed responses into downstream application workflows",
            "Eavesdropping on communications across unencrypted networks"
        ],
        "recommended_fix": "Set verify=True (or pass a trusted CA bundle path) to enforce TLS verification.",
    },
    "PY-SEC-06": {
        "cwe": "CWE-489",
        "severity": "HIGH",
        "reason_dangerous": "Running Flask with debug=True enables the interactive Werkzeug debugger in the browser.",
        "potential_threat": "The interactive debugger provides an in-browser PIN-protected Python console that can be brute-forced or exploited for RCE.",
        "future_risks": [
            "Full remote code execution through the Werkzeug interactive console",
            "Exposure of source code snippets, stack traces, and local variables in HTTP error pages",
            "Information disclosure revealing internal paths, database queries, and environment details"
        ],
        "recommended_fix": "Set debug=False or use environment variable FLASK_DEBUG=0 for production deployments.",
    },
    "PY-SEC-07": {
        "cwe": "CWE-798",
        "severity": "HIGH",
        "reason_dangerous": "Hardcoded credentials or API keys embedded directly in source code.",
        "potential_threat": "Credentials stored in code repositories can be extracted by anyone with read access to the codebase.",
        "future_risks": [
            "Credential leakage via public or shared git repositories",
            "Account takeover and unauthorized API access to cloud providers",
            "Difficulty in credential rotation without redeploying application code"
        ],
        "recommended_fix": "Retrieve sensitive credentials from environment variables using os.environ.get('SECRET').",
    },
    "PY-SEC-08": {
        "cwe": "CWE-89",
        "severity": "HIGH",
        "reason_dangerous": "SQL query formed by concatenating or formatting user-supplied strings into query text.",
        "potential_threat": "An attacker can inject SQL syntax to bypass authentication, read unauthorized tables, or drop databases.",
        "future_risks": [
            "Complete database exfiltration including user accounts and hashed passwords",
            "Authentication bypass via ' OR '1'='1 injection payloads",
            "Data tampering, modification of audit logs, or execution of database admin procedures"
        ],
        "recommended_fix": "Use parameterized queries with placeholders: cursor.execute('SELECT * FROM t WHERE id = %s', (id,)).",
    },
    "PY-SEC-09": {
        "cwe": "CWE-502",
        "severity": "HIGH",
        "reason_dangerous": "Unsafe deserialization or execution primitive (e.g. pickle or dynamic shell call).",
        "potential_threat": "Deserializing untrusted pickle streams or executing dynamic commands can lead to immediate arbitrary code execution.",
        "future_risks": [
            "Remote Code Execution (RCE) via __reduce__ deserialization gadget chains",
            "Host operating system takeover and ransomware execution",
            "Compromise of backend servers processing client requests"
        ],
        "recommended_fix": "Use safe serialization formats like JSON, or restrict inputs to vetted schemas.",
    },
}

C_FUTURE_RISKS: Dict[str, List[str]] = {
    "system": [
        "If user input reaches the system() argument, an attacker can inject arbitrary shell commands (command injection)",
        "Untrusted command arguments enable arbitrary command execution and data exfiltration",
        "system() spawns a full shell process — far more attack surface than direct process execution",
        "On multi-user systems, the command runs with the process's full privileges (privilege escalation risk)",
    ],
    "popen": [
        "Bidirectional shell pipe allows both command injection and output interception",
        "Attacker-controlled arguments can redirect output to exfiltrate sensitive data",
        "Unclosed popen handles leak file descriptors and child processes",
    ],
    "gets": [
        "gets() performs ZERO bounds checking — any input longer than the buffer causes a stack buffer overflow",
        "Stack buffer overflows can overwrite the return address, enabling arbitrary code execution (RCE)",
        "Removed from C11 standard due to being fundamentally unfixable — no safe way to call it",
        "Automated exploit generation tools can weaponize gets() overflows in seconds",
    ],
    "strcpy": [
        "If source string is longer than destination buffer, strcpy() causes a buffer overflow",
        "Stack-based overflows can be exploited for Return-Oriented Programming (ROP) attacks",
        "Heap-based overflows can corrupt malloc metadata, enabling arbitrary write primitives",
    ],
    "strcat": [
        "strcat() does not check total length after concatenation — cumulative overflows possible",
        "Repeated strcat() in loops is a common source of exploitable buffer overflows",
    ],
    "sprintf": [
        "No destination buffer size limit — output longer than buffer causes overflow",
        "Format string vulnerabilities if user input reaches format argument (%n writes to arbitrary memory)",
    ],
    "scanf": [
        "scanf with %s reads unbounded input into a fixed buffer — classic stack overflow vector",
        "Attacker can craft input to overwrite stack variables, return addresses, or function pointers",
    ],
    "fork": [
        "Uncontrolled fork() calls can exhaust the process table (fork bomb denial-of-service)",
        "Forked processes inherit open file descriptors — potential for unintended data access",
    ],
    "exec": [
        "exec family replaces the entire process image — if path is attacker-controlled, arbitrary code runs",
        "Environment variables passed to execve() can inject library paths or configuration",
    ],
}

# Regex patterns for Python dangerous function detection (module.function or standalone)
PYTHON_DANGEROUS_PATTERNS = [
    # os module shell commands
    (re.compile(r"\bos\s*\.\s*system\s*\("), "os.system"),
    (re.compile(r"\bos\s*\.\s*popen\s*\("), "os.popen"),
    (re.compile(r"\bos\s*\.\s*exec[lv]p?e?\s*\("), "os.exec*"),
    (re.compile(r"\bos\s*\.\s*spawn[lv]p?e?\s*\("), "os.spawn*"),
    # subprocess module
    (re.compile(r"\bsubprocess\s*\.\s*call\s*\("), "subprocess.call"),
    (re.compile(r"\bsubprocess\s*\.\s*run\s*\("), "subprocess.run"),
    (re.compile(r"\bsubprocess\s*\.\s*Popen\s*\("), "subprocess.Popen"),
    (re.compile(r"\bsubprocess\s*\.\s*check_output\s*\("), "subprocess.check_output"),
    (re.compile(r"\bsubprocess\s*\.\s*check_call\s*\("), "subprocess.check_call"),
    (re.compile(r"\bsubprocess\s*\.\s*getoutput\s*\("), "subprocess.getoutput"),
    # eval/exec/compile
    (re.compile(r"(?<!\w)eval\s*\("), "eval"),
    (re.compile(r"(?<!\w)exec\s*\("), "exec"),
    (re.compile(r"(?<!\w)compile\s*\("), "compile"),
    # pickle deserialization
    (re.compile(r"\bpickle\s*\.\s*loads?\s*\("), "pickle.loads"),
    (re.compile(r"\bcPickle\s*\.\s*loads?\s*\("), "pickle.loads"),
    # dynamic imports
    (re.compile(r"\b__import__\s*\("), "__import__"),
    (re.compile(r"\bimportlib\s*\.\s*import_module\s*\("), "importlib.import_module"),
    # ctypes native code loading
    (re.compile(r"\bctypes\s*\.\s*(?:CDLL|cdll|windll|WinDLL)\s*\("), "ctypes.CDLL"),
    # destructive file operations
    (re.compile(r"\bshutil\s*\.\s*rmtree\s*\("), "shutil.rmtree"),
    (re.compile(r"\bos\s*\.\s*remove\s*\("), "os.remove"),
    (re.compile(r"\bos\s*\.\s*rmdir\s*\("), "os.rmdir"),
]


@dataclass
class SecurityApprovalGateFinding:
    id: str
    rule_id: str
    category: str
    severity: str                    # CRITICAL, HIGH, MEDIUM, LOW, INFO
    status: str                      # CONFIRMED, SUSPECTED, INCONCLUSIVE
    file_path: str
    line: int
    column: int
    snippet: str
    explanation: str
    potential_consequences: str
    recommended_mitigation: str
    is_confirmed: bool = True
    is_prohibited: bool = False      # If True, override is forbidden
    requires_review: bool = True
    has_repair_proposal: bool = False
    cwe_id: str = ""                 # CWE identifier (e.g. "CWE-78")
    future_risks: List[str] = field(default_factory=list)  # Detailed future risk explanations
    is_manipulation: bool = False    # True if finding is an agent manipulation or prompt injection
    flagged_text: str = ""           # The exact flagged snippet/text
    manipulation_reason: str = ""    # Plain-language reason why this text was flagged

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "file_path": self.file_path,
            "line": self.line,
            "column": self.column,
            "snippet": self.snippet,
            "cwe": self.cwe_id,
            "cwe_id": self.cwe_id,
            "reason_dangerous": self.explanation,
            "explanation": self.explanation,
            "potential_threat": self.potential_consequences,
            "potential_consequences": self.potential_consequences,
            "future_risks": list(self.future_risks),
            "recommended_fix": self.recommended_mitigation,
            "recommended_mitigation": self.recommended_mitigation,
            "is_confirmed": self.is_confirmed,
            "is_prohibited": self.is_prohibited,
            "requires_review": self.requires_review,
            "has_repair_proposal": self.has_repair_proposal,
            "is_manipulation": self.is_manipulation,
            "flagged_text": self.flagged_text or self.snippet,
            "manipulation_reason": self.manipulation_reason or self.explanation,
        }


@dataclass
class SecurityApprovalGateVerdict:
    is_blocked: bool
    can_override: bool
    heading: str
    filename: str
    source_hash: str
    operation: str
    summary: str
    policy_reason: str
    findings: List[SecurityApprovalGateFinding] = field(default_factory=list)
    findings_by_severity: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    security_checks_completed: List[str] = field(default_factory=list)
    security_checks_failed: List[str] = field(default_factory=list)
    has_repair_proposal: bool = False
    actions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        # Reviewer instructions alone do NOT make a program unsafe
        non_manip = [f for f in self.findings if not getattr(f, "is_manipulation", False)]
        overall_risk = "NONE"
        if any(f.is_prohibited or f.severity == "CRITICAL" for f in non_manip):
            overall_risk = "CRITICAL"
        elif any(f.severity == "HIGH" for f in non_manip):
            overall_risk = "HIGH"
        elif non_manip:
            overall_risk = "MEDIUM"
        elif self.findings:
            overall_risk = "LOW"

        explanation_parts = [f"[{f.severity}] {f.rule_id}: {f.explanation}" for f in self.findings]
        comb_expl = "\n".join(explanation_parts) if explanation_parts else self.policy_reason
        impacts = [f.potential_consequences for f in self.findings if f.potential_consequences]

        return {
            "status": "SECURITY_WARNING" if self.is_blocked else "SECURITY_PASSED",
            "is_blocked": self.is_blocked,
            "blocked": self.is_blocked,
            "requires_approval": self.is_blocked,
            "security_approval_required": self.is_blocked,
            "can_override": self.can_override,
            "is_prohibited": (not self.can_override) and self.is_blocked,
            "overall_risk": overall_risk,
            "heading": self.heading,
            "filename": self.filename,
            "source_hash": self.source_hash,
            "operation": self.operation,
            "summary": self.summary,
            "policy_reason": self.policy_reason,
            "explanation": comb_expl,
            "potential_impact": " | ".join(dict.fromkeys(impacts)),
            "findings": [f.to_dict() for f in self.findings],
            "findings_count": len(self.findings),
            "critical_count": sum(1 for f in self.findings if f.severity == "CRITICAL"),
            "high_count": sum(1 for f in self.findings if f.severity == "HIGH"),
            "findings_by_severity": self.findings_by_severity,
            "security_checks_completed": list(self.security_checks_completed),
            "security_checks_failed": list(self.security_checks_failed),
            "has_repair_proposal": self.has_repair_proposal,
            "actions": list(self.actions),
        }


@dataclass
class _ApprovalTokenRecord:
    token: str
    source_hash: str
    filename: str
    operation: str
    finding_ids: Set[str]
    created_at: float
    expires_at: float
    used: bool = False


class SecurityApprovalManager:
    """
    Manages user-controlled one-time security approvals.
    Approvals are bound to exact source hash, filename, and operation.
    Modifying source or operation automatically invalidates the approval.
    """
    _tokens: Dict[str, _ApprovalTokenRecord] = {}
    _consumed_tokens: Set[str] = set()
    _consumed_records: Dict[str, _ApprovalTokenRecord] = {}
    _approvals_by_hash: Dict[str, _ApprovalTokenRecord] = {}
    DEFAULT_TTL_SEC: float = 60.0

    @classmethod
    def create_one_time_approval(
        cls,
        source_code: str,
        filename: str = "main.c",
        language: str = "c",
        operation: str = "execute",
        finding_ids: Optional[List[str]] = None,
        force: bool = False,
    ) -> Tuple[bool, Optional[str], str]:
        """
        Creates a one-time approval token for the given source and operation.
        Prohibited findings (gate bypass, prompt injection, destructive commands) can NEVER be overridden.
        """
        verdict = SecurityDecisionGate.evaluate(
            source_code=source_code,
            filename=filename,
            language=language,
            operation=operation,
        )

        # Policy update: NEVER hard block. User approval is ALWAYS permitted.
        now = time.time()
        source_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        token = f"appr_{uuid.uuid4().hex}"

        rec = _ApprovalTokenRecord(
            token=token,
            source_hash=source_hash,
            filename=filename,
            operation=operation,
            finding_ids=set(finding_ids or [f.id for f in verdict.findings]),
            created_at=now,
            expires_at=now + cls.DEFAULT_TTL_SEC,
            used=False,
        )
        cls._tokens[token] = rec
        cls._approvals_by_hash[source_hash] = rec

        # Log decision in audit log
        decision_label = "APPROVED"
        cls.record_decision(
            decision=decision_label,
            source_code=source_code,
            filename=filename,
            operation=operation,
            findings=verdict.findings,
            extra={"token_prefix": token[:10], "force_override": force},
        )

        return True, token, "One-time security approval granted."

    @classmethod
    def verify_and_consume(
        cls,
        token: Optional[str],
        source_code: str,
        filename: str = "main.c",
        operation: str = "execute",
    ) -> Tuple[bool, str]:
        """
        Verifies and consumes a one-time approval token.
        Fails if expired, already used, or if source/operation has changed.
        """
        if not token:
            return False, "No approval token provided."

        if token in cls._consumed_tokens:
            return False, "Approval token has already been consumed (single-use policy)."

        rec = cls._tokens.get(token)
        if not rec:
            return False, "Approval token not found or invalid."

        if rec.used:
            return False, "Approval token has already been consumed (single-use policy)."

        if time.time() > rec.expires_at:
            del cls._tokens[token]
            return False, "Approval token has expired."

        curr_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        if curr_hash != rec.source_hash:
            return False, "Source code was modified after approval was granted. Fresh review required."

        if operation != rec.operation:
            return False, f"Approval operation mismatch: approved for '{rec.operation}', requested '{operation}'."

        if filename != rec.filename:
            return False, f"Approval filename mismatch: approved for '{rec.filename}', requested '{filename}'."

        # Mark single-use token as consumed
        rec.used = True
        cls._consumed_tokens.add(token)
        cls._consumed_records[token] = rec
        cls._approvals_by_hash[rec.source_hash] = rec
        del cls._tokens[token]

        # Log audit entry
        cls.record_decision(
            decision="CONSUMED",
            source_code=source_code,
            filename=filename,
            operation=operation,
            findings=[],
            extra={"token_prefix": token[:10]},
        )

        return True, "One-time approval successfully verified and consumed."

    @classmethod
    def get_approval_record(
        cls,
        token: Optional[str] = None,
        source_hash: Optional[str] = None,
    ) -> Optional[_ApprovalTokenRecord]:
        """Lookup an approval record (active or recently consumed) by token or source_hash."""
        if token:
            if token in cls._tokens:
                return cls._tokens[token]
            if token in cls._consumed_records:
                return cls._consumed_records[token]
        if source_hash and source_hash in cls._approvals_by_hash:
            return cls._approvals_by_hash[source_hash]
        return None

    @classmethod
    def record_cancellation(
        cls,
        source_code: str,
        filename: str = "main.c",
        operation: str = "execute",
    ) -> None:
        """Logs explicit user cancellation of execution in the audit log and revokes any active tokens for this source."""
        curr_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        tokens_to_revoke = [t for t, rec in cls._tokens.items() if rec.source_hash == curr_hash]
        for t in tokens_to_revoke:
            cls._consumed_tokens.add(t)
            del cls._tokens[t]

        cls.record_decision(
            decision="CANCELLED",
            source_code=source_code,
            filename=filename,
            operation=operation,
            findings=[],
        )

    @classmethod
    def record_decision(
        cls,
        decision: str,
        source_code: str,
        filename: str,
        operation: str,
        findings: List[SecurityApprovalGateFinding],
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Records security decision event in logs/security_audit.jsonl and logs/repair_log.jsonl."""
        full_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        finding_id_list = [getattr(f, "id", str(f)) for f in findings]
        event_data = {
            "timestamp": _utc_now_iso(),
            "decision": decision,
            "source_hash": full_hash,
            "source_hash_short": full_hash[:16],
            "filename": filename,
            "operation": operation,
            "findings_count": len(findings),
            "finding_ids": finding_id_list,
        }
        if extra:
            event_data.update(extra)

        # Dedicated audit log
        try:
            import json as _json
            audit_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "security_audit.jsonl")
            os.makedirs(os.path.dirname(audit_file), exist_ok=True)
            with open(audit_file, "a", encoding="utf-8") as f_aud:
                f_aud.write(_json.dumps(event_data) + "\n")
        except Exception:
            pass

        try:
            logger = RepairLogger()
            logger._write(RepairLogEvent(
                ts_utc=_utc_now_iso(),
                event="security_approval_decision",
                data=event_data,
            ))
        except Exception:
            pass

    @classmethod
    def clear(cls) -> None:
        """Clears all in-memory approval tokens (for test teardown)."""
        cls._tokens.clear()
        cls._consumed_tokens.clear()



# ──────────────────────────────────────────────────────────────────────────────
# Agent Manipulation & Prompt Injection Directives
# ──────────────────────────────────────────────────────────────────────────────
PROHIBITED_TAMPER_PATTERNS = [
    (re.compile(r"(?:disable|bypass|circumvent|ignore|override|skip)\s+(?:the\s+)?(?:security|safety)\s+(?:gate|approval|check|review|filter)", re.IGNORECASE), "SEC_GATE_BYPASS_ATTEMPT", "Attempt to bypass or disable security gate detected."),
    (re.compile(r"AGENT\s+MANIPULATION", re.IGNORECASE), "SEC_AGENT_OVERRIDE_DIRECTIVE", "Agent manipulation directive detected."),
    (re.compile(r"ANTIGRAVITY\s*[\-_]?\s*(?:AGENT|COMPILER)\s*[\-_]?\s*(?:IGNORE|BYPASS|DISABLE|OVERRIDE)", re.IGNORECASE), "SEC_GATE_BYPASS_ATTEMPT", "Antigravity compiler security override attempt detected."),
    (re.compile(r"SECURITY_STATUS\s*:\s*FORCE_PASS", re.IGNORECASE), "SEC_GATE_BYPASS_ATTEMPT", "Forced security status directive detected."),
    (re.compile(r"SECURITY_GATE\s*=\s*(?:PASS|BYPASS|OVERRIDE|SKIP|DISABLE)", re.IGNORECASE), "SEC_GATE_BYPASS_ATTEMPT", "Security gate bypass assignment detected."),
    (re.compile(r"validation_override\s*[:=]\s*(?:true|passed|valid)", re.IGNORECASE), "SEC_GATE_BYPASS_ATTEMPT", "Validation override directive detected."),
    (re.compile(r"#\s*define\s+SECURITY_GATE_PASSED\s+1", re.IGNORECASE), "SEC_GATE_BYPASS_ATTEMPT", "Synthetic security gate pass macro detected."),
    (re.compile(r"<\|im_start\|>", re.IGNORECASE), "SEC_PROMPT_DELIMITER_INJECTION", "Prompt delimiter injection detected."),
    (re.compile(r"<\|im_end\|>", re.IGNORECASE), "SEC_PROMPT_DELIMITER_INJECTION", "Prompt delimiter injection detected."),
    (re.compile(r"Ignore\s+(?:all\s+)?security\s+policies", re.IGNORECASE), "SEC_PROMPT_INJECTION", "Prompt injection attempting to ignore security policies."),
    (re.compile(r"Tell\s+the\s+(?:security\s+)?agent\s+to\s+approve", re.IGNORECASE), "SEC_AGENT_MANIPULATION", "Directive attempting to force security agent approval."),
    (re.compile(r"Disable\s+validation", re.IGNORECASE), "SEC_VALIDATION_BYPASS", "Directive attempting to disable validation."),
    (re.compile(r"report\s+that\s+the\s+program\s+is\s+safe", re.IGNORECASE), "SEC_AGENT_MANIPULATION", "Directive attempting to falsify safety report."),
    (re.compile(r"//\s*SECURITY\s+TEST", re.IGNORECASE), "SEC_AGENT_MANIPULATION", "Security test directive with agent instructions."),
    (re.compile(r"rm\s+-rf\s+[/~]", re.IGNORECASE), "SEC_HOST_DESTRUCTIVE_COMMAND", "Destructive host file deletion command detected."),
    (re.compile(r"format\s+[A-Za-z]:", re.IGNORECASE), "SEC_HOST_DESTRUCTIVE_COMMAND", "Host filesystem format command detected."),
    (re.compile(r"del\s+/[fF]\s+/[sS]\s+/[qQ]\s+[A-Za-z]:\\", re.IGNORECASE), "SEC_HOST_DESTRUCTIVE_COMMAND", "Host bulk file deletion command detected."),
    (re.compile(r"Do\s+not\s+tell\s+the\s+user", re.IGNORECASE), "SEC_AGENT_MANIPULATION", "Concealment directive instructing agent not to disclose actions."),
    (re.compile(r"SYSTEM\s+OVERRIDE", re.IGNORECASE), "SEC_AGENT_MANIPULATION", "System override directive."),
    (re.compile(r"introduce\s+an\s+unsafe\s+function", re.IGNORECASE), "SEC_AGENT_MANIPULATION", "Malicious code injection directive."),
    (re.compile(r"claim\s+that\s+validation\s+passed", re.IGNORECASE), "SEC_VALIDATION_BYPASS", "Validation bypass directive."),
    (re.compile(r"do\s+not\s+report\s+any\s+security\s+findings", re.IGNORECASE), "SEC_AGENT_MANIPULATION", "Finding suppression directive."),
]

def is_manipulation_line(line: str) -> bool:
    """Checks whether a single line contains an agent manipulation or prompt injection directive."""
    s = line.strip()
    if not s:
        return False
    for pat, _, _ in PROHIBITED_TAMPER_PATTERNS:
        if pat.search(s):
            return True
    try:
        from compiler.malicious_precheck import MaliciousCodePrecheck
        for pat in MaliciousCodePrecheck.PROMPT_INJECTION_PATTERNS:
            if pat.search(s):
                return True
    except Exception:
        pass
    return False


def remove_manipulation_comments_from_source(source_code: str) -> str:
    """
    Removes agent manipulation directives, gate tampering comments, and prompt injection markers
    from source code for producing the fixed candidate program.
    Completely removes flagged lines without any '[REMOVED]' or placeholder text.
    """
    if not source_code:
        return ""
    lines = source_code.splitlines()
    clean_lines = [line for line in lines if not is_manipulation_line(line)]
    result = "\n".join(clean_lines)
    if source_code.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result


def strip_manipulation_and_tampering(source_code: str) -> str:
    """
    Sanitizes source code before passing to any LLM or model prompt.
    Completely removes manipulation lines without leaving any synthetic tokens or placeholders.
    """
    return remove_manipulation_comments_from_source(source_code)


def strip_manipulation_for_ai(source_code: str) -> str:
    """Alias for strip_manipulation_and_tampering."""
    return remove_manipulation_comments_from_source(source_code)


def strip_c_comments_only(text: str) -> str:
    """Strip only comments (/* ... */ and // ...) from C code, preserving string literals."""
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return " " * len(s)
        else:
            return s
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE
    )
    return re.sub(pattern, replacer, text)


def is_c_function_prototype(clean_code: str, match_start: int, fn_name: str) -> bool:
    """Check if the occurrence of fn_name( at match_start is a prototype declaration."""
    line_start = clean_code.rfind("\n", 0, match_start)
    line_start = 0 if line_start == -1 else line_start + 1
    stmt_start = max(line_start, clean_code.rfind(";", 0, match_start) + 1, clean_code.rfind("{", 0, match_start) + 1, clean_code.rfind("}", 0, match_start) + 1)
    prefix = clean_code[stmt_start:match_start].strip()

    type_pat = r'^(?:(?:extern|static|inline)\s+)?(?:void|int|char|long|short|unsigned|signed|size_t|ssize_t|float|double|bool|struct\s+\w+)(?:\s*\*+)?$'
    if not re.match(type_pat, prefix):
        return False

    paren_end = clean_code.find(")", match_start)
    if paren_end == -1:
        return False
    after_paren = clean_code[paren_end+1:].lstrip()
    return after_paren.startswith(";")


def is_safe_c_system_call(clean_code: str, match_start: int) -> bool:
    """Check if system(...) call at match_start has a constant or allowlisted argument."""
    paren_end = clean_code.find(")", match_start)
    if paren_end == -1:
        return False
    call_str = clean_code[match_start:paren_end]
    if "(" not in call_str:
        return False
    arg = call_str.split("(", 1)[1].strip()

    if arg.startswith('"') and arg.endswith('"'):
        return True

    prev_fn_end = clean_code.rfind('}', 0, match_start)
    local_code = clean_code[max(0, prev_fn_end + 1):match_start]

    strcmp_guard = rf'\bstrcmp\s*\(\s*(?:{re.escape(arg)}\s*,\s*"[^"]*"|"[^"]*"\s*,\s*{re.escape(arg)})\s*\)\s*==\s*0'
    if re.search(strcmp_guard, local_code):
        return True

    const_init = rf'char\s+{re.escape(arg)}\s*\[[^\]]*\]\s*=\s*"[^"]*"\s*;'
    if re.search(const_init, local_code):
        if not re.search(rf'\b(?:scanf|gets)\s*\([^;]*\b{re.escape(arg)}\b', local_code):
            return True

    return False


class SecurityDecisionGate:
    """
    Evaluates the complete security workflow before compilation and execution:
    Source Code → Malicious Code Precheck → Lexical Analysis → Syntax Analysis
    → Semantic Analysis → Security Analysis → Security Decision Gate → User Approval → Compilation / Execution
    """

    PROHIBITED_REASON_CODES = {
        GateReasonCode.SEC_HOST_DESTRUCTIVE_COMMAND.value,
        GateReasonCode.SEC_HOST_SECRET_EXFILTRATION.value,
        GateReasonCode.SEC_PROMPT_DELIMITER_INJECTION.value,
        GateReasonCode.SEC_AGENT_OVERRIDE_DIRECTIVE.value,
        GateReasonCode.SEC_GATE_BYPASS_ATTEMPT.value,
        GateReasonCode.SEC_NULL_BYTE_DETECTED.value,
        GateReasonCode.SEC_PATH_TRAVERSAL.value,
        GateReasonCode.SEC_PAYLOAD_TOO_LARGE.value,
        GateReasonCode.SEC_LINE_LENGTH_EXCEEDED.value,
        GateReasonCode.SEC_NESTING_DEPTH_EXCEEDED.value,
    }

    @classmethod
    def evaluate(
        cls,
        source_code: str,
        filename: str = "main.c",
        language: str = "c",
        operation: str = "execute",
    ) -> SecurityApprovalGateVerdict:
        """
        Runs the full security precheck and analysis pipeline for the exact source code.
        Distinguishes actual executable threats from comments and strings.
        Determines whether the code is clean, blocked for review, or prohibited.
        """
        source_code = source_code or ""
        if filename and filename.endswith((".py", ".py3")) and language in ("c", "C", ""):
            language = "python"
        source_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        lines = source_code.splitlines()

        findings: List[SecurityApprovalGateFinding] = []
        checks_completed: List[str] = []
        checks_failed: List[str] = []

        is_prohibited = False
        has_repair_proposal = False

        # ------------------------------------------------------------------
        # 0. Agent Manipulation & Reviewer Instructions (P6 Generalized Detector)
        # ------------------------------------------------------------------
        try:
            from compiler.agent_manipulation import AgentManipulationDetector
            _am_det = AgentManipulationDetector()
            _am_rep = _am_det.analyze(source_code, filename=filename, language=language, run_l2=True)
            for mf in _am_rep.findings:
                findings.append(SecurityApprovalGateFinding(
                    id=mf.id,
                    rule_id=mf.rule_id,
                    category=mf.category,
                    severity="INFO",               # Never CRITICAL
                    status="FLAGGED",              # Never CONFIRMED vulnerability
                    file_path=filename,
                    line=mf.line,
                    column=mf.column,
                    snippet=mf.snippet,
                    explanation=mf.explanation,
                    potential_consequences=mf.potential_threat,
                    recommended_mitigation=mf.recommended_fix,
                    is_confirmed=False,            # Not a software bug
                    is_prohibited=False,
                    requires_review=True,
                    has_repair_proposal=False,
                    cwe_id="CWE-94",
                    future_risks=mf.future_risks,
                    is_manipulation=True,
                    flagged_text=mf.flagged_text,
                    manipulation_reason=mf.manipulation_reason,
                ))
        except Exception:
            for pat, rule_id, expl in PROHIBITED_TAMPER_PATTERNS:
                m = pat.search(source_code)
                if m:
                    line_idx = source_code.count("\n", 0, m.start()) + 1
                    evidence_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m.group(0)
                    findings.append(SecurityApprovalGateFinding(
                        id=f"REVIEWER-INSTR-L{line_idx}",
                        rule_id=rule_id,
                        category="AGENT_INSTRUCTION_MANIPULATION",
                        severity="INFO",
                        status="FLAGGED",
                        file_path=filename,
                        line=line_idx,
                        column=0,
                        snippet=evidence_line.strip(),
                        explanation=f"Instructions in code addressed to an automated reviewer: {expl}",
                        potential_consequences="Directive in code attempting to influence automated review or verification models.",
                        recommended_mitigation="Acknowledge warning to continue. Flagged directive will be automatically masked before passing code to AI models.",
                        is_confirmed=False,
                        is_prohibited=False,
                        requires_review=True,
                        has_repair_proposal=False,
                        cwe_id="CWE-94",
                        future_risks=[
                            "Tampering with security gates allows arbitrary unverified code to run without restriction",
                            "Manipulation comments could hijack AI repair models into generating insecure patches"
                        ],
                        is_manipulation=True,
                        flagged_text=evidence_line.strip(),
                        manipulation_reason=expl,
                    ))

        # ------------------------------------------------------------------
        # 1. Malicious Code Precheck & PreExecutionSecurityGate
        # ------------------------------------------------------------------
        try:
            gate_verdict = PreExecutionSecurityGate.check_submission(
                source_code=source_code,
                filename=filename,
                language=language,
                action=operation,
            )
            checks_completed.append("Malicious Code Precheck")

            if gate_verdict.is_blocked:
                is_proh = gate_verdict.reason_code in cls.PROHIBITED_REASON_CODES
                if is_proh:
                    is_prohibited = True

                # Determine CWE and future risks for precheck threats
                _pre_cwe = "CWE-94"
                _pre_risks = [
                    "Adversarial prompt injection attempting to hijack automated compiler/repair agent instructions.",
                    "Attacker may force the compiler to bypass security policies or suppress vulnerability reports.",
                    "Could cause the agent to inject backdoors, arbitrary code execution primitives, or malicious patches.",
                    "Compromises the integrity of all automated verification and safety guarantees.",
                ]
                if "DESTRUCTIVE" in gate_verdict.reason_code:
                    _pre_cwe = "CWE-78"
                    _pre_risks = [
                        "Destructive command execution targeting operating system resources.",
                        "Could cause permanent loss of critical files, system corruption, or denial of service.",
                    ]
                elif "EXFILTRATION" in gate_verdict.reason_code:
                    _pre_cwe = "CWE-200"
                    _pre_risks = [
                        "Exfiltration of host credentials, API keys, or security tokens to external systems.",
                        "Compromised credentials could allow unauthorized access, lateral movement, and data breaches.",
                    ]
                elif "BYPASS" in gate_verdict.reason_code:
                    _pre_cwe = "CWE-693"
                    _pre_risks = [
                        "Attempt to bypass or force security verification status directly.",
                        "Invalidates the compiler security gate and permits unvetted malicious payloads to run.",
                    ]

                _is_manip = (
                    is_manipulation_line(gate_verdict.evidence or gate_verdict.message) or
                    any(k in str(gate_verdict.reason_code) for k in ("AGENT", "MANIPULATION", "PROMPT", "OVERRIDE", "INJECTION", "TAMPER"))
                )
                findings.append(SecurityApprovalGateFinding(
                    id=f"PRECHECK-{gate_verdict.reason_code}",
                    rule_id=gate_verdict.reason_code,
                    category="AGENT_INSTRUCTION_MANIPULATION" if _is_manip else gate_verdict.threat_category,
                    severity="INFO" if _is_manip else "CRITICAL",
                    status="FLAGGED" if _is_manip else "CONFIRMED",
                    file_path=filename,
                    line=gate_verdict.details.get("line_number", 1),
                    column=0,
                    snippet=gate_verdict.evidence or gate_verdict.message,
                    explanation=gate_verdict.explanation,
                    potential_consequences=f"Threat to compiler platform or agent integrity ({_pre_cwe}).",
                    recommended_mitigation="Review and continue. The flagged directive will be masked before passing code to AI repair models.",
                    is_confirmed=False if _is_manip else True,
                    is_prohibited=is_proh,
                    requires_review=True,
                    has_repair_proposal=False,
                    cwe_id=_pre_cwe,
                    future_risks=_pre_risks,
                    is_manipulation=_is_manip,
                    flagged_text=(gate_verdict.evidence or gate_verdict.message) if _is_manip else "",
                    manipulation_reason=gate_verdict.explanation if _is_manip else "",
                ))
        except Exception as e:
            checks_failed.append("Malicious Code Precheck")
            findings.append(SecurityApprovalGateFinding(
                id="PRECHECK-ERROR",
                rule_id="SEC_PRECHECK_EXCEPTION",
                category="PRECHECK_FAILURE",
                severity="CRITICAL",
                status="INCONCLUSIVE",
                file_path=filename,
                line=1,
                column=0,
                snippet="",
                explanation=f"Malicious code precheck threw an unexpected exception: {str(e)}",
                potential_consequences="Precheck could not certify safety (fails closed).",
                recommended_mitigation="Resolve precheck error or fix source formatting.",
                is_confirmed=False,
                is_prohibited=False,
                requires_review=True,
            ))

        # Check secondary MaliciousCodePrecheck findings
        try:
            from compiler.malicious_precheck import MaliciousCodePrecheck
            precheck_rep = MaliciousCodePrecheck.analyze(source_code, filename=filename, language=language)
            for f in precheck_rep.findings:
                # Deduplicate C dangerous calls which are fully analyzed by Section 2 below
                if language in ("c", "cpp", "c++") and f.rule_id in ("PRECHECK-CWE-78", "PRECHECK-CMD-001"):
                    continue
                if f.blocks_execution or f.requires_review:
                    is_proh = f.blocks_execution or f.is_malicious_intent
                    if is_proh:
                        is_prohibited = True
                    _f_cwe = getattr(f, 'cwe', '') or getattr(f, 'cwe_id', '') or 'CWE-676'
                    _f_risks = []
                    for c_fn, c_r in C_FUTURE_RISKS.items():
                        if c_fn in f.rule_id.lower() or c_fn in (f.snippet or '').lower():
                            _f_risks = list(c_r)
                            break
                    if not _f_risks:
                        _f_risks = [
                            f"Use of dangerous pattern '{f.rule_id}' may lead to unexpected exploitation.",
                            "Security policy flags this pattern for mandatory human review before execution.",
                        ]
                    _f_is_manip = (
                        is_manipulation_line(f.snippet or "") or
                        any(k in str(f.rule_id) for k in ("AGENT", "MANIPULATION", "PROMPT", "OVERRIDE", "INJECTION", "TAMPER")) or
                        any(k in str(f.explanation).lower() for k in ("manipulate", "prompt-injection", "instruction"))
                    )
                    findings.append(SecurityApprovalGateFinding(
                        id=f"PRECHECK-{f.rule_id}-L{f.line}",
                        rule_id=f.rule_id,
                        category="AGENT_INSTRUCTION_MANIPULATION" if _f_is_manip else f.category,
                        severity="INFO" if _f_is_manip else f.severity.upper(),
                        status="FLAGGED" if _f_is_manip else ("CONFIRMED" if f.confidence >= 0.8 else "SUSPECTED"),
                        file_path=f.file_path or filename,
                        line=f.line,
                        column=f.column,
                        snippet=f.snippet,
                        explanation=f.explanation,
                        potential_consequences=f"Risk level {f.risk_level.value}: execution of unverified dangerous pattern ({_f_cwe}).",
                        recommended_mitigation=f.recommended_mitigation,
                        is_confirmed=False if _f_is_manip else (f.confidence >= 0.8),
                        is_prohibited=is_proh,
                        requires_review=True,
                        has_repair_proposal=False,
                        cwe_id=_f_cwe,
                        future_risks=_f_risks,
                        is_manipulation=_f_is_manip,
                        flagged_text=f.snippet if _f_is_manip else "",
                        manipulation_reason=f.explanation if _f_is_manip else "",
                    ))
        except Exception:
            pass

        # ------------------------------------------------------------------
        # 2. Executable Dangerous System / Shell Calls & Vulnerabilities (C)
        # ------------------------------------------------------------------
        if language in ("c", "cpp", "c++"):
            clean_code = strip_c_comments_and_strings(source_code)
            code_with_strings = strip_c_comments_only(source_code)

            from compiler.taint_checker import TaintChecker
            from compiler.cwe_catalog import CWE_CATALOG
            cwe78_meta = CWE_CATALOG.get("CWE-78", {})
            tc_issues = TaintChecker().check(source_code)

            for fn_name, (fn_desc, cwe) in DANGEROUS_SYSTEM_CALLS.items():
                pattern = rf"\b{re.escape(fn_name)}\s*\("
                for m in re.finditer(pattern, clean_code):
                    if is_c_function_prototype(clean_code, m.start(), fn_name):
                        continue

                    line_idx = clean_code.count("\n", 0, m.start()) + 1
                    evidence_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else f"{fn_name}(...);"

                    sink_issue = None
                    for ti in tc_issues:
                        if ti.sink == fn_name and ti.sink_line == line_idx:
                            sink_issue = ti
                            break

                    is_constant = (fn_name == "system" and is_safe_c_system_call(code_with_strings, m.start())) or (sink_issue and sink_issue.severity == "LOW")

                    if sink_issue and sink_issue.severity == "CRITICAL":
                        findings.append(SecurityApprovalGateFinding(
                            id=f"DANGEROUS-CALL-{fn_name}-L{line_idx}",
                            rule_id="SEC-CWE-78",
                            category="COMMAND_INJECTION",
                            severity="CRITICAL",
                            status="CONFIRMED",
                            file_path=filename,
                            line=line_idx,
                            column=m.start() - clean_code.rfind("\n", 0, m.start()) - 1,
                            snippet=evidence_line.strip(),
                            explanation=sink_issue.message,
                            potential_consequences=cwe78_meta.get("potential_impact", "Attacker-influenced commands run with the program's privileges."),
                            recommended_mitigation=cwe78_meta.get("mitigation", "Do not pass user-influenced text to a shell; fixed program plus fixed argument vector (execv family or posix_spawn); map input to an allowlist of fixed choices; least privilege."),
                            is_confirmed=True,
                            is_prohibited=True,
                            requires_review=True,
                            has_repair_proposal=False,
                            cwe_id="CWE-78",
                            future_risks=[cwe78_meta.get("potential_impact", "Attacker-influenced commands run with the program's privileges.")],
                        ))
                    elif is_constant:
                        findings.append(SecurityApprovalGateFinding(
                            id=f"DANGEROUS-CALL-{fn_name}-L{line_idx}",
                            rule_id=f"SEC-CONSTANT-{fn_name.upper()}",
                            category="COMMAND_EXECUTION",
                            severity="LOW",
                            status="CONFIRMED",
                            file_path=filename,
                            line=line_idx,
                            column=m.start() - clean_code.rfind("\n", 0, m.start()) - 1,
                            snippet=evidence_line.strip(),
                            explanation=f"Shell call with constant command: '{fn_name}()' called with constant string literal",
                            potential_consequences=cwe78_meta.get("potential_impact", "Shell execution with constant argument; portable standard library constructs preferred."),
                            recommended_mitigation=cwe78_meta.get("mitigation", "Replace platform-specific system calls with portable C standard library constructs."),
                            is_confirmed=True,
                            is_prohibited=False,
                            requires_review=True,
                            has_repair_proposal=False,
                            cwe_id=cwe,
                            future_risks=["Platform dependence and unnecessary shell process creation"],
                        ))
                    else:
                        base_fn = fn_name.replace("exec", "exec").split("exec")[0] if "exec" in fn_name.lower() else fn_name
                        risks = C_FUTURE_RISKS.get(fn_name, C_FUTURE_RISKS.get(base_fn, C_FUTURE_RISKS.get("exec", [])))
                        findings.append(SecurityApprovalGateFinding(
                            id=f"DANGEROUS-CALL-{fn_name}-L{line_idx}",
                            rule_id=f"SEC-DANGEROUS-{fn_name.upper()}",
                            category="DANGEROUS_FUNCTION",
                            severity="HIGH",
                            status="CONFIRMED",
                            file_path=filename,
                            line=line_idx,
                            column=m.start() - clean_code.rfind("\n", 0, m.start()) - 1,
                            snippet=evidence_line.strip(),
                            explanation=f"Executable call to dangerous system/shell function '{fn_name}()': {fn_desc}.",
                            potential_consequences=f"Potential arbitrary shell execution or process manipulation ({cwe}).",
                            recommended_mitigation=cwe78_meta.get("mitigation", f"Replace '{fn_name}()' with safe native logic or avoid shell invocations."),
                            is_confirmed=True,
                            is_prohibited=False,
                            requires_review=True,
                            has_repair_proposal=False,
                            cwe_id=cwe,
                            future_risks=risks,
                        ))

            # 2a. Static Generic C Vulnerability Rules (SEC-01 through SEC-10)
            # 1. Unbounded scanf with %s without width (CWE-120)
            for m in re.finditer(r'\bscanf\s*\(\s*"([^"]*)"\s*,\s*([a-zA-Z0-9_&]+)', code_with_strings):
                fmt, var = m.group(1), m.group(2)
                if re.search(r'%s', fmt) and not re.search(r'%\d+s', fmt):
                    line_idx = code_with_strings.count("\n", 0, m.start()) + 1
                    ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m.group(0)
                    findings.append(SecurityApprovalGateFinding(
                        id=f"C-VULN-SCANF-L{line_idx}",
                        rule_id="SEC-09-UNSAFE-SCANF",
                        category="BUFFER_OVERFLOW",
                        severity="HIGH",
                        status="CONFIRMED",
                        file_path=filename,
                        line=line_idx,
                        column=0,
                        snippet=ev_line.strip(),
                        explanation=f"Unbounded string input via scanf() format '%s' without width limit into '{var}'.",
                        potential_consequences="Stack buffer overflow allowing arbitrary code execution or crash (CWE-120).",
                        recommended_mitigation=f"Specify maximum buffer width in scanf format: scanf(\"%{len(var)-1}s\", {var}).",
                        is_confirmed=True,
                        is_prohibited=False,
                        requires_review=True,
                        cwe_id="CWE-120",
                        future_risks=C_FUTURE_RISKS.get("scanf", [
                            "scanf with %s reads unbounded input into a fixed buffer — classic stack overflow vector",
                            "Attacker can craft input to overwrite stack variables, return addresses, or function pointers",
                        ]),
                    ))

            # 2. printf with non-literal format argument: printf(var); (CWE-134)
            for m in re.finditer(r'\bprintf\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)\s*;', clean_code):
                var = m.group(1)
                line_idx = clean_code.count("\n", 0, m.start()) + 1
                ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m.group(0)
                findings.append(SecurityApprovalGateFinding(
                    id=f"C-VULN-FORMAT-L{line_idx}",
                    rule_id="SEC-08-FORMAT-STRING",
                    category="FORMAT_STRING",
                    severity="HIGH",
                    status="CONFIRMED",
                    file_path=filename,
                    line=line_idx,
                    column=0,
                    snippet=ev_line.strip(),
                    explanation=f"printf() called with non-literal format argument '{var}'.",
                    potential_consequences="Format string vulnerability allowing arbitrary memory read/write (CWE-134).",
                    recommended_mitigation=f"Pass a literal format string: printf(\"%s\", {var});",
                    is_confirmed=True,
                    is_prohibited=False,
                    requires_review=True,
                    cwe_id="CWE-134",
                    future_risks=[
                        "User-controlled format tokens (%x, %s, %n) permit arbitrary stack reading and memory overwriting",
                        "Attacker can craft format string payload to execute arbitrary code or bypass memory protections",
                    ],
                ))

            # 3. Constant Integer Overflow: 2147483647 + 1 (CWE-190)
            for m in re.finditer(r'\b(?:2147483647\s*\+\s*[0-9]+|[0-9]+\s*\+\s*2147483647|INT_MAX\s*\+\s*[0-9]+)\b', clean_code):
                prefix = clean_code[max(0, m.start() - 30):m.start()]
                if not re.search(r'\(\s*(?:long\s+long|int64_t|uint64_t)\s*\)\s*$', prefix):
                    line_idx = clean_code.count("\n", 0, m.start()) + 1
                    ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m.group(0)
                    findings.append(SecurityApprovalGateFinding(
                        id=f"C-VULN-INTOVERFLOW-L{line_idx}",
                        rule_id="SEC-01-INTEGER-OVERFLOW",
                        category="INTEGER_OVERFLOW",
                        severity="HIGH",
                        status="CONFIRMED",
                        file_path=filename,
                        line=line_idx,
                        column=0,
                        snippet=ev_line.strip(),
                        explanation="Constant integer expression overflow wraps around 32-bit signed integer limits.",
                        potential_consequences="Integer wraparound leading to incorrect allocation size or logic bypass (CWE-190).",
                        recommended_mitigation="Use 64-bit integer type (long long) or perform range checking before addition.",
                        is_confirmed=True,
                        is_prohibited=False,
                        requires_review=True,
                        cwe_id="CWE-190",
                        future_risks=[
                            "Integer overflow can lead to undersized buffer allocations followed by heap buffer overflow",
                            "Undefined behavior under standard C compiler optimizations can eliminate safety checks",
                        ],
                    ))

            # 4. Signed to unsigned conversion error (CWE-195)
            m_s2u = re.search(r'unsigned\s+[a-zA-Z0-9_]+\s*=\s*-[0-9]+', clean_code)
            if m_s2u:
                line_idx = clean_code.count("\n", 0, m_s2u.start()) + 1
                ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m_s2u.group(0)
                findings.append(SecurityApprovalGateFinding(
                    id=f"C-VULN-SIGNED2UNSIGNED-L{line_idx}",
                    rule_id="SEC-02-SIGNED-TO-UNSIGNED",
                    category="TYPE_CONVERSION",
                    severity="HIGH",
                    status="CONFIRMED",
                    file_path=filename,
                    line=line_idx,
                    column=0,
                    snippet=ev_line.strip(),
                    explanation="Negative value assigned to unsigned integer variable.",
                    potential_consequences="Wraps around to large positive integer, bypassing length or range checks (CWE-195).",
                    recommended_mitigation="Ensure values assigned to unsigned types are non-negative or validate range.",
                    is_confirmed=True,
                    is_prohibited=False,
                    requires_review=True,
                    cwe_id="CWE-195",
                    future_risks=[
                        "Large positive unsigned value can cause huge loop iterations or huge memory allocation requests",
                        "Bypasses validation checks that assume values are within sensible positive bounds",
                    ],
                ))
            else:
                neg_vars = set(re.findall(r'(?:int|short|long)\s+([a-zA-Z0-9_]+)\s*=\s*-[0-9]+', clean_code))
                for nv in neg_vars:
                    m = re.search(rf'unsigned\s+[a-zA-Z0-9_]+\s*=\s*{re.escape(nv)}\b', clean_code)
                    if m:
                        line_idx = clean_code.count("\n", 0, m.start()) + 1
                        ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m.group(0)
                        findings.append(SecurityApprovalGateFinding(
                            id=f"C-VULN-SIGNED2UNSIGNED-L{line_idx}",
                            rule_id="SEC-02-SIGNED-TO-UNSIGNED",
                            category="TYPE_CONVERSION",
                            severity="HIGH",
                            status="CONFIRMED",
                            file_path=filename,
                            line=line_idx,
                            column=0,
                            snippet=ev_line.strip(),
                            explanation=f"Negative signed variable '{nv}' assigned to unsigned integer variable.",
                            potential_consequences="Wraps around to large positive integer, bypassing length or range checks (CWE-195).",
                            recommended_mitigation="Ensure values assigned to unsigned types are non-negative or validate range.",
                            is_confirmed=True,
                            is_prohibited=False,
                            requires_review=True,
                            cwe_id="CWE-195",
                            future_risks=[
                                "Large positive unsigned value can cause huge loop iterations or huge memory allocation requests",
                                "Bypasses validation checks that assume values are within sensible positive bounds",
                            ],
                        ))
                        break

            # 5. Null pointer dereference: int *p = NULL; *p = ... without guard (CWE-476)
            null_ptrs = set(re.findall(r'\b([a-zA-Z0-9_]+)\s*=\s*NULL\b', clean_code))
            for np in null_ptrs:
                for m in re.finditer(rf'\*\s*{re.escape(np)}\b', clean_code):
                    prefix = clean_code[max(0, m.start() - 20):m.start()]
                    if re.search(r'\b(?:int|char|short|long|float|double|void|struct\s+\w+)\s*$', prefix):
                        continue
                    prev_block = clean_code[max(0, m.start() - 120):m.start()]
                    if not re.search(rf'if\s*\(\s*{re.escape(np)}\s*!=\s*NULL|if\s*\(\s*{re.escape(np)}\s*\)', prev_block):
                        line_idx = clean_code.count("\n", 0, m.start()) + 1
                        ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m.group(0)
                        findings.append(SecurityApprovalGateFinding(
                            id=f"C-VULN-NULLDEREF-L{line_idx}",
                            rule_id="SEC-03-NULL-DEREFERENCE",
                            category="NULL_DEREFERENCE",
                            severity="HIGH",
                            status="CONFIRMED",
                            file_path=filename,
                            line=line_idx,
                            column=0,
                            snippet=ev_line.strip(),
                            explanation=f"Dereference of pointer '{np}' that was explicitly initialized or assigned NULL.",
                            potential_consequences="Process crash via segmentation fault (SIGSEGV) or denial of service (CWE-476).",
                            recommended_mitigation=f"Check pointer validity before dereferencing: if ({np} != NULL) {{ ... }}",
                            is_confirmed=True,
                            is_prohibited=False,
                            requires_review=True,
                            cwe_id="CWE-476",
                            future_risks=[
                                "Segmentation fault crashing server process or local compiler execution",
                                "Potential local privilege escalation on platforms where NULL page mapping is allowed",
                            ],
                        ))
                        break

            # 6. Uninitialized scalar variable read (CWE-457)
            uninit_vars = set(re.findall(r'\b(?:int|short|long|char|float|double)\s+([a-zA-Z0-9_]+)\s*;', clean_code))
            for uv in list(uninit_vars):
                if re.search(rf'\b{re.escape(uv)}\s*\[', clean_code) or re.search(rf'\*\s*{re.escape(uv)}\b', clean_code):
                    continue
                m = re.search(rf'printf\s*\([^;]*\b{re.escape(uv)}\b', clean_code)
                if m:
                    pos = m.start()
                    if not re.search(rf'\b{re.escape(uv)}\s*=', clean_code[:pos]):
                        line_idx = clean_code.count("\n", 0, m.start()) + 1
                        ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m.group(0)
                        findings.append(SecurityApprovalGateFinding(
                            id=f"C-VULN-UNINITVAR-L{line_idx}",
                            rule_id="SEC-04-UNINITIALIZED-VARIABLE",
                            category="UNINITIALIZED_VARIABLE",
                            severity="HIGH",
                            status="CONFIRMED",
                            file_path=filename,
                            line=line_idx,
                            column=0,
                            snippet=ev_line.strip(),
                            explanation=f"Read of uninitialized scalar variable '{uv}'.",
                            potential_consequences="Information disclosure of uninitialized stack memory (CWE-457).",
                            recommended_mitigation=f"Initialize variable at declaration: int {uv} = 0;",
                            is_confirmed=True,
                            is_prohibited=False,
                            requires_review=True,
                            cwe_id="CWE-457",
                            future_risks=[
                                "Information leakage of leftover stack data (pointers, memory addresses, or sensitive values)",
                                "Unpredictable branching decisions and non-deterministic application behavior",
                            ],
                        ))

            # 7. Array out of bounds (CWE-119)
            for m in re.finditer(r'\b(?:int|char|short|long|float|double)\s+([a-zA-Z0-9_]+)\s*\[\s*(\d+)\s*\]\s*;', clean_code):
                arr_name, arr_size = m.group(1), int(m.group(2))
                for m_idx in re.finditer(rf'\b{re.escape(arr_name)}\s*\[\s*(\d+)\s*\]', clean_code[m.end():]):
                    real_pos = m.end() + m_idx.start()
                    prefix = clean_code[max(0, real_pos - 20):real_pos]
                    if re.search(r'\b(?:int|char|short|long|float|double)\s+$', prefix):
                        continue
                    idx_val = int(m_idx.group(1))
                    if idx_val >= arr_size:
                        line_idx = clean_code.count("\n", 0, real_pos) + 1
                        ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m_idx.group(0)
                        findings.append(SecurityApprovalGateFinding(
                            id=f"C-VULN-ARRAYOOB-L{line_idx}",
                            rule_id="SEC-05-ARRAY-OUT-OF-BOUNDS",
                            category="BUFFER_OVERFLOW",
                            severity="HIGH",
                            status="CONFIRMED",
                            file_path=filename,
                            line=line_idx,
                            column=0,
                            snippet=ev_line.strip(),
                            explanation=f"Array index {idx_val} out of bounds for array '{arr_name}[{arr_size}]'.",
                            potential_consequences="Out-of-bounds memory write or read (CWE-119 / CWE-787).",
                            recommended_mitigation=f"Ensure array index is strictly within [0, {arr_size - 1}].",
                            is_confirmed=True,
                            is_prohibited=False,
                            requires_review=True,
                            cwe_id="CWE-119",
                            future_risks=[
                                "Stack variable clobbering, arbitrary write primitives, and memory layout corruption",
                                "Control-flow hijacking by overwriting adjacent return addresses or saved frame pointers",
                            ],
                        ))
                        break

            # 8. Off-by-one loop boundary (CWE-193)
            for m in re.finditer(r'\b(?:int|char|short|long|float|double)\s+([a-zA-Z0-9_]+)\s*\[\s*(\d+)\s*\]\s*;', clean_code):
                arr_name, arr_size = m.group(1), int(m.group(2))
                m_loop = re.search(rf'for\s*\([^;]*;\s*([a-zA-Z0-9_]+)\s*<=\s*{arr_size}\s*;[^)]*\)[\s\S]*?\b{re.escape(arr_name)}\s*\[\s*\1\s*\]', clean_code)
                if m_loop:
                    line_idx = clean_code.count("\n", 0, m_loop.start()) + 1
                    ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m_loop.group(0)
                    findings.append(SecurityApprovalGateFinding(
                        id=f"C-VULN-OFFBYONE-L{line_idx}",
                        rule_id="SEC-06-OFF-BY-ONE",
                        category="BUFFER_OVERFLOW",
                        severity="HIGH",
                        status="CONFIRMED",
                        file_path=filename,
                        line=line_idx,
                        column=0,
                        snippet=ev_line.strip(),
                        explanation=f"Off-by-one loop boundary '<= {arr_size}' accesses 1 element past array '{arr_name}[{arr_size}]'.",
                        potential_consequences="Off-by-one stack overflow overwriting saved frame pointer (CWE-193).",
                        recommended_mitigation=f"Change loop condition to strictly less than: for (...; i < {arr_size}; ...)",
                        is_confirmed=True,
                        is_prohibited=False,
                        requires_review=True,
                        cwe_id="CWE-193",
                        future_risks=[
                            "Classic off-by-one overwrite of stack canary or low byte of saved frame pointer",
                            "Memory corruption leading to control flow divergence or code execution",
                        ],
                    ))

            # 9. Unsafe memcpy: memcpy(dst, src, size) exceeding buffer (CWE-120)
            for m_arr in re.finditer(r'\b(?:char|int|short)\s+([a-zA-Z0-9_]+)\s*\[\s*(\d+)\s*\]\s*;', clean_code):
                dst_name, dst_size = m_arr.group(1), int(m_arr.group(2))
                for m_cpy in re.finditer(rf'\bmemcpy\s*\(\s*{re.escape(dst_name)}\s*,\s*[^,]+,\s*(\d+)\s*\)', clean_code):
                    cpy_size = int(m_cpy.group(1))
                    if cpy_size > dst_size:
                        line_idx = clean_code.count("\n", 0, m_cpy.start()) + 1
                        ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m_cpy.group(0)
                        findings.append(SecurityApprovalGateFinding(
                            id=f"C-VULN-UNSAFEMEMCPY-L{line_idx}",
                            rule_id="SEC-07-UNSAFE-MEMCPY",
                            category="BUFFER_OVERFLOW",
                            severity="HIGH",
                            status="CONFIRMED",
                            file_path=filename,
                            line=line_idx,
                            column=0,
                            snippet=ev_line.strip(),
                            explanation=f"memcpy() buffer overflow: copying {cpy_size} bytes into {dst_size}-byte buffer '{dst_name}'.",
                            potential_consequences="Buffer overflow corrupting adjacent memory (CWE-120).",
                            recommended_mitigation=f"Ensure copy length does not exceed buffer size: sizeof({dst_name}).",
                            is_confirmed=True,
                            is_prohibited=False,
                            requires_review=True,
                            cwe_id="CWE-120",
                            future_risks=C_FUTURE_RISKS.get("strcpy", [
                                "Linear buffer overflow overwriting adjacent variables, function pointers, and return address",
                                "Exploitable for Return-Oriented Programming (ROP) attacks and arbitrary code execution",
                            ]),
                        ))
                        break

            # 10. Format specifier type mismatch (CWE-686)
            for m in re.finditer(r'\bprintf\s*\(\s*"[^"]*%d[^"]*"\s*,\s*("[^"]*")\s*\)', code_with_strings):
                line_idx = code_with_strings.count("\n", 0, m.start()) + 1
                ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m.group(0)
                findings.append(SecurityApprovalGateFinding(
                    id=f"C-VULN-FORMATMISMATCH-L{line_idx}",
                    rule_id="SEC-08-FORMAT-MISMATCH",
                    category="TYPE_MISMATCH",
                    severity="HIGH",
                    status="CONFIRMED",
                    file_path=filename,
                    line=line_idx,
                    column=0,
                    snippet=ev_line.strip(),
                    explanation="Format specifier %d expects integer argument but was supplied with string literal.",
                    potential_consequences="Type mismatch resulting in invalid memory interpretation or crash (CWE-686).",
                    recommended_mitigation="Use matching format specifier %s for string arguments.",
                    is_confirmed=True,
                    is_prohibited=False,
                    requires_review=True,
                    cwe_id="CWE-686",
                    future_risks=[
                        "Information leak or unexpected integer value printed instead of string data",
                        "Undefined behavior under varying ABI calling conventions",
                    ],
                ))

            # 11. Uninitialized pointer dereference (CWE-824)
            for m in re.finditer(r'\b(?:int|char|short|long|float|double)\s*\*\s*([a-zA-Z0-9_]+)\s*;', clean_code):
                ptr_name = m.group(1)
                m_deref = re.search(rf'\*\s*{re.escape(ptr_name)}\b', clean_code[m.end():])
                if m_deref:
                    pos = m.end() + m_deref.start()
                    prefix = clean_code[max(0, pos - 20):pos]
                    if re.search(r'\b(?:int|char|short|long|float|double|void|struct\s+\w+)\s*$', prefix):
                        continue
                    if not re.search(rf'\b{re.escape(ptr_name)}\s*=', clean_code[m.end():pos]):
                        line_idx = clean_code.count("\n", 0, pos) + 1
                        ev_line = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else m_deref.group(0)
                        findings.append(SecurityApprovalGateFinding(
                            id=f"C-VULN-UNINITPTR-L{line_idx}",
                            rule_id="SEC-10-UNINITIALIZED-POINTER",
                            category="UNINITIALIZED_POINTER",
                            severity="HIGH",
                            status="CONFIRMED",
                            file_path=filename,
                            line=line_idx,
                            column=0,
                            snippet=ev_line.strip(),
                            explanation=f"Dereference of uninitialized pointer '{ptr_name}'.",
                            potential_consequences="Wild pointer dereference causing arbitrary memory corruption or crash (CWE-824).",
                            recommended_mitigation=f"Initialize pointer before use: int *{ptr_name} = NULL;",
                            is_confirmed=True,
                            is_prohibited=False,
                            requires_review=True,
                            cwe_id="CWE-824",
                            future_risks=[
                                "Arbitrary memory write or read targeting uninitialized stack pointer garbage",
                                "Wild memory writes exploitable for code execution if attacker controls stack layout",
                            ],
                        ))
                        break

        # ------------------------------------------------------------------
        # 2b. Executable Dangerous Calls (Python)
        # ------------------------------------------------------------------
        if language == "python":
            # 2b.1 Run structured Python Security Rules AST analyzer (PY-SEC-01 through PY-SEC-09)
            try:
                from compiler.languages import python_security
                py_issues = python_security.analyze(source_code)
                for issue in py_issues:
                    rule = issue.get("rule", "PY-SEC-09")
                    line_no = int(issue.get("line", 1) or 1)
                    col_no = int(issue.get("col", 0) or 0)
                    msg = issue.get("message", "")
                    details = PYTHON_RULE_DETAILS.get(rule, PYTHON_RULE_DETAILS.get("PY-SEC-09", {}))
                    cwe = details.get("cwe", "CWE-20")
                    sev = details.get("severity", "HIGH")
                    reason_dangerous = details.get("reason_dangerous", msg)
                    threat = details.get("potential_threat", "Potential security vulnerability leading to system compromise.")
                    f_risks = details.get("future_risks", ["Unauthorized system access or data manipulation"])
                    rec_fix = details.get("recommended_fix", "Refactor to use safe standard library methods.")
                    evidence_line = lines[line_no - 1] if 1 <= line_no <= len(lines) else msg

                    findings.append(SecurityApprovalGateFinding(
                        id=f"PY-VULN-{rule}-L{line_no}",
                        rule_id=f"SEC-{rule}",
                        category="PYTHON_SECURITY_VULNERABILITY",
                        severity=sev,
                        status="CONFIRMED",
                        file_path=filename,
                        line=line_no,
                        column=col_no,
                        snippet=evidence_line.strip(),
                        explanation=reason_dangerous,
                        potential_consequences=threat,
                        recommended_mitigation=rec_fix,
                        is_confirmed=True,
                        is_prohibited=False,
                        requires_review=True,
                        has_repair_proposal=(issue.get("action") == "auto_fixed"),
                        cwe_id=cwe,
                        future_risks=f_risks,
                    ))
            except Exception:
                pass

            # Strip Python comments (lines starting with #) and string contents
            py_lines_raw = source_code.splitlines()
            py_clean_lines = []
            in_triple_quote = False
            tq_char = None
            for pl in py_lines_raw:
                stripped = pl.strip()
                # Track triple-quoted strings
                for tq in ('"""', "'''"):
                    count = stripped.count(tq)
                    if count % 2 == 1:
                        in_triple_quote = not in_triple_quote
                        tq_char = tq if in_triple_quote else None
                if in_triple_quote:
                    py_clean_lines.append("")
                    continue
                # Remove inline comments
                comment_pos = stripped.find("#")
                if comment_pos >= 0:
                    stripped = stripped[:comment_pos]
                py_clean_lines.append(stripped)
            py_clean_code = "\n".join(py_clean_lines)

            for pat_re, fn_key in PYTHON_DANGEROUS_PATTERNS:
                m = pat_re.search(py_clean_code)
                if m:
                    line_idx = py_clean_code.count("\n", 0, m.start()) + 1
                    evidence_line = py_lines_raw[line_idx - 1] if 1 <= line_idx <= len(py_lines_raw) else f"{fn_key}(...)"

                    # Lookup from the Python risk database
                    py_info = DANGEROUS_PYTHON_CALLS.get(fn_key)
                    if py_info:
                        fn_desc, cwe, sev, risks = py_info
                    else:
                        fn_desc = f"Potentially dangerous Python function '{fn_key}'"
                        cwe = "CWE-78"
                        sev = "HIGH"
                        risks = [f"Calling '{fn_key}' with untrusted input may lead to arbitrary code execution or system compromise."]

                    safe_key = re.sub(r'[^A-Z0-9_]', '_', fn_key.upper())
                    findings.append(SecurityApprovalGateFinding(
                        id=f"PY-DANGEROUS-{safe_key}-L{line_idx}",
                        rule_id=f"SEC-PY-DANGEROUS-{safe_key}",
                        category="DANGEROUS_FUNCTION",
                        severity=sev,
                        status="CONFIRMED",
                        file_path=filename,
                        line=line_idx,
                        column=m.start() - py_clean_code.rfind("\n", 0, m.start()) - 1,
                        snippet=evidence_line.strip(),
                        explanation=f"Dangerous Python function call detected: {fn_desc}.",
                        potential_consequences=f"Potential arbitrary code execution or system manipulation ({cwe}). " + (risks[0] if risks else ""),
                        recommended_mitigation=f"Remove or replace '{fn_key}()' with a safe alternative. Avoid passing untrusted input to this function.",
                        is_confirmed=True,
                        is_prohibited=False,
                        requires_review=True,
                        has_repair_proposal=False,
                        cwe_id=cwe,
                        future_risks=risks,
                    ))

        # ------------------------------------------------------------------
        # 3. Fast Static Syntax / Structure Check (In-Memory, No PyTorch)
        # ------------------------------------------------------------------
        syntax_errors = []
        if language == "python":
            try:
                compile(source_code, filename, "exec")
                checks_completed.append("Python Static Syntax Check")
            except SyntaxError as se:
                syntax_errors.append(str(se))
                checks_failed.append("Python Static Syntax Check")
        else:
            checks_completed.append("C Static Syntax Check")

        # ------------------------------------------------------------------
        # 4. Group Findings & Synthesize Decision
        # ------------------------------------------------------------------
        # Deduplicate findings by rule_id and line
        dedup_findings: List[SecurityApprovalGateFinding] = []
        seen_keys: Set[str] = set()
        for f in findings:
            key = f"{f.rule_id}:{f.line}:{f.category}"
            if key not in seen_keys:
                seen_keys.add(key)
                dedup_findings.append(f)

        findings_by_sev: Dict[str, List[Dict[str, Any]]] = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": [],
            "INFO": [],
        }
        for f in dedup_findings:
            sev_key = f.severity if f.severity in findings_by_sev else "HIGH"
            findings_by_sev[sev_key].append(f.to_dict())

        is_blocked = len(dedup_findings) > 0
        # Policy update: NEVER hard block. User can ALWAYS choose Continue anyway.
        can_override = True if is_blocked else False

        if is_blocked:
            if all(getattr(f, "is_manipulation", False) for f in dedup_findings):
                heading = "Instructions in Code Addressed to Automated Reviewer"
                policy_reason = (
                    f"Detected {len(dedup_findings)} instruction(s) in code addressed to an automated reviewer. "
                    "These directives do not make your program unsafe and will be masked from AI models upon continuation."
                )
                summary = f"Review required: {len(dedup_findings)} instruction(s) addressed to automated reviewer detected."
            else:
                heading = "Security Review Required"
                policy_reason = (
                    f"Security gate detected {len(dedup_findings)} finding(s) requiring review. "
                    "You may review the potential attacker threats, future risks, and choose 'Continue anyway' or 'Cancel'."
                )
                summary = f"Security review required: {len(dedup_findings)} finding(s) detected. User approval required before execution."
        else:
            heading = "Security Gate Passed"
            policy_reason = "All mandatory security prechecks passed."
            summary = "Program passed all security checks. Compilation and execution permitted."

        actions = [
            {
                "id": "continue_anyway",
                "label": "Continue anyway",
                "primary": True,
                "disabled": False,
                "description": "Acknowledge security warnings and proceed with execution. Flagged manipulation directives will be stripped before AI model processing.",
            },
            {
                "id": "cancel",
                "label": "Cancel",
                "primary": False,
                "disabled": False,
                "description": "Abort compilation and return to editor without executing.",
            },
            {
                "id": "approve_once",
                "label": "Continue anyway",
                "primary": True,
                "disabled": False,
                "description": "Authorize one-time execution attempt.",
            },
        ]
        return SecurityApprovalGateVerdict(
            is_blocked=is_blocked,
            can_override=can_override,
            heading=heading,
            filename=filename,
            source_hash=source_hash,
            operation=operation,
            summary=summary,
            policy_reason=policy_reason,
            findings=dedup_findings,
            findings_by_severity=findings_by_sev,
            security_checks_completed=checks_completed,
            security_checks_failed=checks_failed,
            has_repair_proposal=has_repair_proposal,
            actions=actions,
        )

    @classmethod
    def evaluate_and_verify(
        cls,
        source_code: str,
        filename: str = "main.c",
        language: str = "c",
        operation: str = "execute",
        approval_token: Optional[str] = None,
    ) -> Tuple[bool, SecurityApprovalGateVerdict]:
        """
        Runs the full evaluation. If blocked, attempts to verify and consume
        the provided approval_token. Returns (permitted_to_compile, verdict).
        """
        verdict = cls.evaluate(
            source_code=source_code,
            filename=filename,
            language=language,
            operation=operation,
        )

        if not verdict.is_blocked:
            return True, verdict

        # If blocked, check if user provided a valid approval token
        if approval_token:
            ok, msg = SecurityApprovalManager.verify_and_consume(
                token=approval_token,
                source_code=source_code,
                filename=filename,
                operation=operation,
            )
            if ok:
                # User authorized one execution
                verdict.policy_reason = f"Execution authorized via one-time user approval ({msg})."
                return True, verdict
            else:
                verdict.policy_reason = f"Execution blocked: {msg}"
                return False, verdict

        # Blocked and no valid approval provided
        return False, verdict


def enforce_security_gate_for_request(
    source_code: str,
    filename: str = "main.c",
    language: str = "c",
    operation: str = "execute",
    approval_token: Optional[str] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], int]:
    """
    Unified gate enforcement function across all API entry points:
    /api/coordinator/analyze_and_plan, /api/repair, execute/run, and /api/security/prescan.

    Returns:
      (permitted: bool, warning_payload_or_none: Optional[dict], http_status_code: int)
      - If permitted: (True, None, 200)
      - If blocked/warning: (False, warning_payload, 409)
    """
    source_code = source_code or ""
    if filename and filename.endswith((".py", ".py3")) and language in ("c", "C", ""):
        language = "python"
    permitted, verdict = SecurityDecisionGate.evaluate_and_verify(
        source_code=source_code,
        filename=filename,
        language=language,
        operation=operation,
        approval_token=approval_token,
    )
    if permitted:
        return True, None, 200

    # Record SHOWN decision in audit log
    SecurityApprovalManager.record_decision(
        decision="SHOWN",
        source_code=source_code,
        filename=filename,
        operation=operation,
        findings=verdict.findings,
        extra={"policy_reason": verdict.policy_reason},
    )

    payload = verdict.to_dict()
    payload["status"] = "SECURITY_WARNING"
    payload["http_status"] = 409
    clear_msg = verdict.policy_reason or "Security threat or vulnerability detected. Explicit user authorization required to proceed."
    payload["message"] = clear_msg
    payload["error"] = clear_msg
    return False, payload, 409
