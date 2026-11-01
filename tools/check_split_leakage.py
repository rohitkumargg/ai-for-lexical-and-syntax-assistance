# tools/check_split_leakage.py
import argparse
import json
import hashlib
from pathlib import Path


def h(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="replace")).hexdigest()


def load_src_hashes(p: Path, src_key="src"):
    hs = set()
    total = 0
    for line in p.open("r", encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        src = row.get(src_key)
        if isinstance(src, str):
            hs.add(h(src))
            total += 1
    return hs, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--val", required=True)
    ap.add_argument("--src_key", default="src")
    args = ap.parse_args()

    train_p = Path(args.train)
    val_p = Path(args.val)

    train_h, train_total = load_src_hashes(train_p, args.src_key)
    val_h, val_total = load_src_hashes(val_p, args.src_key)

    inter = train_h.intersection(val_h)

    print("=== SPLIT LEAKAGE CHECK (src overlap) ===")
    print(f"Train file: {train_p}  (examples: {train_total}, unique src: {len(train_h)})")
    print(f"Val file:   {val_p}    (examples: {val_total}, unique src: {len(val_h)})")
    print(f"Overlap src hashes: {len(inter)}")

    if len(inter) > 0:
        print("[FAIL] Leakage detected. You should re-split ensuring src-disjoint splits.")
    else:
        print("[OK] No src leakage detected.")


if __name__ == "__main__":
    main()