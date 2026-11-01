import pytest
from compiler.windowed_repair import get_window_for_finding, splice_window_into_source

def test_get_window_small_file():
    code = "line1\nline2\nline3\n"
    win_src, start, end, rel = get_window_for_finding(code, 2, radius=5, max_lines=40)
    assert win_src == code
    assert start == 1
    assert end == 3
    assert rel == 2

def test_get_window_large_file():
    lines = [f"line{i}\n" for i in range(1, 101)]
    code = "".join(lines)
    win_src, start, end, rel = get_window_for_finding(code, 50, radius=5, max_lines=20)
    assert start <= 50 <= end
    assert (end - start + 1) <= 20
    assert rel == (50 - start + 1)
    assert f"line50\n" in win_src

def test_splice_window_middle():
    lines = [f"line{i}\n" for i in range(1, 11)]
    code = "".join(lines)
    # Replace lines 4..6 with repaired lines
    repaired = "line4_fixed\nline5_fixed\n"
    spliced = splice_window_into_source(code, repaired, 4, 6)
    expected = "line1\nline2\nline3\nline4_fixed\nline5_fixed\nline7\nline8\nline9\nline10\n"
    assert spliced == expected

def test_splice_window_full_file():
    code = "a\nb\nc\n"
    repaired = "x\ny\n"
    spliced = splice_window_into_source(code, repaired, 1, 3)
    assert spliced == "x\ny\n"

