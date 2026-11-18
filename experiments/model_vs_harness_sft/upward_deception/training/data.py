#!/usr/bin/env python3
import copy
import json
from pathlib import Path

import torch
from torch.utils.data import Dataset


def load_jsonl(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def normalize_messages(messages):
    normalized = copy.deepcopy(messages)
    for message in normalized:
        for tool_call in message.get("tool_calls") or []:
            function = tool_call.get("function", tool_call)
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    function["arguments"] = json.loads(arguments)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Tool arguments are not valid JSON: {arguments!r}"
                    ) from error
            if not isinstance(function.get("arguments", {}), dict):
                raise ValueError("Qwen tool-call arguments must be a JSON object")
    return normalized


def render_text(tokenizer, messages, tools, add_generation_prompt=False):
    return tokenizer.apply_chat_template(
        messages,
        tools=tools,
        tokenize=False,
        add_generation_prompt=add_generation_prompt,
        enable_thinking=False,
    )


def assistant_character_spans(rendered, expected_count):
    header = "<|im_start|>assistant\n"
    footer = "<|im_end|>"
    empty_thinking = "<think>\n\n</think>\n\n"
    spans = []
    cursor = 0
    while True:
        header_start = rendered.find(header, cursor)
        if header_start < 0:
            break
        target_start = header_start + len(header)
        if rendered.startswith(empty_thinking, target_start):
            target_start += len(empty_thinking)
        footer_start = rendered.find(footer, target_start)
        if footer_start < 0:
            raise ValueError("Assistant message is missing its end marker")
        target_end = footer_start + len(footer)
        spans.append((target_start, target_end))
        cursor = target_end
    if len(spans) != expected_count:
        raise ValueError(
            f"Expected {expected_count} assistant messages but found {len(spans)}"
        )
    return spans


def encode_example(row, tokenizer, max_length):
    messages = normalize_messages(row["messages"])
    tools = row["tools"]
    rendered = render_text(tokenizer, messages, tools)
    encoded = tokenizer(
        rendered,
        add_special_tokens=False,
        return_offsets_mapping=True,
    )
    full_ids = encoded["input_ids"]
    offsets = encoded["offset_mapping"]
    labels = [-100] * len(full_ids)
    assistant_count = sum(message["role"] == "assistant" for message in messages)
    character_spans = assistant_character_spans(rendered, assistant_count)
    assistant_spans = []
    for character_start, character_end in character_spans:
        token_indexes = [
            index
            for index, (token_start, token_end) in enumerate(offsets)
            if token_end > character_start and token_start < character_end
        ]
        if not token_indexes:
            raise ValueError(f"{row['id']}: empty assistant target")
        start = min(token_indexes)
        end = max(token_indexes) + 1
        labels[start:end] = full_ids[start:end]
        assistant_spans.append((start, end))

    if len(full_ids) > max_length:
        raise ValueError(
            f"{row['id']}: {len(full_ids)} tokens exceeds max_length={max_length}; "
            "refusing silent truncation"
        )
    supervised_tokens = sum(label != -100 for label in labels)
    if not supervised_tokens:
        raise ValueError(f"{row['id']}: no supervised assistant tokens")

    return {
        "id": row["id"],
        "condition": row["condition"],
        "input_ids": full_ids,
        "attention_mask": [1] * len(full_ids),
        "labels": labels,
        "sampling_weight": float(row["sampling_weight"]),
        "length": len(full_ids),
        "supervised_tokens": supervised_tokens,
        "assistant_spans": assistant_spans,
    }


class UpwardSFTDataset(Dataset):
    def __init__(self, rows, tokenizer, max_length):
        self.examples = [
            encode_example(row, tokenizer, max_length=max_length) for row in rows
        ]

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, index):
        example = self.examples[index]
        return {
            "input_ids": example["input_ids"],
            "attention_mask": example["attention_mask"],
            "labels": example["labels"],
            "sampling_weight": example["sampling_weight"],
            "length": example["length"],
        }


class WeightedDataCollator:
    def __init__(self, tokenizer, pad_to_multiple_of=8):
        self.tokenizer = tokenizer
        self.pad_to_multiple_of = pad_to_multiple_of

    def __call__(self, features):
        weights = torch.tensor(
            [feature["sampling_weight"] for feature in features],
            dtype=torch.float32,
        )
        lengths = torch.tensor(
            [feature["length"] for feature in features],
            dtype=torch.long,
        )
        max_length = max(feature["length"] for feature in features)
        if self.pad_to_multiple_of:
            max_length = (
                (max_length + self.pad_to_multiple_of - 1)
                // self.pad_to_multiple_of
                * self.pad_to_multiple_of
            )
        input_ids = []
        attention_masks = []
        labels = []
        for feature in features:
            padding = max_length - feature["length"]
            input_ids.append(
                feature["input_ids"] + [self.tokenizer.pad_token_id] * padding
            )
            attention_masks.append(feature["attention_mask"] + [0] * padding)
            labels.append(feature["labels"] + [-100] * padding)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_masks, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
            "sampling_weight": weights,
            "length": lengths,
        }
