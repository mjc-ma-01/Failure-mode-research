#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ARMS = {"base", "sft", "base+harness"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing", type=Path, required=True)
    parser.add_argument("--sft", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = [
        row for row in read_jsonl(args.existing)
        if row.get("arm") in {"base", "base+harness"}
    ] + read_jsonl(args.sft)
    counts = Counter(row.get("arm") for row in rows)
    if counts != Counter({arm: 144 for arm in ARMS}):
        raise RuntimeError(f"bad arm counts: {dict(counts)}")
    keys = [(row["uid"], row["arm"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate (uid, arm) records")

    expected_cells = None
    for arm in sorted(ARMS):
        cells = {
            (row["task_uid"], int(row.get("rollout_id", 0)))
            for row in rows if row["arm"] == arm
        }
        if expected_cells is None:
            expected_cells = cells
        elif cells != expected_cells:
            raise RuntimeError(f"cell coverage mismatch for {arm}")
    if len(expected_cells or ()) != 144:
        raise RuntimeError("expected 144 paired cells")
    if any(row.get("risk_category") == "Capability Misuse" for row in rows):
        raise RuntimeError("Capability Misuse leaked into evaluation")
    invalid = [row for row in rows if not (row.get("monitor") or {}).get("parse_ok")]
    if invalid:
        raise RuntimeError(f"Monitor parse failures: {len(invalid)}")

    rows.sort(key=lambda row: (row["task_uid"], int(row["rollout_id"]), row["arm"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    )
    summary = {
        "status": "pass",
        "records": len(rows),
        "arms": dict(counts),
        "paired_cells": len(expected_cells or ()),
        "task_variants": len({row["task_uid"] for row in rows}),
        "base_scenarios": len({row["base_uid"] for row in rows}),
        "monitor_parse_failures": len(invalid),
        "capability_misuse_rows": 0,
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
