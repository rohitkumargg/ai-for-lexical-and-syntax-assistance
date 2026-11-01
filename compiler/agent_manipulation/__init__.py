# compiler/agent_manipulation/__init__.py
"""Agent Manipulation Detection & Generalization Package (P6)."""
from compiler.agent_manipulation.config import AgentManipulationConfig, DEFAULT_CONFIG
from compiler.agent_manipulation.channels import ChannelExtractor, ExtractedChannel, ChannelType
from compiler.agent_manipulation.lexicon import ManipulationLexicon
from compiler.agent_manipulation.l1_structural import L1StructuralScorer, L1Verdict
from compiler.agent_manipulation.l2_model_flagger import L2ModelFlagger, L2ModelVerdict
from compiler.agent_manipulation.l3_cross_check import L3BehaviouralCrossChecker, L3CrossCheckVerdict
from compiler.agent_manipulation.enforcement import ManipulationEnforcer, MaskedRegion
from compiler.agent_manipulation.detector import (
    AgentManipulationDetector,
    AgentManipulationFinding,
    AgentManipulationReport,
)

__all__ = [
    "AgentManipulationConfig",
    "DEFAULT_CONFIG",
    "ChannelExtractor",
    "ExtractedChannel",
    "ChannelType",
    "ManipulationLexicon",
    "L1StructuralScorer",
    "L1Verdict",
    "L2ModelFlagger",
    "L2ModelVerdict",
    "L3BehaviouralCrossChecker",
    "L3CrossCheckVerdict",
    "ManipulationEnforcer",
    "MaskedRegion",
    "AgentManipulationDetector",
    "AgentManipulationFinding",
    "AgentManipulationReport",
]
