from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GreenLogger:
    def __init__(self, log_path: str = "logs/green_metrics.jsonl"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log_run(self, payload: Dict[str, Any]) -> None:
        record = {
            "ts_utc": _utc_now_iso(),
            **payload,
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_recent(self, limit: int = 50) -> list[Dict[str, Any]]:
        """Returns the most recent logged green metrics runs."""
        if not os.path.exists(self.log_path):
            return []
        records = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            continue
        except Exception:
            return []
        return records[-limit:]