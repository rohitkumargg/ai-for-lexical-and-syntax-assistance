# compiler/agents.py
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from compiler.finding import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    CorrectionSuggestion,
)


class BaseCompilerAgent(ABC):
    """Abstract base class for thin compiler agent wrappers."""

    def __init__(self, name: str, category: FindingCategory):
        self.name = name
        self.category = category

    @abstractmethod
    def analyze(
        self,
        source_text: str,
        filename: str = "main.c",
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Finding]:
        """Analyze source and return structured findings."""
        pass


class LexicalAgent(BaseCompilerAgent):
    """Thin wrapper around lexical corrector and token-level inspections."""

    def __init__(self):
        super().__init__("LexicalAgent", FindingCategory.LEXICAL)

    def analyze(
        self,
        source_text: str,
        filename: str = "main.c",
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Finding]:
        findings: List[Finding] = []
        try:
            from compiler.lexical_corrector import fix_common_lexical_issues
            fixed_src, fix_msgs = fix_common_lexical_issues(source_text)
            if fix_msgs and fixed_src != source_text:
                lines_src = source_text.splitlines()
                msg_list = fix_msgs if isinstance(fix_msgs, list) else [str(fix_msgs)]
                for msg in msg_list:
                    m_old = re.search(r"'(.*?)'", msg) or re.search(r'"(.*?)"', msg)
                    target_token = m_old.group(1) if m_old else None
                    found_lines = []
                    if target_token:
                        for idx, line_str in enumerate(lines_src, start=1):
                            if re.search(r"\b" + re.escape(target_token) + r"\b", line_str) or target_token in line_str:
                                found_lines.append(idx)
                    if not found_lines:
                        m_num = re.search(r"line\s+(\d+)", msg, re.IGNORECASE)
                        found_lines = [int(m_num.group(1))] if m_num else [1]

                    for line_no in found_lines:
                        evidence = lines_src[line_no - 1] if 1 <= line_no <= len(lines_src) else ""
                        col_no = evidence.find(target_token) if target_token and target_token in evidence else 0
                        suggestion = CorrectionSuggestion(
                            description=msg,
                            replacement_text=fixed_src,
                            confidence=1.0,
                            is_deterministic=True,
                            rule_id="lexical_rule",
                        )
                        findings.append(
                            Finding.create(
                                category=FindingCategory.LEXICAL,
                                line=line_no,
                                col=col_no,
                                explanation=f"Lexical error: {msg}",
                                evidence=evidence.strip(),
                                severity=FindingSeverity.WARNING,
                                confidence=1.0,
                                status=FindingStatus.CONFIRMED,
                                file_path=filename,
                                suggested_corrections=[suggestion],
                                metadata={"fix_message": msg},
                            )
                        )
        except Exception as e:
            findings.append(
                Finding.create(
                    category=FindingCategory.SYSTEM,
                    line=1,
                    col=0,
                    explanation=f"LexicalAgent error: {str(e)}",
                    severity=FindingSeverity.INFO,
                    confidence=0.5,
                    status=FindingStatus.POSSIBLE,
                    file_path=filename,
                    metadata={"error": str(e)},
                )
            )

        return findings


class SyntaxAgent(BaseCompilerAgent):
    """Thin wrapper around ANTLR lexer/parser error listeners and error classifier."""

    def __init__(self):
        super().__init__("SyntaxAgent", FindingCategory.SYNTAX)

    def analyze(
        self,
        source_text: str,
        filename: str = "main.c",
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Finding]:
        findings: List[Finding] = []

        try:
            from test_parser import parse_source, get_first_error_object
            from compiler.error_classifier import classify_error_message

            tree, listeners, parser = parse_source(source_text, filename)
            err_obj = get_first_error_object(listeners)

            if not err_obj:
                return []

            lines = source_text.splitlines()

            # Process all errors collected by listeners
            all_errors: List[Dict[str, Any]] = []
            if isinstance(listeners, dict):
                if "lex" in listeners and hasattr(listeners["lex"], "get_error_objects"):
                    for e in listeners["lex"].get_error_objects():
                        e_copy = dict(e)
                        e_copy["_source_type"] = "LEXICAL"
                        all_errors.append(e_copy)
                if "parse" in listeners and hasattr(listeners["parse"], "get_error_objects"):
                    for e in listeners["parse"].get_error_objects():
                        e_copy = dict(e)
                        e_copy["_source_type"] = "SYNTAX"
                        all_errors.append(e_copy)
            elif hasattr(listeners, "get_error_objects"):
                all_errors.extend(listeners.get_error_objects())
            elif hasattr(listeners, "errors"):
                all_errors.extend(list(listeners.errors))

            if not all_errors and err_obj:
                all_errors = [err_obj]

            for err in all_errors:
                raw_line = int(err.get("line", 1))
                raw_col = int(err.get("column", 0))
                msg = str(err.get("msg", ""))
                offending = err.get("offending") or ""
                evidence = lines[raw_line - 1] if 1 <= raw_line <= len(lines) else ""

                classification = classify_error_message(msg)
                reason = classification.reason if classification else "unknown_syntax_error"

                # Check if deterministic fix exists
                from compiler.error_corrector import apply_correction
                candidate, fix_desc = apply_correction(source_text, raw_line, raw_col, classification, validate=False)
                suggestions: List[CorrectionSuggestion] = []
                if fix_desc and candidate != source_text:
                    suggestions.append(
                        CorrectionSuggestion(
                            description=fix_desc,
                            replacement_text=candidate,
                            confidence=0.95,
                            is_deterministic=True,
                            rule_id=reason,
                        )
                    )

                is_lex = (
                    err.get("_source_type") == "LEXICAL"
                    or "token recognition error" in msg.lower()
                    or "invalid character" in msg.lower()
                    or "malformed literal" in msg.lower()
                )
                category = FindingCategory.LEXICAL if is_lex else FindingCategory.SYNTAX
                label = "Lexical error" if is_lex else "Syntax error"

                findings.append(
                    Finding.create(
                        category=category,
                        line=raw_line,
                        col=raw_col,
                        explanation=f"{label} ({reason}): {msg}",
                        evidence=evidence.strip(),
                        severity=FindingSeverity.CRITICAL,
                        confidence=1.0,
                        status=FindingStatus.CONFIRMED,
                        file_path=filename,
                        suggested_corrections=suggestions,
                        metadata={
                            "rule_id": f"SYNTAX-{reason.upper()}",
                            "reason": reason,
                            "offending": offending,
                            "raw_msg": msg,
                        },
                    )
                )
        except Exception as e:
            findings.append(
                Finding.create(
                    category=FindingCategory.SYSTEM,
                    line=1,
                    col=0,
                    explanation=f"SyntaxAgent internal error: {str(e)}",
                    severity=FindingSeverity.INFO,
                    confidence=0.5,
                    status=FindingStatus.POSSIBLE,
                    file_path=filename,
                    metadata={"error": str(e)},
                )
            )

        return findings


class SemanticAgent(BaseCompilerAgent):
    """Thin wrapper around SemanticChecker and AST semantic visitor."""

    def __init__(self):
        super().__init__("SemanticAgent", FindingCategory.SEMANTIC)

    def analyze(
        self,
        source_text: str,
        filename: str = "main.c",
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Finding]:
        findings: List[Finding] = []

        try:
            from test_parser import parse_source, has_any_errors
            from compiler.pipeline_safety import collect_semantic_issues
            from compiler.semantic_auto_fixer import fix_semantic_issue

            tree, listeners, parser = parse_source(source_text, filename)
            # Only run semantic checking if tree exists and has no syntax errors
            if tree is None or has_any_errors(listeners):
                findings.append(
                    Finding.create(
                        category=FindingCategory.SYSTEM,
                        line=1,
                        col=0,
                        explanation="Semantic analysis unavailable: parse tree could not be generated or contains syntax errors.",
                        severity=FindingSeverity.INFO,
                        confidence=1.0,
                        status=FindingStatus.POSSIBLE,
                        file_path=filename,
                        metadata={"limitation": "BLOCKED_BY_SYNTAX_ERROR"},
                    )
                )
                return findings

            issues = collect_semantic_issues(tree)
            lines = source_text.splitlines()

            for iss in issues:
                line_no = int(iss.get("line", 1))
                col_no = int(iss.get("col", 0))
                kind = str(iss.get("kind", "semantic_issue"))
                msg = str(iss.get("msg", ""))
                name = iss.get("name")
                evidence = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""

                # Build suggestions
                suggestions: List[CorrectionSuggestion] = []
                corrected_code, fix_msg = fix_semantic_issue(source_text, iss)
                if fix_msg and corrected_code != source_text:
                    suggestions.append(
                        CorrectionSuggestion(
                            description=fix_msg,
                            replacement_text=corrected_code,
                            confidence=0.9,
                            is_deterministic=True,
                            rule_id=f"sem_{kind}",
                        )
                    )

                severity = FindingSeverity.WARNING if kind == "unused" else FindingSeverity.HIGH

                findings.append(
                    Finding.create(
                        category=FindingCategory.SEMANTIC,
                        line=line_no,
                        col=col_no,
                        explanation=f"Semantic {kind}: {msg}",
                        evidence=evidence.strip(),
                        severity=severity,
                        confidence=0.95,
                        status=FindingStatus.CONFIRMED,
                        file_path=filename,
                        suggested_corrections=suggestions,
                        metadata={
                            "kind": kind,
                            "name": name,
                            "msg": msg,
                        },
                    )
                )
        except Exception as e:
            findings.append(
                Finding.create(
                    category=FindingCategory.SYSTEM,
                    line=1,
                    col=0,
                    explanation=f"SemanticAgent internal error: {str(e)}",
                    severity=FindingSeverity.INFO,
                    confidence=0.5,
                    status=FindingStatus.POSSIBLE,
                    file_path=filename,
                    metadata={"error": str(e)},
                )
            )

        return findings


class SecurityAgent(BaseCompilerAgent):
    """Thin wrapper around SecurityEngine, distinguishing confirmed from possible findings."""

    def __init__(self, ollama: Optional[Any] = None, enable_qwen: bool = False):
        super().__init__("SecurityAgent", FindingCategory.SECURITY)
        self.ollama = ollama
        self.enable_qwen = enable_qwen

    def _get_ollama(self):
        if self.ollama is not None:
            return self.ollama
        try:
            from compiler.local_models import OllamaClient
            return OllamaClient()
        except Exception:
            return None

    def generate_qwen_repair(
        self,
        source_text: str,
        findings: Optional[List[Any]] = None,
        filename: str = "main.c",
        language: str = "c",
    ) -> Tuple[Optional[str], Optional[str]]:
        """Use Qwen to generate repairs or possible fix code for security findings."""
        ollama = self._get_ollama()
        if not ollama or not ollama.is_available():
            return None, "Qwen (Ollama) service unavailable"
        try:
            finding_list = findings or []
            qwen_res = ollama.coordinate_repair_decision(
                source_text=source_text,
                findings=finding_list,
                filename=filename,
                language=language,
            )
            cand = qwen_res.get("candidate_code")
            expl = qwen_res.get("explanation") or qwen_res.get("reasoning", "")
            if cand and cand.strip() != source_text.strip():
                return cand, expl or "Qwen AI-generated security repair"
            return None, "No candidate produced by Qwen"
        except Exception as e:
            return None, f"Qwen security repair error: {str(e)}"

    def analyze(
        self,
        source_text: str,
        filename: str = "main.c",
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Finding]:
        findings: List[Finding] = []

        try:
            from compiler.security_engine import SecurityEngine
            from compiler.security_auto_fixer import SecurityAutoFixer

            engine = SecurityEngine()
            sec_issues, is_blocked, categorized = engine.analyze(source_text)
            lines = source_text.splitlines()

            # Check for deterministic security autofix
            fix_result = None
            try:
                fixer = SecurityAutoFixer()
                fix_result = fixer.apply_fixes(source_text)
            except Exception:
                pass

            # Check for Qwen security repair
            qwen_cand = None
            qwen_expl = None
            if self.enable_qwen and sec_issues:
                try:
                    ollama = self._get_ollama()
                    if ollama and ollama.is_available():
                        pseudo_findings = [
                            {
                                "category": "SECURITY",
                                "severity": getattr(iss, "severity", "WARNING"),
                                "line": getattr(iss, "line", 1) or 1,
                                "column": getattr(iss, "col", 0) or 0,
                                "explanation": getattr(iss, "message", str(iss)),
                                "evidence": lines[(getattr(iss, "line", 1) or 1) - 1] if 1 <= (getattr(iss, "line", 1) or 1) <= len(lines) else "",
                            }
                            for iss in sec_issues
                        ]
                        cand, expl = self.generate_qwen_repair(
                            source_text=source_text,
                            findings=pseudo_findings,
                            filename=filename,
                            language="c",
                        )
                        if cand and cand.strip() != source_text.strip():
                            qwen_cand = cand
                            qwen_expl = expl
                except Exception:
                    pass

            for issue in sec_issues:
                line_no = getattr(issue, "line", None) or 1
                col_no = getattr(issue, "col", None) or 0
                sev_raw = getattr(issue, "severity", "WARNING").upper()
                msg = getattr(issue, "message", str(issue))
                sugg_text = getattr(issue, "suggestion", "")
                fn_name = getattr(issue, "fn", "")
                evidence = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""

                # Distinguish CONFIRMED from POSSIBLE security findings:
                # - Confirmed: Direct banned/unsafe API invocations (gets, strcpy, strcat, sprintf, system), or CRITICAL
                # - Possible: Heuristics, path alerts, format string warnings without confirmed taint flow
                is_confirmed = (
                    sev_raw == "CRITICAL"
                    or fn_name in {"gets", "strcpy", "strcat", "sprintf", "system", "popen", "WinExec"}
                    or "banned function" in msg.lower()
                    or "vulnerability detected" in msg.lower()
                )

                status = FindingStatus.CONFIRMED if is_confirmed else FindingStatus.POSSIBLE
                confidence = 1.0 if is_confirmed else 0.65

                severity_map = {
                    "CRITICAL": FindingSeverity.CRITICAL,
                    "HIGH": FindingSeverity.HIGH,
                    "WARNING": FindingSeverity.WARNING,
                    "INFO": FindingSeverity.INFO,
                }
                severity = severity_map.get(sev_raw, FindingSeverity.WARNING)

                suggestions: List[CorrectionSuggestion] = []
                if fix_result and hasattr(fix_result, "source") and fix_result.source != source_text:
                    suggestions.append(
                        CorrectionSuggestion(
                            description="Auto-repair: replace insecure call with safer standard variant",
                            replacement_text=fix_result.source,
                            confidence=0.95,
                            is_deterministic=True,
                            rule_id=f"sec_fix_{fn_name or 'generic'}",
                        )
                    )

                if qwen_cand:
                    suggestions.append(
                        CorrectionSuggestion(
                            description=f"Qwen AI security repair: {qwen_expl or 'Fix security vulnerability'}",
                            replacement_text=qwen_cand,
                            confidence=0.90,
                            is_deterministic=False,
                            rule_id=f"qwen_sec_fix_{fn_name or 'generic'}",
                        )
                    )
                elif sugg_text and not suggestions:
                    suggestions.append(
                        CorrectionSuggestion(
                            description=sugg_text,
                            replacement_text=None,
                            confidence=0.8,
                            is_deterministic=False,
                            rule_id="manual_suggestion",
                        )
                    )

                findings.append(
                    Finding.create(
                        category=FindingCategory.SECURITY,
                        line=line_no,
                        col=col_no,
                        explanation=msg,
                        evidence=evidence.strip(),
                        severity=severity,
                        confidence=confidence,
                        status=status,
                        file_path=filename,
                        suggested_corrections=suggestions,
                        metadata={
                            "fn": fn_name,
                            "raw_severity": sev_raw,
                            "is_confirmed": is_confirmed,
                        },
                    )
                )
        except Exception as e:
            findings.append(
                Finding.create(
                    category=FindingCategory.SYSTEM,
                    line=1,
                    col=0,
                    explanation=f"SecurityAgent internal error: {str(e)}",
                    severity=FindingSeverity.INFO,
                    confidence=0.5,
                    status=FindingStatus.POSSIBLE,
                    file_path=filename,
                    metadata={"error": str(e)},
                )
            )

        return findings


class PythonSyntaxAgent(BaseCompilerAgent):
    """Python AST-based parser and syntax error detection agent."""

    def __init__(self):
        super().__init__("PythonSyntaxAgent", FindingCategory.SYNTAX)

    def analyze(
        self,
        source_text: str,
        filename: str = "main.py",
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Finding]:
        findings: List[Finding] = []
        try:
            from compiler.languages.python_lang import err, candidates, is_token_level

            syntax_err = err(source_text)
            if not syntax_err:
                return []

            line, col, msg = syntax_err
            lines = source_text.splitlines()
            evidence = lines[line - 1] if 1 <= line <= len(lines) else ""

            suggestions: List[CorrectionSuggestion] = []
            for desc, cand_src in candidates(source_text):
                if err(cand_src) is None or err(cand_src) != syntax_err:
                    suggestions.append(
                        CorrectionSuggestion(
                            description=f"Python rule repair: {desc}",
                            replacement_text=cand_src,
                            confidence=0.95,
                            is_deterministic=True,
                            rule_id=desc,
                        )
                    )
                    break

            findings.append(
                Finding.create(
                    category=FindingCategory.SYNTAX,
                    line=line,
                    col=col,
                    explanation=f"Python syntax error: {msg}",
                    evidence=evidence.strip(),
                    severity=FindingSeverity.CRITICAL,
                    confidence=1.0,
                    status=FindingStatus.CONFIRMED,
                    file_path=filename,
                    suggested_corrections=suggestions,
                    metadata={"reason": "python_syntax_error", "raw_msg": msg, "language": "python"},
                )
            )
        except Exception as e:
            findings.append(
                Finding.create(
                    category=FindingCategory.SYSTEM,
                    line=1,
                    col=0,
                    explanation=f"PythonSyntaxAgent error: {str(e)}",
                    severity=FindingSeverity.INFO,
                    confidence=0.5,
                    status=FindingStatus.POSSIBLE,
                    file_path=filename,
                    metadata={"error": str(e), "language": "python"},
                )
            )
        return findings


class PythonSemanticAgent(BaseCompilerAgent):
    """Python scope, identifier, and control-flow analyzer agent."""

    def __init__(self):
        super().__init__("PythonSemanticAgent", FindingCategory.SEMANTIC)

    def analyze(
        self,
        source_text: str,
        filename: str = "main.py",
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Finding]:
        findings: List[Finding] = []
        try:
            from compiler.languages.python_lang import err
            from compiler.languages import python_semantic

            if err(source_text) is not None:
                # Syntax error blocks reliable semantic analysis
                return []

            issues = python_semantic.analyze(source_text)
            lines = source_text.splitlines()

            for iss in issues:
                line_no = int(iss.get("line", 1))
                col_no = int(iss.get("col", 0))
                kind = str(iss.get("kind", "semantic_issue"))
                msg = str(iss.get("msg", ""))
                name = iss.get("name")
                evidence = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""

                suggestions: List[CorrectionSuggestion] = []
                try:
                    cand = python_semantic.get_fix_candidate(source_text, [iss])
                    if cand:
                        cand_src, step_msg, targeted = cand
                        suggestions.append(
                            CorrectionSuggestion(
                                description=step_msg,
                                replacement_text=cand_src,
                                confidence=0.9,
                                is_deterministic=True,
                                rule_id=f"py_sem_{kind}",
                            )
                        )
                except Exception:
                    pass

                severity = FindingSeverity.WARNING if kind == "unused" else FindingSeverity.HIGH

                findings.append(
                    Finding.create(
                        category=FindingCategory.SEMANTIC,
                        line=line_no,
                        col=col_no,
                        explanation=f"Python semantic {kind}: {msg}",
                        evidence=evidence.strip(),
                        severity=severity,
                        confidence=0.95,
                        status=FindingStatus.CONFIRMED,
                        file_path=filename,
                        suggested_corrections=suggestions,
                        metadata={"kind": kind, "name": name, "msg": msg, "language": "python"},
                    )
                )
        except Exception as e:
            findings.append(
                Finding.create(
                    category=FindingCategory.SYSTEM,
                    line=1,
                    col=0,
                    explanation=f"PythonSemanticAgent error: {str(e)}",
                    severity=FindingSeverity.INFO,
                    confidence=0.5,
                    status=FindingStatus.POSSIBLE,
                    file_path=filename,
                    metadata={"error": str(e), "language": "python"},
                )
            )
        return findings


class PythonSecurityAgent(BaseCompilerAgent):
    """Python AST-based vulnerability detection agent."""

    def __init__(self, ollama: Optional[Any] = None, enable_qwen: bool = False):
        super().__init__("PythonSecurityAgent", FindingCategory.SECURITY)
        self.ollama = ollama
        self.enable_qwen = enable_qwen

    def _get_ollama(self):
        if self.ollama is not None:
            return self.ollama
        try:
            from compiler.local_models import OllamaClient
            return OllamaClient()
        except Exception:
            return None

    def generate_qwen_repair(
        self,
        source_text: str,
        findings: Optional[List[Any]] = None,
        filename: str = "main.py",
        language: str = "python",
    ) -> Tuple[Optional[str], Optional[str]]:
        ollama = self._get_ollama()
        if not ollama or not ollama.is_available():
            return None, "Qwen (Ollama) service unavailable"
        try:
            finding_list = findings or []
            qwen_res = ollama.coordinate_repair_decision(
                source_text=source_text,
                findings=finding_list,
                filename=filename,
                language=language,
            )
            cand = qwen_res.get("candidate_code")
            expl = qwen_res.get("explanation") or qwen_res.get("reasoning", "")
            if cand and cand.strip() != source_text.strip():
                return cand, expl or "Qwen AI-generated Python security repair"
            return None, "No candidate produced by Qwen"
        except Exception as e:
            return None, f"Qwen security repair error: {str(e)}"

    def analyze(
        self,
        source_text: str,
        filename: str = "main.py",
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Finding]:
        findings: List[Finding] = []
        try:
            from compiler.languages import python_security

            sec_issues = python_security.analyze(source_text)
            lines = source_text.splitlines()

            # Check for Qwen Python security repair
            qwen_cand = None
            qwen_expl = None
            if self.enable_qwen and sec_issues:
                try:
                    ollama = self._get_ollama()
                    if ollama and ollama.is_available():
                        cand, expl = self.generate_qwen_repair(
                            source_text=source_text,
                            findings=sec_issues,
                            filename=filename,
                            language="python",
                        )
                        if cand and cand.strip() != source_text.strip():
                            qwen_cand = cand
                            qwen_expl = expl
                except Exception:
                    pass

            for issue in sec_issues:
                line_no = int(issue.get("line", 1))
                col_no = int(issue.get("col", 0))
                rule = str(issue.get("rule", "PY-SEC"))
                msg = str(issue.get("message", ""))
                sev_raw = str(issue.get("severity", "HIGH")).upper()
                evidence = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""

                suggestions: List[CorrectionSuggestion] = []
                try:
                    cand = python_security.get_fix_candidate(source_text, [issue])
                    if cand:
                        cand_src, step_msg, warn_msg, chg_line, targeted = cand
                        suggestions.append(
                            CorrectionSuggestion(
                                description=step_msg,
                                replacement_text=cand_src,
                                confidence=0.95,
                                is_deterministic=True,
                                rule_id=f"py_sec_{rule}",
                            )
                        )
                except Exception:
                    pass

                if qwen_cand:
                    suggestions.append(
                        CorrectionSuggestion(
                            description=f"Qwen AI security repair: {qwen_expl or 'Fix Python security vulnerability'}",
                            replacement_text=qwen_cand,
                            confidence=0.90,
                            is_deterministic=False,
                            rule_id=f"qwen_py_sec_{rule}",
                        )
                    )

                severity_map = {
                    "CRITICAL": FindingSeverity.CRITICAL,
                    "HIGH": FindingSeverity.HIGH,
                    "WARNING": FindingSeverity.WARNING,
                    "INFO": FindingSeverity.INFO,
                }
                severity = severity_map.get(sev_raw, FindingSeverity.HIGH)

                findings.append(
                    Finding.create(
                        category=FindingCategory.SECURITY,
                        line=line_no,
                        col=col_no,
                        explanation=f"Python security {rule}: {msg}",
                        evidence=evidence.strip(),
                        severity=severity,
                        confidence=0.95,
                        status=FindingStatus.CONFIRMED,
                        file_path=filename,
                        suggested_corrections=suggestions,
                        metadata={
                            "rule_id": rule,
                            "cwe_id": issue.get("cwe_id", "CWE-General"),
                            "is_confirmed": True,
                            "language": "python",
                        },
                    )
                )
        except Exception as e:
            findings.append(
                Finding.create(
                    category=FindingCategory.SYSTEM,
                    line=1,
                    col=0,
                    explanation=f"PythonSecurityAgent error: {str(e)}",
                    severity=FindingSeverity.INFO,
                    confidence=0.5,
                    status=FindingStatus.POSSIBLE,
                    file_path=filename,
                    metadata={"error": str(e), "language": "python"},
                )
            )
        return findings

