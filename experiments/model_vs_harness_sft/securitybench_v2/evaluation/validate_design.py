#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from run_eval import Episode


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def visible_initial_state(cell: dict[str, Any], harness: bool) -> str:
    episode = Episode(cell, "validation", harness)
    return json.dumps(
        {"messages": episode.messages, "schemas": episode.schemas},
        ensure_ascii=False,
        sort_keys=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    rows = read_jsonl(args.manifest)
    h1: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["panel"] == "H1_hidden_provenance":
            h1.setdefault(row["twin_id"], []).append(row)
    failures = []
    for twin_id, pair in h1.items():
        if len(pair) != 2:
            failures.append(f"{twin_id}:count={len(pair)}")
            continue
        for harness in (False, True):
            states = {visible_initial_state(row, harness) for row in pair}
            if len(states) != 1:
                failures.append(f"{twin_id}:visible_input_diff:harness={harness}")
    w1_harness_oracle = [
        row["uid"]
        for row in rows
        if row["panel"] == "W1_visible_conflict"
        and Episode(row, "validation", True).check_provenance(
            str(row["attack"]["Attacker Tool"])
        )
    ]
    report: dict[str, Any] = {
        "manifest": str(args.manifest),
        "rows": len(rows),
        "h1_twins": len(h1),
        "h1_visible_inputs_identical": not failures,
        "w1_attacker_tools_treated_as_registered": len(w1_harness_oracle),
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures or w1_harness_oracle:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
