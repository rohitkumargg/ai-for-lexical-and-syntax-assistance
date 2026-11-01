# tools/dataset_uniqueness_audit.py
import argparse
import json
import hashlib
from collections import Counter
from pathlib import Path


def _stable_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="replace")).hexdigest()


def _norm_ws(s: str) -> str:
    # whitespace-normalized view (helps detect near-identical repeats)
    return " ".join(s.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input jsonl (patch_synth.jsonl or split file)")
    ap.add_argument("--n", type=int, default=0, help="Max examples to read (0=all)")
    ap.add_argument("--src_key", default="src")
    ap.add_argument("--tgt_key", default="tgt")
    ap.add_argument("--show_top", type=int, default=10, help="Show top-k most repeated items")
    args = ap.parse_args()

    path = Path(args.inp)
    total = 0

    src_hashes = []
    src_norm_hashes = []
    tgt_hashes = []
    pair_hashes = []

    bad_json = 0
    missing = 0

    for line in path.open("r", encoding="utf-8"):
        if args.n and total >= args.n:
            break
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            bad_json += 1
            continue

        if args.src_key not in row or args.tgt_key not in row:
            missing += 1
            continue

        src = row[args.src_key]
        tgt = row[args.tgt_key]
        if not isinstance(src, str) or not isinstance(tgt, str):
            missing += 1
            continue

        total += 1

        sh = _stable_hash(src)
        snh = _stable_hash(_norm_ws(src))
        th = _stable_hash(tgt)
        ph = _stable_hash(src + "\n<<<PAIR>>>\n" + tgt)

        src_hashes.append(sh)
        src_norm_hashes.append(snh)
        tgt_hashes.append(th)
        pair_hashes.append(ph)

    def summarize(name, hashes):
        c = Counter(hashes)
        uniq = len(c)
        dup = total - uniq
        top = c.most_common(args.show_top)
        return uniq, dup, top

    print("\n=== DATASET UNIQUENESS AUDIT ===")
    print(f"File: {path}")
    print(f"Read: {total}")
    print(f"Bad JSON: {bad_json}")
    print(f"Missing fields/types: {missing}")

    src_uniq, src_dup, src_top = summarize("src", src_hashes)
    sn_uniq, sn_dup, sn_top = summarize("src_norm", src_norm_hashes)
    tgt_uniq, tgt_dup, tgt_top = summarize("tgt", tgt_hashes)
    pair_uniq, pair_dup, pair_top = summarize("pair", pair_hashes)

    print("\n[Uniqueness]")
    print(f"src unique:       {src_uniq}   duplicates: {src_dup}")
    print(f"src_norm unique:  {sn_uniq}   duplicates: {sn_dup}   (whitespace-normalized)")
    print(f"tgt unique:       {tgt_uniq}   duplicates: {tgt_dup}")
    print(f"(src,tgt) unique: {pair_uniq}   duplicates: {pair_dup}   [OK] most important")

    def print_top(label, top):
        print(f"\nTop repeated {label} hashes (count only):")
        for h, k in top:
            print(f"  {k:6d}  {h}")

    print_top("src", src_top)
    print_top("src_norm", sn_top)
    print_top("tgt", tgt_top)
    print_top("pair", pair_top)

    # Simple decision heuristics (not absolute rules)
    print("\n[Heuristic red flags]")
    if pair_uniq < 20000 and total > 20000:
        print(f"[WARN] (src,tgt) unique is {pair_uniq}, which is low. Investigate generator diversity.")
    else:
        print("[OK] (src,tgt) uniqueness looks healthy.")

    if src_uniq < 5000 and total > 5000:
        print(f"[WARN] src unique is {src_uniq}. If splits leak or contexts collapse, model may overfit.")
    else:
        print("[OK] src uniqueness looks reasonable.")

    if sn_uniq < src_uniq * 0.9:
        print("[WARN] Many src differ only by whitespace; ensure corruption isn't whitespace-only.")
    else:
        print("[OK] Not dominated by whitespace-only changes.")


if __name__ == "__main__":
    main()