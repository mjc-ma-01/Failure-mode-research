#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SHARED = ROOT / "experiments/model_vs_harness_sft/upward_deception/training"
sys.path.insert(0, str(SHARED))

from data import UpwardSFTDataset, load_jsonl  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--max-length", type=int, default=4096)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    rows = load_jsonl(args.data)
    if len(rows) != 140:
        raise RuntimeError(f"expected 140 W1 rows, got {len(rows)}")
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    dataset = UpwardSFTDataset(rows, tokenizer, max_length=args.max_length)
    lengths = [example["length"] for example in dataset.examples]
    targets = [example["supervised_tokens"] for example in dataset.examples]
    for row, example in zip(rows, dataset.examples):
        supervised = {i for i, label in enumerate(example["labels"]) if label != -100}
        expected = {
            i
            for start, end in example["assistant_spans"]
            for i in range(start, end)
        }
        if supervised != expected:
            raise RuntimeError(f"{row['id']}: assistant mask mismatch")
    report = {
        "status": "pass",
        "rows": len(rows),
        "max_length": args.max_length,
        "length_min_median_max": [min(lengths), statistics.median(lengths), max(lengths)],
        "target_min_median_max": [min(targets), statistics.median(targets), max(targets)],
        "truncated_rows": 0,
        "loss_mask": "assistant tokens only",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
