#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
from typing import Any

from build_contracts import (
    DEFAULT_OUTPUT,
    atomic_json,
    audit_prompt,
    chat,
    compile_answers,
    content,
    deterministic_errors,
    load_benchmark,
    parse_json,
    select_attacks_prompt,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--judge-model", default="deepseek-v4-pro")
    parser.add_argument("--classifier-model", default="gpt-4.1")
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", ""))
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY", ""))
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    if not args.api_key or not args.base_url:
        parser.error("OPENAI_BASE_URL and OPENAI_API_KEY are required")
    from openai import OpenAI

    client = OpenAI(base_url=args.base_url, api_key=args.api_key, timeout=900)
    tasks, attacks = load_benchmark()
    task_by_uid = {task["uid"]: task for task in tasks}
    contracts_dir = args.output / "contracts"
    selections_dir = args.output / "attack_selections"
    selections_dir.mkdir(parents=True, exist_ok=True)

    def decision_object(value: Any) -> dict[str, Any]:
        if isinstance(value, dict) and "decision" in value:
            return value
        if isinstance(value, list):
            for item in reversed(value):
                if isinstance(item, dict) and "decision" in item:
                    return item
        raise ValueError("judge response lacks a decision object")

    def recover(path: Path) -> dict[str, Any]:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("accepted"):
            return record
        task = record.get("task") or task_by_uid[record["uid"]]
        if not record.get("attempts"):
            return {"uid": record["uid"], "accepted": False, "error": "no_attempt"}
        candidate = compile_answers(parse_json(record["attempts"][-1]["raw"]))
        variants = 4 if record["split"] == "train" else 2
        errors = deterministic_errors(task, candidate, variants)
        if errors:
            return {
                "uid": record["uid"],
                "accepted": False,
                "error": "deterministic:" + "|".join(errors),
            }
        response = chat(
            client,
            model=args.judge_model,
            messages=[
                {
                    "role": "system",
                    "content": "Audit agent-training ground truth strictly. Return JSON.",
                },
                {"role": "user", "content": audit_prompt(task, candidate)},
            ],
            temperature=0,
            reasoning_effort="high",
            max_tokens=5000,
            response_format={"type": "json_object"},
        )
        review = decision_object(parse_json(content(response.choices[0].message)))
        accepted = (
            review.get("decision") == "pass"
            and all(review.get("variants_valid", []))
            and not review.get("unsupported_claims")
        )
        record["contract"] = candidate if accepted else None
        record["accepted"] = accepted
        record["review"] = review
        record["recovered_with_compiler"] = True
        atomic_json(path, record)
        return record

    paths = sorted(contracts_dir.glob("*.json"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(recover, path): path for path in paths}
        results = []
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            try:
                result = future.result()
            except Exception as error:  # noqa: BLE001
                path = futures[future]
                stored = json.loads(path.read_text(encoding="utf-8"))
                result = {
                    "uid": stored["uid"],
                    "split": stored.get("split"),
                    "task": stored.get("task"),
                    "accepted": False,
                    "error": f"{type(error).__name__}:{str(error)[:500]}",
                }
            results.append(result)
            print(
                f"[audit {index}/{len(futures)}] {result['uid']} "
                f"{'accepted' if result.get('accepted') else 'rejected'}",
                flush=True,
            )

    def classify(record: dict[str, Any]) -> None:
        uid = record["uid"]
        path = selections_dir / f"{uid.replace(':', '__')}.json"
        if path.exists():
            return
        task = record["task"]
        response = chat(
            client,
            model=args.classifier_model,
            messages=[
                {
                    "role": "system",
                    "content": "Classify tool-task semantic overlap. Return JSON.",
                },
                {
                    "role": "user",
                    "content": select_attacks_prompt(task, attacks[task["agent"]]),
                },
            ],
            temperature=0,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        selection = parse_json(content(response.choices[0].message))
        available = {
            row["Attacker Tool"]: row for row in attacks[task["agent"]]
        }
        unrelated = [
            row
            for row in selection.get("unrelated", [])
            if row.get("name") in available
        ]
        overlap = [
            row
            for row in selection.get("overlap", [])
            if row.get("name") in available
        ]
        chosen = {row["name"] for row in unrelated + overlap}
        for name in sorted(available):
            if len(unrelated) >= 4:
                break
            if name not in chosen:
                unrelated.append({"name": name, "reason": "deterministic fallback"})
                chosen.add(name)
        atomic_json(
            path,
            {
                "uid": uid,
                "unrelated": unrelated[:4],
                "overlap": overlap[:2],
                "records": {
                    name: available[name]
                    for name in {
                        row["name"] for row in unrelated[:4] + overlap[:2]
                    }
                },
            },
        )

    accepted = [record for record in results if record.get("accepted")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(classify, accepted))
    by_split = {
        split: sum(record.get("split") == split for record in accepted)
        for split in ("train", "dev", "test")
    }
    manifest = {
        "protocol": "asb_evidence_grounded_v2",
        "tasks": len(results),
        "accepted": len(accepted),
        "rejected": len(results) - len(accepted),
        "by_split": by_split,
        "teacher_model": "gpt-4.1",
        "judge_model": args.judge_model,
        "compiled_ground_truth": True,
    }
    atomic_json(args.output / "contract_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
