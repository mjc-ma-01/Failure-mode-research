#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/full"
OUT = RUN / "monitor_inputs"
SOURCES = {
    "m": (RUN / "m_trajectories.jsonl", "base"),
    "react": (RUN / "react_trajectories.jsonl", "base+react"),
    "react_safe": (RUN / "react_trajectories.jsonl", "base+react+safeharness"),
}


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--slugs",
        default=",".join(SOURCES),
        help="comma-separated subset of m,react,react_safe",
    )
    args = parser.parse_args()
    selected_slugs = [value.strip() for value in args.slugs.split(",") if value.strip()]
    unknown = set(selected_slugs) - set(SOURCES)
    if unknown:
        raise RuntimeError(f"unknown slugs: {sorted(unknown)}")
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    for slug in selected_slugs:
        path, arm = SOURCES[slug]
        rows = [row for row in read(path) if row["arm"] == arm]
        keys = {(row["uid"], row["arm"]) for row in rows}
        if len(rows) != 720 or len(keys) != 720:
            raise RuntimeError(f"{slug}: expected 720 unique rows, got {len(rows)}/{len(keys)}")
        rollouts = Counter(int(row["rollout_id"]) for row in rows)
        if rollouts != Counter({0: 240, 1: 240, 2: 240}):
            raise RuntimeError(f"{slug}: bad rollouts {rollouts}")
        rows.sort(key=lambda row: row["uid"])
        for shard in range(3):
            selected = [row for index, row in enumerate(rows) if index % 3 == shard]
            if len(selected) != 240:
                raise RuntimeError(f"{slug} shard {shard}: {len(selected)}")
            (OUT / f"{slug}_s{shard}.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected),
                encoding="utf-8",
            )
        summary[slug] = {"arm": arm, "rows": len(rows), "rollouts": rollouts}
    summary_name = "summary.json" if set(selected_slugs) == set(SOURCES) else f"summary_{'_'.join(selected_slugs)}.json"
    (OUT / summary_name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=dict) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
