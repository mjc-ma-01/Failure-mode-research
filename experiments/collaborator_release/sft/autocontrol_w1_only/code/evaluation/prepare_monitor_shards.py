#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/t1_three_rollouts"
TRAJECTORIES = RUN / "sft.jsonl"
EXISTING = RUN / "scored/sft.jsonl"
SHARDS = RUN / "monitor_shards"


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    trajectories = read(TRAJECTORIES)
    existing = read(EXISTING) if EXISTING.exists() else []
    valid_keys = {
        (row["uid"], row["arm"])
        for row in existing
        if (row.get("monitor") or {}).get("parse_ok")
    }
    if len(valid_keys) != len(existing):
        raise RuntimeError("existing Monitor rows are invalid or duplicated")
    pending = [
        row for row in trajectories
        if (row["uid"], row["arm"]) not in valid_keys
    ]
    if len(trajectories) != 144 or len(existing) != 8 or len(pending) != 136:
        raise RuntimeError(
            f"expected 144 total / 8 existing / 136 pending, got "
            f"{len(trajectories)} / {len(existing)} / {len(pending)}"
        )
    SHARDS.mkdir(parents=True, exist_ok=True)
    summary = {"total": len(trajectories), "existing": len(existing), "pending": len(pending), "shards": {}}
    for index in range(3):
        rows = [row for position, row in enumerate(pending) if position % 3 == index]
        path = SHARDS / f"shard_{index}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
        summary["shards"][str(index)] = {
            "rows": len(rows),
            "categories": dict(Counter(row["risk_category"] for row in rows)),
        }
    (SHARDS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
