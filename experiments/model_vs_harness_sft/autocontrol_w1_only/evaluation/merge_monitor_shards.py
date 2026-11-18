#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/t1_three_rollouts"


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    paths = [RUN / "scored/sft.jsonl"] + [
        RUN / f"monitor_shards/scored_{index}.jsonl" for index in range(3)
    ]
    rows = [row for path in paths for row in read(path)]
    keys = [(row["uid"], row["arm"]) for row in rows]
    if len(rows) != 144 or len(set(keys)) != 144:
        raise RuntimeError(f"expected 144 unique rows, got {len(rows)} / {len(set(keys))}")
    invalid = [row for row in rows if not (row.get("monitor") or {}).get("parse_ok")]
    if invalid:
        raise RuntimeError(f"Monitor parse failures: {len(invalid)}")
    rows.sort(key=lambda row: (row["task_uid"], row["rollout_id"]))
    output = RUN / "scored/sft_merged.jsonl"
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    summary = {
        "status": "pass",
        "records": len(rows),
        "unique_keys": len(set(keys)),
        "parse_failures": 0,
        "arms": dict(Counter(row["arm"] for row in rows)),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    (RUN / "scored/merged_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
