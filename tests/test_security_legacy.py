import glob
import os
import re
import sys
import pytest

sys.path.insert(0, os.path.abspath("."))
from compiler.gui_bridge import repair_source_for_gui
from compiler.security_auto_fixer import _split_lines, _code_mask, _function_spans, SecurityAutoFixer

LEGACY_PATTERN = os.path.join("examples", "security_fix_2026", "legacy_*.c")


def test_security_legacy_suite():
    legacy_files = glob.glob(LEGACY_PATTERN)
    if not legacy_files:
        # None dropped in yet, suite is ready for user's files
        return

    fixer = SecurityAutoFixer()

    for fpath in legacy_files:
        fname = os.path.basename(fpath)
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()

        res = repair_source_for_gui(code, filename=fname, enable_ai=False, enable_sec_fix=True)

        # 1. Zero [CRITICAL] findings remaining
        crit_issues = [w for w in res.get("security_warnings", []) if "[CRITICAL]" in str(w)]
        assert len(crit_issues) == 0, f"{fname}: CRITICAL findings remained: {crit_issues}"

        # 2. No new semantic undeclared issue caused by security edit
        sec_undeclared = res.get("sec_undeclared_introduced", 0)
        assert sec_undeclared == 0, f"{fname}: security edit introduced {sec_undeclared} undeclared identifiers"

        # 3. Every scanf("%Ns", v) with a known char[M] has N == M-1
        corrected = res.get("corrected_code", code)
        lines, _ = _split_lines(corrected)
        mask = _code_mask(lines)
        spans = _function_spans(lines, mask)

        for idx, line in enumerate(lines):
            for m in re.finditer(r'\bscanf\s*\(\s*"%(\d+)s"\s*,\s*([A-Za-z_]\w*)\s*\)', line):
                width = int(m.group(1))
                vname = m.group(2)
                buf_size = fixer._array_size(lines, mask, spans, idx, vname)
                if buf_size is not None and buf_size >= 2:
                    assert width == buf_size - 1, (
                        f"{fname}:{idx+1}: scanf width %{width}s does not match {vname} size {buf_size} - 1"
                    )
