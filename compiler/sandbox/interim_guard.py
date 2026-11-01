# compiler/sandbox/interim_guard.py
"""
Interim Guard for Sandbox Backend Verification.

Enforces the non-negotiable Fail-Closed policy:
Until an isolated container sandbox (Docker Desktop with WSL2 backend) is verified,
risky programs must NOT be compiled or executed on the host machine.

Refusal Criteria:
1. Findings: Program has any HIGH or CRITICAL security finding.
2. Dangerous calls: Scan hit for process creation, shell, file deletion, sockets, dynamic code evaluation.
3. Classification status: If classification failed, is missing, or unknown -> REFUSE.
4. Clean code: Clean programs with no dangerous operations or high/critical findings may run on the host.
"""
from __future__ import annotations

import re
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class InterimGuardVerdict:
    is_refused: bool
    status: str
    reason: str
    risk_factors: List[str] = field(default_factory=list)
    findings_count: int = 0
    highest_severity: str = "NONE"


# 1. Dangerous Call Regex Patterns
DANGEROUS_PATTERNS_C = {
    "process_creation_shell": [
        (re.compile(r"\b(?:system|popen|execve?|execvp?|execlp?|execl|execv|execle|fork)\s*\(", re.IGNORECASE), "Process creation / shell execution"),
        (re.compile(r"\b(?:CreateProcess[AW]?)\s*\(", re.IGNORECASE), "Win32 process creation API"),
    ],
    "file_deletion": [
        (re.compile(r"\b(?:remove|unlink|rmdir|DeleteFile[AW]?)\s*\(", re.IGNORECASE), "Filesystem deletion / unlink"),
    ],
    "sockets_network": [
        (re.compile(r"\b(?:socket|connect|bind|listen|accept|WSAStartup|getaddrinfo)\s*\(", re.IGNORECASE), "Network socket communication"),
    ],
    "dynamic_code_eval": [
        (re.compile(r"\b(?:dlopen|dlsym)\s*\(", re.IGNORECASE), "Dynamic library / symbol evaluation"),
    ],
    "critical_memory_corruption": [
        (re.compile(r"\bgets\s*\(", re.IGNORECASE), "Banned unrestricted buffer overflow function 'gets'"),
    ],
}

DANGEROUS_PATTERNS_PY = {
    "process_creation_shell": [
        (re.compile(r"\b(?:subprocess\.(?:call|run|Popen|check_output|check_call|getoutput))\s*\(", re.IGNORECASE), "Subprocess execution"),
        (re.compile(r"\bos\.(?:system|popen|spawn[a-z]*|exec[a-z]*)\s*\(", re.IGNORECASE), "OS shell/process execution"),
    ],
    "file_deletion": [
        (re.compile(r"\b(?:os\.(?:remove|unlink|rmdir)|shutil\.(?:rmtree|move))\s*\(", re.IGNORECASE), "Filesystem deletion API"),
    ],
    "sockets_network": [
        (re.compile(r"\b(?:socket\.(?:socket|create_connection)|urllib\.request|requests\.(?:get|post|put|delete)|http\.client)\b", re.IGNORECASE), "Network / HTTP socket call"),
    ],
    "dynamic_code_eval": [
        (re.compile(r"\b(?:eval|exec|compile|__import__)\s*\(", re.IGNORECASE), "Dynamic code execution (eval/exec)"),
    ],
}


def is_sandbox_verified() -> bool:
    """
    Returns True only when an isolated container runtime (Docker Desktop with WSL2 backend)
    has been verified with `docker version` and `docker run --rm hello-world`.
    Currently returns False pending user installation.
    """
    # Environment variable override for test mocks / verified status
    if os.environ.get("ANTIGRAVITY_SANDBOX_VERIFIED", "").strip().lower() in ("1", "true", "yes"):
        return True
    return False


def scan_dangerous_calls(source_code: str, language: str = "c") -> List[str]:
    """Scans code for dangerous call patterns across process, shell, deletion, sockets, and eval."""
    is_py = (language.lower() == "python" or language.lower().endswith(".py"))
    patterns_dict = DANGEROUS_PATTERNS_PY if is_py else DANGEROUS_PATTERNS_C
    hits = []

    for category, pattern_list in patterns_dict.items():
        for pat, desc in pattern_list:
            m = pat.search(source_code)
            if m:
                hits.append(f"{desc} (matched '{m.group(0)}')")
                break  # one hit per category is sufficient
    return hits


def evaluate_interim_guard(
    source_code: str,
    filename: str = "main.c",
    language: str = "c",
) -> InterimGuardVerdict:
    """
    Evaluates whether a program must be refused on the host under the interim guard.
    Returns an InterimGuardVerdict.
    """
    # If the sandbox backend has been verified, host refusal does not apply
    if is_sandbox_verified():
        return InterimGuardVerdict(
            is_refused=False,
            status="SANDBOX_VERIFIED",
            reason="Sandbox backend verified.",
            risk_factors=[],
        )

    risk_factors = []

    # 1. Scan for dangerous calls (process creation, shell, file deletion, sockets, dynamic eval)
    dangerous_hits = scan_dangerous_calls(source_code, language)
    if dangerous_hits:
        risk_factors.extend(dangerous_hits)

    # 2. Check static security classification & findings
    highest_sev = "NONE"
    findings_count = 0
    classification_failed = False
    classification_error = ""

    try:
        from compiler.security_approval_gate import SecurityDecisionGate
        verdict = SecurityDecisionGate.evaluate(source_code, filename=filename, language=language)
        
        # Check for HIGH or CRITICAL findings
        findings = getattr(verdict, "findings", [])
        findings_count = len(findings)
        
        high_crit = [f for f in findings if getattr(f, "severity", "").upper() in ("CRITICAL", "HIGH")]
        if high_crit:
            for f in high_crit:
                risk_factors.append(f"[{f.severity}] {f.rule_id}: {f.explanation}")
            highest_sev = "CRITICAL" if any(f.severity.upper() == "CRITICAL" for f in high_crit) else "HIGH"

    except Exception as e:
        classification_failed = True
        classification_error = str(e)
        risk_factors.append(f"Classification failure: {classification_error}")

    # 3. Decision logic: Fail closed on risk, dangerous calls, or unknown/failed classification
    if classification_failed:
        reason = (
            f"Program security classification failed ({classification_error}). "
            f"Under the fail-closed policy, unclassified programs cannot execute on the host "
            f"without a verified container sandbox."
        )
        return InterimGuardVerdict(
            is_refused=True,
            status="Refused (Classification Failed)",
            reason=reason,
            risk_factors=risk_factors,
            highest_severity="UNKNOWN",
        )

    if risk_factors:
        factors_summary = "\n- " + "\n- ".join(risk_factors[:5])
        reason = (
            f"Execution refused on host machine.\n"
            f"Program contains dangerous calls or HIGH/CRITICAL findings:{factors_summary}\n\n"
            f"Policy: Until an isolated container sandbox (Docker Desktop with WSL2) is verified, "
            f"risky code is never compiled or executed directly on the host. No host fallback is permitted."
        )
        return InterimGuardVerdict(
            is_refused=True,
            status="Refused (Sandbox Unverified)",
            reason=reason,
            risk_factors=risk_factors,
            findings_count=findings_count,
            highest_severity=highest_sev if highest_sev != "NONE" else "HIGH",
        )

    # Clean program with no dangerous operations
    return InterimGuardVerdict(
        is_refused=False,
        status="ALLOWED_CLEAN",
        reason="Clean program: 0 dangerous calls and 0 HIGH/CRITICAL findings detected.",
        risk_factors=[],
        findings_count=findings_count,
        highest_severity="NONE",
    )

