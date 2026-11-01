# compiler/windowed_repair.py
"""
Windowed code extraction and splicing for localized LLM / model repairs.
Allows language models to focus on the lines immediately surrounding a defect
rather than generating an entire multi-thousand line file, minimizing token usage
and context exhaustion.
"""

from typing import Tuple

def get_window_for_finding(
    source_code: str,
    target_line: int,
    radius: int = 15,
    max_lines: int = 40
) -> Tuple[str, int, int, int]:
    """
    Extracts a window of lines centered around target_line.
    
    Args:
        source_code: Full original source code.
        target_line: 1-indexed line number of the defect.
        radius: Number of lines before and after target_line to include.
        max_lines: Maximum total lines in the extracted window.
        
    Returns:
        (window_source, window_start_line, window_end_line, relative_target_line)
        All line numbers are 1-indexed.
    """
    if not source_code:
        return ("", 1, 1, 1)

    lines = source_code.splitlines(keepends=True)
    total_lines = len(lines)
    if total_lines == 0:
        return ("", 1, 1, 1)

    if target_line < 1:
        target_line = 1
    elif target_line > total_lines:
        target_line = total_lines

    # If the entire file fits within max_lines, return the whole file
    if total_lines <= max_lines:
        return (source_code, 1, total_lines, target_line)

    # 1. Check if target_line is inside a clean enclosing top-level function that fits in max_lines
    fn_start = None
    for i in range(min(target_line - 1, total_lines - 1), -1, -1):
        line = lines[i]
        if line and not line[0].isspace() and '(' in line:
            if line.startswith(('int ', 'void ', 'char ', 'float ', 'double ', 'long ', 'bool ', 'static ', 'struct ', 'viod ')):
                fn_start = i
                break
        elif line and not line[0].isspace() and line.startswith('}') and i < target_line - 1:
            # Reached end of prior function before finding header
            break

    if fn_start is not None:
        fn_end = None
        for j in range(fn_start, total_lines):
            if lines[j].startswith('}'):
                fn_end = j
                if j >= target_line - 1:
                    break
        if fn_end is not None and (fn_end - fn_start + 1) <= max_lines:
            win_start = fn_start + 1
            win_end = fn_end + 1
            window_lines = lines[win_start - 1 : win_end]
            return ("".join(window_lines), win_start, win_end, target_line - win_start + 1)

    # Calculate desired start and end line (1-indexed)
    desired_start = max(1, target_line - radius)
    desired_end = min(total_lines, target_line + radius)

    # Adjust window size to fit within max_lines
    if (desired_end - desired_start + 1) > max_lines:
        excess = (desired_end - desired_start + 1) - max_lines
        trim_end = excess // 2
        trim_start = excess - trim_end
        desired_start += trim_start
        desired_end -= trim_end

    desired_start = max(1, min(desired_start, total_lines))
    desired_end = max(desired_start, min(desired_end, total_lines))

    # Snap window boundaries to clean function / declaration boundaries if available
    for i in range(desired_start - 1, target_line):
        line = lines[i]
        if line and not line[0].isspace() and line.startswith(('int ', 'void ', 'char ', 'float ', 'double ', 'long ', 'bool ', 'static ', 'struct ', 'viod ')) and '(' in line:
            desired_start = i + 1
            break

    found_end = None
    for j in range(desired_end - 1, min(total_lines, desired_start + max_lines)):
        if lines[j].startswith('}'):
            found_end = j + 1
            break
    if found_end and (found_end - desired_start + 1) <= max_lines:
        desired_end = found_end
    else:
        for j in range(desired_end - 1, target_line - 1, -1):
            if lines[j].startswith('}'):
                desired_end = j + 1
                break

    # Balance braces within max_lines if headroom permits
    def _count_braces(text: str) -> Tuple[int, int]:
        stripped = text.split("//")[0]
        return stripped.count("{"), stripped.count("}")

    opens = 0
    closes = 0
    for l in lines[desired_start - 1 : desired_end]:
        o, c = _count_braces(l)
        opens += o
        closes += c
    net = opens - closes

    if net > 0:
        curr = desired_end
        temp_net = net
        found_end = None
        while curr < total_lines and (curr - desired_start + 1) < max_lines:
            curr += 1
            o, c = _count_braces(lines[curr - 1])
            temp_net += (o - c)
            if temp_net <= 0:
                found_end = curr
                break
        if found_end is not None:
            desired_end = found_end
    elif net < 0:
        curr = desired_start
        temp_net = net
        found_start = None
        while curr > 1 and (desired_end - (curr - 1) + 1) <= max_lines:
            curr -= 1
            o, c = _count_braces(lines[curr - 1])
            temp_net += (o - c)
            if temp_net >= 0:
                found_start = curr
                break
        if found_start is not None:
            desired_start = found_start

    window_lines = lines[desired_start - 1 : desired_end]
    window_source = "".join(window_lines)
    relative_target = target_line - desired_start + 1

    return (window_source, desired_start, desired_end, relative_target)


def splice_window_into_source(
    original_source: str,
    repaired_window: str,
    win_start_line: int,
    win_end_line: int
) -> str:
    """
    Splices a repaired code window back into the original source code.
    
    Args:
        original_source: Full original source code.
        repaired_window: Repaired snippet corresponding to lines win_start_line..win_end_line.
        win_start_line: 1-indexed start line of original window.
        win_end_line: 1-indexed end line of original window.
        
    Returns:
        Full source code with the window replaced.
    """
    if not original_source:
        return repaired_window or ""

    lines = original_source.splitlines(keepends=True)
    total_lines = len(lines)

    # If window spanned the entire file
    if win_start_line <= 1 and win_end_line >= total_lines:
        return repaired_window

    prefix_lines = lines[: max(0, win_start_line - 1)]
    suffix_lines = lines[win_end_line :]

    prefix = "".join(prefix_lines)
    suffix = "".join(suffix_lines)

    repaired_clean = repaired_window or ""
    if suffix and not repaired_clean.endswith("\n") and not repaired_clean.endswith("\r\n"):
        repaired_clean += "\n"

    return prefix + repaired_clean + suffix

