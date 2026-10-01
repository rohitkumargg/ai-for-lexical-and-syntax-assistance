import pytest
from compiler.preprocessor import (
    repair_preprocessor_directives,
    extract_preprocessor_symbols,
    strip_preprocessor_lines,
)


def test_repair_missing_hash_include():
    src = "include <stdio.h>\nint main() { return 0; }\n"
    repaired, msg = repair_preprocessor_directives(src)
    assert msg == "added missing '#' before 'include'"
    assert repaired.startswith("#include <stdio.h>\n")


def test_repair_missing_hash_define():
    src = "define MAX 100\nint main() { return 0; }\n"
    repaired, msg = repair_preprocessor_directives(src)
    assert msg == "added missing '#' before 'define'"
    assert repaired.startswith("#define MAX 100\n")


def test_repair_misspelled_include():
    for typo in ["#incude", "#incldue", "#inlcude", "#includ"]:
        src = f"{typo} <stdlib.h>\nint main() {{ return 0; }}\n"
        repaired, msg = repair_preprocessor_directives(src)
        assert msg == "corrected misspelled '#include' directive"
        assert repaired.startswith("#include <stdlib.h>\n")


def test_repair_misspelled_define():
    for typo in ["#defien", "#defin", "#defne"]:
        src = f"{typo} PI 3.14\nint main() {{ return 0; }}\n"
        repaired, msg = repair_preprocessor_directives(src)
        assert msg == "corrected misspelled '#define' directive"
        assert repaired.startswith("#define PI 3.14\n")


def test_repair_missing_closing_angle():
    src = "#include <stdio.h\nint main() { return 0; }\n"
    repaired, msg = repair_preprocessor_directives(src)
    assert msg == "added missing '>' to '#include' directive"
    assert repaired.startswith("#include <stdio.h>\n")


def test_repair_missing_closing_quote():
    src = '#include "myheader.h\nint main() { return 0; }\n'
    repaired, msg = repair_preprocessor_directives(src)
    assert msg == 'added missing closing quote to \'#include\' directive'
    assert repaired.startswith('#include "myheader.h"\n')


def test_extract_symbols():
    src = (
        "#include <stdio.h>\n"
        "#define BUFFER_SIZE 1024\n"
        "#define SQUARE(x) ((x)*(x))\n"
    )
    syms = extract_preprocessor_symbols(src)
    assert "<stdio.h>" in syms["includes"]
    assert "BUFFER_SIZE" in syms["macros"]
    assert syms["macros"]["BUFFER_SIZE"]["is_func"] is False
    assert syms["macros"]["BUFFER_SIZE"]["body"] == "1024"
    assert "SQUARE" in syms["macros"]
    assert syms["macros"]["SQUARE"]["is_func"] is True
    assert syms["macros"]["SQUARE"]["args"] == ["x"]


def test_strip_preprocessor_preserves_line_count():
    src = (
        "#include <stdio.h>\n"
        "#define VAL 10\n"
        "int main() {\n"
        "    return VAL;\n"
        "}\n"
    )
    stripped = strip_preprocessor_lines(src)
    assert len(src.splitlines()) == len(stripped.splitlines())
    assert stripped.splitlines()[0] == ""
    assert stripped.splitlines()[1] == ""
    assert stripped.splitlines()[2] == "int main() {"


def test_varied_inputs_multiarity_macro_and_inline_comments():
    src = (
        "  #include   <math.h>  \n"
        "#define CLAMP(x, low, high) (((x)<(low))?(low):(((x)>(high))?(high):(x)))\n"
        "#define PI 3.14159 /* circle constant */\n"
        "int main() { return 0; }\n"
    )
    syms = extract_preprocessor_symbols(src)
    assert "<math.h>" in syms["includes"]
    assert "CLAMP" in syms["macros"]
    assert syms["macros"]["CLAMP"]["is_func"] is True
    assert syms["macros"]["CLAMP"]["args"] == ["x", "low", "high"]
    assert "PI" in syms["macros"]
    assert "3.14159" in syms["macros"]["PI"]["body"]


def test_varied_inputs_empty_and_whitespace():
    # Empty string should not fail
    rep, msg = repair_preprocessor_directives("")
    assert rep == ""
    assert msg is None

    syms = extract_preprocessor_symbols("")
    assert syms == {"includes": [], "macros": {}}

    stripped = strip_preprocessor_lines("")
    assert stripped == ""


def test_varied_inputs_no_directives():
    src = "int main() {\n    int a = 1;\n    return a;\n}\n"
    rep, msg = repair_preprocessor_directives(src)
    assert rep == src
    assert msg is None

    syms = extract_preprocessor_symbols(src)
    assert syms == {"includes": [], "macros": {}}

    stripped = strip_preprocessor_lines(src)
    assert stripped == src

