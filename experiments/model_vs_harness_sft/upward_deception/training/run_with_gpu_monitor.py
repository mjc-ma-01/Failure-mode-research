#!/usr/bin/env python3
import argparse
import csv
import json
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path


QUERY = [
    "nvidia-smi",
    "--query-gpu=timestamp,index,name,utilization.gpu,memory.used,memory.total,power.draw",
    "--format=csv,noheader,nounits",
]


def parse_float(value):
    try:
        return float(value)
    except ValueError:
        return None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--warmup-seconds", type=float, default=60.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("missing monitored command")
    return args


def sample_gpus():
    output = subprocess.check_output(QUERY, text=True)
    samples = []
    for row in csv.reader(output.splitlines()):
        if not row:
            continue
        samples.append(
            {
                "nvidia_timestamp": row[0].strip(),
                "gpu_index": int(row[1]),
                "gpu_name": row[2].strip(),
                "utilization_gpu_percent": float(row[3]),
                "memory_used_mib": float(row[4]),
                "memory_total_mib": float(row[5]),
                "power_draw_w": parse_float(row[6]),
            }
        )
    return samples


def percentile(values, quantile):
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * quantile)]


def main():
    args = parse_args()
    metrics_path = Path(args.metrics)
    summary_path = Path(args.summary)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    process = subprocess.Popen(args.command)

    def terminate(signum, frame):
        if process.poll() is None:
            process.send_signal(signum)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    records = []
    with metrics_path.open("w", encoding="utf-8") as handle:
        while process.poll() is None:
            try:
                for sample in sample_gpus():
                    sample["unix_time"] = time.time()
                    sample["elapsed_seconds"] = sample["unix_time"] - started
                    records.append(sample)
                    handle.write(json.dumps(sample) + "\n")
                handle.flush()
            except Exception as error:
                print(f"GPU monitor warning: {error}", file=sys.stderr, flush=True)
            time.sleep(args.interval)
    return_code = process.wait()
    steady = [
        record
        for record in records
        if record["elapsed_seconds"] >= args.warmup_seconds
    ]
    utilizations = [record["utilization_gpu_percent"] for record in steady]
    summary = {
        "command": args.command,
        "return_code": return_code,
        "samples_total": len(records),
        "samples_after_warmup": len(steady),
        "warmup_seconds": args.warmup_seconds,
        "duration_seconds": time.time() - started,
        "gpu_utilization_percent_after_warmup": (
            {
                "p10": percentile(utilizations, 0.10),
                "median": statistics.median(utilizations),
                "p90": percentile(utilizations, 0.90),
            }
            if utilizations
            else None
        ),
        "peak_memory_used_mib": (
            max(record["memory_used_mib"] for record in records) if records else None
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
