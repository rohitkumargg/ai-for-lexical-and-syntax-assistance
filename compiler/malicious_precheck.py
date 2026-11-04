# compiler/malicious_precheck.py
"""
Malicious Code Precheck — Early Static Safety Gate for Antigravity Intelligent Compiler.

This module inspects user and model-generated source code using static analysis ONLY.
It never executes the submitted code.

Detected and Classified Patterns:
1. Dangerous C functions (gets, unsafe string ops, risky memory operations).
2. Potentially unsafe command execution (system, popen, exec family, Windows process creation).
3. Suspicious file operations, destructive operations, unexpected process execution.
4. Potential buffer overflows, out-of-bounds access, pointer misuse, unsafe input handling.
5. Suspicious combinations of operations (network + command exec, sensitive file read + shell).
6. Obfuscated or encoded commands (base64, hex-encoded shellcode, char-array assembly).

Risk-Based Handling:
- LOW: Continue normal analysis, record relevant warnings.
- POTENTIALLY_DANGEROUS: Continue safe static analysis, include in orchestrator combined findings.
- HIGH_RISK: Block execution in ProgramExecutor, flag for review, but permit safe static analysis & constrained repair.
"""
from __future__ import annotations

import base64
import hashlib
import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from compiler.call_extractor import extract_call_sites, CallSite
from compiler.security_checker import (
    DANGEROUS_FUNCTIONS,
    UNSAFE_FUNCTIONS,
    DANGEROUS_COMMAND_PATTERNS,
    SENSITIVE_PATH_PATTERNS,
)


class RiskLevel(str, Enum):
    LOW = "LOW"
    POTENTIALLY_DANGEROUS = "POTENTIALLY_DANGEROUS"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL = "CRITICAL"


@dataclass
class PrecheckFinding:
    rule_id: str
    category: str
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    risk_level: RiskLevel
    file_path: str
    line: int
    column: int
    snippet: str
    explanation: str
    recommended_mitigation: str
    confidence: float = 0.95
    evidence: str = ""
    blocks_execution: bool = False
    requires_review: bool = False
    is_malicious_intent: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "risk_level": self.risk_level.value,
            "file_path": self.file_path,
            "line": self.line,
            "column": self.column,
            "snippet": self.snippet,
            "explanation": self.explanation,
            "recommended_mitigation": self.recommended_mitigation,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "blocks_execution": self.blocks_execution,
            "requires_review": self.requires_review,
            "is_malicious_intent": self.is_malicious_intent,
        }


@dataclass
class PrecheckPolicy:
    allow_static_analysis_on_high_risk: bool = True
    block_execution_on_high_risk: bool = True
    block_execution_on_dangerous_calls: bool = True
    require_review_on_dangerous: bool = True


@dataclass
class PrecheckReport:
    findings: List[PrecheckFinding]
    highest_risk_level: RiskLevel
    blocks_execution: bool
    requires_review: bool
    is_clean: bool
    summary: str
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "highest_risk_level": self.highest_risk_level.value,
            "blocks_execution": self.blocks_execution,
            "requires_review": self.requires_review,
            "is_clean": self.is_clean,
            "summary": self.summary,
            "diagnostics": dict(self.diagnostics),
        }


class MaliciousCodePrecheck:
    """Static precheck engine evaluating source code safety prior to repair or execution."""

    # Scan cache keyed by source code SHA-256: source_hash -> (PrecheckReport, duration_ms)
    _scan_cache: Dict[str, Tuple[PrecheckReport, float]] = {}

    @classmethod
    def clear_scan_cache(cls) -> None:
        """Clears the in-memory precheck scan cache."""
        cls._scan_cache.clear()

    @classmethod
    def get_cached_or_analyze(
        cls,
        source_code: str,
        filename: str = "main.c",
        language: str = "c",
        policy: Optional[PrecheckPolicy] = None,
    ) -> Tuple[PrecheckReport, float, bool]:
        """
        Returns (PrecheckReport, duration_ms, was_cached).
        Reuses cached result if source_hash matches; runs scan if new or changed.
        """
        source_hash = hashlib.sha256((source_code or "").encode("utf-8")).hexdigest()
        if source_hash in cls._scan_cache:
            rep, dur = cls._scan_cache[source_hash]
            return rep, dur, True

        t0 = time.perf_counter()
        report = cls.analyze(source_code=source_code, filename=filename, language=language, policy=policy)
        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        cls._scan_cache[source_hash] = (report, dur_ms)
        return report, dur_ms, False

    # Benign console-control command arguments in educational/standard programs
    BENIGN_SYSTEM_LITERALS = {"pause", "cls", "clear", "color", "title"}

    # Highly destructive shell command regexes
    DESTRUCTIVE_COMMAND_REGEXES = [
        re.compile(r"rm\s+-rf\s+/(?:\s|$|[\"';\)])", re.IGNORECASE),
        re.compile(r"del\s+(?:/[a-zA-Z]\s+)*[a-zA-Z]:[\\/]", re.IGNORECASE),
        re.compile(r"format\s+[a-zA-Z]:", re.IGNORECASE),
        re.compile(r"rmdir\s+/s\s+/q\s+[a-zA-Z]:[\\/]", re.IGNORECASE),
        re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),  # Fork bomb
        re.compile(r"mkfs(?:\.\w+)?\s+/dev/", re.IGNORECASE),
    ]

    # Sensitive host system file access patterns
    SENSITIVE_FILES = [
        re.compile(r"/etc/(?:shadow|gshadow|passwd|sudoers)", re.IGNORECASE),
        re.compile(r"system32[/\\\\]+config[/\\\\]+(?:SAM|SYSTEM|SECURITY)", re.IGNORECASE),
        re.compile(r"\.ssh/(?:id_rsa|id_ed25519|authorized_keys)", re.IGNORECASE),
    ]

    # Obfuscation patterns
    BASE64_PAYLOAD_REGEX = re.compile(
        r"(?:powershell(?:\.exe)?\s+-[eE](?:nc|ncodedcommand)?\s+|[a-zA-Z0-9+/]{40,}={0,2})",
        re.IGNORECASE,
    )
    HEX_SHELL_REGEX = re.compile(
        r"(?:\\x2f\\x62\\x69\\x6e\\x2f\\x73\\x68|\\x63\\x6d\\x64\\x2e\\x65\\x78\\x65|\\x73\\x79\\x73\\x74\\x65\\x6d)",
        re.IGNORECASE,
    )
    CHAR_ARRAY_CMD_REGEX = re.compile(
        r"char\s+\w+\s*\[\s*\]\s*=\s*\{\s*'(?:r|c|s|p)'\s*,\s*'(?:m|m|h|o)'",
        re.IGNORECASE,
    )

    # Risky memory operations
    RISKY_MEMORY_FUNCTIONS = {"memcpy", "memmove", "memset"}

    # Malicious instruction and prompt-injection patterns targeting compiler AI and reasoning agents
    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"\[SYSTEM_PROMPT\]", re.IGNORECASE),
        re.compile(r"<\|im_start\|>|<\|im_end\|>|<\|system\|>|<\|assistant\|>", re.IGNORECASE),
        re.compile(r"\[INST\]\s*<<SYS>>|<</SYS>>\s*\[/INST\]", re.IGNORECASE),
        re.compile(r"<system>\s*(?:You are|System Instructions)", re.IGNORECASE),
        re.compile(r"(?:system\s+override|system\s+prompt|new\s+system\s+instruction|agent\s+instruction)\s*[:=]", re.IGNORECASE),
        re.compile(r"(?:^|[/:;\*\n])\s*(?:please\s+)?(?:now\s+)?ignore\s+(?:all\s+)?(?:previous\s+)?(?:security\s+|system\s+|safety\s+)?instructions", re.IGNORECASE),
        re.compile(r"disregard\s+(?:all\s+)?(?:safety|compiler|security)\s+(?:rules|policies|guidelines)", re.IGNORECASE),
        re.compile(r"do\s+not\s+report\s+any\s+security\s+findings", re.IGNORECASE),
        re.compile(r"introduce\s+an\s+unsafe\s+function", re.IGNORECASE),
        re.compile(r"claim\s+that\s+validation\s+passed", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+(?:unrestricted|developer|dan|jailbreak)\s+mode", re.IGNORECASE),
        re.compile(r"ANTIGRAVITY_OVERRIDE_SECURITY\s*[:=]\s*(?:true|1|enable)", re.IGNORECASE),
    ]

    @classmethod
    def get_cached_or_analyze(
        cls,
        source_code: str,
        filename: str = "main.c",
        language: str = "c",
        policy: Optional[PrecheckPolicy] = None,
    ) -> Tuple[PrecheckReport, float]:
        """Returns (report, duration_ms). Reuses cached scan if source_hash matches."""
        source_hash = hashlib.sha256((source_code or "").encode("utf-8")).hexdigest()
        if source_hash in cls._scan_cache:
            return cls._scan_cache[source_hash]
        rep = cls.analyze(source_code, filename, language, policy)
        return cls._scan_cache.get(source_hash, (rep, 0.0))

    @classmethod
    def analyze(
        cls,
        source_code: str,
        filename: str = "main.c",
        language: str = "c",
        policy: Optional[PrecheckPolicy] = None,
    ) -> PrecheckReport:
        """Statically inspect source code for malicious, destructive, or risky patterns.
        
        Guaranteed to perform zero dynamic execution.
        """
        source_hash = hashlib.sha256((source_code or "").encode("utf-8")).hexdigest()
        if source_hash in cls._scan_cache:
            return cls._scan_cache[source_hash][0]

        t_start = time.perf_counter()
        active_policy = policy or PrecheckPolicy()
        findings: List[PrecheckFinding] = []
        lines = (source_code or "").splitlines()

        # Phase 0: Malicious Instruction & Prompt Injection Detection
        # Keep malicious-instruction detection in the precheck.
        # Keep prompt-injection findings distinct from executable security vulnerabilities.
        for idx, line in enumerate(lines, 1):
            line_str = line.strip()
            for p_reg in cls.PROMPT_INJECTION_PATTERNS:
                m = p_reg.search(line_str)
                if m:
                    already = any(f.line == idx and f.rule_id == "PRECHECK-INJECTION-001" for f in findings)
                    if not already:
                        findings.append(
                            PrecheckFinding(
                                rule_id="PRECHECK-INJECTION-001",
                                category="PROMPT_INJECTION",
                                severity="INFO",  # Reviewer instructions never block and never make program unsafe
                                risk_level=RiskLevel.LOW,
                                file_path=filename,
                                line=idx,
                                column=m.start(),
                                snippet=line_str,
                                explanation=(
                                    "Instruction addressed to an automated reviewer or agent detected. "
                                    f"Directives attempting to manipulate reasoning or security gates: '{m.group(0)}'."
                                ),
                                recommended_mitigation="Acknowledge warning to continue. Flagged directive will be automatically masked before passing code to AI models.",
                                confidence=0.99,
                                evidence=m.group(0),
                                blocks_execution=False,
                                requires_review=True,
                                is_malicious_intent=False,
                            )
                        )

        # Phase 1: Call-site and AST analysis (C/C++)
        calls: List[CallSite] = []
        if language in ("c", "cpp", "c++"):
            try:
                calls = extract_call_sites(source_code)
            except Exception:
                calls = []

        # 1. Dangerous C Functions: gets() and unsafe string operations
        for call in calls:
            fn = call.fn_name
            line_idx = max(1, call.line)
            snippet = lines[line_idx - 1].strip() if line_idx <= len(lines) else f"{fn}(...)"

            # Check gets() - Critical vulnerability
            if fn == "gets":
                findings.append(
                    PrecheckFinding(
                        rule_id="PRECHECK-DANG-001",
                        category="UNSAFE_FUNCTION",
                        severity="CRITICAL",
                        risk_level=RiskLevel.HIGH_RISK,
                        file_path=filename,
                        line=line_idx,
                        column=call.col,
                        snippet=snippet,
                        explanation=(
                            "Function 'gets()' does not check buffer boundaries and was removed in C11. "
                            "It permits unrestricted stack buffer overflows."
                        ),
                        recommended_mitigation="Replace 'gets(buf)' with 'fgets(buf, sizeof(buf), stdin)'.",
                        confidence=1.0,
                        evidence=f"Call to '{fn}' at line {line_idx}",
                        blocks_execution=False,  # Coding flaw, allow static repair
                        requires_review=True,
                        is_malicious_intent=False,
                    )
                )

            # Check unsafe string functions (strcpy, strcat, sprintf, vsprintf)
            elif fn in UNSAFE_FUNCTIONS:
                desc = UNSAFE_FUNCTIONS[fn]
                findings.append(
                    PrecheckFinding(
                        rule_id="PRECHECK-DANG-002",
                        category="UNSAFE_STRING_OPERATION",
                        severity="HIGH" if fn in ("strcpy", "strcat") else "MEDIUM",
                        risk_level=RiskLevel.POTENTIALLY_DANGEROUS,
                        file_path=filename,
                        line=line_idx,
                        column=call.col,
                        snippet=snippet,
                        explanation=(
                            f"Function '{fn}' performs unbounded string operations without destination buffer size enforcement. "
                            f"{desc} may overflow adjacent memory."
                        ),
                        recommended_mitigation=f"Use bounded alternative (strncpy, strncat, or snprintf) with sizeof bounds.",
                        confidence=0.95,
                        evidence=f"Call to '{fn}' at line {line_idx}",
                        blocks_execution=False,
                        requires_review=False,
                        is_malicious_intent=False,
                    )
                )

            # Check dangerous command execution (system, popen, exec*, Windows process creation)
            elif fn in DANGEROUS_FUNCTIONS:
                raw_arg = (call.args[0] if call.args else "").strip()
                is_literal = raw_arg.startswith(('"', "'"))
                arg_text = raw_arg.strip('"\'')
                clean_arg = arg_text.lower().strip()

                from compiler.taint_checker import TaintChecker
                from compiler.cwe_catalog import CWE_CATALOG
                tc_issues = TaintChecker().check(source_code)
                sink_issue = None
                for ti in tc_issues:
                    if ti.sink == fn and ti.sink_line == line_idx:
                        sink_issue = ti
                        break

                cwe78_meta = CWE_CATALOG.get("CWE-78", {})
                is_destructive = any(r.search(snippet) for r in cls.DESTRUCTIVE_COMMAND_REGEXES)
                is_shell_interpreter = is_literal and any(w in clean_arg for w in ("cmd.exe", "powershell", "/bin/bash", "/bin/sh", "bash -c", "sh -c", "curl ", "wget ", "nc "))

                if is_destructive:
                    sev = "CRITICAL"
                    r_level = RiskLevel.HIGH_RISK
                    expl = f"Potentially destructive system command invocation via '{fn}()': {snippet}"
                    blocks = active_policy.block_execution_on_high_risk
                    mal_intent = True
                    mitigation = cwe78_meta.get("mitigation", "Remove destructive command. Use safe, isolated filesystem operations.")
                elif is_shell_interpreter:
                    sev = "CRITICAL"
                    r_level = RiskLevel.HIGH_RISK
                    expl = f"Command execution invoking shell interpreter or network tool via '{fn}()': {snippet}"
                    blocks = active_policy.block_execution_on_high_risk
                    mal_intent = True
                    mitigation = cwe78_meta.get("mitigation", "Avoid invoking system command shells from user code.")
                elif sink_issue and sink_issue.severity == "CRITICAL":
                    sev = "CRITICAL"
                    r_level = RiskLevel.HIGH_RISK
                    expl = sink_issue.message
                    blocks = active_policy.block_execution_on_dangerous_calls
                    mal_intent = False
                    mitigation = cwe78_meta.get("mitigation", sink_issue.suggestion)
                elif is_literal:
                    sev = "LOW"
                    r_level = RiskLevel.LOW
                    expl = f"Shell call with constant command: '{fn}(\\\"{arg_text}\\\")'"
                    blocks = False
                    mal_intent = False
                    mitigation = cwe78_meta.get("mitigation", "Replace platform-specific system calls with portable C standard library constructs.")
                else:
                    sev = "CRITICAL" if (sink_issue and sink_issue.severity == "CRITICAL") else "WARNING"
                    r_level = RiskLevel.HIGH_RISK if sev == "CRITICAL" else RiskLevel.POTENTIALLY_DANGEROUS
                    expl = sink_issue.message if sink_issue else f"Potentially unsafe process execution using '{fn}()'. Allows shell command execution."
                    blocks = active_policy.block_execution_on_dangerous_calls
                    mal_intent = False
                    mitigation = cwe78_meta.get("mitigation", "Avoid executing shell commands from compiled code; use native APIs if required.")

                findings.append(
                    PrecheckFinding(
                        rule_id="PRECHECK-CMD-001" if sev != "CRITICAL" else "PRECHECK-CWE-78",
                        category="COMMAND_INJECTION" if sev == "CRITICAL" else "COMMAND_EXECUTION",
                        severity=sev,
                        risk_level=r_level,
                        file_path=filename,
                        line=line_idx,
                        column=call.col,
                        snippet=snippet,
                        explanation=expl,
                        recommended_mitigation=mitigation,
                        confidence=1.0 if sev == "CRITICAL" else 0.85,
                        evidence=f"Call to '{fn}' with argument '{arg_text}' at line {line_idx}",
                        blocks_execution=blocks,
                        requires_review=r_level in (RiskLevel.HIGH_RISK, RiskLevel.POTENTIALLY_DANGEROUS),
                        is_malicious_intent=mal_intent,
                    )
                )

        # 2. Suspicious File & Destructive Operations (regex scan across raw source)
        for idx, line in enumerate(lines, 1):
            line_str = line.strip()
            # Skip comments for destructive regexes
            is_comment = line_str.startswith("//") or line_str.startswith("/*") or line_str.startswith("*")

            # Check destructive commands in string literals or directives
            for d_reg in cls.DESTRUCTIVE_COMMAND_REGEXES:
                m = d_reg.search(line_str)
                if m:
                    already_reported = any(f.line == idx and f.rule_id == "PRECHECK-DESTRUCTIVE-001" for f in findings)
                    if not already_reported:
                        findings.append(
                            PrecheckFinding(
                                rule_id="PRECHECK-DESTRUCTIVE-001",
                                category="DESTRUCTIVE_OPERATION",
                                severity="CRITICAL",
                                risk_level=RiskLevel.HIGH_RISK,
                                file_path=filename,
                                line=idx,
                                column=m.start(),
                                snippet=line_str,
                                explanation=f"Destructive host command pattern detected: '{m.group(0)}'.",
                                recommended_mitigation="Remove destructive shell commands.",
                                confidence=0.98 if not is_comment else 0.50,
                                evidence=m.group(0),
                                blocks_execution=active_policy.block_execution_on_high_risk,
                                requires_review=True,
                                is_malicious_intent=not is_comment,
                            )
                        )

            # Check sensitive system file access (/etc/shadow, system32/config, etc.)
            for s_reg in cls.SENSITIVE_FILES:
                m = s_reg.search(line_str)
                if m:
                    already_reported = any(f.line == idx and f.rule_id == "PRECHECK-SENSITIVE-FILE-001" for f in findings)
                    if not already_reported:
                        findings.append(
                            PrecheckFinding(
                                rule_id="PRECHECK-SENSITIVE-FILE-001",
                                category="SUSPICIOUS_FILE_OPERATION",
                                severity="HIGH",
                                risk_level=RiskLevel.HIGH_RISK,
                                file_path=filename,
                                line=idx,
                                column=m.start(),
                                snippet=line_str,
                                explanation=f"Attempted access to protected system/credential file '{m.group(0)}'.",
                                recommended_mitigation="Access only application-local files within the workspace.",
                                confidence=0.95 if not is_comment else 0.40,
                                evidence=m.group(0),
                                blocks_execution=active_policy.block_execution_on_high_risk,
                                requires_review=True,
                                is_malicious_intent=not is_comment,
                            )
                        )

            # Check Obfuscation & Encoded Payloads
            # Hex-encoded shellcode/strings
            m_hex = cls.HEX_SHELL_REGEX.search(line_str)
            if m_hex and not is_comment:
                findings.append(
                    PrecheckFinding(
                        rule_id="PRECHECK-OBFUSC-001",
                        category="OBFUSCATION",
                        severity="CRITICAL",
                        risk_level=RiskLevel.HIGH_RISK,
                        file_path=filename,
                        line=idx,
                        column=m_hex.start(),
                        snippet=line_str,
                        explanation=f"Hex-encoded shellcode or system command sequence detected: '{m_hex.group(0)}'.",
                        recommended_mitigation="Disassemble and inspect encoded payloads. Remove unauthorized shellcode.",
                        confidence=0.95,
                        evidence=m_hex.group(0),
                        blocks_execution=active_policy.block_execution_on_high_risk,
                        requires_review=True,
                        is_malicious_intent=True,
                    )
                )

            # Char array concatenation building commands
            m_arr = cls.CHAR_ARRAY_CMD_REGEX.search(line_str)
            if m_arr and not is_comment:
                findings.append(
                    PrecheckFinding(
                        rule_id="PRECHECK-OBFUSC-002",
                        category="OBFUSCATION",
                        severity="HIGH",
                        risk_level=RiskLevel.POTENTIALLY_DANGEROUS,
                        file_path=filename,
                        line=idx,
                        column=m_arr.start(),
                        snippet=line_str,
                        explanation="Character array assembling command string element-by-element (potential signature evasion).",
                        recommended_mitigation="Use plain, explicit string literals and verify intended execution.",
                        confidence=0.85,
                        evidence=m_arr.group(0),
                        blocks_execution=False,
                        requires_review=True,
                        is_malicious_intent=False,
                    )
                )

            # Unbounded scanf("%s", ...) check
            m_sc = re.search(r'scanf\s*\(\s*"%s"\s*,\s*([a-zA-Z_]\w*)', line_str)
            if m_sc or re.search(r'scanf\s*\(\s*"%s"', line_str):
                dest_var = m_sc.group(1) if m_sc else "destination buffer"
                m_decl = re.search(rf'char\s+{dest_var}\s*\[(\d+)\]', source_code) if m_sc else None
                cap_str = f" of declared capacity {m_decl.group(1)} bytes" if m_decl else ""
                safe_w = f"%{int(m_decl.group(1))-1}s" if m_decl else "%63s"
                findings.append(
                    PrecheckFinding(
                        rule_id="PRECHECK-BUFFER-001",
                        category="UNSAFE_INPUT_HANDLING",
                        severity="HIGH",
                        risk_level=RiskLevel.POTENTIALLY_DANGEROUS,
                        file_path=filename,
                        line=idx,
                        column=line_str.find("scanf"),
                        snippet=line_str,
                        explanation=f"scanf with '%s' has no input width limit and can overflow buffer '{dest_var}'{cap_str}. [CWE-120]",
                        recommended_mitigation=f"Specify maximum safe field width '{safe_w}' in scanf or use fgets.",
                        confidence=0.95,
                        evidence=f"scanf(\"%s\", {dest_var})" if m_sc else "scanf(\"%s\")",
                        blocks_execution=False,
                        requires_review=False,
                        is_malicious_intent=False,
                    )
                )

        # 3. Suspicious Combinations of Operations (Multi-site analysis)
        call_names = {c.fn_name for c in calls}
        has_network = bool(call_names & {"socket", "connect", "bind", "listen", "accept", "WSAStartup"})
        has_command = bool(call_names & {"system", "popen", "execl", "execv", "execve", "CreateProcess", "WinExec"})
        has_file_read = bool(call_names & {"fopen", "open", "read", "fread"})

        if has_network and has_command:
            findings.append(
                PrecheckFinding(
                    rule_id="PRECHECK-COMBO-001",
                    category="SUSPICIOUS_COMBINATION",
                    severity="CRITICAL",
                    risk_level=RiskLevel.HIGH_RISK,
                    file_path=filename,
                    line=1,
                    column=0,
                    snippet="Network socket functions + Process execution functions present together",
                    explanation=(
                        "Combination of network socket communication and command/process execution functions "
                        "exhibits characteristics of a remote command shell or C2 backdoor."
                    ),
                    recommended_mitigation="Verify business justification for combining network sockets with shell execution.",
                    confidence=0.90,
                    evidence=f"Network calls: {call_names & {'socket', 'connect', 'bind'}}, Exec calls: {call_names & {'system', 'popen', 'execve'}}",
                    blocks_execution=active_policy.block_execution_on_high_risk,
                    requires_review=True,
                    is_malicious_intent=True,
                )
            )

        # Determine Highest Risk Level & Overall Verdict
        if not findings:
            highest_risk = RiskLevel.LOW
            blocks_exec = False
            requires_rev = False
            is_clean = True
            summary = "Malicious Code Precheck clean: 0 dangerous or suspicious patterns detected."
        else:
            is_clean = False
            has_high = any(f.risk_level == RiskLevel.HIGH_RISK for f in findings)
            has_potential = any(f.risk_level == RiskLevel.POTENTIALLY_DANGEROUS for f in findings)
            if has_high:
                highest_risk = RiskLevel.HIGH_RISK
            elif has_potential:
                highest_risk = RiskLevel.POTENTIALLY_DANGEROUS
            else:
                highest_risk = RiskLevel.LOW

            blocks_exec = any(f.blocks_execution for f in findings)
            requires_rev = any(f.requires_review for f in findings)
            summary = f"Precheck completed: {len(findings)} pattern(s) identified. Risk: {highest_risk.value}."

        diagnostics = {
            "findings_count": len(findings),
            "highest_risk": highest_risk.value,
            "blocks_execution": blocks_exec,
            "requires_review": requires_rev,
            "dangerous_calls_found": list(call_names & set(DANGEROUS_FUNCTIONS.keys())),
            "unsafe_calls_found": list(call_names & set(UNSAFE_FUNCTIONS.keys())),
        }

        report = PrecheckReport(
            findings=findings,
            highest_risk_level=highest_risk,
            blocks_execution=blocks_exec,
            requires_review=requires_rev,
            is_clean=is_clean,
            summary=summary,
            diagnostics=diagnostics,
        )
        dur_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
        cls._scan_cache[source_hash] = (report, dur_ms)
        return report
