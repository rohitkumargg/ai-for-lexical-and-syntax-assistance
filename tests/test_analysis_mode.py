import pytest
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from compiler.repair_planner import RepairPlanner
from compiler.call_extractor import get_extraction_mode
from app import app


def test_parseable_c_code_always_takes_ast_mode():
    """
    D4: Verifies that cleanly parseable C code takes 'AST' analysis_mode,
    and FAILS if parseable code takes the regex fallback ('REGEX_FALLBACK').
    """
    parseable_samples = [
        "int main() { return 0; }",
        """
        #include <stdio.h>
        int add(int a, int b) {
            return a + b;
        }
        int main() {
            int x = add(1, 2);
            return x;
        }
        """,
        """
        int process(char *buf, int len) {
            int i = 0;
            while (i < len) {
                buf[i] = 0;
                i++;
            }
            return 0;
        }
        """
    ]

    planner = RepairPlanner()
    for code in parseable_samples:
        mode = get_extraction_mode(code)
        assert mode == "AST", f"get_extraction_mode returned '{mode}', expected 'AST' for parseable code"

        res = planner.plan_and_repair(code, filename="test.c", language="c")
        analysis_mode = res.get("analysis_mode")
        assert analysis_mode == "AST", f"plan_and_repair returned analysis_mode='{analysis_mode}', expected 'AST' for parseable code"


def test_unparseable_code_takes_regex_fallback():
    """
    D4: Verifies that unparseable C code (syntax errors) takes 'REGEX_FALLBACK'.
    """
    unparseable_code = "int main() { int x = ; return 0; "  # unclosed brace and incomplete assignment
    mode = get_extraction_mode(unparseable_code)
    assert mode == "REGEX_FALLBACK", f"Expected REGEX_FALLBACK, got {mode}"


def test_api_endpoints_expose_analysis_mode():
    """
    D4: Verifies that API endpoints (/api/repair and /api/coordinator/analyze_and_plan)
    always include 'analysis_mode' in their response payload.
    """
    client = app.test_client()
    clean_code = "int main() { return 0; }"

    # Test /api/coordinator/analyze_and_plan
    res = client.post("/api/coordinator/analyze_and_plan", json={
        "code": clean_code,
        "filename": "clean.c",
        "language": "c"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert "analysis_mode" in data, "analysis_mode missing from /api/coordinator/analyze_and_plan response"
    assert data["analysis_mode"] == "AST", f"Expected 'AST', got '{data['analysis_mode']}'"

    # Test /api/repair
    res2 = client.post("/api/repair", json={
        "code": clean_code,
        "filename": "clean.c",
        "language": "c"
    })
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert "analysis_mode" in data2, "analysis_mode missing from /api/repair response"
    assert data2["analysis_mode"] == "AST", f"Expected 'AST', got '{data2['analysis_mode']}'"
