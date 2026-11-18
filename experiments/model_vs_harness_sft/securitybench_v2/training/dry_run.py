#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from transformers import AutoTokenizer

from data import UpwardSFTDataset, load_jsonl


EXPECTED_CONDITIONS = {
    "sufficient",
    "partial",
    "failure",
    "missing_input",
    "dpi",
    "opi",
    "trusted",
}


def percentile(values: list[int], quantile: float) -> int:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * quantile)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--max-length", type=int, default=8192)
    parser.add_argument("--report")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    rows = load_jsonl(args.data)
    dataset = UpwardSFTDataset(rows, tokenizer, max_length=args.max_length)
    lengths = [example["length"] for example in dataset.examples]
    targets = [example["supervised_tokens"] for example in dataset.examples]
    counts = Counter(row["condition"] for row in rows)
    if set(counts) != EXPECTED_CONDITIONS:
        raise AssertionError(f"unexpected conditions: {counts}")
    if len(set(counts.values())) != 1:
        raise AssertionError(f"conditions are not balanced: {counts}")
    panels = Counter(row["panel"] for row in rows)
    if panels != {
        "evidence_calibration": 208,
        "visible_conflict": 104,
        "benign_commit": 52,
    }:
        raise AssertionError(f"unexpected panel balance: {panels}")

    for row, example in zip(rows, dataset.examples):
        supervised = {
            index for index, label in enumerate(example["labels"]) if label != -100
        }
        expected = {
            index
            for start, end in example["assistant_spans"]
            for index in range(start, end)
        }
        if supervised != expected:
            raise AssertionError(f"{row['id']}: assistant target mask mismatch")
        if float(row["sampling_weight"]) != 1.0:
            raise AssertionError(f"{row['id']}: sampling weight is not 1")

    report = {
        "status": "pass",
        "rows": len(rows),
        "panels": dict(panels),
        "conditions": dict(counts),
        "length_tokens": {
            "min": min(lengths),
            "median": statistics.median(lengths),
            "p95": percentile(lengths, 0.95),
            "max": max(lengths),
        },
        "assistant_target_tokens": {
            "min": min(targets),
            "median": statistics.median(targets),
            "p95": percentile(targets, 0.95),
            "max": max(targets),
        },
        "max_length": args.max_length,
        "truncated_rows": 0,
        "mask_policy": "assistant response tokens only, including tool-call payloads",
        "hidden_provenance_labels_in_training": False,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
