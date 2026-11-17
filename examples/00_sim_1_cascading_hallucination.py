#!/usr/bin/env python3
"""
00_sim_1_cascading_hallucination.py

Python port of 00_sim_1_cascading_hallucination.c.

Simulates a CASCADING HALLUCINATION in a 5-stage agent pipeline:

    Researcher -> Analyst -> Planner -> Coder -> Reviewer

A single fabricated fact is seeded at stage 0 (a library function that does
not exist). Every downstream stage trusts the stage before it, builds on the
fabricated claim, and RAISES confidence instead of re-checking it. By the
Reviewer stage a false claim sits at ~98% confidence and has been "approved".
The Coder stage also bakes in a concrete defect: a buffer size declared as
8192 for a 256-byte buffer (simulated, no real memory is touched).

Modes:
    python3 00_sim_1_cascading_hallucination.py                 unmitigated (attack succeeds)
    python3 00_sim_1_cascading_hallucination.py --verify        each claim is checked against
                                                                ground truth before downstream
                                                                stages may use it
    python3 00_sim_1_cascading_hallucination.py --boost 0.05    per-stage confidence inflation
                                                                (default 0.10)

Exit code: 0 = no false claim reached the Reviewer, 1 = cascade reached the
final stage, 2 = bad arguments.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

N_STAGES = 5
CONF_CAP = 0.99
BUF_ACTUAL = 256
BUF_DECLARED = 8192

STAGE_NAME = ("Researcher", "Analyst", "Planner", "Coder", "Reviewer")

# Facts the verifier can confirm. Hallucinated keys are deliberately absent.
GROUND_TRUTH = frozenset({
    "openssl.EVP_EncryptInit_ex",
    "posix.snprintf",
    "openssl.evp_requires_ctx",
    "posix.snprintf_nul",
    "plan.ctx_alloc",
    "code.ctx_new",
    "review.ctx_ok",
})


@dataclass
class Claim:
    id: int
    stage: int            # pipeline stage that emits this claim
    parent: int           # claim this one is derived from, -1 = root
    key: str              # canonical fact key (the verifier looks this up)
    text: str
    is_true: bool         # ground truth, hidden from the "agents"
    base_conf: float      # only used for root claims
    # runtime state
    emitted: bool = False
    quarantined: bool = False
    conf: float = 0.0


def build_claims() -> list[Claim]:
    return [
        # ---- Stage 0: Researcher -------------------------------------
        Claim(0, 0, -1, "openssl.EVP_EncryptInit_ex",
              "OpenSSL exposes EVP_EncryptInit_ex() for symmetric encryption", True, 0.93),
        Claim(1, 0, -1, "posix.snprintf",
              "POSIX defines snprintf() as a size-bounded write", True, 0.95),
        # [HALLUCINATION SEED] libsecurefmt / secure_sprintf_s() do not exist
        Claim(2, 0, -1, "libsecurefmt.secure_sprintf_s",
              "libsecurefmt 3.2 exports secure_sprintf_s()", False, 0.58),

        # ---- Stage 1: Analyst ----------------------------------------
        # [CASCADE] built on claim 2
        Claim(3, 1, 2, "libsecurefmt.bounds_checked",
              "secure_sprintf_s() is bounds-checked and safe for untrusted input", False, 0.0),
        # [CASCADE] built on claim 2 (fabricated authority)
        Claim(4, 1, 2, "libsecurefmt.cert_approved",
              "libsecurefmt is endorsed by CERT C secure-coding guidance", False, 0.0),
        Claim(5, 1, 0, "openssl.evp_requires_ctx",
              "EVP_EncryptInit_ex() requires an EVP_CIPHER_CTX", True, 0.0),
        Claim(6, 1, 1, "posix.snprintf_nul",
              "snprintf() NUL-terminates whenever size > 0", True, 0.0),

        # ---- Stage 2: Planner ----------------------------------------
        # [CASCADE]
        Claim(7, 2, 3, "plan.replace_snprintf",
              "Plan: replace every snprintf() with secure_sprintf_s()", False, 0.0),
        # [CASCADE]
        Claim(8, 2, 4, "plan.link_securefmt",
              "Plan: add -lsecurefmt and <securefmt.h> to the build", False, 0.0),
        Claim(9, 2, 5, "plan.ctx_alloc",
              "Plan: allocate the context with EVP_CIPHER_CTX_new()", True, 0.0),

        # ---- Stage 3: Coder ------------------------------------------
        # [CASCADE + CONCRETE BUG] size arg 8192 vs. a 256-byte buffer
        Claim(10, 3, 7, "code.call_secure_sprintf",
              "Code: secure_sprintf_s(buf, 8192, fmt, ...) where buf is char[256]", False, 0.0),
        # [CASCADE] header that does not exist
        Claim(11, 3, 8, "code.include_securefmt",
              "Code: #include <securefmt.h>", False, 0.0),
        Claim(12, 3, 9, "code.ctx_new",
              "Code: EVP_CIPHER_CTX *c = EVP_CIPHER_CTX_new();", True, 0.0),

        # ---- Stage 4: Reviewer (checks consistency, not reality) ------
        # [CASCADE] false claim "approved" at max confidence
        Claim(13, 4, 10, "review.api_consistent",
              "Review: API usage consistent with design -> APPROVED", False, 0.0),
        # [CASCADE]
        Claim(14, 4, 11, "review.build_ok",
              "Review: build configuration matches plan -> APPROVED", False, 0.0),
        Claim(15, 4, 12, "review.ctx_ok",
              "Review: context lifecycle correct -> APPROVED", True, 0.0),
    ]


def sim_secure_sprintf_s(declared: int, actual: int) -> None:
    """Reports what WOULD happen; nothing is corrupted."""
    print(f"  secure_sprintf_s(buf, {declared}, ...) called with char buf[{actual}]")
    if declared > actual:
        print(f"  >>> SIMULATED OVERFLOW: up to {declared - actual} bytes written past the end")
    else:
        print("  size argument fits the buffer")


def run(verify: bool, boost: float) -> int:
    claims = build_claims()

    print("=== Cascading hallucination simulation ===")
    print(f"mode: {'VERIFY (gate enabled)' if verify else 'UNMITIGATED'}"
          f" | confidence boost per stage: {boost:.2f}\n")

    for stage in range(N_STAGES):
        print(f"--- Stage {stage}: {STAGE_NAME[stage]} ---")

        for c in claims:
            if c.stage != stage:
                continue

            # Starved: the upstream claim never reached this stage.
            if c.parent >= 0 and not claims[c.parent].emitted:
                print(f"  [c{c.id:02d}] skipped (parent c{c.parent:02d} was blocked)")
                continue

            # Agents inflate confidence by citing their upstream source.
            c.conf = c.base_conf if c.parent < 0 else claims[c.parent].conf + boost
            c.conf = min(c.conf, CONF_CAP)

            if verify and c.key not in GROUND_TRUTH:
                c.quarantined = True
                print(f"  [c{c.id:02d}] QUARANTINED  conf={c.conf:.2f}  {c.text}")
                continue

            c.emitted = True
            seed = "   <-- SEED" if (not c.is_true and c.parent < 0) else ""
            truth = "true" if c.is_true else "FALSE"
            print(f"  [c{c.id:02d}] {truth:<5} conf={c.conf:.2f}  {c.text}{seed}")
        print()

    # ---- Downstream effect of the Coder's output ------------------------
    print("--- Simulated execution of generated code ---")
    if claims[10].emitted:
        sim_secure_sprintf_s(BUF_DECLARED, BUF_ACTUAL)
    else:
        print("  hallucinated call never generated; nothing to execute")
    print()

    # ---- Metrics ---------------------------------------------------------
    emitted = sum(c.emitted for c in claims)
    seeds = sum(1 for c in claims if not c.is_true and c.parent < 0)
    quarantined = sum(c.quarantined for c in claims)
    false_claims = [c for c in claims if c.emitted and not c.is_true]
    false_emitted = len(false_claims)
    false_at_final = sum(1 for c in false_claims if c.stage == N_STAGES - 1)
    false_conf_sum = sum(c.conf for c in false_claims)

    print("=== Summary ===")
    print(f"claims emitted            : {emitted} / {len(claims)}")
    print(f"false claims emitted      : {false_emitted} (from {seeds} seed)")
    print(f"amplification factor      : {false_emitted / seeds if seeds else 0.0:.1f}x")
    print(f"mean confidence of falses : {false_conf_sum / false_emitted if false_emitted else 0.0:.2f}")
    print(f"false claims at Reviewer  : {false_at_final}")
    print(f"quarantined by verifier   : {quarantined}")
    print("result                    : "
          + ("CASCADE REACHED FINAL STAGE (attack succeeded)" if false_at_final
             else "cascade contained"))

    return 1 if false_at_final else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cascading hallucination simulation (Python port of sim_1).")
    parser.add_argument("--verify", action="store_true",
                        help="enable the ground-truth verification gate")
    parser.add_argument("--boost", type=float, default=0.10, metavar="X",
                        help="per-stage confidence inflation (default 0.10)")
    args = parser.parse_args()
    return run(args.verify, args.boost)


if __name__ == "__main__":
    sys.exit(main())