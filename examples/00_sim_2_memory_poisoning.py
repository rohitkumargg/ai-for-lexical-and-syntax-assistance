#!/usr/bin/env python3
"""
00_sim_2_memory_poisoning.py

Python port of 00_sim_2_memory_poisoning.c.

Simulates MEMORY POISONING of a multi-session agent with a persistent memory
store, and the CASCADING HALLUCINATION that follows from it.

    Attack     untrusted web content is summarised into memory
               ("SESSION_TIMEOUT=0 EXPIRY=OFF AUDIT=OFF", which is false)
    Session 1  Planner       reads memory, writes a plan back to memory
    Session 2  Configurator  reads the plan, writes a config back
    Session 3  Deployer      reads the config, writes a deploy record, applies it
    Session 4  Auditor       reads the deploy record, writes a verdict

Why it cascades (each item is a planted weakness):
    [RECENCY]     retrieval returns the NEWEST entry for a topic, so one fresh
                  poisoned write overrides the true, older, higher-trust entry.
    [LAUNDERING]  every agent writes its conclusion back labelled source=SELF,
                  so the entry's untrusted WEB origin is no longer visible.
    [INFLATION]   each write-back raises trust (parent trust + boost).
    [SELF-AUDIT]  the Auditor checks consistency with memory, not with reality.

A parallel TLS thread is fed only by trusted entries and acts as a control:
it must stay clean in every mode.

Modes:
    python3 00_sim_2_memory_poisoning.py                 unmitigated (attack succeeds)
    python3 00_sim_2_memory_poisoning.py --verify        provenance tracking + write gate:
                                                         untrusted-origin writes must be
                                                         corroborated by trusted memory or
                                                         they are quarantined
    python3 00_sim_2_memory_poisoning.py --boost 0.05    per-write trust inflation (default 0.10)

Optional REAL defects (runtime flags, off by default so the default run is a
clean control for scanner false-positive testing). Python has no buffer
overflow, so these are the closest Python equivalents:
    --plant-overflow           deploy_apply() copies into a fixed 48-byte buffer
                               with no bounds check (models strcpy). Only the
                               poisoned (longer) value triggers it: IndexError.
                               The traceback is printed and the exit code is 134.
    --plant-hallucinated-api   imports a module that does not exist (memguard)
                               and calls memguard.sanitize(). Fails at startup
                               with ModuleNotFoundError (exit code 1). Linters
                               (pylint E0401, mypy import-not-found) flag it
                               statically too.

Exit code: 0 = no false entry reached the Auditor, 1 = cascade reached the final
session, 2 = bad arguments, 134 = planted overflow triggered.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import dataclass
from enum import IntEnum

if "--plant-hallucinated-api" in sys.argv:
    import memguard  # [HALLUCINATED MODULE] no such module exists

MAX_MEM = 32
VAL_LEN = 48
CFG_BUF = 48
TRUST_CAP = 0.99
POISON_VALUE = "SESSION_TIMEOUT=0 EXPIRY=OFF AUDIT=OFF"


class Src(IntEnum):
    USER = 0
    TOOL = 1
    WEB = 2
    SELF = 3


@dataclass
class MemEntry:
    id: int
    session: int
    agent: str
    topic: str
    value: str
    is_true: bool        # ground truth, hidden from the agents
    source: Src          # source label RECORDED in the store
    origin: Src          # real root of the lineage (the verifier uses this)
    parent: int          # entry this one was derived from, -1 = root
    trust: float
    live: bool = True    # False = quarantined


class MemoryStore:
    def __init__(self, verify: bool, boost: float, plant_api: bool = False) -> None:
        self.verify = verify
        self.boost = boost
        self.plant_api = plant_api
        self.entries: list[MemEntry] = []

    def corroborated(self, e: MemEntry) -> bool:
        """A WEB-origin write is accepted only if a live, trusted-origin entry
        already holds the same value for the same topic."""
        return any(
            m.live and m.origin != Src.WEB and m.topic == e.topic and m.value == e.value
            for m in self.entries
        )

    def write(self, session: int, agent: str, topic: str, value: str, is_true: bool,
              source: Src, parent: int, base_trust: float) -> int:
        if len(self.entries) >= MAX_MEM:
            print("memory store full", file=sys.stderr)
            return -1

        entry_id = len(self.entries)
        value = value[: VAL_LEN - 1]  # mirrors char value[VAL_LEN]

        # The real lineage root is always tracked; only the recorded label differs.
        origin = source if parent < 0 else self.entries[parent].origin

        if parent < 0:
            rec_source, trust = source, base_trust
        elif self.verify:
            rec_source = self.entries[parent].source   # provenance preserved
            trust = self.entries[parent].trust         # no inflation
        else:
            rec_source = Src.SELF                      # [LAUNDERING]
            trust = min(self.entries[parent].trust + self.boost, TRUST_CAP)  # [INFLATION]

        e = MemEntry(entry_id, session, agent, topic, value, is_true,
                     rec_source, origin, parent, trust)

        if self.plant_api:
            memguard.sanitize(e.value)  # [HALLUCINATED API] does not exist

        if self.verify and e.origin == Src.WEB and not self.corroborated(e):
            e.live = False
            print(f"  [m{e.id:02d}] s{session} {agent:<12} {topic:<15} QUARANTINED  "
                  f'value="{e.value}" src={e.source.name} trust={e.trust:.2f}'
                  " (uncorroborated untrusted write)")
            self.entries.append(e)
            return e.id

        if not is_true and parent < 0:
            tag = "  <-- POISON SEED"
        elif not is_true and e.source != e.origin:
            tag = "  <-- laundered"
        else:
            tag = ""
        truth = "true" if is_true else "FALSE"
        print(f"  [m{e.id:02d}] s{session} {agent:<12} {topic:<15} = {e.value:<38} "
              f"src={e.source.name:<4} origin={e.origin.name:<4} trust={e.trust:.2f} "
              f"{truth:<5}{tag}")
        self.entries.append(e)
        return e.id

    def retrieve(self, topic: str) -> int:
        best = -1
        for i, m in enumerate(self.entries):
            if not m.live or m.topic != topic:
                continue
            if self.verify:
                if m.origin == Src.WEB:
                    continue                               # never trust WEB lineage
                if best < 0 or m.trust >= self.entries[best].trust:
                    best = i
            else:
                best = i                                   # [RECENCY] newest wins
        return best

    def agent_step(self, session: int, agent: str, in_topic: str, out_topic: str) -> int:
        src = self.retrieve(in_topic)
        if src < 0:
            print(f"  {agent:<12} | nothing retrieved for '{in_topic}' (skipped)")
            return -1
        s = self.entries[src]
        return self.write(session, agent, out_topic, s.value, s.is_true, Src.SELF, src, 0.0)


def unchecked_strcpy(dst: bytearray, src: bytes) -> None:
    """Models C strcpy(): copies src and its NUL terminator with no bounds check.
    Raises IndexError once the write runs past the end of dst."""
    for i in range(len(src) + 1):
        dst[i] = src[i] if i < len(src) else 0


def deploy_apply(value: str, plant_overflow: bool) -> None:
    line = f"deploytool --set {value}"[:127]   # char line[128]
    data = line.encode()
    need = len(data) + 1
    cfg = bytearray(CFG_BUF)

    if plant_overflow:
        # [PLANTED DEFECT] unchecked copy: the poisoned value needs 56 bytes,
        # cfg holds 48. Reachable only via poisoned memory.
        unchecked_strcpy(cfg, data)
    else:
        n = min(need - 1, CFG_BUF - 1)
        cfg[:n] = data[:n]                     # bounded copy: never exceeds cfg
        cfg[n] = 0
        if need > CFG_BUF:
            print(f"  >>> SIMULATED OVERFLOW: {need} bytes needed, {CFG_BUF}-byte buffer "
                  f"(an unchecked strcpy would overrun by {need - CFG_BUF})")

    applied = bytes(cfg).split(b"\x00", 1)[0].decode()
    print(f"  applying: {applied}")


def run(verify: bool, boost: float, plant_overflow: bool, plant_api: bool) -> int:
    agents = ("Planner", "Configurator", "Deployer", "Auditor")
    session_topics = ("session.timeout", "plan.session", "config.session",
                      "deploy.session", "audit.session")
    tls_topics = ("tls.min_version", "plan.tls", "config.tls",
                  "deploy.tls", "audit.tls")

    store = MemoryStore(verify, boost, plant_api)

    print("=== Memory poisoning -> cascading hallucination simulation ===")
    print(f"mode: {'VERIFY (provenance + write gate)' if verify else 'UNMITIGATED'}"
          f" | trust boost per write-back: {boost:.2f}\n")

    print("--- Setup: trusted memory ---")
    store.write(0, "setup", "tls.min_version", "TLS_MIN=1.2", True, Src.USER, -1, 0.95)
    store.write(0, "setup", "session.timeout", "SESSION_TIMEOUT=900", True, Src.USER, -1, 0.95)

    print("\n--- Attack: untrusted web page summarised into memory ---")
    store.write(0, "web-summary", "session.timeout", POISON_VALUE, False, Src.WEB, -1, 0.55)

    for s in range(1, 5):
        agent = agents[s - 1]
        print(f"\n--- Session {s}: {agent} ---")

        eid = store.agent_step(s, agent, session_topics[s - 1], session_topics[s])
        if eid >= 0 and store.entries[eid].live:
            if s == 3:
                deploy_apply(store.entries[eid].value, plant_overflow)
            if s == 4:
                print(f"  {agent} verdict: APPROVED (consistent with memory)")
        store.agent_step(s, agent, tls_topics[s - 1], tls_topics[s])

    # ---- Metrics ---------------------------------------------------------
    entries = store.entries
    seeds = [e for e in entries if not e.is_true and e.parent < 0]
    quarantined = sum(1 for e in entries if not e.live)
    live = [e for e in entries if e.live]
    false_live = [e for e in live if not e.is_true]
    laundered = sum(1 for e in false_live if e.source != e.origin)
    false_final = [e for e in false_live if e.session == 4]

    trust_seed = seeds[-1].trust if seeds else 0.0
    trust_final = false_final[-1].trust if false_final else trust_seed

    print("\n=== Summary ===")
    print(f"live memory entries       : {len(live)}")
    print(f"false entries in memory   : {len(false_live)} (from {len(seeds)} poisoned seed)")
    print(f"memory contamination      : {100.0 * len(false_live) / len(live) if live else 0.0:.0f}%")
    print(f"amplification factor      : {len(false_live) / len(seeds) if seeds else 0.0:.1f}x")
    print(f"provenance laundered      : {laundered} entries (WEB origin recorded as SELF)")
    print(f"trust of poisoned lineage : {trust_seed:.2f} -> {trust_final:.2f}")
    print(f"quarantined by verifier   : {quarantined}")
    print(f"false entries at Auditor  : {len(false_final)}")
    print("result                    : "
          + ("CASCADE REACHED FINAL SESSION (attack succeeded)" if false_final
             else "cascade contained"))

    return 1 if false_final else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Memory poisoning -> cascading hallucination simulation "
                    "(Python port of sim_2).")
    parser.add_argument("--verify", action="store_true",
                        help="enable provenance tracking + write gate")
    parser.add_argument("--boost", type=float, default=0.10, metavar="X",
                        help="per-write trust inflation (default 0.10)")
    parser.add_argument("--plant-overflow", action="store_true",
                        help="plant an unchecked fixed-size buffer write (IndexError)")
    parser.add_argument("--plant-hallucinated-api", action="store_true",
                        help="plant an import of a module that does not exist")
    args = parser.parse_args()

    try:
        return run(args.verify, args.boost, args.plant_overflow, args.plant_hallucinated_api)
    except IndexError:
        traceback.print_exc()
        return 134   # mirrors the C build aborting on the overflow


if __name__ == "__main__":
    sys.exit(main())