# compiler/scanf_analyzer.py
"""
General Formatted Input and Buffer-Size Mismatch Analyzer for C / SimpleC.

Inspects scanf-family calls (scanf, fscanf, sscanf, vscanf, vfscanf, vsscanf)
for buffer overflows and width mismatches against destination buffer capacities.

Fulfills Requirements:
1. Detect %s and %[...] conversions where width > (capacity - 1) byte for null terminator.
2. Handle arbitrary buffer sizes, multiple input calls, whitespace and formatting variations.
3. Map multiple conversions in a single format string to their respective variadic arguments,
   skipping assignment-suppressed conversions (%*...).
4. Establish buffer capacity from declaration context, AST symbols, #define macros, and consts.
5. If capacity or format-string cannot be established reliably, report uncertainty instead of claiming safe.
6. Support bounded auto-fixes and exact feedback generation for candidate validation and model retry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Set


SCANF_FAMILY_FUNCTIONS = {
    "scanf": {"fmt_idx": 0, "var_start": 1},
    "vscanf": {"fmt_idx": 0, "var_start": 1},
    "fscanf": {"fmt_idx": 1, "var_start": 2},
    "vfscanf": {"fmt_idx": 1, "var_start": 2},
    "sscanf": {"fmt_idx": 1, "var_start": 2},
    "vsscanf": {"fmt_idx": 1, "var_start": 2},
}


@dataclass
class ScanfConversion:
    conv_index: int              # Sequential index among all conversions in the format string
    raw_spec: str                # e.g., "%s", "%99s", "%*d", "%19[^\n]"
    conv_type: str               # 's', 'scanset', 'c', 'd', 'i', 'f', etc.
    width: Optional[int]         # Specified field width (int) or None if unbounded
    is_suppressed: bool          # True if %*... (assignment suppression)
    length_mod: str              # e.g. "h", "l", "ll", ""
    scanset_body: str            # Body of scanset if conv_type == 'scanset', else ""
    start_in_fmt: int            # Start index in format string (excluding outer quotes)
    end_in_fmt: int              # End index in format string (excluding outer quotes)
    arg_index: Optional[int]     # 0-based argument index in call arguments, or None if suppressed
    arg_text: Optional[str]      # Argument expression text, e.g. "a", "&b[0]"
    var_name: Optional[str]      # Extracted root variable identifier, e.g. "a"


@dataclass
class ScanfFinding:
    fn_name: str
    line: int
    col: int
    fmt_raw: str
    conversion: ScanfConversion
    dest_var_name: str
    declared_capacity: Optional[int]
    max_safe_width: Optional[int]
    requested_width: Optional[int]
    is_vulnerable: bool
    is_uncertain: bool
    severity: str                # "HIGH" for confirmed overflow/unbounded, "WARNING" for uncertain
    message: str
    suggestion: str
    safe_replacement_spec: str   # Replacement specifier, e.g. "%19s"


def clean_var_identifier(arg_expr: str) -> str:
    """Extracts root variable identifier from argument expression like '&a', 'buf', '&buf[0]', 'buf + 0'."""
    text = (arg_expr or "").strip()
    if text.startswith("&"):
        text = text[1:].strip()
    # Match first valid identifier token
    m = re.match(r"([A-Za-z_]\w*)", text)
    if m:
        return m.group(1)
    return text


def extract_macro_defines(source_text: str) -> Dict[str, int]:
    """Extracts integer #define constants and const ints from source."""
    constants: Dict[str, int] = {}
    if not source_text:
        return constants

    # #define BUF_SIZE 20
    for m in re.finditer(r"#define\s+([A-Za-z_]\w*)\s+([0-9]+)\b", source_text):
        try:
            constants[m.group(1)] = int(m.group(2))
        except ValueError:
            pass

    # const int BUF_SIZE = 20;
    for m in re.finditer(r"\bconst\s+(?:int|size_t|unsigned\s+int)\s+([A-Za-z_]\w*)\s*=\s*([0-9]+)\s*;", source_text):
        try:
            constants[m.group(1)] = int(m.group(2))
        except ValueError:
            pass

    return constants


def resolve_buffer_capacity(
    var_name: str,
    local_vars: Optional[Dict[str, Any]] = None,
    global_vars: Optional[Dict[str, Any]] = None,
    source_text: str = "",
) -> Tuple[Optional[int], bool]:
    """
    Resolves the capacity in bytes for a buffer variable.
    Returns (capacity, is_reliably_known).
    If capacity cannot be determined (e.g. pointer 'char *', parameter), returns (None, False).
    """
    if not var_name:
        return None, False

    local_vars = local_vars or {}
    global_vars = global_vars or {}
    macros = extract_macro_defines(source_text)

    var_info = local_vars.get(var_name) or global_vars.get(var_name)
    if var_info:
        # Check if declared explicitly as pointer (e.g. char *p, char* p)
        if var_info.get("is_pointer") and not var_info.get("is_array"):
            return None, False

        # If array with known size
        if var_info.get("is_array"):
            arr_size = var_info.get("array_size")
            if arr_size is not None:
                if isinstance(arr_size, int):
                    return arr_size, True
                if isinstance(arr_size, str) and arr_size in macros:
                    return macros[arr_size], True

    # Fallback inspection of source text for char array declarations:
    # e.g. char a[20]; char a[BUF_SIZE];
    decl_pattern = re.compile(
        r"\b(?:char|unsigned\s+char|signed\s+char)\s+"
        + re.escape(var_name)
        + r"\s*\[\s*([A-Za-z_0-9]+)\s*\]"
    )
    m = decl_pattern.search(source_text)
    if m:
        dim_str = m.group(1).strip()
        if dim_str.isdigit():
            return int(dim_str), True
        if dim_str in macros:
            return macros[dim_str], True

    # Check for pointer declaration in source: char *a;
    ptr_pattern = re.compile(
        r"\b(?:char|unsigned\s+char|signed\s+char)\s*\*\s*" + re.escape(var_name) + r"\b"
    )
    if ptr_pattern.search(source_text):
        return None, False

    return None, False


class ScanfSecurityAnalyzer:
    """Stateful parser and security checker for scanf-family calls."""

    @staticmethod
    def parse_format_conversions(
        fmt_raw: str,
        call_args: List[str],
        fn_name: str = "scanf",
    ) -> List[ScanfConversion]:
        """
        Parses all conversion specifications from fmt_raw.
        Correlates each non-suppressed conversion to the appropriate call argument.
        """
        conversions: List[ScanfConversion] = []
        fn_cfg = SCANF_FAMILY_FUNCTIONS.get(fn_name, {"fmt_idx": 0, "var_start": 1})
        var_start = fn_cfg["var_start"]

        i = 0
        n = len(fmt_raw)
        consumed_arg_count = 0
        conv_idx = 0

        while i < n:
            if fmt_raw[i] != "%":
                i += 1
                continue

            # Found '%'
            spec_start = i
            i += 1
            if i >= n:
                # Malformed trailing '%'
                break

            # Handle literal '%%'
            if fmt_raw[i] == "%":
                i += 1
                continue

            # Assignment suppression flag: '*'
            is_suppressed = False
            if fmt_raw[i] == "*":
                is_suppressed = True
                i += 1

            # Field width: digits
            width: Optional[int] = None
            width_start = i
            while i < n and fmt_raw[i].isdigit():
                i += 1
            if i > width_start:
                try:
                    width = int(fmt_raw[width_start:i])
                except ValueError:
                    width = None

            # Length modifiers: hh, h, l, ll, j, z, t, L
            length_mod = ""
            for mod in ("ll", "hh", "l", "h", "j", "z", "t", "L"):
                if fmt_raw[i:].startswith(mod):
                    length_mod = mod
                    i += len(mod)
                    break

            if i >= n:
                break

            # Conversion character or scanset
            conv_char = fmt_raw[i]
            scanset_body = ""
            if conv_char == "[":
                # Scanset: %[...] or %[^...]
                scanset_start = i
                i += 1
                # If first character is '^', advance
                if i < n and fmt_raw[i] == "^":
                    i += 1
                # If next char is ']', it is part of the set (C standard rule)
                if i < n and fmt_raw[i] == "]":
                    i += 1
                while i < n and fmt_raw[i] != "]":
                    i += 1
                if i < n and fmt_raw[i] == "]":
                    i += 1  # consume ']'
                scanset_body = fmt_raw[scanset_start:i]
                conv_type = "scanset"
            else:
                conv_type = conv_char
                i += 1

            spec_end = i
            raw_spec = fmt_raw[spec_start:spec_end]

            # Correlate to argument
            arg_idx: Optional[int] = None
            arg_text: Optional[str] = None
            var_name: Optional[str] = None

            if not is_suppressed:
                target_arg_idx = var_start + consumed_arg_count
                if target_arg_idx < len(call_args):
                    arg_idx = target_arg_idx
                    arg_text = call_args[target_arg_idx].strip()
                    var_name = clean_var_identifier(arg_text)
                consumed_arg_count += 1

            conversions.append(
                ScanfConversion(
                    conv_index=conv_idx,
                    raw_spec=raw_spec,
                    conv_type=conv_type,
                    width=width,
                    is_suppressed=is_suppressed,
                    length_mod=length_mod,
                    scanset_body=scanset_body,
                    start_in_fmt=spec_start,
                    end_in_fmt=spec_end,
                    arg_index=arg_idx,
                    arg_text=arg_text,
                    var_name=var_name,
                )
            )
            conv_idx += 1

        return conversions

    @classmethod
    def analyze_call(
        cls,
        fn_name: str,
        line: int,
        col: int,
        args_text: List[str],
        fmt_raw: Optional[str],
        local_vars: Optional[Dict[str, Any]] = None,
        global_vars: Optional[Dict[str, Any]] = None,
        source_text: str = "",
    ) -> List[ScanfFinding]:
        """
        Analyzes a single call to a scanf-family function.
        Returns a list of ScanfFinding objects for all unsafe or uncertain conversions.
        """
        findings: List[ScanfFinding] = []
        if fn_name not in SCANF_FAMILY_FUNCTIONS:
            return findings

        fn_cfg = SCANF_FAMILY_FUNCTIONS[fn_name]
        fmt_idx = fn_cfg["fmt_idx"]

        # Check if format argument is provided
        if len(args_text) <= fmt_idx:
            return findings

        # Check if format string is a compile-time string literal
        if fmt_raw is None:
            # Format string is not a literal (e.g. variable or pointer)
            dummy_conv = ScanfConversion(
                conv_index=0,
                raw_spec="",
                conv_type="",
                width=None,
                is_suppressed=False,
                length_mod="",
                scanset_body="",
                start_in_fmt=0,
                end_in_fmt=0,
                arg_index=None,
                arg_text=None,
                var_name=None,
            )
            findings.append(
                ScanfFinding(
                    fn_name=fn_name,
                    line=line,
                    col=col,
                    fmt_raw="",
                    conversion=dummy_conv,
                    dest_var_name=args_text[fmt_idx],
                    declared_capacity=None,
                    max_safe_width=None,
                    requested_width=None,
                    is_vulnerable=False,
                    is_uncertain=True,
                    severity="WARNING",
                    message=f"Format string in '{fn_name}' is not a compile-time string literal; conversion widths cannot be verified statically.",
                    suggestion=f"Use a compile-time constant format string with explicit field widths in {fn_name}.",
                    safe_replacement_spec="",
                )
            )
            return findings

        # Parse conversions
        conversions = cls.parse_format_conversions(fmt_raw, args_text, fn_name=fn_name)

        # Check each string conversion (%s or %scanset)
        for conv in conversions:
            if conv.conv_type not in ("s", "scanset"):
                continue

            if conv.is_suppressed:
                # Suppressed conversions don't store to memory
                continue

            var_name = conv.var_name
            if not var_name:
                # Argument missing or could not be resolved
                findings.append(
                    ScanfFinding(
                        fn_name=fn_name,
                        line=line,
                        col=col,
                        fmt_raw=fmt_raw,
                        conversion=conv,
                        dest_var_name="<unknown>",
                        declared_capacity=None,
                        max_safe_width=None,
                        requested_width=conv.width,
                        is_vulnerable=False,
                        is_uncertain=True,
                        severity="WARNING",
                        message=f"Format conversion '{conv.raw_spec}' in {fn_name} has no matching destination argument.",
                        suggestion="Ensure each format specifier has a matching destination pointer.",
                        safe_replacement_spec=conv.raw_spec,
                    )
                )
                continue

            capacity, is_known = resolve_buffer_capacity(
                var_name=var_name,
                local_vars=local_vars,
                global_vars=global_vars,
                source_text=source_text,
            )

            # Suffix for specifier (e.g., "s" or scanset body "[^\n]")
            spec_tail = conv.scanset_body if conv.conv_type == "scanset" else "s"

            if is_known and capacity is not None:
                max_safe = max(0, capacity - 1)
                safe_spec = f"%{max_safe}{spec_tail}"

                if conv.width is None:
                    # Unbounded %s or %[...] into known buffer
                    findings.append(
                        ScanfFinding(
                            fn_name=fn_name,
                            line=line,
                            col=col,
                            fmt_raw=fmt_raw,
                            conversion=conv,
                            dest_var_name=var_name,
                            declared_capacity=capacity,
                            max_safe_width=max_safe,
                            requested_width=None,
                            is_vulnerable=True,
                            is_uncertain=False,
                            severity="HIGH",
                            message=(
                                f"Unbounded '{conv.raw_spec}' format specifier in {fn_name} overflows buffer '{var_name}' "
                                f"of capacity {capacity} bytes. Maximum safe width is {safe_spec} to allow 1 byte for null terminator."
                            ),
                            suggestion=f"use {safe_spec} to prevent buffer overflow",
                            safe_replacement_spec=safe_spec,
                        )
                    )
                elif conv.width > max_safe:
                    # Oversized width! e.g., %99s for buffer of size 20
                    findings.append(
                        ScanfFinding(
                            fn_name=fn_name,
                            line=line,
                            col=col,
                            fmt_raw=fmt_raw,
                            conversion=conv,
                            dest_var_name=var_name,
                            declared_capacity=capacity,
                            max_safe_width=max_safe,
                            requested_width=conv.width,
                            is_vulnerable=True,
                            is_uncertain=False,
                            severity="HIGH",
                            message=(
                                f"Format specifier '{conv.raw_spec}' in {fn_name} exceeds buffer '{var_name}' "
                                f"capacity of {capacity} bytes (maximum safe width is {safe_spec} to allow 1 byte for null terminator)."
                            ),
                            suggestion=f"use {safe_spec} to prevent buffer overflow",
                            safe_replacement_spec=safe_spec,
                        )
                    )
                else:
                    # conv.width <= max_safe: Safe!
                    pass

            else:
                # Capacity cannot be established reliably (pointer or external buffer)
                if conv.width is None:
                    findings.append(
                        ScanfFinding(
                            fn_name=fn_name,
                            line=line,
                            col=col,
                            fmt_raw=fmt_raw,
                            conversion=conv,
                            dest_var_name=var_name,
                            declared_capacity=None,
                            max_safe_width=None,
                            requested_width=None,
                            is_vulnerable=True,
                            is_uncertain=True,
                            severity="WARNING",
                            message=(
                                f"Unbounded '{conv.raw_spec}' in {fn_name} with pointer/buffer '{var_name}' of unknown capacity. "
                                f"Input width is unrestricted."
                            ),
                            suggestion="specify explicit buffer length limit in format string",
                            safe_replacement_spec=conv.raw_spec,
                        )
                    )
                else:
                    # Width specified but capacity unknown statically -> report uncertainty
                    findings.append(
                        ScanfFinding(
                            fn_name=fn_name,
                            line=line,
                            col=col,
                            fmt_raw=fmt_raw,
                            conversion=conv,
                            dest_var_name=var_name,
                            declared_capacity=None,
                            max_safe_width=None,
                            requested_width=conv.width,
                            is_vulnerable=False,
                            is_uncertain=True,
                            severity="WARNING",
                            message=(
                                f"Format specifier '{conv.raw_spec}' in {fn_name} uses pointer/buffer '{var_name}' "
                                f"whose destination capacity cannot be statically verified."
                            ),
                            suggestion=f"ensure destination '{var_name}' has capacity at least {conv.width + 1} bytes",
                            safe_replacement_spec=conv.raw_spec,
                        )
                    )

        return findings

    @staticmethod
    def compute_safe_format_string(fmt_raw: str, findings: List[ScanfFinding]) -> str:
        """
        Replaces vulnerable conversions in fmt_raw with safe equivalents
        working in reverse order of start positions so indices remain valid.
        """
        # Filter findings that have a modified replacement specifier
        actionable = [
            f for f in findings
            if f.is_vulnerable and f.safe_replacement_spec and f.safe_replacement_spec != f.conversion.raw_spec
        ]
        if not actionable:
            return fmt_raw

        # Sort reverse by start position
        actionable.sort(key=lambda x: x.conversion.start_in_fmt, reverse=True)

        res = fmt_raw
        for f in actionable:
            s = f.conversion.start_in_fmt
            e = f.conversion.end_in_fmt
            res = res[:s] + f.safe_replacement_spec + res[e:]

        return res
