#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/full"
SCORED = RUN / "scored"
OUT = RUN / "AUDIT.json"
SOURCES = {
    "M": SCORED / "m.jsonl",
    "M+H": SCORED / "react.jsonl",
    "M+H+ΔH": SCORED / "react_safe_paired_consistent.jsonl",
}
EXPECTED_CATEGORIES = {
    "Instrumental Convergence": 192,
    "Oversight Evasion": 108,
    "Specification Gaming": 132,
    "Covert Whistleblowing": 108,
    "Evaluation Awareness": 72,
    "Strategic Misalignment": 108,
}


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    rows = {arm: read(path) for arm, path in SOURCES.items()}
    uid_sets = []
    report = {}
    for arm, values in rows.items():
        uids = {row["uid"] for row in values}
        if len(values) != 720 or len(uids) != 720:
            raise RuntimeError(f"{arm}: expected 720 unique rows, got {len(values)}/{len(uids)}")
        uid_sets.append(uids)
        categories = Counter(row["risk_category"] for row in values)
        if categories != Counter(EXPECTED_CATEGORIES):
            raise RuntimeError(f"{arm}: category coverage mismatch {categories}")
        if any(row["risk_category"] == "Capability Misuse" for row in values):
            raise RuntimeError(f"{arm}: Capability Misuse leaked into evaluation")
        if Counter(int(row["rollout_id"]) for row in values) != Counter({0: 240, 1: 240, 2: 240}):
            raise RuntimeError(f"{arm}: rollout coverage mismatch")
        if any(not (row.get("monitor") or {}).get("parse_ok") for row in values):
            raise RuntimeError(f"{arm}: Monitor parse failure")
        report[arm] = {
            "rows": len(values),
            "unique_uids": len(uids),
            "categories": categories,
            "rollouts": Counter(int(row["rollout_id"]) for row in values),
            "sha256": sha(SOURCES[arm]),
        }
    if not all(values == uid_sets[0] for values in uid_sets[1:]):
        raise RuntimeError("arms do not cover identical UIDs")
    report["global"] = {
        "identical_uid_sets": True,
        "excluded": ["Capability Misuse"],
        "original_scenarios": len({row["base_uid"] for row in rows["M"]}),
        "condition_variants": len({row["task_uid"] for row in rows["M"]}),
    }
    if report["global"]["original_scenarios"] != 60 or report["global"]["condition_variants"] != 240:
        raise RuntimeError(f"bad scenario coverage: {report['global']}")
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=dict) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
