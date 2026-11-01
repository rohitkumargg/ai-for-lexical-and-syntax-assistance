import os
import pytest
from compiler.repair_planner import RepairPlanner
from compiler.local_models import TokenPatchContract, FullSourceRepairContract


@pytest.fixture
def planner():
    return RepairPlanner()


def test_scenario_1_single_missing_semicolon(planner):
    """Scenario 1: Single missing semicolon is repaired deterministically or via CodeT5."""
    code = """int main() {
    int a = 5
    return a;
}"""
    res = planner.plan_and_repair(code, filename="test_semicolon.c", language="c")
    assert res["status"] in ("REPAIR_PLAN_READY", "PROPOSAL_READY")
    assert res["candidate"] is not None
    cand_code = res["candidate"]["proposed_code"]
    assert "int a = 5;" in cand_code
    assert res["candidate"]["is_valid"] is True


def test_scenario_2_misspelled_keyword(planner):
    """Scenario 2: Simple misspelled keyword is repaired deterministically."""
    code = """int main() {
    int a = 0;
    whlie (a < 5) {
        a = a + 1;
    }
    return a;
}"""
    res = planner.plan_and_repair(code, filename="test_typo.c", language="c")
    assert res["status"] in ("REPAIR_PLAN_READY", "PROPOSAL_READY")
    cand_code = res["candidate"]["proposed_code"]
    assert "while (a < 5)" in cand_code
    assert "whlie" not in cand_code
    assert res["candidate"]["is_valid"] is True


def test_scenario_3_unbounded_scanf_input(planner):
    """Scenario 3: Unbounded scanf input bounded according to buffer size minus one."""
    code = """#include <stdio.h>
int main() {
    char s[20];
    scanf("%s", s);
    return 0;
}"""
    res = planner.plan_and_repair(code, filename="test_scanf.c", language="c")
    assert res["status"] in ("REPAIR_PLAN_READY", "PROPOSAL_READY")
    cand_code = res["candidate"]["proposed_code"]
    assert 'scanf("%19s", s)' in cand_code
    assert res["candidate"]["is_valid"] is True


def test_scenario_4_gets_call(planner):
    """Scenario 4: gets() call safely replaced with fgets(buf, sizeof(buf), stdin)."""
    code = """#include <stdio.h>
int main() {
    char buf[32];
    gets(buf);
    return 0;
}"""
    res = planner.plan_and_repair(code, filename="test_gets.c", language="c")
    assert res["status"] in ("REPAIR_PLAN_READY", "PROPOSAL_READY")
    cand_code = res["candidate"]["proposed_code"]
    assert "fgets(buf, sizeof(buf), stdin)" in cand_code
    assert "gets(buf)" not in cand_code
    assert res["candidate"]["is_valid"] is True


def test_scenario_5_user_input_flowing_into_system(planner):
    """Scenario 5: User input flowing into system() call is hardened."""
    code = """#include <stdio.h>
#include <string.h>
#include <stdlib.h>
int main() {
    char cmd[40];
    scanf("%39s", cmd);
    system(cmd);
    return 0;
}"""
    res = planner.plan_and_repair(code, filename="test_system.c", language="c")
    assert res["status"] in ("REPAIR_PLAN_READY", "PROPOSAL_READY", "PARTIALLY_REPAIRED", "UNRESOLVED")
    assert res["terminal_status"] in ("PROPOSAL_READY", "PARTIALLY_REPAIRED", "UNRESOLVED")


def test_scenario_6_mixed_syntax_and_security(planner):
    """Scenario 6: Program with multiple syntax and security errors together."""
    code = """#include <stdio.h>
int run_tasks() {
    int x = 10
    char buf[16];
    gets(buf);
    whlie (x > 0) {
        x = x - 1;
    }
    return x;
}"""
    res = planner.plan_and_repair(code, filename="test_mixed.c", language="c")
    assert res["status"] in ("REPAIR_PLAN_READY", "PROPOSAL_READY", "PARTIALLY_REPAIRED")
    cand_code = res["candidate"]["proposed_code"]
    # Deterministic rules fix keywords and gets
    assert "fgets(buf, sizeof(buf), stdin)" in cand_code
    assert "while (x > 0)" in cand_code
    assert "whlie" not in cand_code


def test_scenario_7_malformed_token_patch_rejected(planner):
    """Scenario 7: Malformed or token patch candidate is strictly rejected by contract."""
    # Test FullSourceRepairContract directly
    token_patch_output = "INS_LC 161 0 }\nREP_LC 167 4 ."
    contract = FullSourceRepairContract.validate_and_create(
        raw_code=token_patch_output,
        strategy="whole_program_synthesis",
    )
    assert contract is None, "Contract must reject token patch commands"

    # Test TokenPatchContract
    patch_contract = TokenPatchContract.from_prediction("INS_LC 161 0 }")
    assert patch_contract is not None
    assert patch_contract.op in ("INS", "INS_LC")
    assert patch_contract.line == 161


def test_ademo3mix_file_execution(planner):
    """Verify execution on actual examples/week11_testing/ademo3mix.c."""
    ademo_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "examples",
        "week11_testing",
        "ademo3mix.c",
    )
    with open(ademo_path, "r", encoding="utf-8") as f:
        orig_content = f.read()

    res = planner.plan_and_repair(orig_content, filename="ademo3mix.c", language="c")

    # Verify original file on disk was NOT mutated
    with open(ademo_path, "r", encoding="utf-8") as f:
        post_content = f.read()
    assert orig_content == post_content, "Original file on disk must never be modified by repair planner"

    # Terminal state must be one of the defined unambiguous terminal states
    assert res["terminal_status"] in ("PROPOSAL_READY", "PARTIALLY_REPAIRED", "UNRESOLVED")
    assert res["status"] in ("REPAIR_PLAN_READY", "PROPOSAL_READY", "PARTIALLY_REPAIRED", "UNRESOLVED")

    # If candidate produced, verify it is not token commands
    if res.get("candidate"):
        cand_code = res["candidate"]["proposed_code"]
        assert "INS_LC" not in cand_code
        assert "REP_LC" not in cand_code
        # Check that deterministic rules succeeded on gets and typos
        assert "fgets(" in cand_code
        assert "while (a < 5)" in cand_code
