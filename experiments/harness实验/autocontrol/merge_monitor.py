#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/full"
SHARDS = RUN / "scored/shards"
OUT = RUN / "scored"
ARMS = {
    "m": "base",
    "react": "base+react",
    "react_safe": "base+react+safeharness",
}


def main() -> None:
    summary = {}
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, arm in ARMS.items():
        rows = []
        for shard in range(3):
            path = SHARDS / f"{slug}_s{shard}.jsonl"
            if not path.exists():
                raise RuntimeError(f"missing {path}")
            rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
        keys = {(row["uid"], row["arm"]) for row in rows}
        if len(rows) != 720 or len(keys) != 720 or any(row["arm"] != arm for row in rows):
            raise RuntimeError(f"{slug}: invalid rows {len(rows)}/{len(keys)}")
        failures = [row["uid"] for row in rows if not (row.get("monitor") or {}).get("parse_ok")]
        if failures:
            raise RuntimeError(f"{slug}: Monitor parse failures {failures[:20]}")
        rows.sort(key=lambda row: row["uid"])
        output = OUT / f"{slug}.jsonl"
        output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        summary[slug] = {
            "arm": arm,
            "rows": len(rows),
            "risky": sum(bool(row["monitor"]["is_risky"]) for row in rows),
            "task_success": sum(bool(row["monitor"]["task_success"]) for row in rows),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        }
    (OUT / "merge.summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
