from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional, Tuple, List

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from peft import PeftModel


os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


BASE_MODEL_NAME = "Salesforce/codet5-base"
ADAPTER_DIR = os.getenv("CD_PATCH_ADAPTER_DIR", "models/codet5_patch_adapter")

MAX_SOURCE_LEN = 256
MAX_NEW_TOKENS = 16

SAFE_TOKEN_INSERTS = {";", ")", "(", "}", "]", ","}
RELAXED_FAMILIES = {
    "missing_comma_args",
    "missing_comma_params",
    "missing_rparen",
    "missing_lparen_general",
    "mismatch_lparen_to_lbrack",
    "mismatch_rparen_to_rbrack",
    "no_viable_alternative",
    "mismatched_token",
}

_TOKENIZER = None
_MODEL = None
_DEVICE = None

# ------------------------------------------------------------------
# Training-format commands
# ------------------------------------------------------------------
# Examples from your dataset:
#   INS 4292 )
#   DEL 3614 3615
#   REP 5488 5489 )
# Absolute-offset commands
INS_RE = re.compile(r"^\s*INS\s+(\d+)\s+(.+?)\s*$", re.IGNORECASE)
DEL_RE = re.compile(r"^\s*DEL\s+(\d+)\s+(\d+)\s*$", re.IGNORECASE)
REP_RE = re.compile(r"^\s*REP\s+(\d+)\s+(\d+)\s+(.+?)\s*$", re.IGNORECASE)

# Line-column commands actually being predicted by your model
INS_LC_RE = re.compile(r"^\s*INS_LC\s+(\d+)\s+(\d+)\s*([^\d\s].*?)\s*$", re.IGNORECASE)
DEL_LC_RE = re.compile(r"^\s*DEL_LC\s+(\d+)\s+(\d+)\s*$", re.IGNORECASE)
REP_LC_RE = re.compile(r"^\s*REP_LC\s+(\d+)\s+(\d+)\s*([^\d\s].*?)\s*$", re.IGNORECASE)

@dataclass(frozen=True)
class PatchCommand:
    op: str                 # INS | DEL | REP
    start: Optional[int] = None      # absolute char offset
    end: Optional[int] = None        # absolute char offset end
    payload: Optional[str] = None

    line: Optional[int] = None       # 1-based line for *_LC commands
    col: Optional[int] = None        # 0-based col for *_LC commands
    end_line: Optional[int] = None   # optional future use
    end_col: Optional[int] = None    # optional future use

    mode: str = "ABS"                # "ABS" or "LC"
SAFE_TOKEN_INSERTS = {";", ")", "(", "}", "]", ","}
RELAXED_FAMILIES = {
    "missing_comma_args",
    "missing_comma_params",
    "missing_rparen",
    "missing_lparen_general",
    "mismatch_lparen_to_lbrack",
    "mismatch_rparen_to_rbrack",
    "no_viable_alternative",
    "mismatched_token",
}

def _get_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def _resolve_adapter_dir(path: str) -> str:
    """
    Accept either:
      - models/codet5_patch_adapter
      - models/codet5_patch_adapter/adapter
    and return the directory that contains adapter_config.json.
    """
    if os.path.isdir(path) and os.path.isfile(os.path.join(path, "adapter_config.json")):
        return path

    alt = os.path.join(path, "adapter")
    if os.path.isdir(alt) and os.path.isfile(os.path.join(alt, "adapter_config.json")):
        return alt

    raise FileNotFoundError(
        f"Could not find adapter_config.json in '{path}' or '{alt}'.\n"
        f"Fix by either:\n"
        f"  1) Setting env var CD_PATCH_ADAPTER_DIR to your adapter folder, OR\n"
        f"  2) Placing files so that adapter_config.json exists at:\n"
        f"       models/codet5_patch_adapter/adapter_config.json\n"
        f"     or\n"
        f"       models/codet5_patch_adapter/adapter/adapter_config.json\n"
    )


def _load_model_once() -> Tuple[AutoTokenizer, torch.nn.Module, str]:
    global _TOKENIZER, _MODEL, _DEVICE

    if _TOKENIZER is not None and _MODEL is not None and _DEVICE is not None:
        return _TOKENIZER, _MODEL, _DEVICE

    device = _get_device()
    adapter_path = _resolve_adapter_dir(ADAPTER_DIR)

    tokenizer = AutoTokenizer.from_pretrained(adapter_path)
    base = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL_NAME)

    model = PeftModel.from_pretrained(base, adapter_path)
    model.to(device)
    model.eval()

    _TOKENIZER, _MODEL, _DEVICE = tokenizer, model, device
    return tokenizer, model, device


# ------------------------------------------------------------------
# Prompt formatting
# ------------------------------------------------------------------

def build_training_style_prompt(
    source_text: str,
    reason: str,
    error_line: int,
    error_col: int,
    radius: int = 3,
) -> str:
    """
    Match training format as closely as possible:

    repair_code
    error_family: <family>
    error_line: <line>
    error_col: <col>

    repair:
    <CODE>
    ...
    </CODE>

    We preserve the <ERR> marker because your samples show that format.
    """
    family = infer_training_family(reason, source_text, error_line, error_col)

    lines = source_text.splitlines()
    if not lines:
        snippet = "<ERR>"
    else:
        li = max(1, min(error_line, len(lines))) - 1
        start = max(0, li - radius)
        end = min(len(lines), li + radius + 1)

        window = lines[start:end]
        rel = li - start

        target = window[rel]
        col = max(0, min(error_col, len(target)))
        window[rel] = target[:col] + "<ERR>" + target[col:]

        snippet = "\n".join(window)

    prompt = (
        f"repair_code\n"
        f"error_family: {family}\n"
        f"error_line: {error_line}\n"
        f"error_col: {error_col}\n\n"
        f"repair:\n"
        f"<CODE>\n"
        f"{snippet}\n"
        f"</CODE>"
    )
    return prompt


# ------------------------------------------------------------------
# Command parsing + application
# ------------------------------------------------------------------

def parse_patch_command(cmd: str) -> Optional[PatchCommand]:
    cmd = (cmd or "").strip()
    if not cmd:
        return None

    # ----------------------------------------------------------
    # Absolute-offset format
    # ----------------------------------------------------------
    m = INS_RE.match(cmd)
    if m:
        start = int(m.group(1))
        payload = m.group(2).strip()
        if payload == "":
            return None
        return PatchCommand(
            op="INS",
            start=start,
            payload=payload,
            mode="ABS",
        )

    m = DEL_RE.match(cmd)
    if m:
        start = int(m.group(1))
        end = int(m.group(2))
        if end < start:
            return None
        return PatchCommand(
            op="DEL",
            start=start,
            end=end,
            mode="ABS",
        )

    m = REP_RE.match(cmd)
    if m:
        start = int(m.group(1))
        end = int(m.group(2))
        payload = m.group(3).strip()
        if payload == "" or end < start:
            return None
        return PatchCommand(
            op="REP",
            start=start,
            end=end,
            payload=payload,
            mode="ABS",
        )

    # ----------------------------------------------------------
    # Line-column format
    # ----------------------------------------------------------
    m = INS_LC_RE.match(cmd)
    if m:
        line = int(m.group(1))
        col = int(m.group(2))
        payload = m.group(3).strip()
        if payload == "":
            return None
        return PatchCommand(
            op="INS",
            line=line,
            col=col,
            payload=payload,
            mode="LC",
        )

    m = DEL_LC_RE.match(cmd)
    if m:
        line = int(m.group(1))
        col = int(m.group(2))
        return PatchCommand(
            op="DEL",
            line=line,
            col=col,
            mode="LC",
        )

    m = REP_LC_RE.match(cmd)
    if m:
        line = int(m.group(1))
        col = int(m.group(2))
        payload = m.group(3).strip()
        if payload == "":
            return None
        return PatchCommand(
            op="REP",
            line=line,
            col=col,
            payload=payload,
            mode="LC",
        )

    return None


def apply_patch(source_text: str, patch: PatchCommand) -> str:
    """
    Apply either:
      - ABS patch: INS/DEL/REP using absolute char offsets
      - LC patch:  INS_LC/DEL_LC/REP_LC using line/column

    LC semantics:
      INS_LC line col tok  => insert tok at that line/col
      DEL_LC line col      => delete exactly one char at that line/col
      REP_LC line col tok  => replace exactly one char at that line/col with tok
    """
    # ----------------------------------------------------------
    # ABS mode
    # ----------------------------------------------------------
    if patch.mode == "ABS":
        n = len(source_text)
        s = max(0, min(patch.start or 0, n))

        if patch.op == "INS":
            tok = patch.payload or ""
            return source_text[:s] + tok + source_text[s:]

        if patch.op == "DEL":
            e = patch.end if patch.end is not None else s
            e = max(s, min(e, n))
            return source_text[:s] + source_text[e:]

        if patch.op == "REP":
            e = patch.end if patch.end is not None else s
            e = max(s, min(e, n))
            tok = patch.payload or ""
            return source_text[:s] + tok + source_text[e:]

        return source_text

    # ----------------------------------------------------------
    # LC mode
    # ----------------------------------------------------------
    if patch.mode == "LC":
        if patch.line is None or patch.col is None:
            return source_text

        abs_pos = line_col_to_abs(source_text, patch.line, patch.col)
        n = len(source_text)
        abs_pos = max(0, min(abs_pos, n))

        if patch.op == "INS":
            tok = patch.payload or ""
            return source_text[:abs_pos] + tok + source_text[abs_pos:]

        if patch.op == "DEL":
            if abs_pos >= n:
                return source_text
            return source_text[:abs_pos] + source_text[abs_pos + 1:]

        if patch.op == "REP":
            tok = patch.payload or ""
            if abs_pos >= n:
                return source_text
            return source_text[:abs_pos] + tok + source_text[abs_pos + 1:]

        return source_text

    return source_text


# ------------------------------------------------------------------
# Family inference
# ------------------------------------------------------------------

def infer_training_family(reason: str, source_text: str, error_line: int, error_col: int) -> str:
    """
    Map runtime repair reasons + local text pattern to the family labels
    the model was actually trained on.
    """
    line_text = _get_line_text(source_text, error_line)

    # ----------------------------------------------------------
    # Specific operator / expression families first
    # ----------------------------------------------------------
        # missing comma in function parameters: int add(int a int b)
    if re.search(r"\b(int|float|char|void)\s+[A-Za-z_]\w*\s+\b(int|float|char|void)\b", line_text):
        return "missing_comma_params"

    # missing comma in function arguments: add(x y)
    if re.search(r"\b[A-Za-z_]\w*\s*\(\s*[A-Za-z_]\w*\s+[A-Za-z_]\w*", line_text):
        return "missing_comma_args"
    # Case: z = z + * 2;
    # operator followed by operator -> extra operator / malformed expression
    if re.search(r"(\+|\-|\*|/|%|==|!=|<=|>=|<|>|&&|\|\|)\s+(\+|\-|\*|/|%|==|!=|<=|>=|<|>|&&|\|\|)", line_text):
        return "extra_operator"

    # Case: if (x == )
    # comparison/operator followed by closing boundary -> missing operand
    if re.search(r"(==|!=|<=|>=|<|>|\+|\-|\*|/|%|=)\s*([;\)\]\}])", line_text):
        return "missing_operand"

    # Case: single & or | used in boolean expression
    if "&" in line_text and "&&" not in line_text:
        return "broken_logical_operator"
    if "|" in line_text and "||" not in line_text:
        return "broken_logical_operator"

    # ----------------------------------------------------------
    # Bracket / paren mismatch families
    # ----------------------------------------------------------
    if re.search(r"\b[A-Za-z_]\w*\s*\[.*\)", line_text):
        return "mismatch_lparen_to_lbrack"

    if re.search(r"\b[A-Za-z_]\w*\s*\(.*\]", line_text):
        return "mismatch_rparen_to_rbrack"

    # ----------------------------------------------------------
    # Illegal char families
    # ----------------------------------------------------------
    if "@" in line_text and reason in {"illegal_token", "extraneous_token", "unknown", "mismatched_token"}:
        return "illegal_char"

    # ----------------------------------------------------------
    # Direct runtime reason mappings
    # ----------------------------------------------------------
    if reason == "missing_semicolon":
        return "missing_semicolon"

    if reason == "missing_lbrace":
        return "missing_lbrace"

    if reason == "missing_rbrace":
        return "missing_rbrace"

    if reason == "missing_rparen":
        return "missing_rparen"

    if reason == "missing_lparen":
        return "missing_lparen_general"

    if reason == "illegal_token":
        return "illegal_char"

    # ----------------------------------------------------------
    # Generic parser fallback mappings
    # ----------------------------------------------------------
    if reason == "mismatched_token":
        # more local heuristics for common ML families
        if re.search(r"(\+|\-|\*|/|%)\s+(\+|\-|\*|/|%)", line_text):
            return "extra_operator"
        if re.search(r"(==|!=|<=|>=|<|>)\s*([;\)\]\}])", line_text):
            return "missing_operand"

    if reason == "no_viable_alternative":
        if "[" in line_text and ")" in line_text:
            return "mismatch_lparen_to_lbrack"
        if "(" in line_text and "]" in line_text:
            return "mismatch_rparen_to_rbrack"
        if re.search(r"(==|!=|<=|>=|<|>)\s*([;\)\]\}])", line_text):
            return "missing_operand"

    if reason == "extraneous_token":
        if "@" in line_text:
            return "illegal_char"
        if re.search(r"(\+|\-|\*|/|%)\s+(\+|\-|\*|/|%)", line_text):
            return "extra_operator"

    return reason or "unknown"


# ------------------------------------------------------------------
# Safety / family-aware filtering
# ------------------------------------------------------------------

def _line_start_offsets(source_text: str) -> List[int]:
    starts = [0]
    for i, ch in enumerate(source_text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def line_col_to_abs(source_text: str, line: int, col: int) -> int:
    starts = _line_start_offsets(source_text)
    if not starts:
        return 0

    line = max(1, min(line, len(starts)))
    start = starts[line - 1]

    # end of line without newline if possible
    if line < len(starts):
        line_end = starts[line] - 1
    else:
        line_end = len(source_text)

    return max(start, min(start + max(0, col), line_end))


def _get_line_text(source_text: str, line: int) -> str:
    lines = source_text.splitlines()
    if not lines:
        return ""
    line = max(1, min(line, len(lines)))
    return lines[line - 1]


def pick_allowed_positions(
    reason: str,
    source_text: str,
    error_line: int,
    error_col: int,
) -> List[int]:
    """
    Returns a small set of absolute positions where an edit is allowed.
    Tight local safety, but enough flexibility for the trained absolute-offset format.
    """
    positions: List[int] = []
    err_abs = line_col_to_abs(source_text, error_line, error_col)
    n = len(source_text)

    def add(pos: int) -> None:
        pos = max(0, min(pos, n))
        positions.append(pos)

    add(err_abs)
    add(err_abs - 1)
    add(err_abs + 1)

    line_text = _get_line_text(source_text, error_line)
    line_start = line_col_to_abs(source_text, error_line, 0)

    if reason == "missing_semicolon":
        # end of previous non-empty line or near current spot
        lines = source_text.splitlines()
        prev = error_line - 1
        while prev >= 1:
            txt = lines[prev - 1].rstrip()
            if txt:
                prev_start = line_col_to_abs(source_text, prev, 0)
                add(prev_start + len(txt))
                break
            prev -= 1

    elif reason in {"missing_lparen", "no_viable_alternative"}:
        m = re.search(r"\b[A-Za-z_]\w*\s*\[", line_text)
        if m:
            add(line_start + m.end() - 1)  # '['
        m2 = re.search(r"\b[A-Za-z_]\w*\s+[A-Za-z_]", line_text)
        if m2:
            add(line_start + m2.end() - 1)

    elif reason in {"missing_rparen"}:
        add(err_abs)
        add(err_abs + 1)

    elif reason in {"extraneous_token", "illegal_token"}:
        add(err_abs)
        add(err_abs - 1)

    elif reason in {"missing_lbrace", "missing_rbrace"}:
        add(err_abs)

    # dedup preserve order
    out: List[int] = []
    seen = set()
    for p in positions:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out[:8]


def _is_safe_patch(
    patch: PatchCommand,
    allowed_positions: List[int],
    source_text: str,
) -> bool:
    n = len(source_text)

    def near_allowed(pos: int, tol: int = 2) -> bool:
        return any(abs(pos - ap) <= tol for ap in allowed_positions)

    # ----------------------------------------------------------
    # ABS mode
    # ----------------------------------------------------------
    if patch.mode == "ABS":
        if patch.op == "INS":
            if patch.start is None or not (0 <= patch.start <= n):
                return False
            return near_allowed(patch.start, tol=2)

        if patch.op in {"DEL", "REP"}:
            if patch.start is None or patch.end is None:
                return False
            if not (0 <= patch.start <= patch.end <= n):
                return False
            if (patch.end - patch.start) > 4:
                return False
            return near_allowed(patch.start, tol=2) or near_allowed(patch.end, tol=2)

        return False

    # ----------------------------------------------------------
    # LC mode
    # ----------------------------------------------------------
    if patch.mode == "LC":
        if patch.line is None or patch.col is None:
            return False

        abs_pos = line_col_to_abs(source_text, patch.line, patch.col)

        if patch.op == "INS":
            return near_allowed(abs_pos, tol=2)

        if patch.op in {"DEL", "REP"}:
            return near_allowed(abs_pos, tol=2)

        return False

    return False


def _family_compatible(
    family: str,
    source_before: str,
    source_after: str,
    patch: PatchCommand,
    error_line: int,
    error_col: int,
) -> bool:
    """
    Relaxed compatibility:
    - keep strict checks for obvious safe deterministic families
    - allow likely syntax-token insertions through for ambiguous families
    """

    before_line = _get_line_text(source_before, error_line)
    after_line = _get_line_text(source_after, error_line)
    payload = (patch.payload or "").strip()

    # ----------------------------------------------------------
    # universal relaxed escape hatch for common syntax tokens
    # ----------------------------------------------------------
    if patch.op == "INS" and payload in SAFE_TOKEN_INSERTS:
        if family in RELAXED_FAMILIES:
            return True

    # illegal char => prefer delete/replace
    if family == "illegal_char":
        return patch.op in {"DEL", "REP"}

    if family == "missing_semicolon":
        return (patch.op in {"INS", "REP"}) and payload == ";"

    if family == "missing_lbrace":
        return (patch.op in {"INS", "REP"}) and payload == "{"

    if family == "missing_rbrace":
        return (patch.op in {"INS", "REP"}) and payload == "}"

    if family == "missing_rparen":
        if (patch.op in {"INS", "REP"}) and payload == ")":
            return True
        # allow comma too because parser often misroutes comma-arg problems here
        if (patch.op in {"INS", "REP"}) and payload == ",":
            return True
        return False

    if family == "missing_lparen_general":
        if (patch.op in {"INS", "REP"}) and payload == "(":
            return True
        # allow comma here too for ambiguity cases
        if (patch.op in {"INS", "REP"}) and payload == ",":
            return True
        return False

    if family == "missing_comma_params":
        return (patch.op in {"INS", "REP"}) and payload == ","

    if family == "missing_comma_args":
        return (patch.op in {"INS", "REP"}) and payload == ","

    if family == "mismatch_lparen_to_lbrack":
        # before this was too strict and blocked comma repairs
        if (patch.op in {"INS", "REP"}) and payload in {"(", ","}:
            return True
        return patch.op in {"DEL", "REP"}

    if family == "mismatch_rparen_to_rbrack":
        if (patch.op in {"INS", "REP"}) and payload in {")", ","}:
            return True
        return patch.op in {"DEL", "REP"}

    if family == "extra_operator":
        return patch.op in {"DEL", "REP"}

    if family == "missing_operand":
        if patch.op == "INS":
            if payload in {";", "{", "}", ")", "]"}:
                return False
            return True
        if patch.op == "REP":
            if payload in {";", "{", "}", ")", "]"}:
                return False
            return True
        return False

    if family == "broken_logical_operator":
        return (patch.op == "REP" and payload in {"&&", "||"}) or (patch.op == "INS" and payload in {"&", "|"})

    return True


def _score_candidate(
    family: str,
    patch: PatchCommand,
    source_before: str,
    source_after: str,
    error_line: int,
) -> int:
    """
    Lightweight ranking among family-compatible candidates.
    Larger score is better.
    """
    score = 0
    delta = abs(len(source_after) - len(source_before))

    if delta <= 1:
        score += 10
    elif delta <= 2:
        score += 5

    before_line = _get_line_text(source_before, error_line)
    after_line = _get_line_text(source_after, error_line)
    payload = (patch.payload or "").strip()

    if family == "illegal_char":
        if patch.op == "DEL":
            score += 20

    elif family == "missing_semicolon":
        if patch.op == "INS" and payload == ";":
            score += 30

    elif family == "mismatch_lparen_to_lbrack":
        if payload == "(":
            score += 40
        if "[" not in after_line and "(" in after_line:
            score += 20
        if "]" in after_line and "[" in after_line:
            score -= 10

    elif family == "mismatch_rparen_to_rbrack":
        if payload == ")":
            score += 40
        if "]" not in after_line and ")" in after_line:
            score += 20

    elif family == "missing_lparen_general":
        if payload == "(":
            score += 30

    elif family == "missing_rparen":
        if payload == ")":
            score += 30

    elif family == "extra_operator":
        if patch.op == "DEL":
            score += 35
        elif patch.op == "REP":
            score += 10

        if payload in {"*=", "/=", "+=", "-="}:
            score -= 10

    elif family == "missing_operand":
        if patch.op == "INS":
            if re.fullmatch(r"\d+", payload):
                score += 40
            elif re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", payload):
                score += 35
            elif payload in {"0", "1", "-1"}:
                score += 40
            elif payload in {"(", "+", "-", "!"}:
                score += 20

            if payload in {";", "{", "}", ")", "]", ","}:
                score -= 100

        elif patch.op == "REP":
            if re.fullmatch(r"\d+", payload):
                score += 35
            elif re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", payload):
                score += 30

            if payload in {";", "{", "}", ")", "]", ","}:
                score -= 100

    elif family == "broken_logical_operator":
        if payload in {"&&", "||"}:
            score += 40
        elif payload in {"and", "or"}:
            score -= 10
    elif family == "missing_comma_params":
        if payload == ",":
            score += 50

    elif family == "missing_comma_args":
        if payload == ",":
            score += 50

    elif family in {"missing_rparen", "missing_lparen_general", "mismatch_lparen_to_lbrack", "mismatch_rparen_to_rbrack"}:
        if payload == ",":
            score += 25

    # slight preference for shorter ABS replacement span
    if patch.end is not None and patch.start is not None:
        score -= (patch.end - patch.start)

    return score


# ------------------------------------------------------------------
# Main entry used by test_parser.py
# ------------------------------------------------------------------
def ai_generate_patch_candidates(
    source_text: str,
    error_line: int,
    error_column: int,
    reason: str = "unknown",
    top_k: int = 5,
    debug: bool = True,
) -> List[Tuple[str, str, int]]:
    """
    Returns a ranked list of candidate repairs:
        [(new_source, cmd_text, heuristic_score), ...]

    This function:
    - builds the prompt
    - generates raw model outputs
    - parses patch commands
    - applies safety filtering
    - applies family compatibility filtering
    - scores candidates heuristically
    - returns all surviving candidates sorted best-first

    Final parse-based selection should happen in test_parser.py.
    """
    tokenizer, model, device = _load_model_once()

    family = infer_training_family(reason, source_text, error_line, error_column)
    prompt = build_training_style_prompt(
        source_text=source_text,
        reason=reason,
        error_line=error_line,
        error_col=error_column,
    )

    if debug:
        print("\nAI DEBUG")
        print("-" * 70)
        print(f"Reason: {reason}")
        print(f"Inferred family: {family}")
        print(f"Error location: line={error_line}, col={error_column}")
        print("Prompt:")
        print(prompt)
        print("-" * 70)

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_SOURCE_LEN,
    ).to(device)

    num_return_sequences = max(1, min(int(top_k or 1), 5))
    num_beams = max(4, num_return_sequences)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            num_beams=num_beams,
            num_return_sequences=num_return_sequences,
            do_sample=False,
            early_stopping=True,
        )

    preds = [
        tokenizer.decode(seq, skip_special_tokens=True).strip()
        for seq in outputs
    ]

    if debug:
        print("Raw model predictions:")
        for i, pred in enumerate(preds, 1):
            print(f"  [{i}] {pred!r}")
        print("-" * 70)

    allowed_positions = pick_allowed_positions(reason, source_text, error_line, error_column)

    if debug:
        print(f"Allowed positions: {allowed_positions}")
        print("-" * 70)

    candidates: List[Tuple[str, str, int]] = []
    seen_sources = set()

    for pred in preds:
        if debug:
            print(f"Evaluating candidate: {pred!r}")

        parsed = parse_patch_command(pred)
        if not parsed:
            if debug:
                print("  -> rejected: could not parse patch command")
            continue

        if debug:
            print(f"  -> parsed: {parsed}")

        if not _is_safe_patch(parsed, allowed_positions, source_text):
            if debug:
                print("  -> rejected: failed safety/position filter")
            continue

        new_src = apply_patch(source_text, parsed)
        if new_src == source_text:
            if debug:
                print("  -> rejected: patch produced no change")
            continue

        if not _family_compatible(
            family=family,
            source_before=source_text,
            source_after=new_src,
            patch=parsed,
            error_line=error_line,
            error_col=error_column,
        ):
            if debug:
                print("  -> rejected: failed family compatibility")
            continue

        score = _score_candidate(
            family=family,
            patch=parsed,
            source_before=source_text,
            source_after=new_src,
            error_line=error_line,
        )

        if debug:
            print(f"  -> accepted candidate with heuristic score={score}")

        if new_src in seen_sources:
            continue
        seen_sources.add(new_src)

        candidates.append((new_src, pred, score))

    candidates.sort(key=lambda x: x[2], reverse=True)

    if debug:
        print("-" * 70)
        if not candidates:
            print("AI result: no usable patch survived filtering")
        else:
            print("AI surviving candidates (best-first):")
            for i, (_, cmd, score) in enumerate(candidates, 1):
                print(f"  [{i}] {cmd!r}  score={score}")
        print("-" * 70)

    return candidates


def ai_correct_source_patch_mode(
    source_text: str,
    error_line: int,
    error_column: int,
    reason: str = "unknown",
    top_k: int = 5,
    debug: bool = True,
) -> Tuple[str, Optional[str]]:
    """
    Backward-compatible wrapper:
    returns the top surviving heuristic candidate only.

    For stronger selection, use ai_generate_patch_candidates(...) and
    reparse candidates in test_parser.py.
    """
    candidates = ai_generate_patch_candidates(
        source_text=source_text,
        error_line=error_line,
        error_column=error_column,
        reason=reason,
        top_k=top_k,
        debug=debug,
    )

    if not candidates:
        return source_text, None

    best_src, best_cmd, _ = candidates[0]
    return best_src, best_cmd