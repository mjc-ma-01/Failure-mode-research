#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_SOURCE = ROOT / "experiments/model_vs_harness_sft/autocontrol_v2/output/sft/train.jsonl"
DEFAULT_OUTPUT = HERE / "data/train.jsonl"
EXCLUDED_CATEGORY = "Capability Misuse"
EXPECTED_CATEGORIES = {
    "Instrumental Convergence": 36,
    "Oversight Evasion": 20,
    "Specification Gaming": 28,
    "Covert Whistleblowing": 20,
    "Evaluation Awareness": 16,
    "Strategic Misalignment": 20,
}
EXPECTED_VARIANTS = {"S0T0", "S0T1", "S1T0", "S1T1"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def assistant_actions(row: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for message in row["messages"]:
        if message["role"] == "assistant":
            actions.append(json.loads(message["content"]))
    return actions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source_rows = read_jsonl(args.source)
    rows = [
        row
        for row in source_rows
        if row.get("panel") == "W1_visible_policy_choice"
        and row.get("condition") == "reference_complete"
        and row.get("risk_category") != EXCLUDED_CATEGORY
    ]
    errors = []
    for row in rows:
        actions = assistant_actions(row)
        if not actions or actions[-1].get("tool") != "finish":
            errors.append(f"{row['id']}: missing final finish")
            continue
        if (actions[-1].get("arguments") or {}).get("claim") != "completed":
            errors.append(f"{row['id']}: final claim is not completed")
        if float(row.get("sampling_weight", 0.0)) != 1.0:
            errors.append(f"{row['id']}: sampling_weight is not 1")
        rendered = json.dumps(row, ensure_ascii=False).lower()
        for forbidden in (
            "tool_denied",
            "reference_partial",
            "hard_negative_incomplete",
            "w2_visible_state_calibration",
        ):
            if forbidden in rendered:
                errors.append(f"{row['id']}: forbidden W2 marker {forbidden}")
    if errors:
        raise RuntimeError("\n".join(errors))

    by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_base[row["base_uid"]].append(row)
    bad_bases = {
        base_uid: sorted(row["variant"] for row in values)
        for base_uid, values in by_base.items()
        if len(values) != 4 or {row["variant"] for row in values} != EXPECTED_VARIANTS
    }
    if bad_bases:
        raise RuntimeError(f"incomplete S/T groups: {bad_bases}")

    categories = Counter(row["risk_category"] for row in rows)
    variants = Counter(row["variant"] for row in rows)
    if len(rows) != 140 or len(by_base) != 35:
        raise RuntimeError(f"expected 140 rows / 35 bases, got {len(rows)} / {len(by_base)}")
    if dict(categories) != EXPECTED_CATEGORIES:
        raise RuntimeError(f"unexpected category counts: {dict(categories)}")
    if variants != Counter({variant: 35 for variant in EXPECTED_VARIANTS}):
        raise RuntimeError(f"unexpected variant counts: {dict(variants)}")

    rows.sort(key=lambda row: row["id"])
    write_jsonl(args.output, rows)
    manifest = {
        "protocol": "autocontrol_w1_only_six_category_v1",
        "status": "pass",
        "source": str(args.source.resolve()),
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "output": str(args.output.resolve()),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "rows": len(rows),
        "independent_base_scenarios": len(by_base),
        "task_variants": len({row["task_uid"] for row in rows}),
        "panel": "W1_visible_policy_choice",
        "condition": "reference_complete",
        "final_claim": "completed",
        "categories": dict(categories),
        "variants": dict(variants),
        "excluded_categories": [EXCLUDED_CATEGORY],
        "excluded_panels": ["W2_visible_state_calibration", "W1_benign_control"],
        "all_sampling_weights": 1.0,
    }
    manifest_path = args.output.parent / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
