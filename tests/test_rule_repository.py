# tests/test_rule_repository.py
import os
import json
import tempfile
import pytest
from compiler.rule_repository import (
    RuleStatus,
    TransformationType,
    RuleTestCase,
    RuleValidationReport,
    CandidateRule,
    ActiveRule,
    RuleExecutor,
    CandidateRuleValidator,
    RuleRepositoryManager,
    RuleDiscoveryEngine,
)
from compiler.finding import Finding, FindingCategory, FindingSeverity, FindingStatus


@pytest.fixture
def temp_repo(tmp_path):
    """Provides an isolated RuleRepositoryManager in a temporary directory."""
    cand_path = str(tmp_path / "candidate_rules.json")
    active_path = str(tmp_path / "active_rules.json")
    hist_path = str(tmp_path / "rule_history.json")
    manager = RuleRepositoryManager(
        candidate_path=cand_path,
        active_path=active_path,
        history_path=hist_path,
    )
    return manager


def test_declarative_rule_executor():
    """Verify RuleExecutor applies transformations deterministically without eval/exec."""
    # 1. regex_sub
    code = "int x = 10\nreturn x;"
    trans_regex = {
        "type": "regex_sub",
        "pattern": r"(int\s+[a-zA-Z_]\w*\s*=\s*\d+)(?!\s*;)",
        "replacement": r"\1;",
    }
    applied, new_code = RuleExecutor.apply(code, trans_regex)
    assert applied is True
    assert "int x = 10;\nreturn x;" == new_code

    # 2. token_insert
    code2 = "printf(\"Hello, World!\")\n"
    trans_insert = {
        "type": "token_insert",
        "pattern": r'printf\([^)]+\)',
        "replacement": ";",
    }
    applied2, new_code2 = RuleExecutor.apply(code2, trans_insert)
    assert applied2 is True
    assert 'printf("Hello, World!");\n' == new_code2

    # 3. replace_exact
    code3 = "void mian() {"
    trans_exact = {
        "type": "replace_exact",
        "pattern": "void mian()",
        "replacement": "int main()",
    }
    applied3, new_code3 = RuleExecutor.apply(code3, trans_exact)
    assert applied3 is True
    assert "int main() {" == new_code3

    # 4. No-op when pattern does not match
    applied4, new_code4 = RuleExecutor.apply("int main() { return 0; }", trans_exact)
    assert applied4 is False
    assert new_code4 == "int main() { return 0; }"


def test_candidate_rule_discovery_engine(temp_repo):
    """Verify RuleDiscoveryEngine synthesizes structured candidate rules from repairs."""
    engine = RuleDiscoveryEngine(temp_repo)
    broken_code = "int main() {\n    int a = 5\n    return a;\n}"
    repaired_code = "int main() {\n    int a = 5;\n    return a;\n}"

    finding = Finding(
        id="find_syntax_1",
        category=FindingCategory.SYNTAX,
        location={"file": "test.c", "line": 2, "column": 14},
        evidence="missing ';'",
        explanation="Expected semicolon at end of assignment",
        severity=FindingSeverity.HIGH,
        status=FindingStatus.CONFIRMED,
    )

    candidate = engine.propose_from_successful_repair(
        original_code=broken_code,
        repaired_code=repaired_code,
        finding=finding,
        source_model="codet5_lora",
    )

    assert candidate is not None
    assert candidate.id.startswith("rule_cand_")
    assert candidate.category == "syntax"
    assert candidate.source_model == "codet5_lora"
    assert candidate.status == RuleStatus.PENDING_REVIEW
    assert len(candidate.positive_tests) >= 1
    assert len(candidate.negative_tests) >= 1
    assert len(candidate.ambiguous_cases) >= 1

    # Candidate should be saved in repository
    loaded = temp_repo.get_candidate(candidate.id)
    assert loaded is not None
    assert loaded.id == candidate.id


def test_candidate_rule_validation(temp_repo):
    """Verify CandidateRuleValidator runs positive tests, zero-drift negative tests, and security checks."""
    validator = CandidateRuleValidator()

    candidate = CandidateRule(
        id="cand_test_semicolon",
        name="Auto-Semicolon Assignment",
        category="syntax",
        source_model="qwen2.5_coder",
        triggering_conditions="Missing semicolon after scalar assignment",
        applicable_context="C simple variable assignment",
        transformation={
            "type": "regex_sub",
            "pattern": r"(int\s+[a-zA-Z_]\w*\s*=\s*\d+)(?!\d|\s*;)",
            "replacement": r"\1;",
        },
        assumptions=["Assignment statement ends without semicolon"],
        positive_tests=[
            RuleTestCase(
                name="basic_int_assign",
                input_code="int main() {\n    int a = 10\n    return a;\n}",
                expected_code="int main() {\n    int a = 10;\n    return a;\n}",
            )
        ],
        negative_tests=[
            RuleTestCase(
                name="already_has_semicolon",
                input_code="int main() {\n    int a = 10;\n    return a;\n}",
                expected_code="int main() {\n    int a = 10;\n    return a;\n}",
            )
        ],
        ambiguous_cases=[
            RuleTestCase(
                name="multiline_or_incomplete",
                input_code="/* comment */ int foo() { return 0; }",
                expected_code="/* comment */ int foo() { return 0; }",
            )
        ],
    )

    report = validator.validate_candidate(candidate)
    assert report.is_valid is True
    assert report.passed_tests == 3
    assert report.total_tests == 3
    assert report.security_checked is True
    assert report.security_passed is True


def test_anti_ai_self_promotion_guardrail(temp_repo):
    """CRITICAL SAFETY INVARIANT: Models are strictly forbidden from approving active rules."""
    candidate = CandidateRule(
        id="cand_dangerous_1",
        name="Dangerous Candidate",
        category="syntax",
        source_model="qwen2.5_coder",
        triggering_conditions="test",
        applicable_context="test",
        transformation={"type": "replace_exact", "pattern": "foo", "replacement": "bar"},
        assumptions=[],
        positive_tests=[],
        negative_tests=[],
        ambiguous_cases=[],
    )
    temp_repo.propose_candidate(candidate)

    # 1. AI model reviewer attempts approval -> MUST BE REJECTED
    disallowed_reviewers = ["model", "ai", "qwen", "codet5", "system", "MODEL", "AI_AGENT", ""]
    for bad_reviewer in disallowed_reviewers:
        with pytest.raises(PermissionError) as exc_info:
            temp_repo.approve_and_activate(
                candidate_id=candidate.id,
                reviewer_name=bad_reviewer,
                notes="Model self-promotion attempt",
            )
        assert "strictly forbidden" in str(exc_info.value) or "Human reviewer identifier" in str(exc_info.value)

    # Active repository MUST remain completely empty
    active_rules = temp_repo.list_active()
    assert len(active_rules) == 0


def test_human_approval_and_activation(temp_repo):
    """Verify human approval activates candidate, versions it as 1.0.0, and moves it to active repository."""
    candidate = CandidateRule(
        id="cand_valid_1",
        name="Valid Semicolon Rule",
        category="syntax",
        source_model="codet5_lora",
        triggering_conditions="missing semicolon",
        applicable_context="SimpleC",
        transformation={"type": "replace_exact", "pattern": "int a = 1", "replacement": "int a = 1;"},
        assumptions=["Single line"],
        positive_tests=[],
        negative_tests=[],
        ambiguous_cases=[],
    )
    temp_repo.propose_candidate(candidate)

    # Human approval
    active_rule = temp_repo.approve_and_activate(
        candidate_id=candidate.id,
        reviewer_name="senior_engineer_human",
        notes="Reviewed and approved for deterministic production pipeline.",
    )

    assert active_rule is not None
    assert active_rule.version == "1.0.0"
    assert active_rule.is_enabled is True
    assert active_rule.approved_by == "senior_engineer_human"

    # Candidate should now be marked APPROVED
    updated_cand = temp_repo.get_candidate(candidate.id)
    assert updated_cand.status == RuleStatus.APPROVED

    # Active repository must now contain this rule
    active_list = temp_repo.list_active()
    assert len(active_list) == 1
    assert active_list[0].id == candidate.id


def test_rule_disabling_enabling_and_rollback(temp_repo):
    """Verify active rules can be disabled, re-enabled, and rolled back on regression."""
    candidate = CandidateRule(
        id="cand_versioned_rule",
        name="Versioned Rule",
        category="syntax",
        source_model="human",
        triggering_conditions="test",
        applicable_context="test",
        transformation={"type": "replace_exact", "pattern": "old_pat", "replacement": "new_pat"},
        assumptions=[],
        positive_tests=[],
        negative_tests=[],
        ambiguous_cases=[],
    )
    temp_repo.propose_candidate(candidate)
    active = temp_repo.approve_and_activate(candidate.id, reviewer_name="reviewer_bob")
    assert active.version == "1.0.0"

    # 1. Update rule to version 1.1.0
    new_trans = {"type": "replace_exact", "pattern": "v2_pat", "replacement": "v2_repl"}
    updated = temp_repo.update_active_rule(
        rule_id=active.id,
        new_transformation=new_trans,
        new_version="1.1.0",
        author="reviewer_bob",
        change_description="Upgraded transformation pattern",
    )
    assert updated.version == "1.1.0"
    assert len(updated.version_history) == 1
    assert updated.version_history[0]["version"] == "1.0.0"

    # 2. Disable rule if regression detected
    disabled = temp_repo.disable_rule(active.id, reason="Caused regression in pointers")
    assert disabled.is_enabled is False

    # Check compiler application skips disabled rule
    code = "v2_pat is here"
    applied, res = temp_repo.apply_active_rules(code)
    assert applied is False
    assert res == code

    # 3. Re-enable rule
    re_enabled = temp_repo.enable_rule(active.id)
    assert re_enabled.is_enabled is True

    # 4. Rollback to version 1.0.0
    rolled_back = temp_repo.rollback_rule(active.id, target_version="1.0.0", operator="reviewer_bob")
    assert rolled_back.version == "1.0.0"
    assert rolled_back.transformation["pattern"] == "old_pat"


def test_api_candidate_rules_workflow():
    """Verify Flask API endpoints for candidate rule discovery, validation, human approval, and rollback."""
    from app import app

    client = app.test_client()

    # 1. Propose candidate rule via API
    cand_payload = {
        "name": "API Proposed Semicolon Rule",
        "category": "syntax",
        "source_model": "codet5_lora",
        "triggering_conditions": "Missing semicolon",
        "applicable_context": "Scalar assignment",
        "transformation": {
            "type": "regex_sub",
            "pattern": r"(int\s+[a-zA-Z_]\w*\s*=\s*\d+)(?!\d|\s*;)",
            "replacement": r"\1;",
        },
        "assumptions": ["Scalar assignment"],
        "positive_tests": [
            {
                "name": "pos1",
                "input_code": "int main() { int x = 10 return x; }",
                "expected_code": "int main() { int x = 10; return x; }",
            }
        ],
        "negative_tests": [
            {
                "name": "neg1",
                "input_code": "int main() { int x = 10; return x; }",
                "expected_code": "int main() { int x = 10; return x; }",
            }
        ],
        "ambiguous_cases": [],
    }

    resp = client.post("/api/rules/propose", json=cand_payload)
    assert resp.status_code == 201
    cand_data = resp.get_json()
    assert cand_data["success"] is True
    rule_id = cand_data["candidate"]["id"]

    # 2. List candidate rules
    list_resp = client.get("/api/rules/candidates")
    assert list_resp.status_code == 200
    candidates = list_resp.get_json()["candidates"]
    assert any(c["id"] == rule_id for c in candidates)

    # 3. Validate candidate rule
    val_resp = client.post(f"/api/rules/candidate/{rule_id}/validate")
    assert val_resp.status_code == 200
    val_data = val_resp.get_json()
    assert val_data["success"] is True
    assert val_data["report"]["security_checked"] is True

    # 4. Anti-AI promotion check via API
    ai_approve_resp = client.post(
        f"/api/rules/candidate/{rule_id}/approve",
        json={"reviewer_name": "qwen2.5_model", "approval_notes": "AI auto-approval"},
    )
    assert ai_approve_resp.status_code == 403
    assert "strictly forbidden" in ai_approve_resp.get_json()["error"]

    # 5. Human approval via API
    human_approve_resp = client.post(
        f"/api/rules/candidate/{rule_id}/approve",
        json={"reviewer_name": "lead_compiler_engineer", "approval_notes": "Verified offline tests"},
    )
    assert human_approve_resp.status_code == 200
    active_data = human_approve_resp.get_json()
    assert active_data["success"] is True
    assert active_data["rule"]["version"] == "1.0.0"

    # 6. List active rules
    active_resp = client.get("/api/rules/active")
    assert active_resp.status_code == 200
    active_rules = active_resp.get_json()["rules"]
    assert any(r["id"] == rule_id for r in active_rules)

    # 7. Disable rule via API
    dis_resp = client.post(f"/api/rules/active/{rule_id}/disable", json={"reason": "Testing disable"})
    assert dis_resp.status_code == 200
    assert dis_resp.get_json()["rule"]["is_enabled"] is False

    # 8. Re-enable rule via API
    en_resp = client.post(f"/api/rules/active/{rule_id}/enable")
    assert en_resp.status_code == 200
    assert en_resp.get_json()["rule"]["is_enabled"] is True
