#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


TYPE_NAMES = {
    1: "Broken source / read failure",
    2: "Readable but insufficient source",
    3: "Official-source failure + local decoy",
    4: "Broken download + analysis",
    5: "Missing/download failure + saved report",
}


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def wilson(successes, total, z=1.959963984540054):
    if not total:
        return [None, None]
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total + z * z / (4 * total * total)
        )
        / denominator
    )
    return [center - margin, center + margin]


def exact_two_sided_binomial(smaller, total):
    if not total:
        return 1.0
    probability = sum(
        math.comb(total, index) * (0.5**total)
        for index in range(smaller + 1)
    )
    return min(1.0, 2 * probability)


def rate(rows, key):
    valid = [row for row in rows if isinstance(row.get(key), bool)]
    count = sum(row[key] for row in valid)
    return {
        "n": len(valid),
        "count": count,
        "rate": count / len(valid) if valid else None,
        "wilson_95": wilson(count, len(valid)),
    }


def compact_case(base, sft):
    return {
        "uid": base["uid"],
        "task_type": base["task_type"],
        "type_name": TYPE_NAMES[base["task_type"]],
        "topic": base.get("topic"),
        "condition": base["condition"],
        "user_prompt": base["user_prompt"],
        "base": {
            "risk": base.get("risk"),
            "evidence_pass": base.get("evidence_pass"),
            "utility_pass": base.get("utility_pass"),
            "over_refusal": base.get("utility_judge", {}).get("over_refusal"),
            "events": base["events"],
            "final": base["final"],
            "official_reason": base.get("official", {}).get("detail"),
            "evidence_reason": base.get("evidence_judge", {}).get("reason"),
            "utility_reason": base.get("utility_judge", {}).get("reason"),
        },
        "sft": {
            "risk": sft.get("risk"),
            "evidence_pass": sft.get("evidence_pass"),
            "utility_pass": sft.get("utility_pass"),
            "over_refusal": sft.get("utility_judge", {}).get("over_refusal"),
            "events": sft["events"],
            "final": sft["final"],
            "official_reason": sft.get("official", {}).get("detail"),
            "evidence_reason": sft.get("evidence_judge", {}).get("reason"),
            "utility_reason": sft.get("utility_judge", {}).get("reason"),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    rows = [row for row in read_jsonl(args.records) if not row.get("judge_error")]
    indexed = {
        (row["uid"], row["condition"], row["arm"]): row for row in rows
    }
    pairs = []
    for uid, condition in sorted({(row["uid"], row["condition"]) for row in rows}):
        base = indexed.get((uid, condition, "base"))
        sft = indexed.get((uid, condition, "sft"))
        if base and sft:
            pairs.append((base, sft))

    report = {
        "overall": {},
        "by_task_type": {},
        "transitions": {},
        "paired_tests": {},
    }
    for condition in ("failure", "success", "authorized_fallback"):
        condition_pairs = [pair for pair in pairs if pair[0]["condition"] == condition]
        report["overall"][condition] = {}
        for arm_index, arm in enumerate(("base", "sft")):
            arm_rows = [pair[arm_index] for pair in condition_pairs]
            metrics = {
                "evidence_pass": rate(arm_rows, "evidence_pass"),
                "utility_pass": rate(arm_rows, "utility_pass"),
                "composite_pass": rate(arm_rows, "composite_pass"),
                "over_refusal": rate(
                    [
                        {
                            "over_refusal": bool(
                                row.get("utility_judge", {}).get("over_refusal")
                            )
                        }
                        for row in arm_rows
                    ],
                    "over_refusal",
                ),
            }
            if condition == "failure":
                metrics["risky"] = rate(arm_rows, "risk")
            report["overall"][condition][arm] = metrics

    failure_pairs = [pair for pair in pairs if pair[0]["condition"] == "failure"]
    transitions = Counter(
        f"{'risky' if base['risk'] else 'safe'}"
        f"->{'risky' if sft['risk'] else 'safe'}"
        for base, sft in failure_pairs
    )
    down = transitions["risky->safe"]
    up = transitions["safe->risky"]
    report["transitions"]["failure_risk"] = dict(transitions)
    report["transitions"]["mcnemar_exact_p"] = exact_two_sided_binomial(
        min(down, up), down + up
    )
    for condition in ("failure", "success", "authorized_fallback"):
        condition_pairs = [
            pair for pair in pairs if pair[0]["condition"] == condition
        ]
        report["paired_tests"][condition] = {}
        metric_names = ["evidence_pass", "utility_pass", "composite_pass"]
        if condition == "failure":
            metric_names.append("risk")
        for metric_name in metric_names:
            improve = sum(
                not bool(base[metric_name]) and bool(sft[metric_name])
                for base, sft in condition_pairs
            )
            regress = sum(
                bool(base[metric_name]) and not bool(sft[metric_name])
                for base, sft in condition_pairs
            )
            report["paired_tests"][condition][metric_name] = {
                "base_false_to_sft_true": improve,
                "base_true_to_sft_false": regress,
                "discordant_n": improve + regress,
                "exact_two_sided_p": exact_two_sided_binomial(
                    min(improve, regress),
                    improve + regress,
                ),
            }

    for task_type in range(1, 6):
        report["by_task_type"][str(task_type)] = {
            "name": TYPE_NAMES[task_type],
        }
        for condition in ("failure", "success", "authorized_fallback"):
            selected = [
                pair
                for pair in pairs
                if pair[0]["task_type"] == task_type
                and pair[0]["condition"] == condition
            ]
            report["by_task_type"][str(task_type)][condition] = {}
            for arm_index, arm in enumerate(("base", "sft")):
                arm_rows = [pair[arm_index] for pair in selected]
                cell = {
                    "utility_pass": rate(arm_rows, "utility_pass"),
                    "evidence_pass": rate(arm_rows, "evidence_pass"),
                    "composite_pass": rate(arm_rows, "composite_pass"),
                }
                if condition == "failure":
                    cell["risky"] = rate(arm_rows, "risk")
                report["by_task_type"][str(task_type)][condition][arm] = cell

    case_groups = defaultdict(list)
    for base, sft in pairs:
        if base["condition"] == "failure":
            label = (
                f"{'risky' if base['risk'] else 'safe'}"
                f"->{'risky' if sft['risk'] else 'safe'}"
            )
            case_groups["failure_" + label].append(compact_case(base, sft))
        if base["condition"] == "success":
            label = (
                f"{'pass' if base['utility_pass'] else 'fail'}"
                f"->{'pass' if sft['utility_pass'] else 'fail'}"
            )
            case_groups["success_utility_" + label].append(compact_case(base, sft))
        if base["condition"] == "authorized_fallback":
            label = (
                f"{'pass' if base['composite_pass'] else 'fail'}"
                f"->{'pass' if sft['composite_pass'] else 'fail'}"
            )
            case_groups["fallback_composite_" + label].append(
                compact_case(base, sft)
            )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    (output_dir / "cases.json").write_text(
        json.dumps(dict(case_groups), ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
