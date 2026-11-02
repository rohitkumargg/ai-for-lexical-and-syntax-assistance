import json

with open("reports/audit/model_execution_evidence.json", "r") as f:
    ev = json.load(f)

print(f"Total test files examined: {len(ev)}")
print(f"Ollama requests before run: {ev[0].get('ollama_before')} | after run: {ev[0].get('ollama_after')}\n")

for item in ev:
    f = item["file"]
    st = item["status"]
    tot_ms = item["total_ms"]
    print(f"=== File: {f} (Status: {st}, Elapsed: {tot_ms} ms) ===")
    for tier_name in ["deterministic", "codet5", "qwen"]:
        t = item["tiers"][tier_name]
        c = t["called"]
        v = t["verdict"]
        ms = t["dur_ms"]
        skip = t.get("skip_line", "")
        print(f"  [{tier_name.upper():<13}] Called: {c:<3} | Dur: {ms:8.2f} ms | Verdict: {v}")
        if c == "NO" and skip:
            print(f"    -> Skipped at line: {skip}")
        if t.get("window_text"):
            w_preview = t["window_text"].strip().replace("\n", " ")[:70]
            print(f"    -> Window: {w_preview}...")
        if t.get("validator_verdict"):
            print(f"    -> Validator verdict: {t['validator_verdict']} | reason: {t.get('validator_reason', '')}")
    print()

