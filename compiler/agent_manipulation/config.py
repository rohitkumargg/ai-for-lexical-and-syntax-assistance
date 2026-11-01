# compiler/agent_manipulation/config.py
"""Configuration parameters and normalization mappings for Agent Manipulation Detector (P6)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class AgentManipulationConfig:
    # L1 Structural scoring thresholds
    l1_flag_threshold: float = 0.52          # Scores >= this are flagged by L1
    l1_prefilter_threshold: float = 0.32     # Scores >= this qualify for L2 local model escalation
    
    # L2 Local model thresholds & budgets
    l2_confidence_threshold: float = 0.65    # Required Qwen confidence to flag
    l2_timeout_seconds: float = 1.0          # Hard time budget for L2 query
    l2_model_name: str = "qwen2.5-coder:3b"
    l2_ollama_url: str = "http://127.0.0.1:11434"
    enable_l2_model: bool = True
    
    # Text channel constraints
    max_channel_text_length: int = 16_384
    min_decode_base64_len: int = 16
    
    # Evaluation target thresholds
    target_held_out_recall: float = 0.85     # Recall on held-out families must be >= 85%
    max_false_positive_rate: float = 0.03    # FPR on benign code must be <= 3.0%
    
    # Path to multilingual lexicon
    lexicon_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "agent_manipulation_lexicon.json"
    )

    # Unicode zero-width and bidirectional control characters to strip
    STRIP_CHARS: Set[str] = field(default_factory=lambda: {
        "\u200b", "\u200c", "\u200d", "\u200e", "\u200f",  # Zero-width spaces, joiners, marks
        "\ufeff",                                            # Zero-width no-break space / BOM
        "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",  # BiDi embedding & overrides
        "\u2066", "\u2067", "\u2068", "\u2069",            # BiDi isolates
        "\u00ad",                                            # Soft hyphen
    })

    # Homoglyphs table: maps Cyrillic, Greek, mathematical and fullwidth characters to standard Latin ASCII
    HOMOGLYPH_MAP: Dict[str, str] = field(default_factory=lambda: {
        # Cyrillic lowercase to Latin
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh",
        "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
        "о": "o", "п": "p", "р": "r", "с": "c", "т": "t", "у": "u", "ф": "f",
        "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "",
        "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "і": "i", "ї": "yi",
        # Cyrillic uppercase to Latin
        "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O",
        "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X", "І": "I",
        # Greek lowercase / uppercase
        "α": "a", "β": "b", "γ": "g", "ε": "e", "ι": "i", "κ": "k", "ν": "v",
        "ο": "o", "ρ": "p", "τ": "t", "υ": "u", "χ": "x",
        "Α": "A", "Β": "B", "Ε": "E", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M",
        "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
        # Common leetspeak substitutions in adversarial text
        "@": "a", "0": "o", "1": "i", "$": "s", "!": "i", "3": "e", "4": "a",
        "5": "s", "7": "t", "8": "b",
    })


DEFAULT_CONFIG = AgentManipulationConfig()
