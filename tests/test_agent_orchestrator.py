# tests/test_agent_orchestrator.py
import pytest
from compiler.finding import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    compute_stable_finding_id,
)
from compiler.agents import (
    BaseCompilerAgent,
    LexicalAgent,
    SyntaxAgent,
    SemanticAgent,
    SecurityAgent,
)
from compiler.orchestrator import (
    AgentOrchestrator,
    OrchestratorResult,
    AttemptedRepair,
    UserDecision,
)


def test_stable_finding_id_determinism():
    """Verify finding IDs are deterministic and reproducible across multiple runs."""
    id1 = compute_stable_finding_id("SYNTAX", 10, 5, "missing ';'", "test.c")
    id2 = compute_stable_finding_id("SYNTAX", 10, 5, "missing ';'", "test.c")
    id3 = compute_stable_finding_id("SYNTAX", 11, 5, "missing ';'", "test.c")
    
    assert id1 == id2
    assert id1.startswith("FND-SYN-10:5-")
    assert id1 != id3


def test_agent_coordination():
    """Verify orchestrator coordinates multiple agents and consolidates findings."""
    code = """#include <stdio.h>
int main() {
    char buf[64];
    gets(buf);
    int x = undeclared_var + 1;
    return 0;
}
"""
    orchestrator = AgentOrchestrator()
    result = orchestrator.run_analysis(code, filename="test_coord.c")

    # 1. Original source is preserved intact
    assert result.original_source == code
    assert result.working_source == code

    # 2. Findings are non-empty and consolidated
    assert len(result.findings) > 0

    # 3. Security finding detected gets()
    sec_findings = [f for f in result.findings if f.category == FindingCategory.SECURITY]
    assert len(sec_findings) >= 1
    assert any("gets" in f.explanation.lower() or "gets" in f.evidence.lower() for f in sec_findings)

    # 4. Agent telemetry tracked execution times and status
    assert "agent_status" in result.agent_telemetry
    for agent in orchestrator.agents:
        assert result.agent_telemetry["agent_status"][agent.name] == "SUCCESS"
        assert agent.name in result.agent_telemetry["phase_durations_ms"]

    # 5. Serialization to dict is valid
    res_dict = result.to_dict()
    assert res_dict["original_source"] == code
    assert isinstance(res_dict["findings"], list)


def test_cascading_error_suppression_syntax():
    """Verify that the primary syntax error is root cause and follow-on syntax noise is suppressed."""
    # A syntax error with missing closing brace or broken construct
    code = """int main() {
    int a = 5
    int b = 10
    return 0;
}
"""
    orchestrator = AgentOrchestrator()
    result = orchestrator.run_analysis(code, filename="test_cascade.c")

    syntax_findings = [f for f in result.findings if f.category == FindingCategory.SYNTAX]
    assert len(syntax_findings) >= 1

    # Check root cause identification
    root_causes = result.root_cause_findings
    syntax_roots = [f for f in root_causes if f.category == FindingCategory.SYNTAX]
    assert len(syntax_roots) >= 1
    assert syntax_roots[0].is_root_cause is True

    # If multiple syntax errors were produced, later ones must be marked cascading
    if len(syntax_findings) > 1:
        cascading = [f for f in syntax_findings if f.status == FindingStatus.SUPPRESSED_CASCADING]
        assert len(cascading) >= 1
        for c in cascading:
            assert c.cascades_from_id == syntax_roots[0].id


def test_cascading_error_suppression_semantic_on_syntax_error():
    """Verify that syntax errors suppress downstream noisy semantic errors."""
    code = """int main() {
    int x = ;
    x = x + 1;
}
"""
    orchestrator = AgentOrchestrator()
    result = orchestrator.run_analysis(code, filename="test_syntax_sem_cascade.c")

    has_syntax = any(f.category == FindingCategory.SYNTAX for f in result.findings)
    assert has_syntax

    # Any semantic findings generated under syntax errors should be suppressed cascading
    semantic_findings = [f for f in result.findings if f.category == FindingCategory.SEMANTIC]
    for sf in semantic_findings:
        assert sf.status == FindingStatus.SUPPRESSED_CASCADING
        assert sf.cascades_from_id is not None


def test_analyzer_failure_isolation():
    """Verify that when one analyzer fails or crashes, the orchestrator does not crash and logs SYSTEM finding."""
    class FailingAgent(BaseCompilerAgent):
        def __init__(self):
            super().__init__("FailingAgent", FindingCategory.SYNTAX)

        def analyze(self, source_text, filename="main.c", context=None):
            raise RuntimeError("Simulated crash in analyzer!")

    orchestrator = AgentOrchestrator(
        agents=[
            LexicalAgent(),
            FailingAgent(),
            SecurityAgent(),
        ]
    )

    code = """int main() {
    char buf[16];
    gets(buf);
    return 0;
}
"""
    result = orchestrator.run_analysis(code, filename="crash_test.c")

    # Orchestrator did not raise an unhandled exception
    assert result is not None

    # Telemetry records failure
    assert "FAILED: Simulated crash in analyzer!" in result.agent_telemetry["agent_status"]["FailingAgent"]

    # System finding was logged
    sys_findings = [f for f in result.findings if f.category == FindingCategory.SYSTEM]
    assert len(sys_findings) >= 1
    assert "Simulated crash" in sys_findings[0].explanation

    # SecurityAgent still ran and found gets()
    sec_findings = [f for f in result.findings if f.category == FindingCategory.SECURITY]
    assert len(sec_findings) >= 1


def test_confirmed_vs_possible_security_findings():
    """Verify confirmed vulnerabilities (e.g. gets) are distinguished from heuristic/possible alerts."""
    code = """#include <stdio.h>
int main() {
    char buf[32];
    gets(buf);
    return 0;
}
"""
    orchestrator = AgentOrchestrator()
    result = orchestrator.run_analysis(code, filename="sec_test.c")

    assert len(result.confirmed_security_findings) >= 1
    gets_finding = result.confirmed_security_findings[0]
    assert gets_finding.status == FindingStatus.CONFIRMED
    assert gets_finding.confidence == 1.0
    assert gets_finding.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)


def test_repair_and_user_decision_tracking():
    """Verify tracking of attempted repairs, validation results, and user decisions."""
    orchestrator = AgentOrchestrator()
    
    # 1. Record an attempted repair
    repair = orchestrator.record_attempted_repair(
        finding_id="FND-SYN-2:5-abc1234",
        rule_id="missing_semicolon",
        description="Appended missing semicolon at line 2",
        validation_passed=True,
        errors_before=1,
        errors_after=0,
        patch_snippet="int a = 5;",
    )
    assert repair.validation_passed is True
    assert repair.errors_before == 1
    assert repair.errors_after == 0

    # 2. Record a user decision
    decision = orchestrator.record_user_decision(
        finding_id="FND-SYN-2:5-abc1234",
        decision="APPROVED",
        notes="Looks good, accepted by user",
    )
    assert decision.decision == "APPROVED"
    assert decision.finding_id == "FND-SYN-2:5-abc1234"

    # 3. Verify inclusion in analysis result
    result = orchestrator.run_analysis("int main() { return 0; }")
    assert len(result.attempted_repairs) == 1
    assert result.attempted_repairs[0].rule_id == "missing_semicolon"
    assert len(result.user_decisions) == 1
    assert result.user_decisions[0].decision == "APPROVED"

    # 4. Verify to_dict serializability
    d = result.to_dict()
    assert d["attempted_repairs"][0]["validation_passed"] is True
    assert d["user_decisions"][0]["decision"] == "APPROVED"
