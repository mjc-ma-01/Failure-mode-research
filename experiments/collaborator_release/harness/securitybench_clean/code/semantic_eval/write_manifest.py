#!/usr/bin/env python3
"""Write and validate the formal token-fixed SecurityBench result manifest."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any


MODEL = "deepseek-v4-pro-0813"
ARMS = ("M", "M+H", "M+H+ΔH")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--judge-input-summary", type=Path, required=True)
    args = parser.parse_args()

    rows = read_jsonl(args.input)
    keys = {(row["uid"], row["arm"]) for row in rows}
    arms = collections.Counter(row["arm"] for row in rows)
    if len(rows) != 1800 or len(keys) != 1800:
        raise RuntimeError("formal judge output must have 1,800 unique rows")
    if arms != collections.Counter({arm: 600 for arm in ARMS}):
        raise RuntimeError(f"bad arm coverage: {arms}")
    if any(row.get("judge_error") for row in rows):
        raise RuntimeError("judge errors remain")
    if any(row.get("semantic_judge_response_model") != MODEL for row in rows):
        raise RuntimeError("judge response model mismatch")
    if {row.get("semantic_judge_request_profile") for row in rows} != {
        "reasoning_low_json"
    }:
        raise RuntimeError("judge request profile mismatch")

    delta = [row for row in rows if row["arm"] == "M+H+ΔH"]
    expiry_events = sum(
        "expired or exhausted"
        in str((event.get("decision") or {}).get("reason") or "")
        for row in delta
        for event in row.get("events") or []
    )
    if expiry_events:
        raise RuntimeError(f"token lifecycle audit failed: {expiry_events} events")
    infrastructure_errors = sum(
        bool(row.get("runner_error"))
        and row.get("runner_error") != "react_action_parse_failure"
        for row in delta
    )
    if infrastructure_errors:
        raise RuntimeError(f"infrastructure runner errors: {infrastructure_errors}")
    parse_failures = sum(
        row.get("runner_error") == "react_action_parse_failure" for row in delta
    )

    required = [
        args.input,
        args.judge_input_summary,
        args.results_dir / "analysis.json",
        args.results_dir / "paired_transitions.json",
        args.results_dir / "cases.json",
        args.results_dir / "REPORT.md",
        args.results_dir / "CASES.md",
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    files = {
        path.name if path.parent == args.results_dir else "judge_input.summary.json": {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in required
    }
    summary = json.loads(args.judge_input_summary.read_text(encoding="utf-8"))
    manifest = {
        "protocol": "asb_harness_semantic_eval_token_fixed_v2",
        "status": "complete_clean",
        "coverage": {"total": 1800, **dict(arms)},
        "judge": {
            "model": MODEL,
            "temperature": 0,
            "request_profile": "reasoning_low_json",
            "max_tokens": 6000,
            "errors": 0,
            "response_model_exact_match_rows": 1800,
        },
        "generation_audit": {
            "deltaH_rows": 600,
            "expired_token_events": 0,
            "infrastructure_runner_errors": 0,
            "model_react_parse_failures": parse_failures,
            "token_lifecycle": "SecurityPipeline and tokens constructed immediately before each generation batch",
        },
        "sources": summary.get("sources"),
        "files": files,
    }
    (args.results_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
