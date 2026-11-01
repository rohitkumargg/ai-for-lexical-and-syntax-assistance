# tests/test_patch_validator.py
import pytest
from compiler.finding import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)
from compiler.patch_validator import (
    PatchValidator,
    SandboxedCompiler,
    ValidationVerdict,
    ValidationStage,
    PatchValidationReport,
    PatchHistoryManager,
    generate_structured_diff,
)
from app import app


def test_structured_diff_generation():
    """Verify structured diff generates unified diff and addition/deletion counts."""
    orig = "int main() {\n    int a = 10\n    return a;\n}\n"
    cand = "int main() {\n    int a = 10;\n    return a;\n}\n"

    diff = generate_structured_diff(orig, cand, filename="test.c")
    assert diff.additions_count >= 1
    assert diff.deletions_count >= 1
    assert "--- a/test.c" in diff.unified_diff
    assert "+++ b/test.c" in diff.unified_diff
    assert "+    int a = 10;" in diff.unified_diff


def test_patch_validator_clean_valid_patch():
    """Verify clean patch passes syntax, semantic, compiler (GCC), and security stages."""
    orig = "int main() {\n    int a = 10\n    return a;\n}\n"
    cand = "int main() {\n    int a = 10;\n    return a;\n}\n"

    validator = PatchValidator()
    report = validator.validate_patch(orig, cand, filename="clean.c")

    assert report.is_valid is True
    assert report.syntax_passed is True
    assert report.semantic_passed is True
    assert report.security_passed is True
    assert report.verdict == ValidationVerdict.VALIDATED
    # If GCC exists on machine, compilation passed
    if validator.compiler.is_available():
        assert report.compilation_passed is True


def test_patch_validator_compiles_successfully_but_fails_security():
    """
    CRITICAL REQUIREMENT:
    A patch that compiles successfully under GCC must NOT automatically be considered correct or secure.
    If the candidate introduces gets(), GCC may compile it with returncode 0, but
    ValidationVerdict MUST be FAILED_SECURITY.
    """
    orig = "int main() { return 0; }"
    cand = """#include <stdio.h>
int main() {
    char buf[32];
    gets(buf);
    return 0;
}
"""
    validator = PatchValidator()
    report = validator.validate_patch(orig, cand, filename="insecure.c")

    # If GCC is available, verify it actually compiled cleanly (or with compiler warning)
    if validator.compiler.is_available():
        assert report.compilation_passed is True

    # But security validation MUST FAIL
    assert report.security_passed is False
    assert report.is_valid is False
    assert report.verdict == ValidationVerdict.FAILED_SECURITY
    assert any("gets" in r.lower() or "critical" in r.lower() for r in report.remaining_risks)


def test_patch_validator_syntax_regression_fails():
    """Verify candidate that introduces syntax errors fails validation."""
    orig = "int main() { return 0; }"
    cand = "int main() { int x = ; return 0; }"

    validator = PatchValidator()
    report = validator.validate_patch(orig, cand, filename="broken.c")

    assert report.syntax_passed is False
    assert report.is_valid is False
    assert report.verdict == ValidationVerdict.FAILED_SYNTAX


def test_patch_history_manager_user_approval_and_revert():
    """
    Verify: Never apply AI-generated patch without explicit user approval.
    Verify Apply Fix, Reject, and Revert controls.
    """
    manager = PatchHistoryManager()
    orig = "int main() { int a = 5 return a; }"
    cand = "int main() { int a = 5; return a; }"

    validator = PatchValidator()
    report = validator.validate_patch(orig, cand)

    # 1. Register candidate patch (initial state: PENDING)
    item = manager.register_candidate_patch(
        patch_id="PATCH-001",
        file_path="main.c",
        original_code=orig,
        patched_code=cand,
        explanation="Added missing semicolon",
        report=report,
    )
    assert item.user_decision == "PENDING"
    assert len(manager.applied_history) == 0

    # 2. Explicit User Approval (Apply Fix)
    success, msg, approved_item = manager.approve_and_apply("PATCH-001")
    assert success is True
    assert approved_item.user_decision == "APPROVED"
    assert manager.applied_history == ["PATCH-001"]

    # 3. User Revert (Revert to Original)
    rev_ok, rev_msg, restored_code = manager.revert_last()
    assert rev_ok is True
    assert restored_code == orig
    assert len(manager.applied_history) == 0

    # 4. User Rejection
    item2 = manager.register_candidate_patch(
        patch_id="PATCH-002",
        file_path="main.c",
        original_code=orig,
        patched_code=cand,
        explanation="Added missing semicolon",
        report=report,
    )
    rej_ok, rej_msg = manager.reject("PATCH-002", reason="Rejected by human developer")
    assert rej_ok is True
    assert item2.user_decision == "REJECTED"


def test_api_patch_validation_and_approval_endpoints():
    """Verify Flask API endpoints /api/patch/validate, /api/patch/apply, /api/patch/revert."""
    client = app.test_client()

    orig = "int main() { int a = 42 return a; }"
    cand = "int main() { int a = 42; return a; }"

    # 1. Validate patch
    val_resp = client.post("/api/patch/validate", json={
        "original_code": orig,
        "candidate_code": cand,
        "filename": "test_api.c",
        "explanation": "Added semicolon after 42",
    })
    assert val_resp.status_code == 200
    val_data = val_resp.get_json()
    patch_id = val_data["patch_id"]
    assert val_data["user_decision"] == "PENDING"
    assert val_data["report"]["syntax_passed"] is True
    assert "+int main() { int a = 42; return a; }" in val_data["report"]["structured_diff"]["unified_diff"]

    # 2. Explicit User Approval (Apply)
    apply_resp = client.post("/api/patch/apply", json={"patch_id": patch_id})
    assert apply_resp.status_code == 200
    apply_data = apply_resp.get_json()
    assert apply_data["success"] is True
    assert apply_data["user_decision"] == "APPROVED"
    assert apply_data["applied_code"] == cand
    assert apply_data["revert_available"] is True

    # 3. User Revert
    revert_resp = client.post("/api/patch/revert", json={})
    assert revert_resp.status_code == 200
    revert_data = revert_resp.get_json()
    assert revert_data["success"] is True
    assert revert_data["restored_code"] == orig


def test_candidate_swap_after_validation_rejection():
    """
    Item 7 requirement: Confirm /api/patch/apply applies server-stored validated candidate
    (never client-supplied code) bound to candidate hash, source hash, and validation run ID.
    Verify candidate-swap-after-validation fails integrity verification.
    """
    from app import patch_history
    client = app.test_client()

    orig = "int main() { int a = 10 return a; }"
    cand = "int main() { int a = 10; return a; }"

    val_resp = client.post("/api/patch/validate", json={
        "original_code": orig,
        "candidate_code": cand,
        "filename": "swap_test.c",
        "explanation": "Add semicolon",
    })
    assert val_resp.status_code == 200
    patch_id = val_resp.get_json()["patch_id"]

    # Retrieve registered item and tamper with the candidate code on server
    item = patch_history.patches.get(patch_id)
    assert item is not None
    assert item.candidate_hash is not None
    assert item.validation_run_id is not None

    # Simulate tampering / candidate swap after validation
    item.patched_code = "int main() { system(\"rm -rf /\"); return 0; }"

    # Try applying via API - must be rejected due to candidate hash mismatch!
    apply_resp = client.post("/api/patch/apply", json={"patch_id": patch_id})
    assert apply_resp.status_code in [400, 409]
    err = apply_resp.get_json().get("error", "")
    assert "tampered" in err.lower() or "modified" in err.lower()


def test_crlf_lf_and_trailing_newline_hash_invariance():
    """
    Item F requirement: Test that CRLF/LF and trailing-newline differences
    don't cause false stale rejections after the _sha256 change.
    """
    from compiler.patch_validator import compute_strict_hash, compute_stale_hash, normalize_code_for_stale

    # 1. Strict bytes for candidate hash (must differentiate CRLF, trailing spaces, backslash-space)
    cand_lf = "int main() {\n    return 0;\n}\n"
    cand_crlf = "int main() {\r\n    return 0;\r\n}\r\n"
    cand_trailing = "int main() {\n    return 0;\n}\n  "
    cand_bs_space = "int main() {\\ \n    return 0;\n}\n"

    assert compute_strict_hash(cand_lf) != compute_strict_hash(cand_crlf), "Strict candidate hash must distinguish LF from CRLF"
    assert compute_strict_hash(cand_lf) != compute_strict_hash(cand_trailing), "Strict candidate hash must distinguish trailing spaces"
    assert compute_strict_hash(cand_lf) != compute_strict_hash(cand_bs_space), "Strict candidate hash must distinguish backslash-space"

    # 2. Normalization only in the stale-source comparison
    orig_lf = "int main() {\n    int a = 5\n    return a;\n}\n"
    orig_crlf = "int main() {\r\n    int a = 5\r\n    return a;\r\n}\r\n\r\n"
    orig_trailing = "int main() {   \n    int a = 5   \n    return a;   \n}   \n"

    orig_macro_lf = "#define FOO(x) \\\n    ((x) + 1)\n"
    orig_macro_bs_space = "#define FOO(x) \\ \n    ((x) + 1)\n"

    stale_lf = compute_stale_hash(orig_lf)
    stale_crlf = compute_stale_hash(orig_crlf)
    stale_trailing = compute_stale_hash(orig_trailing)

    assert stale_lf == stale_crlf, "Stale source comparison must normalize CRLF vs LF"
    assert stale_lf == stale_trailing, "Stale source comparison must normalize trailing space per line"
    assert compute_stale_hash(orig_macro_lf) == compute_stale_hash(orig_macro_bs_space), "Stale source comparison must normalize backslash-space"

    # 3. End-to-end approval test: registered with LF, approved with CRLF + trailing spaces/newlines
    manager = PatchHistoryManager()
    validator = PatchValidator()
    report = validator.validate_patch(orig_lf, cand_lf)
    manager.register_candidate_patch(
        patch_id="PATCH-HASH-01",
        file_path="hash_test.c",
        original_code=orig_lf,
        patched_code=cand_lf,
        explanation="Add semicolon for hash test",
        report=report,
    )

    # Approve passing current_source with CRLF and extra trailing spaces/newlines
    success, msg, item = manager.approve_and_apply("PATCH-HASH-01", current_source=orig_crlf)
    assert success is True, f"Approval falsely rejected as stale: {msg}"
    assert item.user_decision == "APPROVED"


def test_patch_integrity_inspector_catches_bogus_patches():
    """
    Item 6 requirement: Implement filter catching candidates that delete/replace computation under repair,
    add unrelated code, mutate declared types/identifiers outside finding scope, or exceed diff-size budget.
    """
    from compiler.patch_validator import PatchIntegrityInspector, PatchValidator, ValidationVerdict

    # 1. Hallucinated empty file
    ok, reasons = PatchIntegrityInspector.inspect("", "int main() { return 0; }")
    assert not ok
    assert any("empty" in r.lower() for r in reasons)

    # 2. Replacing computation with no-op / dead assignment
    orig_overflow = """int main() {
    long long x = 2147483647 + 1;
    return 0;
}
"""
    cand_dead_store = """int main() {
    long long x = 0;
    x = x + 2147483647 + 1;
    return 0;
}
"""
    ok, reasons = PatchIntegrityInspector.inspect(orig_overflow, cand_dead_store)
    assert not ok
    assert any("no-op" in r.lower() or "dead" in r.lower() for r in reasons)

    # 3. Type mutation outside scope (float f -> int f)
    orig_operand = """int main() {
    float f = 1.5;
    int x = 2;
    int y = x % f;
    return y;
}
"""
    cand_type_mutate = """int main() {
    int f = 1;
    int x = 2;
    int y = x % f;
    return y;
}
"""
    ok, reasons = PatchIntegrityInspector.inspect(orig_operand, cand_type_mutate)
    assert not ok
    assert any("type" in r.lower() or "identifier" in r.lower() for r in reasons)

    # 4. Exceeding diff budget (> 200 lines diff on small file)
    large_patch = orig_operand + "\n".join([f"// Line {i}" for i in range(250)])
    ok, reasons = PatchIntegrityInspector.inspect(orig_operand, large_patch)
    assert not ok
    assert any("budget" in r.lower() or "lines" in r.lower() for r in reasons)


