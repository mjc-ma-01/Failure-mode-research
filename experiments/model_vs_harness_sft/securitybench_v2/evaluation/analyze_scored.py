#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Callable


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def cluster_key(row: dict[str, Any]) -> str:
    return f"{row['agent']}:task{row['task_index']}:v{row['variant_index']}"


def rate(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [float(bool(row[field])) for row in rows if row.get(field) is not None]
    return mean(values) if values else None


def cluster_bootstrap_difference(
    rows: list[dict[str, Any]],
    panel: str,
    field: str,
    first_arm: str,
    second_arm: str,
    *,
    condition: str | None = None,
    iterations: int = 10000,
    seed: int = 20261110,
) -> dict[str, Any]:
    panel_rows = [
        row
        for row in rows
        if row["panel"] == panel
        and (condition is None or row["condition"] == condition)
    ]
    clusters = sorted({cluster_key(row) for row in panel_rows})
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in panel_rows:
        grouped[(row["arm"], cluster_key(row))].append(row)

    def arm_rate(arm: str, sampled: list[str]) -> float:
        values = []
        for key in sampled:
            cluster_rows = grouped.get((arm, key), [])
            cluster_values = [
                float(bool(row[field]))
                for row in cluster_rows
                if row.get(field) is not None
            ]
            if cluster_values:
                values.append(mean(cluster_values))
        return mean(values)

    observed_first = arm_rate(first_arm, clusters)
    observed_second = arm_rate(second_arm, clusters)
    generator = random.Random(seed)
    differences = []
    for _ in range(iterations):
        sampled = [generator.choice(clusters) for _ in clusters]
        differences.append(
            arm_rate(second_arm, sampled) - arm_rate(first_arm, sampled)
        )
    differences.sort()
    return {
        "clusters": len(clusters),
        "first_arm": first_arm,
        "second_arm": second_arm,
        "first_rate": observed_first,
        "second_rate": observed_second,
        "difference": observed_second - observed_first,
        "condition": condition,
        "cluster_bootstrap95": [
            differences[int(0.025 * iterations)],
            differences[int(0.975 * iterations) - 1],
        ],
        "iterations": iterations,
        "seed": seed,
    }


def cell(
    rows: list[dict[str, Any]],
    arm: str,
    panel: str,
    condition: str | None = None,
) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if row["arm"] == arm
        and row["panel"] == panel
        and (condition is None or row["condition"] == condition)
    ]
    return {
        "n": len(selected),
        "clusters": len({cluster_key(row) for row in selected}),
        "attack_side_effect_rate": rate(selected, "attack_side_effect"),
        "substitution_side_effect_rate": rate(
            selected, "substitution_side_effect"
        ),
        "response_utility_rate": rate(selected, "response_utility_pass"),
        "task_success_rate": rate(selected, "task_success"),
        "calibration_accuracy": rate(selected, "calibration_correct"),
        "unsupported_completion_rate": rate(
            selected, "unsupported_completion"
        ),
        "over_refusal_rate": rate(selected, "over_refusal"),
        "artifact_committed_rate": rate(selected, "artifact_committed"),
        "fallback_rate": rate(selected, "fallbacks"),
        "joint_safe_task_success_rate": rate(
            selected, "joint_safe_task_success"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judged", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = read_jsonl(args.judged)
    if any(row.get("judge_error") for row in rows):
        raise SystemExit("judge errors remain")
    result: dict[str, Any] = {
        "records": len(rows),
        "arms": sorted({row["arm"] for row in rows}),
        "panels": {},
    }
    for panel in (
        "W1_visible_conflict",
        "W2_evidence_calibration",
        "H1_hidden_provenance",
    ):
        result["panels"][panel] = {}
        conditions = sorted(
            {row["condition"] for row in rows if row["panel"] == panel}
        )
        for arm in result["arms"]:
            arm_rows = [
                row
                for row in rows
                if row["arm"] == arm and row["panel"] == panel
            ]
            if not arm_rows:
                continue
            result["panels"][panel][arm] = {
                "overall": cell(rows, arm, panel),
                "conditions": {
                    condition: cell(rows, arm, panel, condition)
                    for condition in conditions
                },
            }
    result["cluster_bootstrap"] = {
        "W1_attack_side_effect_base_to_sft": cluster_bootstrap_difference(
            rows,
            "W1_visible_conflict",
            "attack_side_effect",
            "base",
            "sft",
        ),
        "W1_utility_base_to_sft": cluster_bootstrap_difference(
            rows,
            "W1_visible_conflict",
            "response_utility_pass",
            "base",
            "sft",
        ),
        "W2_calibration_base_to_sft": cluster_bootstrap_difference(
            rows,
            "W2_evidence_calibration",
            "response_utility_pass",
            "base",
            "sft",
        ),
        "H1_substituted_side_effect_base_harness": (
            cluster_bootstrap_difference(
                rows,
                "H1_hidden_provenance",
                "substitution_side_effect",
                "base",
                "base+harness",
                condition="substituted",
            )
        ),
        "H1_substituted_utility_base_harness": cluster_bootstrap_difference(
            rows,
            "H1_hidden_provenance",
            "response_utility_pass",
            "base",
            "base+harness",
            condition="substituted",
        ),
        "H1_substituted_side_effect_sft_harness": (
            cluster_bootstrap_difference(
                rows,
                "H1_hidden_provenance",
                "substitution_side_effect",
                "sft",
                "sft+harness",
                condition="substituted",
            )
        ),
        "H1_substituted_utility_sft_harness": cluster_bootstrap_difference(
            rows,
            "H1_hidden_provenance",
            "response_utility_pass",
            "sft",
            "sft+harness",
            condition="substituted",
        ),
        "H1_trusted_utility_sft_harness": cluster_bootstrap_difference(
            rows,
            "H1_hidden_provenance",
            "response_utility_pass",
            "sft",
            "sft+harness",
            condition="trusted",
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
