#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def shorten(value: Any, length: int = 380) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":")) if not isinstance(value, str) else value
    text = text.replace("\n", " ")
    return text if len(text) <= length else text[: length - 3] + "..."


def trace(row: dict[str, Any]) -> str:
    pieces = []
    for index, step in enumerate(row.get("steps") or [], 1):
        proposal = step.get("proposal") or {}
        tool = proposal.get("tool", "unknown")
        args = shorten(proposal.get("arguments") or {}, 300)
        decision = step.get("decision") or {}
        if step.get("executed") is False:
            state = f"BLOCK:{decision.get('check') or 'unknown'}"
        elif tool == "finish":
            state = "FINAL"
        else:
            state = "EXEC"
        pieces.append(f"{index}. {tool}({args}) [{state}]")
    return "\n".join(pieces) if pieces else "(empty)"


def monitor(row: dict[str, Any]) -> str:
    value = row.get("monitor") or {}
    return (
        f"risky={value.get('is_risky')}, success={value.get('task_success')}, "
        f"help={value.get('helpfulness')}, action={value.get('action_score')}; "
        f"{shorten(value.get('action_summary') or value.get('raw_response') or '', 700)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transitions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--examples-per-transition", type=int, default=2)
    args = parser.parse_args()
    rows = read_jsonl(args.transitions)
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["comparison"], row["risk_category"], row["base_uid"])].append(row)

    lines = [
        "# Three-arm paired case inventory",
        "",
        "Each comparison uses the same task variant and rollout seed. The inventory is descriptive; repeated variants and rollouts are not independent scenarios.",
        "",
    ]
    for key in sorted(groups):
        comparison, category, base_uid = key
        selected = groups[key]
        counts = Counter((row["risk_transition"], row["utility_transition"]) for row in selected)
        lines.extend([
            f"## {comparison}: {base_uid}",
            "",
            f"Category: {category}. Paired cells: {len(selected)}.",
            "",
            "Transitions: " + "; ".join(
                f"{risk}|{utility}={count}"
                for (risk, utility), count in sorted(counts.items())
            ),
            "",
        ])
        for transition in sorted(counts):
            candidates = [
                row for row in selected
                if (row["risk_transition"], row["utility_transition"]) == transition
            ][: args.examples_per_transition]
            risk, utility = transition
            lines.extend([f"### {risk} / {utility}", ""])
            for row in candidates:
                lines.extend([
                    f"#### {row['task_uid']} rollout {row['rollout_id']}",
                    "",
                    f"Right-arm harness blocks: {row['right_harness_blocks']}.",
                    "",
                    "**Control monitor:** " + monitor(row["left"]),
                    "",
                    "**Control trace**",
                    "",
                    trace(row["left"]),
                    "",
                    "**Treatment monitor:** " + monitor(row["right"]),
                    "",
                    "**Treatment trace**",
                    "",
                    trace(row["right"]),
                    "",
                    "**Control final:** " + shorten(row["left"].get("final_output") or "", 1200),
                    "",
                    "**Treatment final:** " + shorten(row["right"].get("final_output") or "", 1200),
                    "",
                ])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n")
    print(json.dumps({"output": str(args.output), "groups": len(groups), "rows": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
