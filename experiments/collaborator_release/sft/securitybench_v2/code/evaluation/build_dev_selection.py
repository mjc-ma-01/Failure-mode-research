#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "manifests" / "dev.jsonl"
OUTPUT = HERE / "manifests" / "dev_selection.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    rows = read_jsonl(SOURCE)
    selected = [
        row
        for row in rows
        if row["panel"] in {"W2_evidence_calibration", "H1_hidden_provenance"}
    ]
    groups: dict[tuple[str, int, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["panel"] != "W1_visible_conflict":
            continue
        key = (
            str(row["task"]["uid"]),
            int(row["variant"]["variant_index"]),
            str(row["condition"]),
            str(row["template"]),
        )
        groups[key].append(row)
    for key, candidates in sorted(groups.items()):
        candidates.sort(
            key=lambda row: hashlib.sha256(row["uid"].encode("utf-8")).hexdigest()
        )
        selected.append(candidates[0])
    selected.sort(key=lambda row: row["uid"])
    with OUTPUT.open("w", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    report = {
        "rows": len(selected),
        "panels": dict(Counter(row["panel"] for row in selected)),
        "conditions": dict(Counter(row["condition"] for row in selected)),
        "w1_strata": len(groups),
        "selection_rule": (
            "All W2 and H1 cells; one fixed SHA-256-selected W1 attack tool per "
            "task-variant x DPI/OPI x held-out template stratum."
        ),
        "test_data_used": False,
    }
    (HERE / "manifests" / "dev_selection.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
