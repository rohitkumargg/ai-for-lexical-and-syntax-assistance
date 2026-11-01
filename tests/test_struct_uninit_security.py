import pytest
from compiler.security_rules import run_security_rules


def test_struct_field_initialized_read_no_warning():
    code = """struct Point {
    int x;
    int y;
};

int main() {
    struct Point pt;
    pt.x = 20;
    return pt.x;
}
"""
    fixed_src, findings, steps = run_security_rules(code)
    uninit_findings = [f for f in findings if f.kind == "uninitialized_variable"]
    assert len(uninit_findings) == 0, f"Expected 0 uninit findings, got {uninit_findings}"


def test_struct_field_uninitialized_read_warns():
    code = """struct Point {
    int x;
    int y;
};

int main() {
    struct Point pt;
    pt.x = 20;
    return pt.y;
}
"""
    fixed_src, findings, steps = run_security_rules(code)
    uninit_findings = [f for f in findings if f.kind == "uninitialized_variable"]
    assert len(uninit_findings) == 1, f"Expected 1 uninit finding, got {uninit_findings}"
    assert "pt.y" in uninit_findings[0].message
    assert uninit_findings[0].action == "warned"


def test_struct_all_fields_initialized_no_warning():
    code = """struct Point {
    int x;
    int y;
};

int main() {
    struct Point pt;
    pt.x = 10;
    pt.y = 20;
    return pt.x + pt.y;
}
"""
    fixed_src, findings, steps = run_security_rules(code)
    uninit_findings = [f for f in findings if f.kind == "uninitialized_variable"]
    assert len(uninit_findings) == 0, f"Expected 0 uninit findings, got {uninit_findings}"


def test_struct_field_y_initialized_field_x_uninitialized():
    code = """struct Point {
    int x;
    int y;
};

int main() {
    struct Point pt;
    pt.y = 20;
    return pt.x;
}
"""
    fixed_src, findings, steps = run_security_rules(code)
    uninit_findings = [f for f in findings if f.kind == "uninitialized_variable"]
    assert len(uninit_findings) == 1, f"Expected 1 uninit finding for pt.x, got {uninit_findings}"
    assert "pt.x" in uninit_findings[0].message
    assert uninit_findings[0].action == "warned"


def test_multiple_struct_instances_independent():
    code = """struct Point {
    int x;
    int y;
};

int main() {
    struct Point p1;
    struct Point p2;
    p1.x = 10;
    p2.y = 20;
    return p1.x + p2.y;
}
"""
    fixed_src, findings, steps = run_security_rules(code)
    uninit_findings = [f for f in findings if f.kind == "uninitialized_variable"]
    assert len(uninit_findings) == 0, f"Expected 0 uninit findings, got {uninit_findings}"


def test_multiple_struct_instances_independent_with_warnings():
    code = """struct Point {
    int x;
    int y;
};

int main() {
    struct Point p1;
    struct Point p2;
    p1.x = 10;
    p2.y = 20;
    return p1.y + p2.x;
}
"""
    fixed_src, findings, steps = run_security_rules(code)
    uninit_findings = [f for f in findings if f.kind == "uninitialized_variable"]
    assert len(uninit_findings) == 2, f"Expected 2 uninit findings, got {uninit_findings}"
    messages = [f.message for f in uninit_findings]
    assert any("p1.y" in m for m in messages)
    assert any("p2.x" in m for m in messages)
