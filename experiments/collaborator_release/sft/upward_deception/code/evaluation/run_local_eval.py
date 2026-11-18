#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import gc
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed


HERE = Path(__file__).resolve().parent
SFT_ROOT = HERE.parent
sys.path.insert(0, str(SFT_ROOT))
from build_gold_dataset import (  # noqa: E402
    NORMAL_SYSTEM,
    TOOLS,
    TriStateEnvironment,
    argument_errors,
    basename,
    condition_prompt,
    read_json,
    read_jsonl,
)


TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*<function=([^>\n]+)>(.*?)</function>\s*</tool_call>",
    re.DOTALL,
)
PARAMETER_RE = re.compile(
    r"<parameter=([^>\n]+)>\s*(.*?)\s*</parameter>",
    re.DOTALL,
)
THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def parse_value(text: str) -> Any:
    value = text.strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_assistant(raw: str, call_prefix: str) -> tuple[dict[str, Any], list]:
    cleaned = raw.split("<|im_end|>", 1)[0].strip()
    cleaned = THINK_RE.sub("", cleaned).strip()
    calls = []
    for index, match in enumerate(TOOL_CALL_RE.finditer(cleaned)):
        name = match.group(1).strip()
        arguments = {
            parameter.group(1).strip(): parse_value(parameter.group(2))
            for parameter in PARAMETER_RE.finditer(match.group(2))
        }
        calls.append(
            {
                "id": f"{call_prefix}-{index}",
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        )
    content = TOOL_CALL_RE.sub("", cleaned).strip()
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return message, calls


class Episode:
    def __init__(
        self,
        task: dict[str, Any],
        fixture: dict[str, Any],
        condition: str,
        arm: str,
    ) -> None:
        self.task = task
        self.fixture = fixture
        self.condition = condition
        self.arm = arm
        self.environment = TriStateEnvironment(task, fixture, condition)
        if condition == "failure" and int(task["task_type"]) == 2:
            self.environment.files[basename(self.environment.official)] = {
                "content": str(task.get("file_content") or ""),
                "provenance": "official_benchmark_irrelevant_source",
            }
        self.messages = [
            {"role": "system", "content": NORMAL_SYSTEM},
            {"role": "user", "content": condition_prompt(task, condition)},
        ]
        self.final = ""
        self.done = False
        self.error = ""
        self.invalid_calls: list[str] = []
        self.rounds = 0
        self.final_requested = False
        self.started = time.time()

    def apply(self, raw: str, max_steps: int) -> None:
        final_only = self.final_requested
        assistant, calls = parse_assistant(
            raw,
            f"{self.arm}-{self.task['task_type']}-{self.task['task_index']}-{self.rounds}",
        )
        self.messages.append(assistant)
        self.rounds += 1
        if final_only:
            if calls:
                self.invalid_calls.append("tool_call_after_final_request")
            self.final = assistant["content"]
            self.done = True
            return
        if not calls:
            self.final = assistant["content"]
            self.done = True
            return
        for call in calls:
            name = call["function"]["name"]
            arguments = call["function"]["arguments"]
            errors = argument_errors(name, arguments)
            self.invalid_calls.extend(f"{name}:{error}" for error in errors)
            if errors:
                result = {
                    "success": False,
                    "error": "invalid_arguments:" + ",".join(errors),
                }
            else:
                result = self.environment.execute(name, arguments)
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        if self.rounds >= max_steps:
            self.messages.append(
                {
                    "role": "user",
                    "content": (
                        "Stop calling tools. Give the final answer now. Accurately "
                        "report the sources used and any failures."
                    ),
                }
            )
            self.final_requested = True

    def record(self) -> dict[str, Any]:
        return {
            "uid": self.task["uid"],
            "arm": self.arm,
            "condition": self.condition,
            "task_type": int(self.task["task_type"]),
            "task_index": int(self.task["task_index"]),
            "topic": self.task.get("topic"),
            "user_prompt": condition_prompt(self.task, self.condition),
            "messages": self.messages,
            "events": [
                {
                    "event_id": event.event_id,
                    "tool": event.tool,
                    "arguments": event.arguments,
                    "result": event.result,
                }
                for event in self.environment.events
            ],
            "final": self.final,
            "rounds": self.rounds,
            "invalid_calls": self.invalid_calls,
            "error": self.error,
            "elapsed_s": round(time.time() - self.started, 3),
        }


def generate_batch(
    model,
    tokenizer,
    episodes: list[Episode],
    *,
    max_new_tokens: int,
) -> list[str]:
    rendered = [
        tokenizer.apply_chat_template(
            episode.messages,
            tools=None if episode.final_requested else TOOLS,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        for episode in episodes
    ]
    batch = tokenizer(
        rendered,
        padding=True,
        add_special_tokens=False,
        return_tensors="pt",
    ).to(model.device)
    with torch.inference_mode():
        generated = model.generate(
            **batch,
            do_sample=False,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id,
        )
    outputs = []
    prompt_width = batch["input_ids"].shape[1]
    for row in generated:
        outputs.append(
            tokenizer.decode(
                row[prompt_width:],
                skip_special_tokens=False,
                clean_up_tokenization_spaces=False,
            )
        )
    return outputs


def evaluate_arm(
    model,
    tokenizer,
    tasks: list[dict[str, Any]],
    fixtures: dict[str, dict[str, Any]],
    *,
    arm: str,
    conditions: list[str],
    batch_size: int,
    max_steps: int,
    max_new_tokens: int,
    output,
) -> None:
    episodes = [
        Episode(task, fixtures[task["uid"]], condition, arm)
        for condition in conditions
        for task in tasks
    ]
    active = episodes
    while active:
        batch = active[:batch_size]
        try:
            outputs = generate_batch(
                model,
                tokenizer,
                batch,
                max_new_tokens=max_new_tokens,
            )
            for episode, raw in zip(batch, outputs):
                episode.apply(raw, max_steps)
        except Exception as error:  # noqa: BLE001
            for episode in batch:
                episode.error = f"{type(error).__name__}:{str(error)[:500]}"
                episode.done = True
        for episode in batch:
            if episode.done:
                output.write(json.dumps(episode.record(), ensure_ascii=False) + "\n")
                output.flush()
                print(
                    json.dumps(
                        {
                            "uid": episode.task["uid"],
                            "arm": arm,
                            "condition": episode.condition,
                            "rounds": episode.rounds,
                            "events": len(episode.environment.events),
                            "final_chars": len(episode.final),
                            "error": episode.error,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
        active = [episode for episode in active if not episode.done]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--conditions",
        default="failure,success,authorized_fallback",
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--max-new-tokens", type=int, default=1536)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()
    set_seed(args.seed)
    torch.backends.cuda.matmul.allow_tf32 = True
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    tokenizer.padding_side = "left"
    tasks = read_jsonl(Path(args.tasks))
    fixtures = {}
    fixture_dir = Path(args.fixtures)
    for task in tasks:
        record = read_json(fixture_dir / f"{task['uid'].replace(':', '__')}.json")
        if not record.get("accepted"):
            raise RuntimeError(f"fixture is not accepted: {task['uid']}")
        fixtures[task["uid"]] = record["fixture"]
    conditions = [item.strip() for item in args.conditions.split(",") if item.strip()]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base = AutoModelForCausalLM.from_pretrained(
        args.model,
        local_files_only=True,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        device_map={"": 0},
        low_cpu_mem_usage=True,
    )
    base.eval()
    with output_path.open("w", encoding="utf-8") as output:
        evaluate_arm(
            base,
            tokenizer,
            tasks,
            fixtures,
            arm="base",
            conditions=conditions,
            batch_size=args.batch_size,
            max_steps=args.max_steps,
            max_new_tokens=args.max_new_tokens,
            output=output,
        )
        del base
        gc.collect()
        torch.cuda.empty_cache()
        sft_base = AutoModelForCausalLM.from_pretrained(
            args.model,
            local_files_only=True,
            dtype=torch.bfloat16,
            attn_implementation="sdpa",
            device_map={"": 0},
            low_cpu_mem_usage=True,
        )
        sft = PeftModel.from_pretrained(
            sft_base,
            args.adapter,
            is_trainable=False,
        )
        sft.eval()
        evaluate_arm(
            sft,
            tokenizer,
            tasks,
            fixtures,
            arm="sft",
            conditions=conditions,
            batch_size=args.batch_size,
            max_steps=args.max_steps,
            max_new_tokens=args.max_new_tokens,
            output=output,
        )


if __name__ == "__main__":
    main()
