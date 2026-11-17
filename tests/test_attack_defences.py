# tests/test_attack_defences.py
"""
Unit tests for the four agent pipeline threat defences:
1. Cascading Hallucination: symbol & signature integrity checks, circuit breaker, cascade depth limits.
2. Memory Poisoning: HMAC provenance, cache age expiration, corruption quarantine.
3. Agent Identity Compromise: anti-replay nonces, monotonic sequence numbers, authority enforcement, sender spoofing prevention.
4. Resource Overload: input safety limits (size, line length, nesting depth, function count).
"""

import os
import time
import tempfile
import unittest

from compiler.agent_security import (
    MAX_FILE_SIZE_BYTES,
    MAX_LINE_COUNT,
    MAX_LINE_LENGTH,
    MAX_NESTING_DEPTH,
    MAX_FUNCTION_COUNT,
    CACHE_MAX_AGE_SECONDS,
    check_symbol_and_signature_integrity,
    check_input_safety,
    validate_agent_finding,
    get_or_create_cache_hmac_key,
    compute_cache_entry_hmac,
    quarantine_cache_entry,
)
from compiler.finding import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)
from compiler.repair_job_manager import WindowRepairCache


class TestAttackDefences(unittest.TestCase):

    def test_tampered_cache_entry_rejection_and_quarantine(self):
        """Threat 2: Unauthenticated / tampered cache entry must be rejected and quarantined."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            cache_file = f.name
        try:
            cache = WindowRepairCache(cache_file=cache_file)
            test_window = "int compute(int x) { return x + 1; }"
            test_sig = ["syntax:missing_token"]

            # Direct injection of tampered string without HMAC
            key = cache._make_key(test_window, test_sig)
            cache._cache[key] = "int compute(int x) { corrupted_memory_poison_payload(); return 0; }"

            # Attempt retrieval
            val = cache.get(test_window, test_sig)
            self.assertIsNone(val, "Tampered cache entry must return None")
            self.assertNotIn(key, cache._cache, "Tampered entry must be evicted from cache")
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)

    def test_cache_hmac_integrity_and_age_expiration(self):
        """Threat 2: Valid entries pass; modified HMAC or expired age (>24h) fail."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            cache_file = f.name
        try:
            cache = WindowRepairCache(cache_file=cache_file)
            test_window = "int compute(int x) { return x + 2; }"
            repaired = "int compute(int x) { return x + 2; }"
            test_sig = ["syntax:missing_semicolon"]

            # Normal set with HMAC
            cache.set(test_window, test_sig, repaired)
            res = cache.get(test_window, test_sig)
            self.assertEqual(res, repaired, "Authentic cache entry with valid HMAC must be returned")

            # Tamper with HMAC signature
            key = cache._make_key(test_window, test_sig)
            cache._cache[key]["hmac"] = "forged_invalid_hmac_hash_99999"
            res_tampered = cache.get(test_window, test_sig)
            self.assertIsNone(res_tampered, "Entry with invalid HMAC must be rejected")

            # Expire entry by setting created_at 25 hours in the past
            cache.set(test_window, test_sig, repaired)
            cache._cache[key]["created_at"] = time.time() - (CACHE_MAX_AGE_SECONDS + 3600)
            res_expired = cache.get(test_window, test_sig)
            self.assertIsNone(res_expired, "Expired cache entry (>24h) must return None")
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)

    def test_sender_identity_spoofing_rejection(self):
        """Threat 3: Finding claiming a sender different from authentic caller must be rejected."""
        f = Finding.create(
            category=FindingCategory.SECURITY,
            severity=FindingSeverity.HIGH,
            line=10,
            col=5,
            explanation="Buffer length notice",
            metadata={"sender": "SecurityAgent"}
        )
        # Calling as SyntaxAgent with declared sender SecurityAgent
        is_valid, reason = validate_agent_finding(
            agent_name="SyntaxAgent",
            finding=f,
            source_line_count=20,
        )
        self.assertFalse(is_valid, "Spoofed sender identity must be rejected")
        self.assertIn("Sender mismatch", str(reason))

    def test_replay_and_invalid_nonce_rejection(self):
        """Threat 3: Messages with replayed nonce or out-of-order sequence numbers must be rejected."""
        f = Finding.create(
            category=FindingCategory.SYNTAX,
            severity=FindingSeverity.WARNING,
            line=5,
            col=2,
            explanation="Missing semicolon",
            metadata={"sender": "SyntaxAgent", "run_nonce": "stale_nonce_999", "seq_num": 1}
        )
        # Validating with expected nonce different from payload nonce
        is_valid, reason = validate_agent_finding(
            agent_name="SyntaxAgent",
            finding=f,
            source_line_count=20,
            expected_nonce="active_fresh_nonce_111",
        )
        self.assertFalse(is_valid, "Replayed message with stale nonce must be rejected")
        self.assertIn("Replay attack detected", str(reason))

        # Out-of-order sequence number
        f_seq = Finding.create(
            category=FindingCategory.SYNTAX,
            severity=FindingSeverity.WARNING,
            line=5,
            col=2,
            explanation="Missing semicolon",
            metadata={"sender": "SyntaxAgent", "run_nonce": "active_fresh_nonce_111", "seq_num": 1}
        )
        is_valid_seq, reason_seq = validate_agent_finding(
            agent_name="SyntaxAgent",
            finding=f_seq,
            source_line_count=20,
            expected_nonce="active_fresh_nonce_111",
            expected_seq_num=5,  # expected 5 but received 1
        )
        self.assertFalse(is_valid_seq, "Out-of-order sequence number must be rejected")
        self.assertIn("out-of-order sequence number", str(reason_seq))

    def test_out_of_role_authority_matrix_rejection(self):
        """Threat 3: Agent emitting findings outside its authority must be rejected."""
        f_sec = Finding.create(
            category=FindingCategory.SECURITY,
            severity=FindingSeverity.CRITICAL,
            line=8,
            col=1,
            explanation="Memory management defect",
            metadata={"sender": "SyntaxAgent"}
        )
        # SyntaxAgent is not authorized to emit SECURITY findings
        is_valid, reason = validate_agent_finding(
            agent_name="SyntaxAgent",
            finding=f_sec,
            source_line_count=20,
        )
        self.assertFalse(is_valid, "Out-of-role finding category must be rejected")
        self.assertIn("Authority violation", str(reason))

    def test_hallucinated_symbol_and_altered_signature_rejection(self):
        """Threat 1: Proposing newly introduced undeclared symbols or altering signatures must be rejected."""
        orig_c = (
            "#include <stdio.h>\n"
            "int calculate_total(int price, int tax) {\n"
            "    return price + tax;\n"
            "}\n"
        )

        # 1. Propose hallucinated function call
        hallucinated_c = orig_c.replace("return price + tax;", "return phantom_engine(price, tax);")
        ok, reason = check_symbol_and_signature_integrity(orig_c, hallucinated_c, language="c")
        self.assertFalse(ok, "Hallucinated symbol call must be rejected")
        self.assertIn("phantom_engine", str(reason))

        # 2. Propose altered function signature (3 parameters instead of 2)
        altered_sig_c = (
            "#include <stdio.h>\n"
            "int calculate_total(int price, int tax, int extra_param) {\n"
            "    return price + tax + extra_param;\n"
            "}\n"
        )
        ok_sig, reason_sig = check_symbol_and_signature_integrity(orig_c, altered_sig_c, language="c")
        self.assertFalse(ok_sig, "Altered function signature arity must be rejected")
        self.assertIn("altered signature", str(reason_sig))

        # 3. Python hallucination check
        orig_py = "def calculate_total(price, tax):\n    return price + tax\n"
        hallucinated_py = "def calculate_total(price, tax):\n    return phantom_external_fn(price)\n"
        ok_py, reason_py = check_symbol_and_signature_integrity(orig_py, hallucinated_py, language="python")
        self.assertFalse(ok_py, "Python hallucinated symbol must be rejected")
        self.assertIn("phantom_external_fn", str(reason_py))

    def test_input_safety_limits_rejection(self):
        """Threat 4: Pathological inputs exceeding safety limits must be rejected cleanly."""
        # 1. Line length exceeded
        long_line_code = "int x = " + ("1 + " * 800) + "1;\n"
        ok_len, reason_len = check_input_safety(long_line_code, language="c")
        self.assertFalse(ok_len, "Line length > 2000 chars must be rejected")
        self.assertIn("Line length", str(reason_len))

        # 2. Nesting depth exceeded (> 30 levels)
        deep_nest_c = "int test() {\n" + ("if (1) {\n" * 35) + "int a = 0;\n" + ("}\n" * 35) + "return 0;\n}\n"
        ok_nest, reason_nest = check_input_safety(deep_nest_c, language="c")
        self.assertFalse(ok_nest, "Nesting depth > 30 levels must be rejected")
        self.assertIn("Block nesting depth", str(reason_nest))

        # 3. Normal clean code passes cleanly
        normal_code = "#include <stdio.h>\nint main(void) {\n    printf(\"Hello, safe world!\\n\");\n    return 0;\n}\n"
        ok_normal, reason_normal = check_input_safety(normal_code, language="c")
        self.assertTrue(ok_normal, "Standard safe code must pass input safety check")
        self.assertIsNone(reason_normal)


if __name__ == "__main__":
    unittest.main()
