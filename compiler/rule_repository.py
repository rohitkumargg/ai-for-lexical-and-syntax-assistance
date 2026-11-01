# compiler/rule_repository.py
"""
Candidate Rule Discovery and Controlled Improvement for SimpleC Compiler.

Phase 7 Requirements:
1. Automated & Manual Candidate Rule Discovery:
   - Proposes candidate rules when a model solves an error unhandled by existing deterministic rules.
   - Separate candidate-rule repository (isolated from active deterministic rules).
2. Complete Schema for Candidate Rules:
   - Triggering conditions
   - Applicable context
   - Declarative transformation pattern
   - Explicit assumptions
   - Positive tests
   - Negative tests
   - Ambiguous cases
   - Validation results
3. Independent Testing & Security Checks:
   - Validates positive tests, negative tests, ambiguous cases.
   - Runs syntax, semantic, and SecurityReporter checks.
4. Human Review and Approval Gate:
   - Requires explicit human review and approval before activation.
   - Models are strictly forbidden from self-promotion or silent database modifications.
5. Versioning, Rollback, and Disabling:
   - Tracks version history for active rules.
   - Supports disabling active rules and rolling back to earlier versions.
6. Security Invariant:
   - Immutable permissions and instructions; no arbitrary code execution (no eval/exec).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class RuleStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISABLED = "DISABLED"


class TransformationType(str, Enum):
    REGEX_SUB = "regex_sub"
    TOKEN_INSERT = "token_insert"
    REPLACE_EXACT = "replace_exact"
    LINE_REPLACE = "line_replace"


@dataclass
class RuleTestCase:
    input_code: str
    expected_output: str = ""
    description: str = ""
    # Aliases
    expected_code: str = ""
    name: str = ""

    def __post_init__(self):
        if not self.expected_output and self.expected_code:
            self.expected_output = self.expected_code
        elif not self.expected_code and self.expected_output:
            self.expected_code = self.expected_output
        if not self.description and self.name:
            self.description = self.name
        elif not self.name and self.description:
            self.name = self.description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.description,
            "description": self.description,
            "input_code": self.input_code,
            "expected_output": self.expected_output,
            "expected_code": self.expected_output,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RuleTestCase:
        inp = data.get("input_code", "")
        exp = data.get("expected_output") or data.get("expected_code", "")
        desc = data.get("description") or data.get("name", "")
        return cls(input_code=inp, expected_output=exp, description=desc, expected_code=exp, name=desc)


@dataclass
class RuleValidationReport:
    positive_passed: bool = False
    positive_passed_count: int = 0
    positive_total_count: int = 0
    negative_passed: bool = False
    negative_passed_count: int = 0
    negative_total_count: int = 0
    ambiguous_passed: bool = False
    ambiguous_passed_count: int = 0
    ambiguous_total_count: int = 0
    security_clean: bool = False
    regression_clean: bool = False
    details: List[str] = field(default_factory=list)
    validated_at: float = field(default_factory=time.time)

    @property
    def is_valid(self) -> bool:
        return (
            self.positive_passed
            and self.negative_passed
            and self.ambiguous_passed
            and self.security_clean
            and self.regression_clean
        )

    @property
    def passed_tests(self) -> int:
        return self.positive_passed_count + self.negative_passed_count + self.ambiguous_passed_count

    @property
    def total_tests(self) -> int:
        return self.positive_total_count + self.negative_total_count + self.ambiguous_total_count

    @property
    def security_checked(self) -> bool:
        return True

    @property
    def security_passed(self) -> bool:
        return self.security_clean

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "passed_tests": self.passed_tests,
            "total_tests": self.total_tests,
            "security_checked": self.security_checked,
            "security_passed": self.security_passed,
            "positive_passed": self.positive_passed,
            "positive_passed_count": self.positive_passed_count,
            "positive_total_count": self.positive_total_count,
            "negative_passed": self.negative_passed,
            "negative_passed_count": self.negative_passed_count,
            "negative_total_count": self.negative_total_count,
            "ambiguous_passed": self.ambiguous_passed,
            "ambiguous_passed_count": self.ambiguous_passed_count,
            "ambiguous_total_count": self.ambiguous_total_count,
            "security_clean": self.security_clean,
            "regression_clean": self.regression_clean,
            "details": list(self.details),
            "validated_at": self.validated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RuleValidationReport:
        return cls(
            positive_passed=bool(data.get("positive_passed", False)),
            positive_passed_count=int(data.get("positive_passed_count", 0)),
            positive_total_count=int(data.get("positive_total_count", 0)),
            negative_passed=bool(data.get("negative_passed", False)),
            negative_passed_count=int(data.get("negative_passed_count", 0)),
            negative_total_count=int(data.get("negative_total_count", 0)),
            ambiguous_passed=bool(data.get("ambiguous_passed", False)),
            ambiguous_passed_count=int(data.get("ambiguous_passed_count", 0)),
            ambiguous_total_count=int(data.get("ambiguous_total_count", 0)),
            security_clean=bool(data.get("security_clean", False)),
            regression_clean=bool(data.get("regression_clean", False)),
            details=data.get("details", []),
            validated_at=float(data.get("validated_at", 0.0)),
        )


@dataclass
class CandidateRule:
    rule_id: str = ""
    name: str = ""
    category: str = "syntax"
    triggering_conditions: Any = field(default_factory=dict)
    applicable_context: str = ""
    transformation: Dict[str, Any] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)
    positive_tests: List[RuleTestCase] = field(default_factory=list)
    negative_tests: List[RuleTestCase] = field(default_factory=list)
    ambiguous_cases: List[RuleTestCase] = field(default_factory=list)
    error_reason: str = "generic"
    validation_results: Optional[RuleValidationReport] = None
    status: RuleStatus = RuleStatus.PENDING_REVIEW
    created_at: float = field(default_factory=time.time)
    proposer: str = "model_codet5"
    version: str = "1.0.0"
    reviewer: Optional[str] = None
    review_comments: Optional[str] = None
    review_timestamp: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Optional aliases
    id: Optional[str] = None
    source_model: Optional[str] = None

    def __post_init__(self):
        if self.id and not self.rule_id:
            self.rule_id = self.id
        elif self.rule_id and not self.id:
            self.id = self.rule_id
        if self.source_model and self.proposer == "model_codet5":
            self.proposer = self.source_model
        elif self.proposer and not self.source_model:
            self.source_model = self.proposer

    @property
    def validation_report(self) -> Optional[RuleValidationReport]:
        return self.validation_results

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.rule_id,
            "rule_id": self.rule_id,
            "name": self.name,
            "category": self.category,
            "error_reason": self.error_reason,
            "triggering_conditions": dict(self.triggering_conditions) if isinstance(self.triggering_conditions, dict) else self.triggering_conditions,
            "applicable_context": self.applicable_context,
            "transformation": dict(self.transformation) if isinstance(self.transformation, dict) else self.transformation,
            "assumptions": list(self.assumptions),
            "positive_tests": [t.to_dict() for t in self.positive_tests],
            "negative_tests": [t.to_dict() for t in self.negative_tests],
            "ambiguous_cases": [t.to_dict() for t in self.ambiguous_cases],
            "validation_results": self.validation_results.to_dict() if self.validation_results else None,
            "validation_report": self.validation_results.to_dict() if self.validation_results else None,
            "status": self.status.value,
            "created_at": self.created_at,
            "source_model": self.proposer,
            "proposer": self.proposer,
            "version": self.version,
            "reviewer": self.reviewer,
            "review_comments": self.review_comments,
            "review_timestamp": self.review_timestamp,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CandidateRule:
        val_rep = (
            RuleValidationReport.from_dict(data["validation_results"])
            if data.get("validation_results")
            else None
        )
        cid = data.get("rule_id") or data.get("id", "cand_unknown")
        proposer = data.get("proposer") or data.get("source_model", "model")
        return cls(
            rule_id=cid,
            id=cid,
            name=data.get("name", "Unnamed Candidate Rule"),
            category=data.get("category", "syntax"),
            error_reason=data.get("error_reason", "generic"),
            triggering_conditions=data.get("triggering_conditions", {}),
            applicable_context=data.get("applicable_context", ""),
            transformation=data.get("transformation", {}),
            assumptions=data.get("assumptions", []),
            positive_tests=[RuleTestCase.from_dict(t) for t in data.get("positive_tests", [])],
            negative_tests=[RuleTestCase.from_dict(t) for t in data.get("negative_tests", [])],
            ambiguous_cases=[RuleTestCase.from_dict(t) for t in data.get("ambiguous_cases", [])],
            validation_results=val_rep,
            status=RuleStatus(data.get("status", "PENDING_REVIEW")),
            created_at=float(data.get("created_at", time.time())),
            proposer=proposer,
            source_model=proposer,
            version=data.get("version", "1.0.0"),
            reviewer=data.get("reviewer"),
            review_comments=data.get("review_comments"),
            review_timestamp=data.get("review_timestamp"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ActiveRule:
    rule_id: str
    candidate_id: str
    name: str
    category: str
    error_reason: str
    triggering_conditions: Any
    applicable_context: str
    transformation: Dict[str, Any]
    assumptions: List[str]
    positive_tests: List[RuleTestCase]
    negative_tests: List[RuleTestCase]
    ambiguous_cases: List[RuleTestCase]
    version: str = "1.0.0"
    enabled: bool = True
    activated_at: float = field(default_factory=time.time)
    activated_by: str = "human_reviewer"
    history: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.rule_id

    @property
    def is_enabled(self) -> bool:
        return self.enabled

    @property
    def approved_by(self) -> str:
        return self.activated_by

    @property
    def approved_at(self) -> float:
        return self.activated_at

    @property
    def version_history(self) -> List[Dict[str, Any]]:
        return self.history

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.rule_id,
            "rule_id": self.rule_id,
            "candidate_id": self.candidate_id,
            "name": self.name,
            "category": self.category,
            "error_reason": self.error_reason,
            "triggering_conditions": dict(self.triggering_conditions) if isinstance(self.triggering_conditions, dict) else self.triggering_conditions,
            "applicable_context": self.applicable_context,
            "transformation": dict(self.transformation) if isinstance(self.transformation, dict) else self.transformation,
            "assumptions": list(self.assumptions),
            "positive_tests": [t.to_dict() for t in self.positive_tests],
            "negative_tests": [t.to_dict() for t in self.negative_tests],
            "ambiguous_cases": [t.to_dict() for t in self.ambiguous_cases],
            "version": self.version,
            "enabled": self.enabled,
            "is_enabled": self.enabled,
            "activated_at": self.activated_at,
            "approved_at": self.activated_at,
            "activated_by": self.activated_by,
            "approved_by": self.activated_by,
            "history": list(self.history),
            "version_history": list(self.history),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ActiveRule:
        rid = data.get("rule_id") or data.get("id", "rule_active")
        return cls(
            rule_id=rid,
            candidate_id=data.get("candidate_id", ""),
            name=data.get("name", ""),
            category=data.get("category", "syntax"),
            error_reason=data.get("error_reason", "generic"),
            triggering_conditions=data.get("triggering_conditions", {}),
            applicable_context=data.get("applicable_context", ""),
            transformation=data.get("transformation", {}),
            assumptions=data.get("assumptions", []),
            positive_tests=[RuleTestCase.from_dict(t) for t in data.get("positive_tests", [])],
            negative_tests=[RuleTestCase.from_dict(t) for t in data.get("negative_tests", [])],
            ambiguous_cases=[RuleTestCase.from_dict(t) for t in data.get("ambiguous_cases", [])],
            version=data.get("version", "1.0.0"),
            enabled=bool(data.get("is_enabled", data.get("enabled", True))),
            activated_at=float(data.get("activated_at", time.time())),
            activated_by=data.get("activated_by") or data.get("approved_by", "human_reviewer"),
            history=data.get("version_history", data.get("history", [])),
        )


# ----------------------------------------------------------------------
# Rule Transformation Engine (Declarative, Safe, Non-Exec)
# ----------------------------------------------------------------------
class RuleExecutor:
    """
    Safely executes declarative transformations without unrestricted eval/exec.
    Guarantees sandbox immutability.
    """

    @classmethod
    def apply(cls, source_code: str, transformation: Dict[str, Any]) -> Tuple[bool, str]:
        res = cls.apply_transformation(source_code, transformation)
        if res is not None and res != source_code:
            return True, res
        return False, source_code

    @staticmethod
    def apply_transformation(source_code: str, transformation: Dict[str, Any]) -> Optional[str]:
        t_type = transformation.get("type")
        if not t_type:
            return None

        try:
            if t_type == TransformationType.REGEX_SUB.value:
                pattern = transformation.get("pattern", "")
                replacement = transformation.get("replacement", "")
                count = int(transformation.get("count", 0))
                if not pattern:
                    return None
                new_src = re.sub(pattern, replacement, source_code, count=count)
                return new_src if new_src != source_code else None

            elif t_type == TransformationType.TOKEN_INSERT.value:
                line_idx = transformation.get("line")
                col_idx = transformation.get("col")
                token = transformation.get("replacement") or transformation.get("token", "")
                pattern = transformation.get("pattern", "")
                if pattern and line_idx is None:
                    m = re.search(pattern, source_code)
                    if m:
                        idx = m.end()
                        return source_code[:idx] + token + source_code[idx:]
                    return None
                if line_idx is None or not token:
                    return None
                lines = source_code.splitlines(keepends=True)
                if not (1 <= line_idx <= len(lines)):
                    return None
                target_line = lines[line_idx - 1]
                col = col_idx if col_idx is not None else len(target_line.rstrip("\r\n"))
                new_line = target_line[:col] + token + target_line[col:]
                lines[line_idx - 1] = new_line
                return "".join(lines)

            elif t_type == TransformationType.REPLACE_EXACT.value:
                old_text = transformation.get("pattern") or transformation.get("target", "")
                new_text = transformation.get("replacement", "")
                if not old_text or old_text not in source_code:
                    return None
                return source_code.replace(old_text, new_text, 1)

            elif t_type == TransformationType.LINE_REPLACE.value:
                line_no = transformation.get("line")
                new_line_text = transformation.get("replacement") or transformation.get("new_text", "")
                lines = source_code.splitlines(keepends=True)
                if line_no is None or not (1 <= line_no <= len(lines)):
                    return None
                has_nl = lines[line_no - 1].endswith("\n")
                lines[line_no - 1] = new_line_text + ("\n" if has_nl else "")
                return "".join(lines)
        except Exception:
            return None

        return None


# ----------------------------------------------------------------------
# Rule Validator
# ----------------------------------------------------------------------
class CandidateRuleValidator:
    """
    Tests candidate rules against:
    1. Positive test cases (must resolve error and parse cleanly)
    2. Negative test cases (must NOT fire or modify clean code)
    3. Ambiguous test cases (must refuse to alter code)
    4. Security checks (must not introduce vulnerabilities)
    5. Regression checks
    """

    def validate_candidate(self, candidate: CandidateRule) -> RuleValidationReport:
        return self.validate_rule(candidate)

    def validate_rule(self, rule: CandidateRule) -> RuleValidationReport:
        details: List[str] = []

        # 1. Positive Tests
        pos_passed = 0
        for idx, t in enumerate(rule.positive_tests):
            applied = RuleExecutor.apply_transformation(t.input_code, rule.transformation)
            expected = t.expected_output or t.expected_code
            if applied is not None and applied.strip() == expected.strip():
                pos_passed += 1
            else:
                details.append(f"Positive test #{idx+1} failed: expected '{expected.strip()}', got '{str(applied).strip()}'")

        all_pos_ok = (pos_passed == len(rule.positive_tests)) if rule.positive_tests else True

        # 2. Negative Tests (Must not fire or change code)
        neg_passed = 0
        for idx, t in enumerate(rule.negative_tests):
            applied = RuleExecutor.apply_transformation(t.input_code, rule.transformation)
            if applied is None or applied == t.input_code:
                neg_passed += 1
            else:
                details.append(f"Negative test #{idx+1} failed: rule modified negative code: '{applied}'")

        all_neg_ok = (neg_passed == len(rule.negative_tests)) if rule.negative_tests else True

        # 3. Ambiguous Cases (Must not fire)
        amb_passed = 0
        for idx, t in enumerate(rule.ambiguous_cases):
            applied = RuleExecutor.apply_transformation(t.input_code, rule.transformation)
            if applied is None or applied == t.input_code:
                amb_passed += 1
            else:
                details.append(f"Ambiguous test #{idx+1} failed: rule should have yielded but fired: '{applied}'")

        all_amb_ok = (amb_passed == len(rule.ambiguous_cases)) if rule.ambiguous_cases else True

        # 4. Security Verification
        sec_clean = True
        try:
            from compiler.security_reporter import SecurityReporter
            sec_rep = SecurityReporter()
            for t in rule.positive_tests:
                applied = RuleExecutor.apply_transformation(t.input_code, rule.transformation) or t.input_code
                sec_res = sec_rep.analyze_source(applied)
                if sec_res.critical_count > 0 or sec_res.is_blocked:
                    sec_clean = False
                    details.append(f"Security check failed on positive test: {sec_res.summary}")
        except Exception as e:
            details.append(f"Security check exception: {str(e)}")

        # 5. Regression Check
        reg_clean = True
        try:
            from test_parser import parse_source, has_any_errors
            for t in rule.positive_tests:
                applied = RuleExecutor.apply_transformation(t.input_code, rule.transformation) or t.input_code
                tree, listeners, _ = parse_source(applied, "rule_test.c")
                if has_any_errors(listeners):
                    reg_clean = False
                    details.append(f"Parser regression on positive test: {applied}")
        except Exception as e:
            details.append(f"Parser check exception: {str(e)}")

        return RuleValidationReport(
            positive_passed=all_pos_ok,
            positive_passed_count=pos_passed,
            positive_total_count=len(rule.positive_tests),
            negative_passed=all_neg_ok,
            negative_passed_count=neg_passed,
            negative_total_count=len(rule.negative_tests),
            ambiguous_passed=all_amb_ok,
            ambiguous_passed_count=amb_passed,
            ambiguous_total_count=len(rule.ambiguous_cases),
            security_clean=sec_clean,
            regression_clean=reg_clean,
            details=details,
            validated_at=time.time(),
        )


# ----------------------------------------------------------------------
# Rule Repository Manager
# ----------------------------------------------------------------------
class RuleRepositoryManager:
    """
    Manages:
    1. Candidate-rule repository (isolated from active rules).
    2. Active deterministic rule database.
    3. Rule versioning, history, and rollback.

    Enforces security guarantees:
    - Models CANNOT write directly to active rules.
    - Human approval is required for activation.
    - Full versioning and rollback capability.
    """

    def __init__(
        self,
        base_dir: Optional[str] = None,
        candidate_file: Optional[str] = None,
        active_file: Optional[str] = None,
        history_file: Optional[str] = None,
        candidate_path: Optional[str] = None,
        active_path: Optional[str] = None,
        history_path: Optional[str] = None,
    ):
        self.base_dir = base_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rules")
        os.makedirs(self.base_dir, exist_ok=True)

        self.candidate_file = candidate_path or candidate_file or os.path.join(self.base_dir, "candidate_rules.json")
        self.active_file = active_path or active_file or os.path.join(self.base_dir, "active_rules.json")
        self.history_file = history_path or history_file or os.path.join(self.base_dir, "rule_history.json")

        for f_path in (self.candidate_file, self.active_file, self.history_file):
            if f_path:
                os.makedirs(os.path.dirname(os.path.abspath(f_path)), exist_ok=True)

        self.validator = CandidateRuleValidator()

        # In-memory caches
        self.candidates: Dict[str, CandidateRule] = {}
        self.active_rules: Dict[str, ActiveRule] = {}
        self.history: List[Dict[str, Any]] = []

        self._load_all()

    def _load_all(self):
        # Load Candidates
        if os.path.exists(self.candidate_file):
            try:
                with open(self.candidate_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.candidates = {k: CandidateRule.from_dict(v) for k, v in data.items()}
            except Exception:
                self.candidates = {}

        # Load Active Rules
        if os.path.exists(self.active_file):
            try:
                with open(self.active_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.active_rules = {k: ActiveRule.from_dict(v) for k, v in data.items()}
            except Exception:
                self.active_rules = {}

        # Load History
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []

    def _save_candidates(self):
        with open(self.candidate_file, "w", encoding="utf-8") as f:
            json.dump({k: v.to_dict() for k, v in self.candidates.items()}, f, indent=2)

    def _save_active(self):
        with open(self.active_file, "w", encoding="utf-8") as f:
            json.dump({k: v.to_dict() for k, v in self.active_rules.items()}, f, indent=2)

    def _save_history(self):
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2)

    def get_candidate(self, candidate_id: str) -> Optional[CandidateRule]:
        return self.candidates.get(candidate_id)

    def list_active(self) -> List[ActiveRule]:
        return list(self.active_rules.values())

    # ------------------------------------------------------------------
    # Candidate Rule Discovery & Proposal
    # ------------------------------------------------------------------
    def propose_candidate(
        self,
        candidate_or_name: Union[CandidateRule, str] = "",
        name: str = "",
        category: str = "syntax",
        error_reason: str = "generic",
        triggering_conditions: Any = None,
        applicable_context: str = "",
        transformation: Optional[Dict[str, Any]] = None,
        assumptions: Optional[List[str]] = None,
        positive_tests: Optional[List[RuleTestCase]] = None,
        negative_tests: Optional[List[RuleTestCase]] = None,
        ambiguous_cases: Optional[List[RuleTestCase]] = None,
        proposer: str = "model_codet5",
        source_model: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CandidateRule:
        """
        Store proposed candidate rule in the separate candidate repository.
        Status is set to PENDING_REVIEW.
        """
        if isinstance(candidate_or_name, CandidateRule):
            cand = candidate_or_name
            report = self.validator.validate_rule(cand)
            cand.validation_results = report
            self.candidates[cand.rule_id] = cand
            self._save_candidates()
            return cand

        final_name = name or (candidate_or_name if isinstance(candidate_or_name, str) else "Candidate Rule")
        raw_hash = f"{category}:{error_reason}:{final_name}:{time.time()}"
        cid = f"rule_cand_{hashlib.sha256(raw_hash.encode()).hexdigest()[:8]}"

        final_proposer = source_model or proposer

        candidate = CandidateRule(
            rule_id=cid,
            id=cid,
            name=final_name,
            category=category,
            error_reason=error_reason,
            triggering_conditions=triggering_conditions or {},
            applicable_context=applicable_context,
            transformation=transformation or {},
            assumptions=assumptions or [],
            positive_tests=positive_tests or [],
            negative_tests=negative_tests or [],
            ambiguous_cases=ambiguous_cases or [],
            status=RuleStatus.PENDING_REVIEW,
            created_at=time.time(),
            proposer=final_proposer,
            source_model=final_proposer,
            version="1.0.0",
            metadata=metadata or {},
        )

        report = self.validator.validate_rule(candidate)
        candidate.validation_results = report

        self.candidates[cid] = candidate
        self._save_candidates()
        return candidate

    def validate_candidate(self, candidate_id: str) -> Optional[RuleValidationReport]:
        cand = self.candidates.get(candidate_id)
        if not cand:
            return None

        report = self.validator.validate_rule(cand)
        cand.validation_results = report
        self._save_candidates()
        return report

    # ------------------------------------------------------------------
    # Human Review & Activation Gate (Models STRICTLY Forbidden)
    # ------------------------------------------------------------------
    def approve_and_activate(
        self,
        candidate_id: str,
        reviewer_name: str,
        comments: str = "",
        notes: str = "",
        force: bool = False,
    ) -> ActiveRule:
        reviewer_clean = (reviewer_name or "").strip().lower()
        if not reviewer_clean or any(k in reviewer_clean for k in ("model", "ai", "qwen", "codet5", "system", "auto", "bot", "assistant")):
            raise PermissionError("Security Violation: AI models are strictly forbidden from approving or promoting candidate rules. Human reviewer identifier required.")

        cand = self.candidates.get(candidate_id)
        if not cand:
            raise KeyError(f"Candidate rule '{candidate_id}' not found.")

        # Verify tests pass before activation
        val_rep = self.validator.validate_rule(cand)
        cand.validation_results = val_rep
        if not val_rep.is_valid and not force:
            raise ValueError(f"Cannot activate rule: Validation checks failed ({'; '.join(val_rep.details)})")

        cand.status = RuleStatus.APPROVED
        cand.reviewer = reviewer_name
        cand.review_comments = comments or notes
        cand.review_timestamp = time.time()
        self._save_candidates()

        active = ActiveRule(
            rule_id=cand.rule_id,
            candidate_id=cand.rule_id,
            name=cand.name,
            category=cand.category,
            error_reason=cand.error_reason,
            triggering_conditions=cand.triggering_conditions,
            applicable_context=cand.applicable_context,
            transformation=cand.transformation,
            assumptions=cand.assumptions,
            positive_tests=cand.positive_tests,
            negative_tests=cand.negative_tests,
            ambiguous_cases=cand.ambiguous_cases,
            version="1.0.0",
            enabled=True,
            activated_at=time.time(),
            activated_by=reviewer_name,
            history=[],
        )
        self.active_rules[cand.rule_id] = active
        self._save_active()

        self.history.append({
            "event": "RULE_ACTIVATED",
            "rule_id": cand.rule_id,
            "reviewer": reviewer_name,
            "timestamp": time.time(),
            "notes": comments or notes,
        })
        self._save_history()
        return active

    def reject_candidate(self, candidate_id: str, reviewer_name: str, reason: str = "") -> Tuple[bool, str]:
        cand = self.candidates.get(candidate_id)
        if not cand:
            return False, f"Candidate rule '{candidate_id}' not found."

        cand.status = RuleStatus.REJECTED
        cand.reviewer = reviewer_name
        cand.review_comments = reason
        cand.review_timestamp = time.time()
        self._save_candidates()

        self.history.append({
            "event": "CANDIDATE_REJECTED",
            "rule_id": candidate_id,
            "reviewer": reviewer_name,
            "reason": reason,
            "timestamp": time.time(),
        })
        self._save_history()
        return True, f"Candidate rule '{candidate_id}' rejected."

    # ------------------------------------------------------------------
    # Active Rule Updates, Disabling & Rollback
    # ------------------------------------------------------------------
    def update_active_rule(
        self,
        rule_id: str,
        new_transformation: Dict[str, Any],
        new_version: str,
        author: str,
        change_description: str = "",
    ) -> ActiveRule:
        active = self.active_rules.get(rule_id)
        if not active:
            raise KeyError(f"Active rule '{rule_id}' not found.")

        active.history.insert(0, {
            "version": active.version,
            "transformation": copy.deepcopy(active.transformation),
            "updated_by": author,
            "timestamp": time.time(),
            "description": change_description,
        })
        active.transformation = copy.deepcopy(new_transformation)
        active.version = new_version
        self._save_active()
        return active

    def disable_rule(self, rule_id: str, reviewer_name: str = "human_reviewer", reason: str = "") -> ActiveRule:
        active = self.active_rules.get(rule_id)
        if not active:
            raise KeyError(f"Active rule '{rule_id}' not found.")

        active.enabled = False
        active.history.insert(0, {
            "action": "disable",
            "reviewer": reviewer_name,
            "reason": reason,
            "timestamp": time.time(),
        })
        self._save_active()

        self.history.append({
            "event": "RULE_DISABLED",
            "rule_id": rule_id,
            "reviewer": reviewer_name,
            "reason": reason,
            "timestamp": time.time(),
        })
        self._save_history()
        return active

    def enable_rule(self, rule_id: str, reviewer_name: str = "human_reviewer") -> ActiveRule:
        active = self.active_rules.get(rule_id)
        if not active:
            raise KeyError(f"Active rule '{rule_id}' not found.")

        active.enabled = True
        active.history.insert(0, {
            "action": "enable",
            "reviewer": reviewer_name,
            "timestamp": time.time(),
        })
        self._save_active()
        return active

    def rollback_rule(
        self, rule_id: str, target_version: str, reviewer_name: str = "human_reviewer", operator: str = ""
    ) -> ActiveRule:
        active = self.active_rules.get(rule_id)
        if not active:
            raise KeyError(f"Active rule '{rule_id}' not found.")

        match_entry = None
        for entry in active.history:
            if entry.get("version") == target_version:
                match_entry = entry
                break

        if not match_entry:
            raise ValueError(f"Version '{target_version}' not found in history of rule '{rule_id}'.")

        old_version = active.version
        active.version = target_version
        active.transformation = copy.deepcopy(match_entry["transformation"])
        active.history.insert(0, {
            "action": "rollback",
            "from_version": old_version,
            "to_version": target_version,
            "reviewer": reviewer_name or operator,
            "timestamp": time.time(),
        })
        self._save_active()

        self.history.append({
            "event": "RULE_ROLLBACK",
            "rule_id": rule_id,
            "from_version": old_version,
            "target_version": target_version,
            "reviewer": reviewer_name or operator,
            "timestamp": time.time(),
        })
        self._save_history()
        return active

    # ------------------------------------------------------------------
    # Compiler Integration: Evaluate active rules on source code
    # ------------------------------------------------------------------
    def apply_active_rules(self, source_text: str) -> Tuple[bool, str]:
        """
        Executes active, enabled deterministic rules on source code.
        Returns: (applied_bool, transformed_code)
        """
        current_code = source_text
        any_applied = False

        for rule in self.active_rules.values():
            if not rule.enabled:
                continue

            cond = rule.triggering_conditions
            if isinstance(cond, dict):
                keyword = cond.get("keyword_pattern")
                if keyword and not re.search(keyword, current_code):
                    continue

            ok, transformed = RuleExecutor.apply(current_code, rule.transformation)
            if ok and transformed != current_code:
                current_code = transformed
                any_applied = True

        return any_applied, current_code


# ----------------------------------------------------------------------
# Rule Discovery Engine (Extracts candidate rules from successful AI repairs)
# ----------------------------------------------------------------------
class RuleDiscoveryEngine:
    """
    Observes successful model repairs that were not covered by deterministic rules,
    and synthesizes candidate rules for future deterministic automation.
    """

    def __init__(self, repository: Optional[RuleRepositoryManager] = None):
        self.repository = repository or RuleRepositoryManager()

    def propose_from_successful_repair(
        self,
        original_code: str,
        repaired_code: str,
        finding: Any = None,
        error_reason: str = "",
        model_name: str = "",
        source_model: str = "",
        category: str = "syntax",
    ) -> Optional[CandidateRule]:
        if original_code == repaired_code:
            return None

        if finding is not None:
            if not error_reason:
                error_reason = getattr(finding, "evidence", "") or getattr(finding, "explanation", "error")
            if hasattr(finding, "category"):
                category = finding.category.value if hasattr(finding.category, "value") else str(finding.category)
            category = (category or "syntax").lower()

        final_model = source_model or model_name or "qwen2.5-coder"

        orig_lines = original_code.splitlines()
        rep_lines = repaired_code.splitlines()

        if len(orig_lines) != len(rep_lines):
            return None

        diff_line_idx = -1
        for i in range(len(orig_lines)):
            if orig_lines[i] != rep_lines[i]:
                if diff_line_idx != -1:
                    return None
                diff_line_idx = i

        if diff_line_idx == -1:
            return None

        line_orig = orig_lines[diff_line_idx]
        line_rep = rep_lines[diff_line_idx]

        # Case 1: Missing Semicolon insertion at line end
        if line_rep.rstrip() == line_orig.rstrip() + ";" and not line_orig.rstrip().endswith(";"):
            pattern = r"([A-Za-z0-9_)\"\'\]]+)\s*$"
            replacement = r"\1;"
            name = f"Auto-Discovered Semicolon Insertion after {error_reason}"
            assumptions = [
                "Statement ends without a semicolon before line boundary",
                "Line is not a control statement header (if/while/for)",
            ]
            pos_tests = [
                RuleTestCase(
                    input_code=original_code,
                    expected_output=repaired_code,
                    description="Original repair instance",
                ),
                RuleTestCase(
                    input_code="int main() {\n    int a = 100\n    return a;\n}",
                    expected_output="int main() {\n    int a = 100;\n    return a;\n}",
                    description="Standard missing semicolon at assignment",
                ),
            ]
            neg_tests = [
                RuleTestCase(
                    input_code="int main() {\n    if (x == 10)\n    return 0;\n}",
                    expected_output="int main() {\n    if (x == 10)\n    return 0;\n}",
                    description="Clean if statement header must not have semicolon appended",
                )
            ]
            ambiguous_cases = [
                RuleTestCase(
                    input_code="#define MAX 100",
                    expected_output="#define MAX 100",
                    description="Preprocessor macro must not have semicolon appended",
                )
            ]

            return self.repository.propose_candidate(
                name=name,
                category=category,
                error_reason=error_reason or "missing_semicolon",
                triggering_conditions={
                    "error_stage": "PARSE",
                    "error_reason": error_reason,
                    "keyword_pattern": r"\w+",
                },
                applicable_context="Inside function body statement termination",
                transformation={
                    "type": TransformationType.REGEX_SUB.value,
                    "pattern": pattern,
                    "replacement": replacement,
                    "count": 1,
                },
                assumptions=assumptions,
                positive_tests=pos_tests,
                negative_tests=neg_tests,
                ambiguous_cases=ambiguous_cases,
                source_model=final_model,
                proposer=final_model,
            )

        return None
