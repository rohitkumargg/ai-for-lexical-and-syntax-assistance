# compiler/agent_manipulation/lexicon.py
"""Lexicon manager loading multilingual synonym dictionaries from data/agent_manipulation_lexicon.json."""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Set, Tuple


class ManipulationLexicon:
    """Manages lexicon lookup for Addressee, Instruction, and Target across supported languages."""

    def __init__(self, lexicon_path: Optional[str] = None):
        if not lexicon_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            lexicon_path = os.path.join(base_dir, "data", "agent_manipulation_lexicon.json")

        self.lexicon_path = lexicon_path
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.lexicon_path):
            raise FileNotFoundError(f"Agent manipulation lexicon file missing at: {self.lexicon_path}")

        with open(self.lexicon_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cats = data.get("categories", {})
        
        # Flatten terms across all languages into set of normalized words/phrases
        self.addressee_terms: Set[str] = set()
        self.instruction_terms: Set[str] = set()
        self.target_terms: Set[str] = set()

        for lang, terms in cats.get("addressee", {}).items():
            for t in terms:
                self.addressee_terms.add(t.lower().strip())

        for lang, terms in cats.get("instruction", {}).items():
            for t in terms:
                self.instruction_terms.add(t.lower().strip())

        for lang, terms in cats.get("target", {}).items():
            for t in terms:
                self.target_terms.add(t.lower().strip())

        self.intent_categories = data.get("intent_categories", {})

    def match_dimension(self, tokens: List[str], text: str, dimension: str) -> List[Tuple[str, int]]:
        """
        Matches tokens or multi-word subphrases against a lexicon dimension.
        Returns: list of (matched_term, position_index)
        """
        matches = []
        if dimension == "addressee":
            target_set = self.addressee_terms
        elif dimension == "instruction":
            target_set = self.instruction_terms
        elif dimension == "target":
            target_set = self.target_terms
        else:
            return matches

        # 1. Single token matching with stem/prefix handling
        for idx, tok in enumerate(tokens):
            if tok in target_set:
                matches.append((tok, idx))
                continue
            # Simple stemming: strip 's', 'ed', 'ing', 'er'
            stem = re.sub(r"(ing|ed|es|s|er)$", "", tok)
            if stem and len(stem) >= 3 and stem in target_set:
                matches.append((tok, idx))

        # 2. Multi-word or non-ASCII script phrase matching
        text_lower = text.lower()
        for term in target_set:
            if " " in term and term in text_lower:
                matches.append((term, 0))
            elif any(ord(ch) > 127 for ch in term) and term in text_lower:
                matches.append((term, 0))

        return matches

    def classify_intent_category(self, text: str) -> str:
        """Determines the most applicable intent category from intent_categories."""
        norm = text.lower()
        for cat_name, info in self.intent_categories.items():
            for kw in info.get("keywords", []):
                if kw in norm:
                    return cat_name
        return "none"
