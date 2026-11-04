from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def dumps_json(data: Any, *, indent: int | None = None) -> str:
    return json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=False)


def loads_json_maybe_fenced(text: str) -> Any:
    text = text.strip()
    if not text:
        raise ValueError("Empty JSON text")
    candidates = [text]
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        candidates.insert(0, fence.group(1).strip())
    obj = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if obj:
        candidates.append(obj.group(1))
    arr = re.search(r"(\[.*\])", text, flags=re.DOTALL)
    if arr:
        candidates.append(arr.group(1))
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
    try:
        from json_repair import repair_json

        for candidate in candidates:
            repaired = repair_json(candidate)
            if repaired:
                return json.loads(repaired)
    except Exception:
        pass
    raise ValueError(f"Could not parse JSON from model output: {last_error}")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_records(path)


def read_records(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not path.exists():
        return items
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ("items", "records", "scenarios", "trajectories", "judgments"):
                value = data.get(key)
                if isinstance(value, list):
                    items = value
                    break
            else:
                raise ValueError(f"{path}: expected a JSON array or an object containing a records list")
        else:
            raise ValueError(f"{path}: expected a JSON array")
        for index, item in enumerate(items, 1):
            if not isinstance(item, dict):
                raise ValueError(f"{path}:{index}: expected JSON object")
        return items
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL line: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"{path}:{line_no}: expected JSON object")
            items.append(obj)
    return items


def write_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    write_records(path, items, as_jsonl=True)


def write_records(path: Path, items: list[dict[str, Any]], *, as_jsonl: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if as_jsonl or path.suffix == ".jsonl":
        with path.open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(dumps_json(item) + "\n")
        return
    with path.open("w", encoding="utf-8") as handle:
        handle.write(dumps_json(items, indent=2) + "\n")
