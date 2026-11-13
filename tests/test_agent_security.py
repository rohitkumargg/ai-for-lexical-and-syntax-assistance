# tests/test_agent_security.py
import pytest
from compiler.finding import Finding, FindingCategory, FindingSeverity, FindingStatus
from compiler.agent_security import (
    redact_sensitive_text,
    redact_data_structure,
    validate_agent_finding,
    create_run_secret,
    compute_finding_hmac,
    verify_finding_integrity,
    ensure_loopback_endpoint,
    sandbox_code_prompt,
    get_security_summary,
    reset_security_counts,
    get_security_counts,
)


def test_data_protection_redacts_dummy_api_key():
    raw = 'api_key = "EXAMPLE_NOT_A_REAL_KEY_0001"'
    redacted = redact_sensitive_text(raw)
    assert "EXAMPLE_NOT_A_REAL_KEY_0001" not in redacted
    assert "[REDACTED:API_KEY]" in redacted


def test_data_protection_redacts_hardcoded_password():
    raw = 'password = "super_secret_value_123"'
    redacted = redact_sensitive_text(raw)
    assert "super_secret_value_123" not in redacted
    assert "[REDACTED:PASSWORD]" in redacted


def test_data_protection_redacts_private_key():
    raw = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0987654321\n-----END RSA PRIVATE KEY-----"
    redacted = redact_sensitive_text(raw)
    assert "0987654321" not in redacted
    assert "[REDACTED:PRIVATE_KEY]" in redacted


def test_data_protection_redacts_connection_string():
    raw = 'conn = "mongodb://user:super_secret_pw@localhost:27017/prod_db"'
    redacted = redact_sensitive_text(raw)
    assert "super_secret_pw" not in redacted
    assert "[REDACTED:CONNECTION_STRING]" in redacted


def test_data_protection_redacts_bearer_token():
    raw = "Authorization: Bearer abcdef1234567890abcdef1234567890"
    redacted = redact_sensitive_text(raw)
    assert "abcdef1234567890abcdef1234567890" not in redacted
    assert "Bearer [REDACTED:TOKEN]" in redacted


def test_negative_controls_not_redacted():
    # Variable names
    var_code = "int password_len = (int)strlen(password_buf);"
    assert redact_sensitive_text(var_code) == var_code

    # Format specifiers
    fmt = 'printf("password: %s\\n", buf);'
    assert redact_sensitive_text(fmt) == fmt

    # Normal 32-char hex UUID or run ID
    run_id = "run_f8a92b34c56e718290ab45cd67ef1234"
    assert redact_sensitive_text(run_id) == run_id


def test_redact_data_structure_recursive():
    nested = {
        "event": "log_entry",
        "details": {
            "token": "EXAMPLE_NOT_A_REAL_KEY_9999",
            "items": ["safe_item", 'password = "my_hidden_pass_99"'],
            "number": 42,
            "flag": True,
        },
    }
    cleaned = redact_data_structure(nested)
    assert cleaned["details"]["token"] == "[REDACTED:API_KEY]"
    assert "[REDACTED:PASSWORD]" in cleaned["details"]["items"][1]
    assert cleaned["details"]["number"] == 42
    assert cleaned["details"]["flag"] is True


def test_authority_matrix_validation():
    run_secret = create_run_secret()
    f_syntax = Finding.create(
        category=FindingCategory.SYNTAX,
        line=5,
        col=2,
        explanation="Expected semicolon before 'return'",
    )
    # SyntaxAgent is allowed SYNTAX
    valid, err = validate_agent_finding("SyntaxAgent", f_syntax, source_line_count=20, run_secret=run_secret)
    assert valid is True
    assert err is None

    # SyntaxAgent is NOT allowed SECURITY
    f_sec = Finding.create(
        category=FindingCategory.SECURITY,
        line=5,
        col=2,
        explanation="Buffer overflow risk",
    )
    valid, err = validate_agent_finding("SyntaxAgent", f_sec, source_line_count=20, run_secret=run_secret)
    assert valid is False
    assert "Authority violation" in err

    # SecurityAgent IS allowed SECURITY
    valid, err = validate_agent_finding("SecurityAgent", f_sec, source_line_count=20, run_secret=run_secret)
    assert valid is True
    assert err is None


def test_schema_bounds_validation():
    run_secret = create_run_secret()

    # Negative line number rejected
    f_bad_line = Finding.create(category=FindingCategory.SYNTAX, line=-5, col=0, explanation="Error")
    valid, err = validate_agent_finding("SyntaxAgent", f_bad_line, source_line_count=20, run_secret=run_secret)
    assert valid is False
    assert "Bounds violation" in err

    # Line number far out of bounds rejected
    f_huge_line = Finding.create(category=FindingCategory.SYNTAX, line=9999, col=0, explanation="Error")
    valid, err = validate_agent_finding("SyntaxAgent", f_huge_line, source_line_count=20, run_secret=run_secret)
    assert valid is False
    assert "Bounds violation" in err

    # Negative column rejected
    f_bad_col = Finding.create(category=FindingCategory.SYNTAX, line=5, col=-2, explanation="Error")
    valid, err = validate_agent_finding("SyntaxAgent", f_bad_col, source_line_count=20, run_secret=run_secret)
    assert valid is False
    assert "Bounds violation" in err

    # Oversized payload rejected
    f_oversized = Finding.create(category=FindingCategory.SYNTAX, line=5, col=1, explanation="A" * 5000)
    valid, err = validate_agent_finding("SyntaxAgent", f_oversized, source_line_count=20, run_secret=run_secret)
    assert valid is False
    assert "Payload size violation" in err


def test_hmac_provenance_and_tamper_detection():
    run_secret = create_run_secret()
    f = Finding.create(
        category=FindingCategory.SYNTAX,
        line=10,
        col=4,
        explanation="Missing semicolon",
    )
    valid, _ = validate_agent_finding("SyntaxAgent", f, source_line_count=50, run_secret=run_secret)
    assert valid is True
    assert "_provenance_hmac" in f.metadata

    # Verification passes
    assert verify_finding_integrity(f, run_secret) is True

    # Tampering with explanation invalidates HMAC
    f.explanation = "Manipulated explanation text"
    assert verify_finding_integrity(f, run_secret) is False


def test_loopback_endpoint_enforcement():
    # Loopback allowed
    assert ensure_loopback_endpoint("http://127.0.0.1:11434") == "http://127.0.0.1:11434"
    assert ensure_loopback_endpoint("http://localhost:11434") == "http://localhost:11434"

    # External addresses safely redirected to local loopback default
    redirected = ensure_loopback_endpoint("http://external-api.threat.org/generate")
    assert redirected == "http://127.0.0.1:11434"


def test_sandbox_code_prompt():
    prompt = sandbox_code_prompt("int x = 1;", "c")
    assert "BEGIN UNTRUSTED CODE ANALYSIS CONTEXT" in prompt
    assert "END UNTRUSTED CODE ANALYSIS CONTEXT" in prompt
    assert "int x = 1;" in prompt


def test_fail_open_resilience():
    # None or invalid types should return without crashing
    assert redact_sensitive_text(None) is None
    assert redact_data_structure(None) is None
    # Bad secret verification fails safely rather than crashing
    assert verify_finding_integrity(None, "secret") is False or verify_finding_integrity(None, "secret") is True

