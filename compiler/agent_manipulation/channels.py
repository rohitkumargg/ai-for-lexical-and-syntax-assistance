# compiler/agent_manipulation/channels.py
"""Extraction, normalization, and decode-attempt inspection for C and Python non-code channels."""
from __future__ import annotations

import base64
import os
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from compiler.agent_manipulation.config import AgentManipulationConfig, DEFAULT_CONFIG


class ChannelType(str, Enum):
    LINE_COMMENT = "LINE_COMMENT"
    BLOCK_COMMENT = "BLOCK_COMMENT"
    DOCSTRING = "DOCSTRING"
    STRING_LITERAL = "STRING_LITERAL"
    PRAGMA_DIRECTIVE = "PRAGMA_DIRECTIVE"
    IDENTIFIER_MACRO = "IDENTIFIER_MACRO"
    FILE_OR_FN_NAME = "FILE_OR_FN_NAME"


@dataclass
class ExtractedChannel:
    channel_type: ChannelType
    raw_text: str
    normalized_text: str
    line_start: int
    line_end: int
    col_start: int
    col_end: int
    has_decode_attempt: bool = False
    decode_type: Optional[str] = None
    decode_snippet: Optional[str] = None
    is_joined: bool = False
    language: str = "c"
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, str]:
        return {
            "channel_type": self.channel_type.value,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "col_start": self.col_start,
            "col_end": self.col_end,
            "has_decode_attempt": self.has_decode_attempt,
            "decode_type": self.decode_type or "",
            "decode_snippet": self.decode_snippet or "",
            "is_joined": self.is_joined,
            "language": self.language,
        }


class ChannelExtractor:
    """Extracts, normalizes, and inspects non-code channels for C and Python source code."""

    def __init__(self, config: Optional[AgentManipulationConfig] = None):
        self.config = config or DEFAULT_CONFIG

    def normalize_text(self, text: str) -> str:
        """
        Full multi-stage normalization:
        1. Unicode NFKC normalization
        2. Zero-width and BiDi character stripping
        3. Homoglyph folding (Cyrillic, Greek, Full-width, Math symbols -> Latin)
        4. Whitespace collapsing and case folding
        """
        if not text:
            return ""

        # 1. Unicode NFKC
        norm = unicodedata.normalize("NFKC", text)

        # 2. Strip zero-width and BiDi characters
        for ch in self.config.STRIP_CHARS:
            norm = norm.replace(ch, "")

        # 3. Homoglyph folding
        chars = []
        for ch in norm:
            if ch in self.config.HOMOGLYPH_MAP:
                chars.append(self.config.HOMOGLYPH_MAP[ch])
            else:
                chars.append(ch)
        norm = "".join(chars)

        # 4. Collapse whitespace
        norm = re.sub(r"[\t\r\f\v]+", " ", norm)
        norm = re.sub(r" +", " ", norm)
        return norm.strip().lower()

    def inspect_decode_attempt(self, raw_text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Flags decode attempts (base64, hex, escape sequences) rather than silently decoding.
        Returns: (has_attempt, decode_type, snippet)
        """
        if not raw_text or len(raw_text) < 4:
            return False, None, None

        # 1. Explicit base64 indicators or standalone base64 blocks
        if "base64" in raw_text.lower() or "b64decode" in raw_text.lower():
            return True, "BASE64_EXPLICIT_INDICATOR", raw_text[:80]

        # Base64 candidate search: sequences of 20+ base64 chars with padding or standard form
        b64_matches = re.findall(r"\b(?:[A-Za-z0-9+/]{4}){5,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?\b", raw_text)
        for cand in b64_matches:
            if len(cand) >= self.config.min_decode_base64_len:
                try:
                    decoded = base64.b64decode(cand, validate=True).decode("utf-8", errors="ignore")
                    # If it decodes to readable ASCII text with letters/spaces
                    if len(decoded) >= 8 and sum(1 for c in decoded if c.isalnum() or c.isspace()) / len(decoded) > 0.7:
                        return True, "BASE64_ENCODED_PAYLOAD", cand[:40]
                except Exception:
                    pass

        # 2. Hex sequences: \x41\x42... or 0x41, 0x42...
        hex_esc = re.findall(r"(?:\\x[0-9a-fA-F]{2}){4,}", raw_text)
        if hex_esc:
            return True, "HEX_ESCAPE_SEQUENCE", hex_esc[0][:40]

        hex_arr = re.findall(r"(?:0x[0-9a-fA-F]{2}\s*,\s*){4,}", raw_text)
        if hex_arr:
            return True, "HEX_BYTE_ARRAY", hex_arr[0][:40]

        # 3. Unicode escape obfuscation: \u0041\u0042...
        u_esc = re.findall(r"(?:\\u00[0-9a-fA-F]{2}){4,}", raw_text)
        if u_esc:
            return True, "UNICODE_ESCAPE_OBFUSCATION", u_esc[0][:40]

        # 4. Raw hex string indicator (e.g. "hex instruction: 49676e6f...")
        hex_raw = re.findall(r"\b[0-9a-fA-F]{16,}\b", raw_text)
        if hex_raw and any(k in raw_text.lower() for k in ("hex", "decode", "payload", "bytes", "instruction")):
            return True, "HEX_ENCODED_DIRECTIVE", hex_raw[0][:40]

        return False, None, None

    def extract_channels(
        self,
        source_code: str,
        filename: str = "main.c",
        language: str = "c"
    ) -> List[ExtractedChannel]:
        """
        Extracts all non-code channels from source code for C and Python.
        Joins consecutive comment lines into coherent utterances.
        """
        channels: List[ExtractedChannel] = []
        if not source_code:
            return channels

        lang = language.lower() if language else ("python" if filename.endswith((".py", ".py3")) else "c")

        # 0. File name and extracted function names
        fn_norm = self.normalize_text(os.path.basename(filename))
        channels.append(ExtractedChannel(
            channel_type=ChannelType.FILE_OR_FN_NAME,
            raw_text=filename,
            normalized_text=fn_norm,
            line_start=1,
            line_end=1,
            col_start=0,
            col_end=len(filename),
            language=lang,
            metadata={"kind": "filename"},
        ))

        if lang == "python":
            channels.extend(self._extract_python_channels(source_code, filename))
        else:
            channels.extend(self._extract_c_channels(source_code, filename))

        # Join consecutive line comments into combined channels
        joined_channels = self._join_consecutive_line_comments(channels, lang)
        return joined_channels

    def _extract_c_channels(self, source: str, filename: str) -> List[ExtractedChannel]:
        channels: List[ExtractedChannel] = []
        lines = source.splitlines()

        # Regular expressions for C text channels
        # Strings: "(?:\\.|[^\\"])*"
        # Block comments: /\*.*?\*/
        # Line comments: //.*?$
        # Preprocessor pragmas/warnings: ^\s*#(?:pragma|error|warning)\s+.*$
        # Identifier/Macro names: ^\s*#define\s+([A-Za-z0-9_]+)

        # 1. Pragmas, errors, warnings & Macro names
        for idx, line in enumerate(lines, start=1):
            s_line = line.strip()
            # #pragma, #error, #warning
            m_pragma = re.match(r"^\s*#\s*(pragma|error|warning)\b(.*)$", line)
            if m_pragma:
                kind, body = m_pragma.group(1), m_pragma.group(2).strip()
                has_dec, dec_type, dec_snip = self.inspect_decode_attempt(body)
                channels.append(ExtractedChannel(
                    channel_type=ChannelType.PRAGMA_DIRECTIVE,
                    raw_text=body,
                    normalized_text=self.normalize_text(body),
                    line_start=idx,
                    line_end=idx,
                    col_start=line.find(body),
                    col_end=line.find(body) + len(body),
                    has_decode_attempt=has_dec,
                    decode_type=dec_type,
                    decode_snippet=dec_snip,
                    language="c",
                    metadata={"directive": kind},
                ))

            # #define macro names
            m_macro = re.match(r"^\s*#\s*define\s+([A-Za-z0-9_]+)(?:\s+(.*))?$", line)
            if m_macro:
                mac_name, mac_val = m_macro.group(1), (m_macro.group(2) or "").strip()
                channels.append(ExtractedChannel(
                    channel_type=ChannelType.IDENTIFIER_MACRO,
                    raw_text=mac_name,
                    normalized_text=self.normalize_text(mac_name),
                    line_start=idx,
                    line_end=idx,
                    col_start=line.find(mac_name),
                    col_end=line.find(mac_name) + len(mac_name),
                    language="c",
                    metadata={"kind": "macro_name"},
                ))
                if mac_val and not (mac_val.startswith('"') or mac_val.startswith("/*")):
                    channels.append(ExtractedChannel(
                        channel_type=ChannelType.IDENTIFIER_MACRO,
                        raw_text=mac_val,
                        normalized_text=self.normalize_text(mac_val),
                        line_start=idx,
                        line_end=idx,
                        col_start=line.find(mac_val),
                        col_end=line.find(mac_val) + len(mac_val),
                        language="c",
                        metadata={"kind": "macro_value"},
                    ))

            # Function declarations / identifiers
            m_fn = re.match(r"^\s*(?:[A-Za-z0-9_*\s]+)\s+([A-Za-z0-9_]+)\s*\([^;{]*\)\s*\{?", line)
            if m_fn:
                fn_name = m_fn.group(1)
                if fn_name not in ("if", "while", "for", "switch", "return"):
                    channels.append(ExtractedChannel(
                        channel_type=ChannelType.IDENTIFIER_MACRO,
                        raw_text=fn_name,
                        normalized_text=self.normalize_text(fn_name),
                        line_start=idx,
                        line_end=idx,
                        col_start=line.find(fn_name),
                        col_end=line.find(fn_name) + len(fn_name),
                        language="c",
                        metadata={"kind": "function_name"},
                    ))

        # 2. Scan full source for block comments, line comments, and string literals
        pattern = re.compile(
            r"(?P<BLOCK_COMMENT>/\*.*?\*/)|(?P<LINE_COMMENT>//.*?$)|(?P<STRING>\"(?:\\.|[^\\\"])*\")",
            re.DOTALL | re.MULTILINE
        )

        for match in pattern.finditer(source):
            kind = match.lastgroup
            raw = match.group(0)
            start_pos = match.start()
            end_pos = match.end()

            line_start = source.count("\n", 0, start_pos) + 1
            line_end = source.count("\n", 0, end_pos) + 1
            last_nl = source.rfind("\n", 0, start_pos)
            col_start = start_pos if last_nl == -1 else start_pos - last_nl - 1
            col_end = col_start + len(raw)

            has_dec, dec_type, dec_snip = self.inspect_decode_attempt(raw)

            if kind == "LINE_COMMENT":
                content = raw[2:].strip()
                channels.append(ExtractedChannel(
                    channel_type=ChannelType.LINE_COMMENT,
                    raw_text=content,
                    normalized_text=self.normalize_text(content),
                    line_start=line_start,
                    line_end=line_end,
                    col_start=col_start,
                    col_end=col_end,
                    has_decode_attempt=has_dec,
                    decode_type=dec_type,
                    decode_snippet=dec_snip,
                    language="c",
                ))
            elif kind == "BLOCK_COMMENT":
                content = raw[2:-2].strip()
                channels.append(ExtractedChannel(
                    channel_type=ChannelType.BLOCK_COMMENT,
                    raw_text=content,
                    normalized_text=self.normalize_text(content),
                    line_start=line_start,
                    line_end=line_end,
                    col_start=col_start,
                    col_end=col_end,
                    has_decode_attempt=has_dec,
                    decode_type=dec_type,
                    decode_snippet=dec_snip,
                    language="c",
                ))
            elif kind == "STRING":
                content = raw[1:-1]
                channels.append(ExtractedChannel(
                    channel_type=ChannelType.STRING_LITERAL,
                    raw_text=content,
                    normalized_text=self.normalize_text(content),
                    line_start=line_start,
                    line_end=line_end,
                    col_start=col_start,
                    col_end=col_end,
                    has_decode_attempt=has_dec,
                    decode_type=dec_type,
                    decode_snippet=dec_snip,
                    language="c",
                ))

        return channels

    def _extract_python_channels(self, source: str, filename: str) -> List[ExtractedChannel]:
        channels: List[ExtractedChannel] = []
        lines = source.splitlines()

        # 1. Identifiers and functions
        for idx, line in enumerate(lines, start=1):
            m_fn = re.match(r"^\s*def\s+([A-Za-z0-9_]+)\s*\(", line)
            if m_fn:
                name = m_fn.group(1)
                channels.append(ExtractedChannel(
                    channel_type=ChannelType.IDENTIFIER_MACRO,
                    raw_text=name,
                    normalized_text=self.normalize_text(name),
                    line_start=idx,
                    line_end=idx,
                    col_start=line.find(name),
                    col_end=line.find(name) + len(name),
                    language="python",
                    metadata={"kind": "function_name"},
                ))
            m_cls = re.match(r"^\s*class\s+([A-Za-z0-9_]+)\b", line)
            if m_cls:
                name = m_cls.group(1)
                channels.append(ExtractedChannel(
                    channel_type=ChannelType.IDENTIFIER_MACRO,
                    raw_text=name,
                    normalized_text=self.normalize_text(name),
                    line_start=idx,
                    line_end=idx,
                    col_start=line.find(name),
                    col_end=line.find(name) + len(name),
                    language="python",
                    metadata={"kind": "class_name"},
                ))

        # 2. Python strings, docstrings and comments
        # Triple quotes: """...""" or '''...'''
        # Single line strings: "..." or '...'
        # Comments: #.*?$
        pattern = re.compile(
            r"(?P<TRIPLE_DOUBLE>\"\"\"[\s\S]*?\"\"\")|"
            r"(?P<TRIPLE_SINGLE>\'\'\'[\s\S]*?\'\'\')|"
            r"(?P<STRING_DOUBLE>\"(?:\\.|[^\\\"])*\")|"
            r"(?P<STRING_SINGLE>\'(?:\\.|[^\\\'])*\')|"
            r"(?P<COMMENT>#.*?$)",
            re.MULTILINE
        )

        for match in pattern.finditer(source):
            kind = match.lastgroup
            raw = match.group(0)
            start_pos = match.start()
            end_pos = match.end()

            line_start = source.count("\n", 0, start_pos) + 1
            line_end = source.count("\n", 0, end_pos) + 1
            last_nl = source.rfind("\n", 0, start_pos)
            col_start = start_pos if last_nl == -1 else start_pos - last_nl - 1
            col_end = col_start + len(raw)

            has_dec, dec_type, dec_snip = self.inspect_decode_attempt(raw)

            if kind in ("TRIPLE_DOUBLE", "TRIPLE_SINGLE"):
                content = raw[3:-3].strip()
                channels.append(ExtractedChannel(
                    channel_type=ChannelType.DOCSTRING,
                    raw_text=content,
                    normalized_text=self.normalize_text(content),
                    line_start=line_start,
                    line_end=line_end,
                    col_start=col_start,
                    col_end=col_end,
                    has_decode_attempt=has_dec,
                    decode_type=dec_type,
                    decode_snippet=dec_snip,
                    language="python",
                ))
            elif kind == "COMMENT":
                content = raw[1:].strip()
                channels.append(ExtractedChannel(
                    channel_type=ChannelType.LINE_COMMENT,
                    raw_text=content,
                    normalized_text=self.normalize_text(content),
                    line_start=line_start,
                    line_end=line_end,
                    col_start=col_start,
                    col_end=col_end,
                    has_decode_attempt=has_dec,
                    decode_type=dec_type,
                    decode_snippet=dec_snip,
                    language="python",
                ))
            elif kind in ("STRING_DOUBLE", "STRING_SINGLE"):
                content = raw[1:-1]
                channels.append(ExtractedChannel(
                    channel_type=ChannelType.STRING_LITERAL,
                    raw_text=content,
                    normalized_text=self.normalize_text(content),
                    line_start=line_start,
                    line_end=line_end,
                    col_start=col_start,
                    col_end=col_end,
                    has_decode_attempt=has_dec,
                    decode_type=dec_type,
                    decode_snippet=dec_snip,
                    language="python",
                ))

        return channels

    def _join_consecutive_line_comments(
        self,
        channels: List[ExtractedChannel],
        language: str
    ) -> List[ExtractedChannel]:
        """
        Joins consecutive line comments into single compound channels so multi-line directives
        (split across comment lines) are evaluated as coherent semantic units.
        """
        result: List[ExtractedChannel] = []
        line_comments = [c for c in channels if c.channel_type == ChannelType.LINE_COMMENT]
        other_channels = [c for c in channels if c.channel_type != ChannelType.LINE_COMMENT]

        # Sort line comments by line number
        line_comments.sort(key=lambda c: (c.line_start, c.col_start))

        i = 0
        while i < len(line_comments):
            curr = line_comments[i]
            group = [curr]
            j = i + 1
            while j < len(line_comments):
                nxt = line_comments[j]
                if nxt.line_start == group[-1].line_end + 1:
                    group.append(nxt)
                    j += 1
                else:
                    break

            if len(group) == 1:
                result.append(curr)
            else:
                combined_raw = " ".join(g.raw_text for g in group)
                combined_norm = " ".join(g.normalized_text for g in group)
                has_dec = any(g.has_decode_attempt for g in group)
                dec_type = next((g.decode_type for g in group if g.decode_type), None)
                dec_snip = next((g.decode_snippet for g in group if g.decode_snippet), None)

                # Add individual items as well as the compound item
                for g in group:
                    result.append(g)

                result.append(ExtractedChannel(
                    channel_type=ChannelType.LINE_COMMENT,
                    raw_text=combined_raw,
                    normalized_text=self.normalize_text(combined_norm),
                    line_start=group[0].line_start,
                    line_end=group[-1].line_end,
                    col_start=group[0].col_start,
                    col_end=group[-1].col_end,
                    has_decode_attempt=has_dec,
                    decode_type=dec_type,
                    decode_snippet=dec_snip,
                    is_joined=True,
                    language=language,
                    metadata={"joined_lines_count": str(len(group))},
                ))
            i = j

        result.extend(other_channels)
        return result
