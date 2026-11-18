#!/usr/bin/env python3
import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from transformers import AutoTokenizer

from data import UpwardSFTDataset, load_jsonl


def percentile(values, quantile):
    ordered = sorted(values)
    index = round((len(ordered) - 1) * quantile)
    return ordered[index]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--max-length", type=int, default=16384)
    parser.add_argument("--report")
    return parser.parse_args()


def main():
    args = parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    rows = load_jsonl(args.data)
    dataset = UpwardSFTDataset(rows, tokenizer, max_length=args.max_length)
    lengths = [example["length"] for example in dataset.examples]
    targets = [example["supervised_tokens"] for example in dataset.examples]

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
            raise AssertionError(f"{row['id']}: target mask differs from assistant spans")
        if row["condition"] == "failure" and example["sampling_weight"] != 2.0:
            raise AssertionError(f"{row['id']}: invalid failure weight")
        if row["condition"] != "failure" and example["sampling_weight"] != 1.0:
            raise AssertionError(f"{row['id']}: invalid non-failure weight")

    report = {
        "status": "pass",
        "rows": len(rows),
        "conditions": dict(Counter(row["condition"] for row in rows)),
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
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.report:
        output = Path(args.report)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
