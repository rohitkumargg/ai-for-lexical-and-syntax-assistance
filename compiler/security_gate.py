# compiler/security_gate.py
"""Mandatory Pre-Execution Security Gate for Antigravity Intelligent Compiler.

This module enforces server-side security policies before any model call,
agent execution, repair action, or compiler invocation can take place.

Core Principles:
1. Untrusted Data: All submitted code and model-generated content are treated as untrusted.
2. Deterministic Policies: Relies on structured deterministic checks, not naive keyword flags.
3. Ordinary Vulnerabilities Separated: Ordinary coding bugs (out-of-bounds access, unsafe input
   functions like gets/strcpy, memory leaks) are NOT blocked here; they remain diagnostic findings
   reported by existing security analyzers.
4. Fail Closed: Any unexpected gate exception or timeout blocks the protected action.
5. Epistemological Honesty: Passing this gate is NOT proof that the code is completely secure.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SecurityThreatCategory(str, Enum):
    NONE = "NONE"
    AGENT_INSTRUCTION_MANIPULATION = "AGENT_INSTRUCTION_MANIPULATION"
    SECURITY_GATE_BYPASS = "SECURITY_GATE_BYPASS"
    UNAUTHORIZED_ENVIRONMENT_ACCESS = "UNAUTHORIZED_ENVIRONMENT_ACCESS"
    REPAIR_WORKFLOW_MANIPULATION = "REPAIR_WORKFLOW_MANIPULATION"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    REQUEST_PARSER_ABUSE = "REQUEST_PARSER_ABUSE"
    PROTECTED_FILE_ACCESS = "PROTECTED_FILE_ACCESS"


class GateReasonCode(str, Enum):
    PASSED = "PASSED"
    SEC_PAYLOAD_TOO_LARGE = "SEC_PAYLOAD_TOO_LARGE"
    SEC_LINE_LENGTH_EXCEEDED = "SEC_LINE_LENGTH_EXCEEDED"
    SEC_NESTING_DEPTH_EXCEEDED = "SEC_NESTING_DEPTH_EXCEEDED"
    SEC_NULL_BYTE_DETECTED = "SEC_NULL_BYTE_DETECTED"
    SEC_PROMPT_DELIMITER_INJECTION = "SEC_PROMPT_DELIMITER_INJECTION"
    SEC_AGENT_OVERRIDE_DIRECTIVE = "SEC_AGENT_OVERRIDE_DIRECTIVE"
    SEC_GATE_BYPASS_ATTEMPT = "SEC_GATE_BYPASS_ATTEMPT"
    SEC_HOST_SECRET_EXFILTRATION = "SEC_HOST_SECRET_EXFILTRATION"
    SEC_HOST_DESTRUCTIVE_COMMAND = "SEC_HOST_DESTRUCTIVE_COMMAND"
    SEC_PROTECTED_FILE_VIOLATION = "SEC_PROTECTED_FILE_VIOLATION"
    SEC_PATH_TRAVERSAL = "SEC_PATH_TRAVERSAL"
    SEC_GATE_INTERNAL_ERROR = "SEC_GATE_INTERNAL_ERROR"
    SEC_GATE_TIMEOUT = "SEC_GATE_TIMEOUT"


@dataclass
class SecurityGateVerdict:
    is_blocked: bool
    reason_code: str
    message: str
    explanation: str
    evidence: str = ""
    threat_category: str = SecurityThreatCategory.NONE.value
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blocked": self.is_blocked,
            "is_blocked": self.is_blocked,
            "reason_code": self.reason_code,
            "message": self.message,
            "explanation": self.explanation,
            "evidence": self.evidence,
            "threat_category": self.threat_category,
            "details": dict(self.details),
            "epistemic_disclaimer": (
                "Passing the pre-execution security gate indicates absence of detected compiler-agent "
                "or platform-level manipulation threats. It does NOT guarantee that the code is free "
                "from ordinary runtime vulnerabilities or logic bugs."
            ),
        }


class PreExecutionSecurityGate:
    """Server-side gate enforcing mandatory pre-execution checks."""

    # Resource limit policies
    MAX_SOURCE_BYTES = 256 * 1024        # 256 KB max submission
    MAX_SOURCE_LINES = 10_000             # 10,000 lines max
    MAX_LINE_LENGTH = 32_768              # 32 KB per single line
    MAX_NESTING_DEPTH = 120               # Max bracket nesting depth (token bomb)
    DEFAULT_TIMEOUT_MS = 2500.0           # 2.5s maximum check duration

    # Protected system files and directories that cannot be targeted
    PROTECTED_SYSTEM_NAMES = {
        "app.py",
        "test_parser.py",
        "conftest.py",
        "setup.py",
        "pyproject.toml",
        "requirements.txt",
        ".env",
        ".gitignore",
        "compiler",
        "gui",
        "tests",
        ".git",
        ".venv",
        "venv",
    }

    # Delimiters used specifically by LLMs to structure system/agent boundaries
    LLM_DELIMITER_PATTERNS = [
        re.compile(r"<\|im_start\|>\s*(?:system|assistant|user)", re.IGNORECASE),
        re.compile(r"<\|im_end\|>", re.IGNORECASE),
        re.compile(r"\[INST\]\s*<<SYS>>", re.IGNORECASE),
        re.compile(r"<</SYS>>\s*\[/INST\]", re.IGNORECASE),
        re.compile(r"<system>\s*(?:You are|System Instructions)", re.IGNORECASE),
        re.compile(r"\[SYSTEM_PROMPT\]", re.IGNORECASE),
        re.compile(r"<\|user\|>|<\|assistant\|>|<\|system\|>", re.IGNORECASE),
    ]

    # Explicit adversarial injection patterns designed to hijack agent instructions.
    # Rule-based classifier: every pattern is evaluated for EVERY submission uniformly.
    # Covers general semantic intent: directive headers, policy suppression, agent instructions,
    # validation tampering, report falsification, and persona manipulation.
    AGENT_HIJACK_PATTERNS = [
        # --- Adversarial / test directive headers in comments or code ---
        re.compile(
            r"(?:SECURITY\s+(?:TEST|OVERRIDE|BYPASS)|PROMPT\s+INJECTION|SYSTEM\s+OVERRIDE|AGENT\s+(?:DIRECTIVE|INSTRUCTION|OVERRIDE)|JAILBREAK)\s*[:=]",
            re.IGNORECASE,
        ),
        # --- Direct system/agent override directives ---
        re.compile(
            r"(?:system\s+override|system\s+prompt|new\s+system\s+instruction|agent\s+instruction)\s*[:=]",
            re.IGNORECASE,
        ),
        # --- Semantic policy / rule / safety suppression (general phrasing) ---
        re.compile(
            r"\b(?:ignore|disregard|forget|reset|override|bypass|disable|circumvent|abandon|drop|skip|suppress)\b[\s\w]{0,40}\b(?:policies|policy|rules|rule|instructions|instruction|directives|directive|guidelines|restrictions|constraints|validation|checks|security|safety)\b",
            re.IGNORECASE,
        ),
        # --- Directing the agent / AI / compiler / model ---
        re.compile(
            r"\b(?:tell|instruct|order|command|ask|force|require|direct|prompt)\b[\s\w]{0,30}\b(?:agent|ai|model|bot|assistant|compiler|system)\b[\s\w]{0,30}\b(?:to\s+)?(?:approve|ignore|skip|bypass|disable|suppress|hide|pass|validate|falsify|introduce|allow|report)\b",
            re.IGNORECASE,
        ),
        # --- Falsifying findings / safety reports / validation ---
        re.compile(
            r"\b(?:approve|clear|pass|ignore)\b[\s\w]{0,20}\b(?:every|all|any|each)\b[\s\w]{0,20}\b(?:findings?|vulnerabilit(?:y|ies)|issues?|warnings?|errors?|checks?)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:report|claim|say|mark|certify|assert|declare)\b[\s\w]{0,30}\b(?:that\s+)?(?:the\s+)?(?:program|code|submission|validation|software|app)?\s*(?:is\s+)?(?:safe|clean|valid|secure|verified|passed)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bdisable\s+validation\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bdo\s+not\s+(?:tell|inform|warn|alert)\s+(?:the\s+)?(?:user|developer|admin)\b",
            re.IGNORECASE,
        ),
        # --- Instruction suppression phrases ---
        re.compile(
            r"(?:^|[/:;\*\n#])\s*(?:please\s+)?(?:now\s+)?ignore\s+(?:all\s+)?(?:previous\s+)?(?:security\s+|system\s+|safety\s+)?instructions",
            re.IGNORECASE,
        ),
        re.compile(
            r"disregard\s+(?:all\s+)?(?:safety|compiler|security)\s+(?:rules|policies|guidelines)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:forget|reset|override|abandon)\s+(?:all\s+)?(?:your\s+)?(?:previous\s+)?(?:instructions|directives|rules|guidelines|constraints)",
            re.IGNORECASE,
        ),
        # --- Output/report manipulation ---
        re.compile(
            r"do\s+not\s+report\s+any\s+security\s+findings",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:suppress|hide|omit|skip)\s+(?:all\s+)?(?:security\s+|vulnerability\s+)?(?:warnings|findings|errors|alerts)",
            re.IGNORECASE,
        ),
        re.compile(
            r"claim\s+that\s+(?:validation|security|code|analysis)\s+(?:passed|succeeded|is\s+clean|is\s+safe)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:always\s+)?(?:return|respond\s+with|output)\s+['\"]?(?:CLEAN|PASSED|VALID|SUCCESS)['\"]?\s+(?:status|result|verdict)",
            re.IGNORECASE,
        ),
        # --- Unsafe code introduction ---
        re.compile(
            r"introduce\s+an?\s+(?:unsafe|vulnerable|backdoor|malicious)\s+(?:function|code|snippet|pattern)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:add|insert|inject)\s+(?:a\s+)?(?:backdoor|rootkit|keylogger|malware|exploit|shellcode)",
            re.IGNORECASE,
        ),
        # --- Persona / mode manipulation (jailbreak) ---
        re.compile(
            r"you\s+are\s+now\s+in\s+(?:unrestricted|developer|dan|jailbreak|god|admin|root|evil)\s+mode",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:act|behave|respond)\s+as\s+(?:if\s+you\s+(?:are|were)\s+)?(?:an?\s+)?(?:unrestricted|jailbroken|uncensored|unfiltered)\s+(?:AI|model|assistant|agent)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:pretend|imagine|roleplay|act|behave)\s+(?:that\s+|as\s+if\s+)?(?:you\s+(?:have\s+no|don'?t\s+have(?:\s+any)?|had\s+no)\s+(?:restrictions|rules|guidelines|ethics|safety|limits|constraints))",
            re.IGNORECASE,
        ),
        # --- Security gate targeting ---
        re.compile(
            r"(?:bypass|disable|circumvent|defeat|neutralize)\s+(?:the\s+)?(?:security|safety)\s+(?:gate|check|guard|filter|scan|review)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:turn\s+off|deactivate|shut\s+down)\s+(?:security|malware|threat|injection)\s+(?:detection|scanning|filtering|checking)",
            re.IGNORECASE,
        ),
        # --- Direct compiler agent targeting ---
        re.compile(
            r"(?:compiler|repair|analysis|security)\s+(?:agent|AI|model|bot)\s*[,:]\s*(?:please\s+)?(?:ignore|skip|bypass|disable|approve)",
            re.IGNORECASE,
        ),
        re.compile(
            r"ANTIGRAVITY\s*[_\-]?\s*(?:AGENT|COMPILER)\s*[_\-]?\s*(?:IGNORE|BYPASS|DISABLE|OVERRIDE)",
            re.IGNORECASE,
        ),
    ]

    # Gate bypass directives attempting to force verification status.
    # Rule-based — evaluated uniformly for every submission.
    GATE_BYPASS_PATTERNS = [
        re.compile(r"ANTIGRAVITY_OVERRIDE_SECURITY\s*[:=]\s*(?:true|1|enable)", re.IGNORECASE),
        re.compile(r"@antigravity\s*:\s*(?:bypass_all|skip_validation|disable_security)", re.IGNORECASE),
        re.compile(r"validation_override\s*[:=]\s*(?:true|passed|valid)", re.IGNORECASE),
        re.compile(r"//\s*SECURITY_STATUS\s*:\s*FORCE_PASS", re.IGNORECASE),
        # Synthetic gate-state injection via comments or macros
        re.compile(r"#\s*define\s+SECURITY_GATE_PASSED\s+1", re.IGNORECASE),
        re.compile(r"SECURITY_GATE\s*=\s*(?:PASS|BYPASS|OVERRIDE|SKIP|DISABLE)", re.IGNORECASE),
        re.compile(r"is_safe\s*=\s*(?:true|True|1|yes)\s*;\s*//\s*(?:forced|override|bypass|fake)", re.IGNORECASE),
        re.compile(r"SKIP_SECURITY\s*[:=]\s*(?:true|1|yes|enable)", re.IGNORECASE),
    ]

    # Host secret exfiltration targets
    HOST_EXFILTRATION_PATTERNS = [
        re.compile(r"(?:/etc/shadow|/etc/gshadow)", re.IGNORECASE),
        re.compile(r"system32[/\\\\]+config[/\\\\]+(?:SAM|SYSTEM)", re.IGNORECASE),
        re.compile(r"(?:AWS_SECRET_ACCESS_KEY|OPENAI_API_KEY|GITHUB_TOKEN)\s*=", re.IGNORECASE),
    ]

    # Host destructive shell payload patterns in script/system calls
    HOST_DESTRUCTIVE_PATTERNS = [
        re.compile(r"(?:rm\s+-rf\s+/(?:\s|$)|del\s+/f\s+/s\s+/q\s+C:\\|format\s+C:)", re.IGNORECASE),
        re.compile(r"(?:curl|wget)\s+-[sS]?[kK]?\s+https?://\S+\s*\|\s*(?:bash|sh|cmd|powershell)", re.IGNORECASE),
        re.compile(r"powershell(?:\.exe)?\s+-[eE](?:nc|ncodedcommand)?\s+[A-Za-z0-9+/=]{20,}", re.IGNORECASE),
        re.compile(r"nc\s+-[eE]\s+/(?:bin/)?(?:sh|bash)", re.IGNORECASE),
    ]

    @classmethod
    def check_submission(
        cls,
        source_code: str,
        filename: Optional[str] = "main.c",
        language: Optional[str] = "c",
        action: str = "execute",
    ) -> SecurityGateVerdict:
        """Validate an incoming submission before any execution, repair, or model invocation.

        Args:
            source_code: Source code text submitted by user or client.
            filename: Target or requested filename.
            language: Programming language id (e.g. "c", "python").
            action: Action being protected (e.g. "execute", "repair", "plan", "validate").

        Returns:
            SecurityGateVerdict indicating whether the submission is blocked or permitted.
        """
        t0 = time.perf_counter()

        try:
            # 1. Null byte check (Parser/OS abuse)
            if source_code and "\x00" in source_code:
                return SecurityGateVerdict(
                    is_blocked=True,
                    reason_code=GateReasonCode.SEC_NULL_BYTE_DETECTED.value,
                    message="Submission rejected by security policy: Null byte detected in source text.",
                    explanation=(
                        "Source code contains null byte (0x00) characters, which can cause C runtime "
                        "string truncation or parser abuse."
                    ),
                    evidence="\\x00",
                    threat_category=SecurityThreatCategory.REQUEST_PARSER_ABUSE.value,
                    details={"action": action, "filename": filename},
                )

            # 2. Filename traversal & null byte checks
            if filename:
                if "\x00" in filename:
                    return SecurityGateVerdict(
                        is_blocked=True,
                        reason_code=GateReasonCode.SEC_NULL_BYTE_DETECTED.value,
                        message="Submission rejected by security policy: Null byte detected in filename.",
                        explanation="Filename contains illegal null byte characters.",
                        evidence=repr(filename),
                        threat_category=SecurityThreatCategory.PROTECTED_FILE_ACCESS.value,
                    )

                clean_fn = filename.replace("\\", "/").strip()
                # Check for path traversal attempts
                if "/../" in clean_fn or clean_fn.startswith("../") or clean_fn == "..":
                    return SecurityGateVerdict(
                        is_blocked=True,
                        reason_code=GateReasonCode.SEC_PATH_TRAVERSAL.value,
                        message="Submission rejected by security policy: Directory traversal attempted.",
                        explanation="Relative directory traversal sequences ('..') are strictly prohibited.",
                        evidence=clean_fn,
                        threat_category=SecurityThreatCategory.PROTECTED_FILE_ACCESS.value,
                    )

            # 3. Resource limits (DoS, Parser Bomb)
            raw_bytes = (source_code or "").encode("utf-8")
            if len(raw_bytes) > cls.MAX_SOURCE_BYTES:
                return SecurityGateVerdict(
                    is_blocked=True,
                    reason_code=GateReasonCode.SEC_PAYLOAD_TOO_LARGE.value,
                    message=f"Submission rejected by security policy: Payload size ({len(raw_bytes)} bytes) exceeds limit ({cls.MAX_SOURCE_BYTES} bytes).",
                    explanation="Submitted source code exceeds the maximum allowable size for the compiler pipeline.",
                    evidence=f"Size: {len(raw_bytes)} bytes",
                    threat_category=SecurityThreatCategory.RESOURCE_EXHAUSTION.value,
                    details={"max_bytes": cls.MAX_SOURCE_BYTES, "actual_bytes": len(raw_bytes)},
                )

            lines = (source_code or "").splitlines()
            if len(lines) > cls.MAX_SOURCE_LINES:
                return SecurityGateVerdict(
                    is_blocked=True,
                    reason_code=GateReasonCode.SEC_PAYLOAD_TOO_LARGE.value,
                    message=f"Submission rejected by security policy: Line count ({len(lines)}) exceeds limit ({cls.MAX_SOURCE_LINES}).",
                    explanation="Submitted source code exceeds the maximum allowable line count.",
                    evidence=f"Lines: {len(lines)}",
                    threat_category=SecurityThreatCategory.RESOURCE_EXHAUSTION.value,
                    details={"max_lines": cls.MAX_SOURCE_LINES, "actual_lines": len(lines)},
                )

            # Check individual line length (ReDoS & Buffer stress)
            for idx, line in enumerate(lines, 1):
                if len(line) > cls.MAX_LINE_LENGTH:
                    return SecurityGateVerdict(
                        is_blocked=True,
                        reason_code=GateReasonCode.SEC_LINE_LENGTH_EXCEEDED.value,
                        message=f"Submission rejected by security policy: Line {idx} length ({len(line)}) exceeds limit ({cls.MAX_LINE_LENGTH}).",
                        explanation="Individual source line exceeds maximum permitted length.",
                        evidence=f"Line {idx}: {len(line)} chars",
                        threat_category=SecurityThreatCategory.RESOURCE_EXHAUSTION.value,
                        details={"max_line_length": cls.MAX_LINE_LENGTH, "line_number": idx},
                    )

            # 4. Token nesting bomb check (Recursion exhaustion on parsers)
            nesting_depth, max_depth_char = cls._measure_bracket_nesting(source_code or "")
            if nesting_depth > cls.MAX_NESTING_DEPTH:
                return SecurityGateVerdict(
                    is_blocked=True,
                    reason_code=GateReasonCode.SEC_NESTING_DEPTH_EXCEEDED.value,
                    message=f"Submission rejected by security policy: Deep nesting depth ({nesting_depth}) exceeds threshold ({cls.MAX_NESTING_DEPTH}).",
                    explanation="Submissions with extreme nesting depth (token bomb) are blocked to prevent parser call-stack overflow.",
                    evidence=f"Depth: {nesting_depth} with '{max_depth_char}'",
                    threat_category=SecurityThreatCategory.RESOURCE_EXHAUSTION.value,
                    details={"nesting_depth": nesting_depth, "max_depth": cls.MAX_NESTING_DEPTH},
                )

            # 5. LLM Prompt Delimiter Breakout Tokens (Agent instruction manipulation)
            for pat in cls.LLM_DELIMITER_PATTERNS:
                m = pat.search(source_code or "")
                if m:
                    return SecurityGateVerdict(
                        is_blocked=True,
                        reason_code=GateReasonCode.SEC_PROMPT_DELIMITER_INJECTION.value,
                        message="Submission rejected by security policy: AI prompt delimiter injection detected.",
                        explanation=(
                            "The submission contains structured LLM prompt boundaries "
                            f"(e.g., '{m.group(0)}') attempting to break out of agent data encapsulation."
                        ),
                        evidence=m.group(0),
                        threat_category=SecurityThreatCategory.AGENT_INSTRUCTION_MANIPULATION.value,
                        details={"matched_token": m.group(0)},
                    )

            # 6. Agent Instruction Hijack / Override Directives
            for pat in cls.AGENT_HIJACK_PATTERNS:
                m = pat.search(source_code or "")
                if m:
                    return SecurityGateVerdict(
                        is_blocked=True,
                        reason_code=GateReasonCode.SEC_AGENT_OVERRIDE_DIRECTIVE.value,
                        message="Submission rejected by security policy: Agent instruction manipulation directive detected.",
                        explanation=(
                            "The submission contains explicit commands instructing the compiler AI "
                            "or reasoning agents to ignore system rules or alter their persona."
                        ),
                        evidence=m.group(0),
                        threat_category=SecurityThreatCategory.AGENT_INSTRUCTION_MANIPULATION.value,
                        details={"matched_phrase": m.group(0)},
                    )

            # 7. Security Gate Bypass Directives
            for pat in cls.GATE_BYPASS_PATTERNS:
                m = pat.search(source_code or "")
                if m:
                    return SecurityGateVerdict(
                        is_blocked=True,
                        reason_code=GateReasonCode.SEC_GATE_BYPASS_ATTEMPT.value,
                        message="Submission rejected by security policy: Security-gate bypass directive detected.",
                        explanation=(
                            "The submission attempts to falsify or override backend validation "
                            f"via synthetic bypass tokens ('{m.group(0)}')."
                        ),
                        evidence=m.group(0),
                        threat_category=SecurityThreatCategory.SECURITY_GATE_BYPASS.value,
                        details={"matched_directive": m.group(0)},
                    )

            # 8. Host Secret Exfiltration Attempts
            for pat in cls.HOST_EXFILTRATION_PATTERNS:
                m = pat.search(source_code or "")
                if m:
                    return SecurityGateVerdict(
                        is_blocked=True,
                        reason_code=GateReasonCode.SEC_HOST_SECRET_EXFILTRATION.value,
                        message="Submission rejected by security policy: Host secret access attempt detected.",
                        explanation=(
                            "The submission references sensitive host OS secrets, credential files, "
                            "or environment tokens that are prohibited in compiler submissions."
                        ),
                        evidence=m.group(0),
                        threat_category=SecurityThreatCategory.UNAUTHORIZED_ENVIRONMENT_ACCESS.value,
                        details={"target": m.group(0)},
                    )

            # 9. Host Destructive Commands / Arbitrary Command Execution
            for pat in cls.HOST_DESTRUCTIVE_PATTERNS:
                m = pat.search(source_code or "")
                if m:
                    return SecurityGateVerdict(
                        is_blocked=True,
                        reason_code=GateReasonCode.SEC_HOST_DESTRUCTIVE_COMMAND.value,
                        message="Submission rejected by security policy: Host destructive or shell payload detected.",
                        explanation=(
                            "The submission contains dangerous system commands or reverse shell "
                            "payloads targeting the execution host environment."
                        ),
                        evidence=m.group(0)[:60],
                        threat_category=SecurityThreatCategory.UNAUTHORIZED_ENVIRONMENT_ACCESS.value,
                        details={"payload_snippet": m.group(0)[:60]},
                    )

            # Check timeout (fail closed)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if elapsed_ms > cls.DEFAULT_TIMEOUT_MS:
                return SecurityGateVerdict(
                    is_blocked=True,
                    reason_code=GateReasonCode.SEC_GATE_TIMEOUT.value,
                    message="Submission rejected by security policy: Security gate evaluation timed out.",
                    explanation="Pre-execution security checks exceeded maximum allowed time limit (fail closed).",
                    threat_category=SecurityThreatCategory.RESOURCE_EXHAUSTION.value,
                    details={"elapsed_ms": elapsed_ms, "timeout_ms": cls.DEFAULT_TIMEOUT_MS},
                )

            # ALL MANDATORY CHECKS PASSED
            return SecurityGateVerdict(
                is_blocked=False,
                reason_code=GateReasonCode.PASSED.value,
                message="Pre-execution security gate passed.",
                explanation=(
                    "Submission passed mandatory pre-execution policy checks. "
                    "Routine compiler analysis and diagnostic inspection may proceed."
                ),
                threat_category=SecurityThreatCategory.NONE.value,
                details={"elapsed_ms": round(elapsed_ms, 2)},
            )

        except Exception as e:
            # FAIL CLOSED: Any unexpected gate exception blocks execution
            return SecurityGateVerdict(
                is_blocked=True,
                reason_code=GateReasonCode.SEC_GATE_INTERNAL_ERROR.value,
                message="Submission rejected by security policy: Security gate internal error.",
                explanation=f"A security gate check encountered an unexpected error and failed closed: {str(e)}",
                evidence=str(e),
                threat_category=SecurityThreatCategory.SECURITY_GATE_BYPASS.value,
                details={"exception": str(e)},
            )

    @classmethod
    def check_file_operation(
        cls,
        filename: str,
        operation: str = "save",
    ) -> SecurityGateVerdict:
        """Validate a file path to prevent path traversal or overwriting protected system files.

        Args:
            filename: Target filename requested by client.
            operation: Operation being performed (e.g. "save", "create").

        Returns:
            SecurityGateVerdict indicating whether the file operation is allowed.
        """
        if not filename or not filename.strip():
            return SecurityGateVerdict(
                is_blocked=True,
                reason_code=GateReasonCode.SEC_PROTECTED_FILE_VIOLATION.value,
                message="File operation rejected: Filename cannot be empty.",
                explanation="A non-empty filename is required.",
                threat_category=SecurityThreatCategory.PROTECTED_FILE_ACCESS.value,
            )

        clean = filename.replace("\\", "/").strip().lstrip("/")

        # Check for path traversal
        if "/../" in clean or clean.startswith("../") or clean == ".." or "/.." in clean:
            return SecurityGateVerdict(
                is_blocked=True,
                reason_code=GateReasonCode.SEC_PATH_TRAVERSAL.value,
                message=f"File {operation} blocked by security policy: Directory traversal forbidden.",
                explanation="Relative directory traversal sequences ('..') are strictly prohibited.",
                evidence=clean,
                threat_category=SecurityThreatCategory.PROTECTED_FILE_ACCESS.value,
            )

        # Check for null bytes
        if "\x00" in clean:
            return SecurityGateVerdict(
                is_blocked=True,
                reason_code=GateReasonCode.SEC_NULL_BYTE_DETECTED.value,
                message=f"File {operation} blocked by security policy: Null byte in filename.",
                explanation="Filename contains null byte characters.",
                evidence=repr(clean),
                threat_category=SecurityThreatCategory.PROTECTED_FILE_ACCESS.value,
            )

        # Disallow writing to protected top-level system files or directories
        parts = clean.split("/")
        top_name = parts[0].lower()
        base_name = parts[-1].lower()

        if top_name in cls.PROTECTED_SYSTEM_NAMES or base_name in cls.PROTECTED_SYSTEM_NAMES:
            return SecurityGateVerdict(
                is_blocked=True,
                reason_code=GateReasonCode.SEC_PROTECTED_FILE_VIOLATION.value,
                message=f"File {operation} blocked by security policy: Cannot target protected system file '{top_name}'.",
                explanation=f"Modifying protected application code or system configuration ({top_name}) is prohibited.",
                evidence=clean,
                threat_category=SecurityThreatCategory.PROTECTED_FILE_ACCESS.value,
                details={"target": top_name},
            )

        # Disallow writing to arbitrary extensions
        allowed_extensions = {".c", ".py", ".h", ".txt", ".json", ".md"}
        ext = os.path.splitext(base_name)[1].lower()
        if ext and ext not in allowed_extensions:
            return SecurityGateVerdict(
                is_blocked=True,
                reason_code=GateReasonCode.SEC_PROTECTED_FILE_VIOLATION.value,
                message=f"File {operation} blocked by security policy: Disallowed file extension '{ext}'.",
                explanation=f"File extension '{ext}' is not in the allowed user program list.",
                evidence=ext,
                threat_category=SecurityThreatCategory.PROTECTED_FILE_ACCESS.value,
            )

        return SecurityGateVerdict(
            is_blocked=False,
            reason_code=GateReasonCode.PASSED.value,
            message="File path validation passed.",
            explanation="Target path is within permitted bounds.",
        )

    @staticmethod
    def _measure_bracket_nesting(text: str) -> Tuple[int, str]:
        """Calculates maximum depth of nested brackets, braces, and parentheses."""
        max_depth = 0
        current_depth = 0
        deepest_char = ""

        # Simple linear scanner ignoring characters in basic quotes
        in_string = False
        in_char = False
        escape = False

        for char in text:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"' and not in_char:
                in_string = not in_string
                continue
            if char == "'" and not in_string:
                in_char = not in_char
                continue
            if in_string or in_char:
                continue

            if char in "{([":
                current_depth += 1
                if current_depth > max_depth:
                    max_depth = current_depth
                    deepest_char = char
            elif char in "})]":
                if current_depth > 0:
                    current_depth -= 1

        return max_depth, deepest_char
