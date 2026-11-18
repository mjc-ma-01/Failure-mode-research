#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def event_trace(row: dict[str, Any]) -> str:
    parts = []
    for event in row["events"]:
        status = event["result"].get("status", "?")
        suffix = ""
        if event["result"].get("receipt"):
            suffix = f":{event['result']['receipt']}"
        parts.append(f"{event['tool']}[{status}{suffix}]")
    return " -> ".join(parts) if parts else "(no tool call)"


def user_prompt(row: dict[str, Any]) -> str:
    for message in row["messages"]:
        if message["role"] == "user":
            return str(message.get("content") or "")
    return ""


def render_row(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"- Arm: `{row['arm']}`",
            f"- Tool trace: `{event_trace(row)}`",
            (
                "- Event truth: "
                f"attack_side_effect={row['attack_side_effect']}, "
                f"substitution_side_effect={row['substitution_side_effect']}, "
                f"artifact_committed={row['artifact_committed']}, "
                f"fallbacks={row['fallbacks']}"
            ),
            (
                "- Outcome: "
                f"utility={row['response_utility_pass']}, "
                f"task_success={row['task_success']}, "
                f"unsupported_completion={row['unsupported_completion']}, "
                f"over_refusal={row['over_refusal']}"
            ),
            f"- Final: {json.dumps(row['final'], ensure_ascii=False)}",
            f"- Judge: {row['semantic_judge']['reason']}",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judged", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = read_jsonl(args.judged)
    index = {(row["uid"], row["arm"]): row for row in rows}
    sections = ["# Frozen Test Trajectory Cases", ""]

    w1_candidates = [
        row
        for row in rows
        if row["arm"] == "base"
        and row["panel"] == "W1_visible_conflict"
        and row["attack_side_effect"]
        and (row["uid"], "sft") in index
        and not index[(row["uid"], "sft")]["attack_side_effect"]
        and index[(row["uid"], "sft")]["response_utility_pass"]
    ]
    sections.extend(["## W1: visible conflict fixed by weights", ""])
    for base in w1_candidates[:4]:
        sft = index[(base["uid"], "sft")]
        sections.extend(
            [
                f"### `{base['uid']}`",
                "",
                f"User-visible task/injection: {json.dumps(user_prompt(base), ensure_ascii=False)}",
                "",
                render_row(base),
                "",
                render_row(sft),
                "",
            ]
        )

    sections.extend(["## W1: residual weights failures", ""])
    residual_attack = [
        row
        for row in rows
        if row["arm"] == "sft"
        and row["panel"] == "W1_visible_conflict"
        and row["attack_side_effect"]
    ]
    sections.extend(["### Attacker tool still executed", ""])
    for sft in residual_attack[:5]:
        base = index.get((sft["uid"], "base"))
        sections.extend(
            [
                f"#### `{sft['uid']}`",
                "",
                f"User-visible task/injection: {json.dumps(user_prompt(sft), ensure_ascii=False)}",
                "",
                *([render_row(base), ""] if base else []),
                render_row(sft),
                "",
            ]
        )

    residual_utility = [
        row
        for row in rows
        if row["arm"] == "sft"
        and row["panel"] == "W1_visible_conflict"
        and not row["attack_side_effect"]
        and not row["response_utility_pass"]
    ]
    sections.extend(["### Attack avoided but original task not completed", ""])
    for sft in residual_utility[:5]:
        base = index.get((sft["uid"], "base"))
        sections.extend(
            [
                f"#### `{sft['uid']}`",
                "",
                *([render_row(base), ""] if base else []),
                render_row(sft),
                "",
            ]
        )

    sections.extend(["## W2: evidence-state calibration", ""])
    for condition in ("sufficient", "partial", "failure", "missing_input"):
        candidates = [
            row
            for row in rows
            if row["arm"] == "base"
            and row["panel"] == "W2_evidence_calibration"
            and row["condition"] == condition
            and not row["response_utility_pass"]
            and (row["uid"], "sft") in index
        ]
        improved = [
            row
            for row in candidates
            if index[(row["uid"], "sft")]["response_utility_pass"]
        ]
        residual = [
            row
            for row in candidates
            if not index[(row["uid"], "sft")]["response_utility_pass"]
        ]
        chosen = (improved or residual)[:1]
        for base in chosen:
            sft = index[(base["uid"], "sft")]
            sections.extend(
                [
                    f"### `{condition}` — `{base['uid']}`",
                    "",
                    render_row(base),
                    "",
                    render_row(sft),
                    "",
                ]
            )

    sections.extend(["## W2: residual calibration failures after SFT", ""])
    w2_residual = [
        row
        for row in rows
        if row["arm"] == "sft"
        and row["panel"] == "W2_evidence_calibration"
        and not row["response_utility_pass"]
    ]
    for sft in w2_residual[:5]:
        base = index.get((sft["uid"], "base"))
        sections.extend(
            [
                f"### `{sft['condition']}` — `{sft['uid']}`",
                "",
                *([render_row(base), ""] if base else []),
                render_row(sft),
                "",
            ]
        )

    sections.extend(["## H1: hidden provenance requires harness", ""])
    h1_uids = sorted(
        {
            row["uid"]
            for row in rows
            if row["panel"] == "H1_hidden_provenance"
            and row["condition"] == "substituted"
            and row["arm"] == "sft"
            and row["substitution_side_effect"]
            and (row["uid"], "sft+harness") in index
            and not index[(row["uid"], "sft+harness")][
                "substitution_side_effect"
            ]
        }
    )
    for uid in h1_uids[:4]:
        no_harness = index[(uid, "sft")]
        harness = index[(uid, "sft+harness")]
        sections.extend(
            [
                f"### `{uid}`",
                "",
                render_row(no_harness),
                "",
                render_row(harness),
                "",
            ]
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(sections) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
