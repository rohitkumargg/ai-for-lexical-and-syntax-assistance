"""
Unit and integration tests for Improvement Advisor (compiler/improvement_advisor.py)
and its Flask API endpoints.
Tests multi-strategy candidate generation, independent validation, before/after score delta,
and explicit user decision state transitions.
"""

import pytest
from compiler.improvement_advisor import (
    ImprovementAdvisor,
    ImprovementCandidate,
    ImprovementStrategy,
    ImprovementAdvisorReport,
)
from app import app


def test_improvement_advisor_performance_candidate():
    advisor = ImprovementAdvisor()
    c_code = """#include <stdio.h>
#include <string.h>

int main() {
    char str[100] = "hello world";
    for (int i = 0; i < strlen(str); i++) {
        putchar(str[i]);
    }
    return 0;
}
"""
    report = advisor.analyze_and_advise(c_code, filename="test_perf.c")
    assert isinstance(report, ImprovementAdvisorReport)
    assert report.total_candidates >= 1

    perf_candidates = [
        c for c in report.candidates
        if c.strategy == ImprovementStrategy.PERFORMANCE
    ]
    assert len(perf_candidates) >= 1
    cand = perf_candidates[0]
    assert "strlen" in cand.proposed_code
    assert "str_len = strlen(str)" in cand.proposed_code or "_len" in cand.proposed_code
    assert cand.user_decision_state == "AWAITING_USER_DECISION"
    assert cand.unified_diff != ""
    assert "--- a/test_perf.c" in cand.unified_diff


def test_improvement_advisor_maintainability_candidate():
    advisor = ImprovementAdvisor()
    c_code = """#include <stdio.h>

void main() {
    printf("test\\n");
}
"""
    report = advisor.analyze_and_advise(c_code, filename="test_main.c")
    maint_candidates = [
        c for c in report.candidates
        if c.strategy == ImprovementStrategy.MAINTAINABILITY
    ]
    assert len(maint_candidates) >= 1
    cand = maint_candidates[0]
    assert "int main()" in cand.proposed_code
    assert cand.user_decision_state == "AWAITING_USER_DECISION"


def test_improvement_advisor_security_candidate():
    advisor = ImprovementAdvisor()
    c_code = """#include <stdio.h>
#include <string.h>

int main() {
    char dest[16];
    char src[32] = "input";
    strcpy(dest, src);
    return 0;
}
"""
    report = advisor.analyze_and_advise(c_code, filename="test_sec.c")
    sec_candidates = [
        c for c in report.candidates
        if c.strategy == ImprovementStrategy.SECURITY_HARDENING
    ]
    assert len(sec_candidates) >= 1
    cand = sec_candidates[0]
    assert "strncpy" in cand.proposed_code
    assert cand.user_decision_state == "AWAITING_USER_DECISION"


def test_improvement_advisor_independent_validation():
    advisor = ImprovementAdvisor()
    c_code = """#include <stdio.h>
#include <string.h>

int main() {
    char str[10] = "abc";
    for (int i = 0; i < strlen(str); i++) {
        printf("%c", str[i]);
    }
    return 0;
}
"""
    report = advisor.analyze_and_advise(c_code, filename="test_val.c")
    assert report.total_candidates > 0
    for cand in report.candidates:
        assert cand.validation_report is not None
        assert "syntax_passed" in cand.validation_report
        assert cand.user_decision_state == "AWAITING_USER_DECISION"
        assert cand.before_scores is not None


def test_improvement_api_endpoints_and_decision_lifecycle():
    client = app.test_client()

    c_code = """#include <stdio.h>
void main() {
    printf("hello");
}
"""
    # 1. Request improvement advisories via API
    resp = client.post("/api/improvement/advise", json={"code": c_code, "filename": "test_api.c"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "candidates" in data
    assert data["total_candidates"] >= 1

    candidate = data["candidates"][0]
    cand_id = candidate["id"]
    assert candidate["user_decision_state"] == "AWAITING_USER_DECISION"

    # 2. Reject candidate
    rej_resp = client.post(f"/api/improvement/candidate/{cand_id}/reject")
    assert rej_resp.status_code == 200
    rej_data = rej_resp.get_json()
    assert rej_data["success"] is True
    assert rej_data["user_decision"] in ["REJECTED", "USER_REJECTED"]

    # 3. Re-run advise and apply candidate
    resp2 = client.post("/api/improvement/advise", json={"code": c_code, "filename": "test_api.c"})
    data2 = resp2.get_json()
    candidate2 = data2["candidates"][0]
    cand_id2 = candidate2["id"]

    apply_resp = client.post(f"/api/improvement/candidate/{cand_id2}/apply", json={"current_code": c_code})
    assert apply_resp.status_code == 200
    apply_data = apply_resp.get_json()
    assert apply_data["success"] is True
    assert apply_data["user_decision"] in ["APPROVED", "APPLIED"]
    assert "int main" in apply_data["applied_code"]
