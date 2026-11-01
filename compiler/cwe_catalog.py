"""
CWE Per-Class Explanations and Threat Metadata Catalog.

Each entry provides:
- problem: concise description of the security issue
- why_dangerous: theoretical cause of vulnerability
- potential_impact: concrete impact when exploited
- mitigation: authoritative, actionable engineering remediation

Strictly free of attack input examples.
"""

from typing import Any, Dict

CWE_CATALOG: Dict[str, Dict[str, str]] = {
    "CWE-78": {
        "cwe_id": "CWE-78",
        "name": "OS Command Injection",
        "problem": "Passing variable or untrusted input to an operating system command shell execution interface.",
        "why_dangerous": "The command interpreter treats user input as executable shell commands and arguments.",
        "potential_impact": "Attacker-influenced commands run with the program's privileges.",
        "mitigation": "Do not pass user-influenced text to a shell; fixed program plus fixed argument vector (execv family or posix_spawn); map input to an allowlist of fixed choices; least privilege.",
    },
    "CWE-120": {
        "cwe_id": "CWE-120",
        "name": "Buffer Copy without Checking Size of Input",
        "problem": "Copying data into a fixed-size buffer without enforcing destination capacity limits.",
        "why_dangerous": "Data exceeding destination capacity overwrites adjacent stack or heap memory structures.",
        "potential_impact": "Memory corruption, abnormal application termination, or unauthorized control flow redirection.",
        "mitigation": "Enforce explicit buffer capacity limits; replace unbounded functions with bounds-checked alternatives such as fgets and snprintf.",
    },
    "CWE-242": {
        "cwe_id": "CWE-242",
        "name": "Use of Inherently Dangerous Function",
        "problem": "Invoking gets(), which possesses no parameter or mechanism to constrain input length.",
        "why_dangerous": "The function reads input indefinitely until encountering a newline or EOF marker regardless of target buffer size.",
        "potential_impact": "Stack buffer overflow and arbitrary memory corruption.",
        "mitigation": "Replace gets(buf) with fgets(buf, sizeof(buf), stdin).",
    },
    "CWE-134": {
        "cwe_id": "CWE-134",
        "name": "Use of Externally-Controlled Format String",
        "problem": "Supplying variable or user-influenced data as the format string parameter to formatted output functions.",
        "why_dangerous": "Format specifiers in the string allow unauthorized read and write operations to execution memory.",
        "potential_impact": "Sensitive information disclosure or arbitrary memory alteration.",
        "mitigation": "Always supply static string literals as format strings; pass dynamic values in subsequent positional arguments.",
    },
    "CWE-190": {
        "cwe_id": "CWE-190",
        "name": "Integer Overflow or Wraparound",
        "problem": "Performing arithmetic operations that exceed the representable range of the destination numeric data type.",
        "why_dangerous": "Numeric values wrap around to unexpected negative or truncated quantities, compromising boundary checks.",
        "potential_impact": "Unexpected program logic branching, undersized memory allocations, and secondary memory safety faults.",
        "mitigation": "Perform pre-condition range validation before arithmetic operations to prevent integer wraparound.",
    },
    "CWE-476": {
        "cwe_id": "CWE-476",
        "name": "NULL Pointer Dereference",
        "problem": "Dereferencing a pointer that contains a NULL value.",
        "why_dangerous": "Accessing address zero triggers hardware page faults and abnormal process termination.",
        "potential_impact": "Application crash and denial of service.",
        "mitigation": "Verify that pointer references are non-NULL prior to any dereference operation.",
    },
    "CWE-457": {
        "cwe_id": "CWE-457",
        "name": "Use of Uninitialized Variable",
        "problem": "Reading a variable before an initial value has been written to its allocated storage.",
        "why_dangerous": "Residual contents on the stack or heap are consumed as valid operational data.",
        "potential_impact": "Non-deterministic runtime behavior, logic corruption, or memory information leakage.",
        "mitigation": "Initialize all variables explicitly at their point of declaration.",
    },
    "CWE-676": {
        "cwe_id": "CWE-676",
        "name": "Use of Potentially Dangerous Function",
        "problem": "Invocation of a legacy or insecure standard library function with safer replacements available.",
        "why_dangerous": "Inherent interface design flaws make safe usage error-prone across maintenance lifecycles.",
        "potential_impact": "Vulnerability to buffer overflow, race conditions, or unhandled exceptions.",
        "mitigation": "Migrate to modern, bounds-checked APIs with explicit size parameters and error return codes.",
    },
}


def get_cwe_details(cwe_id: str) -> Dict[str, str]:
    """Retrieve structured explanation and mitigation for a given CWE identifier."""
    clean_id = (cwe_id or "").strip().upper()
    if clean_id in CWE_CATALOG:
        return CWE_CATALOG[clean_id]
    for k, v in CWE_CATALOG.items():
        if k in clean_id:
            return v
    return {
        "cwe_id": clean_id or "CWE-676",
        "name": "General Security Finding",
        "problem": f"Security policy violation or dangerous construct ({clean_id}).",
        "why_dangerous": "Construct violates standard secure coding practices and may allow unauthorized actions.",
        "potential_impact": "Potential security compromise or application stability degradation.",
        "mitigation": "Review flagged construct and apply safe coding patterns with strict input validation.",
    }

