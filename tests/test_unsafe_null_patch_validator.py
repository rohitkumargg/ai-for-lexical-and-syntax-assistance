import pytest
from compiler.patch_validator import PatchValidator, ValidationVerdict

def test_validator_rejects_call_replacement_with_null_used_downstream():
    """
    Test C2 requirement:
    A candidate may not replace a call's result with a constant (NULL/0) that later code uses.
    Example: replacing popen() with NULL where fgets(buf, sizeof(buf), fp) reads fp downstream.
    """
    original = """
void *popen(char *cmd, char *mode);
int fgets(char *s, int size, void *stream);
int fclose(void *stream);

int main() {
    char cmd[64] = "ls";
    void *fp = popen(cmd, "r");
    char buf[128];
    while (fgets(buf, 128, fp)) {
        printf("%s", buf);
    }
    fclose(fp);
    return 0;
}
"""
    # Unsafe patch that replaces popen with NULL
    candidate_null = """
void *popen(char *cmd, char *mode);
int fgets(char *s, int size, void *stream);
int fclose(void *stream);

int main() {
    char cmd[64] = "ls";
    void *fp = NULL; /* Disallowed command invocation remediated */
    char buf[128];
    while (fgets(buf, 128, fp)) {
        printf("%s", buf);
    }
    fclose(fp);
    return 0;
}
"""
    validator = PatchValidator()
    report = validator.validate_patch(
        original_code=original,
        candidate_code=candidate_null,
        filename="test_popen.c",
        language="c"
    )

    assert report.is_valid is False
    assert report.verdict == ValidationVerdict.FAILED_SECURITY
    assert any("Unsafe Constant Replacement" in r or "NULL dereference" in r for r in report.remaining_risks)


def test_validator_catches_new_null_dereference():
    """
    Test C2 requirement:
    The validator must catch a new NULL dereference (e.g. *p where p is set to NULL).
    """
    original = """
#include <stdio.h>
#include <stdlib.h>
int main() {
    int *p = (int*)malloc(sizeof(int));
    *p = 42;
    printf("%d\\n", *p);
    free(p);
    return 0;
}
"""
    candidate_null_deref = """
#include <stdio.h>
#include <stdlib.h>
int main() {
    int *p = NULL;
    *p = 42;
    printf("%d\\n", *p);
    return 0;
}
"""
    validator = PatchValidator()
    report = validator.validate_patch(
        original_code=original,
        candidate_code=candidate_null_deref,
        filename="test_null_deref.c",
        language="c"
    )

    assert report.is_valid is False
    assert report.verdict == ValidationVerdict.FAILED_SECURITY
    assert any("NULL Dereference" in r for r in report.remaining_risks)
