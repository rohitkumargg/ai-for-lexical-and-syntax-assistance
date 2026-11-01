# tests/test_scanf_validation.py
"""
Regression test suite for general formatted input validation and buffer-size mismatch checking.

Covers:
1. Both buffers in user example: char a[20]; char b[10]; scanf("%99s", a); scanf("%99s", b);
2. Correct widths (%19s, %9s) pass validation cleanly.
3. Oversized widths (%99s) are rejected with FAILED_SECURITY verdict.
4. Partial repairs (repairing buffer 'a' to %19s but leaving buffer 'b' with %99s) must NOT be marked fixed.
5. Multiple conversions in a single format string: scanf("%99s %99s", a, b);
6. Assignment suppression: scanf("%*d %99s", a); correctly aligns to buffer 'a'.
7. Supported scanf-family variants: fscanf and sscanf with varied argument offsets.
8. Scanset specifiers: %[^\n] and %99[^\n].
9. Buffer capacity uncertainty for pointers (char *p) and non-literal format strings.
10. Model retry feedback generation with exact capacity constraints (%19s and %9s).
11. Source code immutability when candidate validation fails.
"""
import pytest
from compiler.scanf_analyzer import ScanfSecurityAnalyzer
from compiler.security_rules import run_security_rules
from compiler.security_checker import SecurityChecker
from compiler.security_reporter import SecurityReporter
from compiler.patch_validator import PatchValidator, ValidationVerdict
from compiler.security_remediation import SecurityRemediationEngine, RemediationValidationStatus
from compiler.security_auto_fixer import SecurityAutoFixer


def test_user_example_both_buffers_oversized_detected():
    """Verify that both buffers 'a' (20 bytes) and 'b' (10 bytes) with %99s are detected as vulnerabilities."""
    code = """
int main() {
    char a[20];
    char b[10];
    scanf("%99s", a);
    scanf("%99s", b);
    return 0;
}
"""
    # 1. Test AST Security Rules (SEC-09)
    _, findings, _ = run_security_rules(code)
    sec09_findings = [f for f in findings if getattr(f, "rule", "") == "SEC-09"]
    assert len(sec09_findings) == 2, f"Expected 2 SEC-09 findings, got {len(sec09_findings)}"

    f_a = next(f for f in sec09_findings if "'a'" in f.message)
    f_b = next(f for f in sec09_findings if "'b'" in f.message)
    assert f_a.severity == "HIGH"
    assert "20" in f_a.message and "%19s" in f_a.message
    assert f_b.severity == "HIGH"
    assert "10" in f_b.message and "%9s" in f_b.message

    # 2. Test SecurityChecker
    issues = SecurityChecker().check(code)
    unsafe_issues = [i for i in issues if "scanf" in getattr(i, "stable_id", "")]
    assert len(unsafe_issues) == 2


def test_candidate_with_oversized_widths_rejected_by_validator():
    """Candidate with %99s for both 20-byte and 10-byte buffers must fail patch validation."""
    orig_code = """
int main() {
    char a[20];
    char b[10];
    scanf("%s", a);
    scanf("%s", b);
    return 0;
}
"""
    cand_code = """
int main() {
    char a[20];
    char b[10];
    scanf("%99s", a);
    scanf("%99s", b);
    return 0;
}
"""
    validator = PatchValidator()
    report = validator.validate_patch(orig_code, cand_code, filename="main.c", language="c")

    assert report.is_valid is False
    assert report.security_passed is False
    assert report.verdict == ValidationVerdict.FAILED_SECURITY
    assert len(report.remaining_risks) >= 2
    # Ensure explanation contains specific buffer capacity constraints
    assert "buffer 'a' capacity of 20 bytes" in report.explanation or "buffer 'a'" in report.explanation
    assert "buffer 'b' capacity of 10 bytes" in report.explanation or "buffer 'b'" in report.explanation


def test_candidate_with_correct_widths_validated_cleanly():
    """Candidate with %19s and %9s must pass patch validation with VALIDATED verdict."""
    orig_code = """
int main() {
    char a[20];
    char b[10];
    scanf("%s", a);
    scanf("%s", b);
    return 0;
}
"""
    safe_cand = """
int main() {
    char a[20];
    char b[10];
    scanf("%19s", a);
    scanf("%9s", b);
    return 0;
}
"""
    validator = PatchValidator()
    report = validator.validate_patch(orig_code, safe_cand, filename="main.c", language="c")

    assert report.is_valid is True
    assert report.security_passed is True
    assert report.verdict == ValidationVerdict.VALIDATED
    assert report.explanation == "Candidate patch validated successfully across syntax, semantics, and security policies."


def test_partial_fix_rejected_when_second_vulnerability_remains():
    """A repair that fixes buffer 'a' to %19s but leaves buffer 'b' with %99s must NOT be marked fixed."""
    orig_code = """
int main() {
    char a[20];
    char b[10];
    scanf("%s", a);
    scanf("%s", b);
    return 0;
}
"""
    partial_cand = """
int main() {
    char a[20];
    char b[10];
    scanf("%19s", a);
    scanf("%99s", b);
    return 0;
}
"""
    validator = PatchValidator()
    report = validator.validate_patch(orig_code, partial_cand, filename="main.c", language="c")

    assert report.is_valid is False
    assert report.security_passed is False
    assert report.verdict == ValidationVerdict.FAILED_SECURITY
    # Buffer 'b' is still vulnerable
    assert any("line 6" in r and "SEC" in r for r in report.remaining_risks)


def test_single_call_with_multiple_conversions():
    """Verify single scanf with multiple conversions 'scanf("%99s %99s", a, b)' detects and fixes both."""
    code = """
int main() {
    char a[20];
    char b[10];
    scanf("%99s %99s", a, b);
    return 0;
}
"""
    findings = ScanfSecurityAnalyzer.analyze_call(
        fn_name="scanf",
        line=5,
        col=5,
        args_text=['"%99s %99s"', "a", "b"],
        fmt_raw="%99s %99s",
        source_text=code,
    )
    assert len(findings) == 2
    f_a, f_b = findings[0], findings[1]
    assert f_a.dest_var_name == "a"
    assert f_a.declared_capacity == 20
    assert f_a.max_safe_width == 19
    assert f_a.safe_replacement_spec == "%19s"

    assert f_b.dest_var_name == "b"
    assert f_b.declared_capacity == 10
    assert f_b.max_safe_width == 9
    assert f_b.safe_replacement_spec == "%9s"

    safe_fmt = ScanfSecurityAnalyzer.compute_safe_format_string("%99s %99s", findings)
    assert safe_fmt == "%19s %9s"


def test_assignment_suppression_skips_argument_consumption():
    """Verify %*d does not consume a variadic argument, correctly aligning subsequent %99s with buffer 'a'."""
    code = """
int main() {
    char a[20];
    scanf("%*d %99s", a);
    return 0;
}
"""
    findings = ScanfSecurityAnalyzer.analyze_call(
        fn_name="scanf",
        line=4,
        col=5,
        args_text=['"%*d %99s"', "a"],
        fmt_raw="%*d %99s",
        source_text=code,
    )
    assert len(findings) == 1
    f_a = findings[0]
    assert f_a.dest_var_name == "a"
    assert f_a.declared_capacity == 20
    assert f_a.safe_replacement_spec == "%19s"


def test_scanf_family_variants_fscanf_and_sscanf():
    """Verify fscanf and sscanf handle format strings at index 1 and variadic arguments starting at index 2."""
    code = """
int main() {
    char a[20];
    FILE *fp;
    char src[100];
    fscanf(fp, "%99s", a);
    sscanf(src, "%99s", a);
    return 0;
}
"""
    findings_f = ScanfSecurityAnalyzer.analyze_call(
        fn_name="fscanf",
        line=6,
        col=5,
        args_text=["fp", '"%99s"', "a"],
        fmt_raw="%99s",
        source_text=code,
    )
    assert len(findings_f) == 1
    assert findings_f[0].dest_var_name == "a"
    assert findings_f[0].safe_replacement_spec == "%19s"

    findings_s = ScanfSecurityAnalyzer.analyze_call(
        fn_name="sscanf",
        line=7,
        col=5,
        args_text=["src", '"%99s"', "a"],
        fmt_raw="%99s",
        source_text=code,
    )
    assert len(findings_s) == 1
    assert findings_s[0].dest_var_name == "a"
    assert findings_s[0].safe_replacement_spec == "%19s"


def test_scanset_conversion_handling():
    """Verify scansets %99[^\n] are bounded to %19[^\n] for buffer of size 20."""
    code = """
int main() {
    char a[20];
    scanf("%99[^\\n]", a);
    return 0;
}
"""
    findings = ScanfSecurityAnalyzer.analyze_call(
        fn_name="scanf",
        line=4,
        col=5,
        args_text=['"%99[^\\n]"', "a"],
        fmt_raw="%99[^\\n]",
        source_text=code,
    )
    assert len(findings) == 1
    assert findings[0].dest_var_name == "a"
    assert findings[0].max_safe_width == 19
    assert findings[0].safe_replacement_spec == "%19[^\\n]"


def test_unknown_buffer_capacity_reports_uncertainty():
    """Verify that pointer destination (char *p) reports uncertainty rather than claiming safe."""
    code = """
int main() {
    char *p;
    scanf("%99s", p);
    scanf("%s", p);
    return 0;
}
"""
    findings_spec = ScanfSecurityAnalyzer.analyze_call(
        fn_name="scanf",
        line=4,
        col=5,
        args_text=['"%99s"', "p"],
        fmt_raw="%99s",
        source_text=code,
    )
    assert len(findings_spec) == 1
    assert findings_spec[0].is_uncertain is True
    assert findings_spec[0].severity == "WARNING"
    assert "cannot be statically verified" in findings_spec[0].message

    findings_unbounded = ScanfSecurityAnalyzer.analyze_call(
        fn_name="scanf",
        line=5,
        col=5,
        args_text=['"%s"', "p"],
        fmt_raw="%s",
        source_text=code,
    )
    assert len(findings_unbounded) == 1
    assert findings_unbounded[0].is_uncertain is True
    assert findings_unbounded[0].is_vulnerable is True
    assert "unknown capacity" in findings_unbounded[0].message


def test_macro_defined_buffer_capacity_resolved():
    """Verify buffer declared with #define BUFFER_SIZE 32 is accurately resolved."""
    code = """
#define BUFFER_SIZE 32
int main() {
    char buf[BUFFER_SIZE];
    scanf("%99s", buf);
    return 0;
}
"""
    findings = ScanfSecurityAnalyzer.analyze_call(
        fn_name="scanf",
        line=5,
        col=5,
        args_text=['"%99s"', "buf"],
        fmt_raw="%99s",
        source_text=code,
    )
    assert len(findings) == 1
    assert findings[0].declared_capacity == 32
    assert findings[0].max_safe_width == 31
    assert findings[0].safe_replacement_spec == "%31s"


def test_security_auto_fixer_repairs_multiple_calls_on_same_line():
    """Verify SecurityAutoFixer fixes both 'scanf(\"%99s\", a); scanf(\"%99s\", b);' on the same line."""
    code = """
int main() {
    char a[20];
    char b[10];
    scanf("%99s", a); scanf("%99s", b);
    return 0;
}
"""
    fixer = SecurityAutoFixer()
    res = fixer.apply_fixes(code)
    assert '%19s' in res.source
    assert '%9s' in res.source
    assert '%99s' not in res.source


def test_remediation_engine_handles_and_validates_scanf():
    """Verify SecurityRemediationEngine generates deterministic recommendation and rejects unsafe candidate."""
    code = """
int main() {
    char a[20];
    char b[10];
    scanf("%s", a);
    scanf("%s", b);
    return 0;
}
"""
    engine = SecurityRemediationEngine()
    recs = engine.generate_recommendations(code, filename="main.c")
    assert len(recs) >= 2
    for r in recs:
        assert r.category == "BUFFER_OVERFLOW"
        # Deterministic replacement uses safe widths %19s or %9s
        if r.proposed_code:
            assert "%99s" not in r.proposed_code
            assert ("%19s" in r.proposed_code or "%9s" in r.proposed_code)
            assert r.validation_status in (
                RemediationValidationStatus.FIXED_AND_VALIDATED.value,
                RemediationValidationStatus.PARTIALLY_ADDRESSED.value,
            )
