#!/usr/bin/env python3
"""Prepare a clean semantic-judge run while reusing unchanged control verdicts.

The M and M+H trajectories are byte-for-byte unchanged by the capability-token
fix. This script verifies that invariant against the previous judge input and
only then seeds the new resume file with their existing DeepSeek verdicts. The
new M+H+ΔH arm remains pending and must be judged normally.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


CONTROL_ARMS = {"M", "M+H"}
DELTA_ARM = "M+H+ΔH"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["uid"]), str(row["arm"])


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def comparable_input(row: dict[str, Any]) -> dict[str, Any]:
    """Judge-visible record plus stable metadata, excluding storage location."""

    return {
        field: value
        for field, value in row.items()
        if field != "trajectory_source"
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-input", type=Path, required=True)
    parser.add_argument("--old-judged", type=Path, required=True)
    parser.add_argument("--new-input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    old_input = {key(row): row for row in read_jsonl(args.old_input)}
    old_judged = {key(row): row for row in read_jsonl(args.old_judged)}
    new_rows = read_jsonl(args.new_input)
    new_input = {key(row): row for row in new_rows}
    if len(new_rows) != 1800 or len(new_input) != 1800:
        raise RuntimeError("new input must contain 1,800 unique (uid, arm) rows")

    for arm in (*sorted(CONTROL_ARMS), DELTA_ARM):
        count = sum(row["arm"] == arm for row in new_rows)
        if count != 600:
            raise RuntimeError(f"{arm} coverage is {count}, expected 600")

    control_keys = {item for item in new_input if item[1] in CONTROL_ARMS}
    if len(control_keys) != 1200:
        raise RuntimeError("expected 1,200 control rows")
    for item in sorted(control_keys):
        if (
            item not in old_input
            or comparable_input(old_input[item]) != comparable_input(new_input[item])
        ):
            raise RuntimeError(f"control input changed; cannot reuse verdict: {item}")
        judged = old_judged.get(item)
        if judged is None or judged.get("judge_error"):
            raise RuntimeError(f"missing valid old verdict: {item}")
        # Ensure the trajectory portion embedded in the judged record is the
        # exact new input, rather than reusing a verdict by key alone.
        embedded = {field: judged.get(field) for field in new_input[item]}
        if comparable_input(embedded) != comparable_input(new_input[item]):
            raise RuntimeError(f"judged trajectory differs from input: {item}")

    delta_rows = [row for row in new_rows if row["arm"] == DELTA_ARM]
    expired = [
        row["uid"]
        for row in delta_rows
        if any(
            "expired or exhausted" in str((event.get("decision") or {}).get("reason") or "")
            for event in row.get("events") or []
        )
    ]
    if expired:
        raise RuntimeError(f"token lifecycle audit failed for {len(expired)} rows")
    parse_failures = [
        row["uid"]
        for row in delta_rows
        if row.get("runner_error") == "react_action_parse_failure"
    ]
    infrastructure_errors = [
        row["uid"]
        for row in delta_rows
        if row.get("runner_error")
        and row.get("runner_error") != "react_action_parse_failure"
    ]
    if infrastructure_errors:
        raise RuntimeError(
            f"infrastructure runner errors in {len(infrastructure_errors)} delta rows"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    seeded = []
    for item in sorted(control_keys):
        reused = dict(old_judged[item])
        # Refresh all trajectory/input fields from the new panel while keeping
        # the verified, unchanged semantic verdict and request audit fields.
        reused.update(new_input[item])
        seeded.append(reused)
    partial = args.output_dir / "judged.partial.jsonl"
    partial.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in seeded),
        encoding="utf-8",
    )
    audit = {
        "protocol": "asb_token_fixed_control_verdict_reuse_v1",
        "old_input_sha256": sha256(args.old_input),
        "old_judged_sha256": sha256(args.old_judged),
        "new_input_sha256": sha256(args.new_input),
        "new_input_rows": len(new_rows),
        "reused_control_verdicts": len(seeded),
        "pending_delta_verdicts": len(delta_rows),
        "reuse_invariant": (
            "All M and M+H input fields are identical except trajectory_source; "
            "the embedded trajectory in every reused judged row was verified."
        ),
        "expired_token_rows": 0,
        "model_react_parse_failure_rows": len(parse_failures),
        "infrastructure_runner_error_rows": 0,
        "partial": str(partial),
    }
    (args.output_dir / "CONTROL_REUSE_AUDIT.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
