#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
SHARDS = HERE / "runs/full/generation_shards"
OUTPUT = HERE / "runs/full/react_trajectories.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-react-only",
        action="store_true",
        help="materialize the completed 720-row M+H arm early so Monitor can overlap M+H+ΔH generation",
    )
    args = parser.parse_args()
    rows = []
    for shard in range(6):
        path = SHARDS / f"shard_{shard}.jsonl"
        if not path.exists():
            raise RuntimeError(f"missing {path}")
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    if args.base_react_only:
        rows = [row for row in rows if row["arm"] == "base+react"]
        keys = [(row["uid"], row["arm"]) for row in rows]
        if len(rows) != 720 or len(set(keys)) != 720:
            raise RuntimeError(f"expected 720 completed base+react rows, got {len(rows)}/{len(set(keys))}")
        rows.sort(key=lambda row: (row["arm"], row["task_uid"], int(row["rollout_id"])))
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        summary = {
            "records": len(rows),
            "arms": Counter(row["arm"] for row in rows),
            "unique_keys": len(set(keys)),
            "early_base_react_only": True,
            "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        }
        (OUTPUT.parent / "generation.base_react_early.summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=dict) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))
        return
    keys = [(row["uid"], row["arm"]) for row in rows]
    arms = Counter(row["arm"] for row in rows)
    if len(rows) != 1440 or len(set(keys)) != 1440:
        raise RuntimeError(f"expected 1440 unique rows, got {len(rows)}/{len(set(keys))}")
    expected = Counter({"base+react": 720, "base+react+safeharness": 720})
    if arms != expected:
        raise RuntimeError(f"bad arms: {arms}")
    unexpected = Counter(
        str(row.get("error"))
        for row in rows
        if row.get("error") and row.get("error") != "three consecutive action parse failures"
    )
    if unexpected:
        raise RuntimeError(f"unexpected generation errors: {unexpected}")
    rows.sort(key=lambda row: (row["arm"], row["task_uid"], int(row["rollout_id"])))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    summary = {
        "records": len(rows),
        "arms": arms,
        "unique_keys": len(set(keys)),
        "terminal_react_format_failures": Counter(
            row["arm"] for row in rows if row.get("error") == "three consecutive action parse failures"
        ),
        "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
    }
    (OUTPUT.parent / "generation.summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=dict) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
