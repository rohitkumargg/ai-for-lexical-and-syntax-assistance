import json
import re
import hashlib
from pathlib import Path
from collections import Counter

import sys

INP = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/splits/train.jsonl")
SRC_KEY = "input"

# remove identifiers and numbers to get a "skeleton"
ident = re.compile(r"\b[_A-Za-z][_A-Za-z0-9]*\b")
num   = re.compile(r"\b\d+\b")

def skeleton(code: str) -> str:
    code = ident.sub("ID", code)
    code = num.sub("NUM", code)
    code = re.sub(r"\s+", " ", code).strip()
    return code

def h(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()

def main():
    c = Counter()
    n = 0
    with INP.open("r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            s = skeleton(r.get(SRC_KEY, ""))
            c[h(s)] += 1
            n += 1

    print("=== TRAIN SKELETON DIVERSITY ===")
    print("rows:", n)
    print("unique skeletons:", len(c))

    top = c.most_common(15)
    print("\nTop repeated skeleton hashes (count):")
    for hh, cnt in top:
        print(f"{cnt:6d}  {hh}")

    frac_top10 = sum(cnt for _, cnt in c.most_common(10)) / max(1, n)
    print(f"\nTop-10 skeleton coverage: {frac_top10*100:.2f}%")

    if frac_top10 > 25:
        print("⚠️  Many examples share very similar program structure (template-heavy).")
    else:
        print("✅ Structure diversity looks decent.")

if __name__ == "__main__":
    main()