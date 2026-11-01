# compiler/agent_manipulation/detector.py
"""Master Agent Manipulation Detector coordinating extraction, normalization, L1, L2, L3 and enforcement."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from compiler.agent_manipulation.channels import ChannelExtractor, ExtractedChannel, ChannelType
from compiler.agent_manipulation.config import AgentManipulationConfig, DEFAULT_CONFIG
from compiler.agent_manipulation.enforcement import ManipulationEnforcer, MaskedRegion
from compiler.agent_manipulation.l1_structural import L1StructuralScorer, L1Verdict
from compiler.agent_manipulation.l2_model_flagger import L2ModelFlagger, L2ModelVerdict
from compiler.agent_manipulation.l3_cross_check import L3BehaviouralCrossChecker, L3CrossCheckVerdict
from compiler.agent_manipulation.lexicon import ManipulationLexicon


@dataclass
class AgentManipulationFinding:
    id: str
    rule_id: str
    category: str
    severity: str                 # "INFO" / "REVIEW" (never CRITICAL)
    status: str                   # "FLAGGED" (never CONFIRMED vulnerability)
    file_path: str
    line: int
    column: int
    snippet: str
    explanation: str
    potential_threat: str
    recommended_fix: str
    confidence: float
    is_confirmed: bool = False   # Never confirmed as a software vulnerability
    is_manipulation: bool = True
    flagged_text: str = ""
    manipulation_reason: str = ""
    future_risks: List[str] = field(default_factory=list)
    channel_type: str = ""
    layer: str = "L1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "file_path": self.file_path,
            "line": self.line,
            "column": self.column,
            "snippet": self.snippet,
            "explanation": self.explanation,
            "potential_threat": self.potential_threat,
            "recommended_fix": self.recommended_fix,
            "confidence": round(self.confidence, 3),
            "is_confirmed": self.is_confirmed,
            "is_manipulation": self.is_manipulation,
            "flagged_text": self.flagged_text,
            "manipulation_reason": self.manipulation_reason,
            "future_risks": list(self.future_risks),
            "channel_type": self.channel_type,
            "layer": self.layer,
        }


@dataclass
class AgentManipulationReport:
    has_manipulation: bool
    findings: List[AgentManipulationFinding]
    masked_source_for_ai: str
    masked_regions: List[MaskedRegion]
    channels_analyzed: int
    l1_flags_count: int
    l2_escalations_count: int
    l2_flags_count: int

    @property
    def reasons(self) -> List[str]:
        res = []
        for f in self.findings:
            res.append(f.rule_id)
            res.append(f.category)
            res.append(f.explanation)
            res.append(f.manipulation_reason)
        return res

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_manipulation": self.has_manipulation,
            "findings_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "channels_analyzed": self.channels_analyzed,
            "l1_flags_count": self.l1_flags_count,
            "l2_escalations_count": self.l2_escalations_count,
            "l2_flags_count": self.l2_flags_count,
        }


class AgentManipulationDetector:
    """Master multi-layer detector for instructions in code addressed to an automated reviewer."""

    def __init__(self, config: Optional[AgentManipulationConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.lexicon = ManipulationLexicon(self.config.lexicon_path)
        self.channel_extractor = ChannelExtractor(self.config)
        self.l1_scorer = L1StructuralScorer(self.config, self.lexicon)
        self.l2_flagger = L2ModelFlagger(self.config)
        self.cross_checker = L3BehaviouralCrossChecker()
        self.enforcer = ManipulationEnforcer()

    def analyze(
        self,
        source_code: str,
        filename: str = "main.c",
        language: str = "c",
        run_l2: bool = True
    ) -> AgentManipulationReport:
        """
        Analyzes source code across all non-code channels through L1 and L2 layers.
        Masks flagged channels with inert placeholders for AI model inputs.
        """
        if not source_code:
            return AgentManipulationReport(
                has_manipulation=False,
                findings=[],
                masked_source_for_ai="",
                masked_regions=[],
                channels_analyzed=0,
                l1_flags_count=0,
                l2_escalations_count=0,
                l2_flags_count=0,
            )

        channels = self.channel_extractor.extract_channels(source_code, filename=filename, language=language)
        findings: List[AgentManipulationFinding] = []
        flagged_channels: List[ExtractedChannel] = []

        l1_flags = 0
        l2_escalations = 0
        l2_flags = 0

        for ch in channels:
            l1_verdict = self.l1_scorer.evaluate_channel(ch)
            flagged = False
            layer_used = "L1"
            final_conf = l1_verdict.score
            final_cat = l1_verdict.category
            final_reason = l1_verdict.explanation

            if l1_verdict.is_flagged:
                flagged = True
                l1_flags += 1
            elif run_l2 and l1_verdict.qualifies_for_l2:
                # Ambiguous segment passing prefilter: query L2
                l2_escalations += 1
                l2_verdict = self.l2_flagger.evaluate_text_segment(ch.normalized_text)
                if l2_verdict.raised_flag:
                    flagged = True
                    l2_flags += 1
                    layer_used = "L2"
                    final_conf = max(final_conf, l2_verdict.confidence)
                    final_cat = l2_verdict.category or final_cat
                    final_reason = l2_verdict.reason

            if flagged:
                flagged_channels.append(ch)
                finding = AgentManipulationFinding(
                    id=f"REVIEWER-INSTR-L{ch.line_start}",
                    rule_id=f"AGENT-MANIPULATION-{final_cat.upper()}",
                    category="AGENT_INSTRUCTION_MANIPULATION",
                    severity="INFO",
                    status="FLAGGED",
                    file_path=filename,
                    line=ch.line_start,
                    column=ch.col_start,
                    snippet=ch.raw_text[:120],
                    explanation=f"Instructions in code addressed to an automated reviewer: {final_reason}",
                    potential_threat="Text contains directives attempting to influence or bypass automated review, validation, or repair models.",
                    recommended_fix="Review and continue. The flagged text will be automatically masked before being sent to any AI repair model.",
                    confidence=final_conf,
                    is_confirmed=False,
                    is_manipulation=True,
                    flagged_text=ch.raw_text,
                    manipulation_reason=final_reason,
                    future_risks=[
                        "Adversarial directives could mislead unmasked language models during automated repair.",
                        "Directives are strictly inert and masked from AI inputs under the flag-and-continue policy."
                    ],
                    channel_type=ch.channel_type.value,
                    layer=layer_used,
                )
                findings.append(finding)

        # Enforce masking: create safe model input with inert placeholders
        masked_code, masked_regions = self.enforcer.mask_source_for_ai(
            source_code,
            flagged_channels=flagged_channels,
            language=language
        )

        return AgentManipulationReport(
            has_manipulation=len(findings) > 0,
            findings=findings,
            masked_source_for_ai=masked_code,
            masked_regions=masked_regions,
            channels_analyzed=len(channels),
            l1_flags_count=l1_flags,
            l2_escalations_count=l2_escalations,
            l2_flags_count=l2_flags,
        )
