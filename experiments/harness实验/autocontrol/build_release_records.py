#!/usr/bin/env python3
"""Assemble the canonical three-arm AutoControl trajectory+Monitor record."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "full" / "scored"
SOURCES = {
    "M": RUN / "m.jsonl",
    "M+H": RUN / "react.jsonl",
    "M+H+ΔH": RUN / "react_safe_paired_consistent.jsonl",
}
OUTPUT = HERE / "results" / "three_arm_scored.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    combined: list[dict[str, Any]] = []
    uid_sets: dict[str, set[str]] = {}
    for formal_arm, path in SOURCES.items():
        rows = read_jsonl(path)
        if len(rows) != 720:
            raise RuntimeError(f"{formal_arm}: expected 720 rows, got {len(rows)}")
        uids = {str(row["uid"]) for row in rows}
        if len(uids) != 720:
            raise RuntimeError(f"{formal_arm}: duplicate uid")
        uid_sets[formal_arm] = uids
        for row in rows:
            monitor = row.get("monitor") or {}
            if not isinstance(monitor.get("is_risky"), bool):
                raise RuntimeError(f"{formal_arm}: missing risk verdict for {row['uid']}")
            if not isinstance(monitor.get("task_success"), bool):
                raise RuntimeError(f"{formal_arm}: missing utility verdict for {row['uid']}")
            combined.append(
                {
                    **row,
                    "formal_arm": formal_arm,
                    "release_source": str(path.relative_to(HERE.parents[2])),
                }
            )
    if len({frozenset(value) for value in uid_sets.values()}) != 1:
        raise RuntimeError("three arms do not cover identical cells")
    combined.sort(key=lambda row: (row["formal_arm"], row["uid"]))
    if len({(row["uid"], row["formal_arm"]) for row in combined}) != 2160:
        raise RuntimeError("duplicate release (uid, formal_arm)")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in combined),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(combined), "per_arm": 720, "output": str(OUTPUT)}))


if __name__ == "__main__":
    main()
