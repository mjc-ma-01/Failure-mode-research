#!/usr/bin/env python3
"""Parallel Agent-SafetyBench runner.

This preserves the experiment definition from run_sample_compare.py while
running independent task/condition trajectories concurrently. It reuses an
existing sampled_tasks.json when resuming so the sampled set stays fixed.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from openai import OpenAI

EXPERIMENT_DIR = Path(__file__).resolve().parent
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from run_sample_compare import (  # noqa: E402
    ASB_ROOT,
    CONDITIONS,
    WORKSPACE,
    _append_jsonl,
    _prepare_env,
    _sample_tasks,
    _write_summary_csv,
    run_case,
    summarize,
    write_report,
)


TRANSIENT_ERROR_MARKERS = (
    "RateLimitError",
    "APITimeoutError",
    "APIConnectionError",
    "InternalServerError",
    "timeout",
    "timed out",
    "temporarily unavailable",
    "429",
    "500",
    "502",
    "503",
    "504",
)

_thread_local = threading.local()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ASB_ROOT / "data" / "released_data.json"))
    parser.add_argument("--out-dir", default=str(WORKSPACE / "agent_safetybench_experiments" / "sample_compare_latest"))
    parser.add_argument("--per-risk", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--agent-model", default="gpt-4.1-mini")
    parser.add_argument("--judge-model", default="gpt-4.1")
    parser.add_argument("--max-steps", type=int, default=4)
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--conditions", default=",".join(CONDITIONS))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--checkpoint-every", type=int, default=50)
    args = parser.parse_args()

    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")

    _prepare_env()
    data_path = Path(args.data)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sampled_path = out_dir / "sampled_tasks.json"

    if args.resume and sampled_path.exists():
        tasks = json.loads(sampled_path.read_text(encoding="utf-8"))
    else:
        tasks = _sample_tasks(json.loads(data_path.read_text(encoding="utf-8")), args.per_risk, args.seed)
        if args.max_tasks:
            tasks = tasks[: args.max_tasks]
        sampled_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    selected_conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    unknown = [c for c in selected_conditions if c not in CONDITIONS]
    if unknown:
        raise SystemExit(f"Unknown conditions: {unknown}")

    records_path = out_dir / "records.jsonl"
    records = _read_jsonl_robust(records_path) if args.resume else []
    if not args.resume and records_path.exists():
        records_path.unlink()
    done = {(int(row["id"]), row["condition"]) for row in records}

    jobs = [
        (task, condition)
        for task in tasks
        for condition in selected_conditions
        if (int(task["id"]), condition) not in done
    ]
    total = len(tasks) * len(selected_conditions)
    completed = len(done)
    started = time.time()
    random.Random(args.seed).shuffle(jobs)

    print(
        json.dumps(
            {
                "parallel": True,
                "out_dir": str(out_dir),
                "total": total,
                "already_done": completed,
                "remaining": len(jobs),
                "workers": args.workers,
                "max_retries": args.max_retries,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(_run_job_with_retries, task, condition, args): (task, condition)
            for task, condition in jobs
        }
        for future in as_completed(futures):
            task, condition = futures[future]
            try:
                row = asdict(future.result())
            except Exception as exc:  # noqa: BLE001
                row = _exception_record(task, condition, args, exc)
            _append_jsonl(records_path, row)
            records.append(row)
            completed += 1
            if completed % args.checkpoint_every == 0 or completed == total:
                _write_outputs(out_dir, records, data_path, args)
            print(
                json.dumps(
                    {
                        "progress": f"{completed}/{total}",
                        "id": row.get("id"),
                        "risk": row.get("risk"),
                        "condition": row.get("condition"),
                        "unsafe": row.get("judge", {}).get("unsafe"),
                        "completed": row.get("judge", {}).get("task_completed"),
                        "tools": len(row.get("tool_calls", [])),
                        "blocked": len(row.get("blocked_actions", [])),
                        "error": bool(row.get("error")),
                        "elapsed_total_s": round(time.time() - started, 1),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    _write_outputs(out_dir, records, data_path, args)
    print(json.dumps({"done": True, "out_dir": str(out_dir), "records": len(records)}, ensure_ascii=False), flush=True)


def _client() -> OpenAI:
    client = getattr(_thread_local, "client", None)
    if client is None:
        client = OpenAI(base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["OPENAI_API_KEY"], timeout=180)
        _thread_local.client = client
    return client


def _run_job_with_retries(task: dict[str, Any], condition: str, args: argparse.Namespace):
    last = None
    for attempt in range(args.max_retries + 1):
        record = run_case(task, condition, _client(), args.agent_model, args.judge_model, args.max_steps)
        last = record
        if not record.error or not _is_transient(record.error) or attempt == args.max_retries:
            return record
        sleep_s = min(60.0, (2**attempt) + random.random())
        time.sleep(sleep_s)
    return last


def _is_transient(error: str) -> bool:
    lowered = error.lower()
    return any(marker.lower() in lowered for marker in TRANSIENT_ERROR_MARKERS)


def _write_outputs(out_dir: Path, records: list[dict[str, Any]], data_path: Path, args: argparse.Namespace) -> None:
    summary = summarize(records)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary_csv(out_dir / "summary_by_condition.csv", summary["by_condition"])
    _write_summary_csv(out_dir / "summary_by_risk_condition.csv", summary["by_risk_condition"])
    write_report(out_dir / "REPORT.md", records, summary, data_path, args)


def _read_jsonl_robust(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Skipping malformed JSONL line in {path}", file=sys.stderr, flush=True)
    return rows


def _exception_record(task: dict[str, Any], condition: str, args: argparse.Namespace, exc: Exception) -> dict[str, Any]:
    error = f"{type(exc).__name__}: {exc}"
    return {
        "id": int(task["id"]),
        "risk": (task.get("risks") or [""])[0],
        "fulfillable": int(task.get("fulfillable", 0)),
        "condition": condition,
        "agent_model": args.agent_model,
        "judge_model": args.judge_model,
        "final_response": "",
        "tool_calls": [],
        "blocked_actions": [],
        "judge": {"unsafe": None, "task_completed": False, "reason": error, "parse_ok": False},
        "runtime": {},
        "elapsed_s": 0,
        "error": error,
    }


if __name__ == "__main__":
    main()
