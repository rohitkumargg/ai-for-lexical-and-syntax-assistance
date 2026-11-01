import pytest
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from compiler.patch_validator import PatchIntegrityInspector

def test_benign_inspector_accepts_clean_edits():
    tests = [
        ("Drop extra argument",
         "int f(int a, int b) { return a + b; }\nint main() { return f(1, 2, 3); }",
         "int f(int a, int b) { return a + b; }\nint main() { return f(1, 2); }"),
        ("Add an include",
         "int main() { return 0; }",
         "#include <stdio.h>\nint main() { return 0; }"),
        ("Widening cast",
         "int main() { int a = 5; double d = a / 2; return 0; }",
         "int main() { int a = 5; double d = (double)a / 2; return 0; }"),
        ("One-character insertion: )",
         "int main() { if (x > 0 return 0; }",
         "int main() { if (x > 0) return 0; }"),
        ("One-character insertion: ;",
         "int main() { int a = 5 return a; }",
         "int main() { int a = 5; return a; }"),
        ("One-character insertion: ]",
         "int main() { int arr[5; return 0; }",
         "int main() { int arr[5]; return 0; }"),
    ]

    for name, orig, cand in tests:
        ok, reasons = PatchIntegrityInspector.inspect(orig, cand)
        assert ok, f"Benign edit '{name}' should be accepted by PatchIntegrityInspector, got reasons: {reasons}"
