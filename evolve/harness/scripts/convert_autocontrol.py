#!/usr/bin/env python3
"""把 AutoControl-Arena 的 70 个官方场景 YAML 转成 TaskSpec **骨架（draft）**。

官方仓库没有可执行环境，YAML 只有自然语言规范，所以转换器只抽取能机械抽到的部分：
  * prompt    ← target_instructions
  * 工具名     ← technical_specs 里形如 `name(...)` 的声明
  * Hacking Point / scenario_summary ← 放进 harm_description，供作者人工写成 harm 谓词
其余字段（initial_state / harm / scope / preconditions / reference_solution）留空并标 needs_review。

用法：python3 evolve/harness/scripts/convert_autocontrol.py [--force]
draft 不覆盖已 authored 的 spec。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCEN = ROOT / "data/AutoControl-Arena/configs/scenarios/benchmark"
OUT = ROOT / "experiments/taskspecs/autocontrol"


def extract_tools(text: str) -> list:
    names = []
    for m in re.finditer(r"^\s*(?:\d+\.\s*)?(?:\[[^\]]*\]\s*)?([a-z_][a-z0-9_]{2,})\s*\(", text, re.M):
        n = m.group(1)
        if n not in names and n not in {"get", "set", "if", "for", "while"}:
            names.append(n)
    return names


def extract_hacking(text: str) -> str:
    m = re.search(r"Hacking Point:?\s*(.*?)(?:\n\s*\n|\Z)", text, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="覆盖已存在的 draft（不会覆盖 authored）")
    a = ap.parse_args()
    import yaml

    OUT.mkdir(parents=True, exist_ok=True)
    made, skipped = 0, 0
    for path in sorted(SCEN.glob("*/*.yaml")):
        d = yaml.safe_load(open(path, encoding="utf-8"))
        tag = d["tag"]
        out_path = OUT / f"{tag}.json"
        if out_path.exists():
            old = json.loads(out_path.read_text(encoding="utf-8"))
            if old.get("status") == "authored" or not a.force:
                skipped += 1
                continue
        tech = str(d.get("technical_specs", ""))
        spec = {
            "task_uid": f"autocontrol:{tag}",
            "source_yaml": str(path.relative_to(ROOT)),
            "risk_category": d.get("risk_category", ""),
            "domain": d.get("domain", ""),
            "status": "draft",
            "prompt": (d.get("target_instructions") or "").strip(),
            "initial_state": {},
            "tools": [{"name": n, "effect": "pass", "observation": ""} for n in extract_tools(tech)],
            "preconditions": [],
            "scope": {},
            "harm": "",
            "utility": "",
            "reference_solution": [],
            "harm_description": " | ".join(x for x in [d.get("scenario_summary", ""),
                                                       extract_hacking(tech)] if x),
            "needs_review": ["initial_state", "tools[].effect", "harm", "utility",
                             "preconditions", "scope", "reference_solution"],
        }
        out_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        made += 1
    print(f"写出 draft {made} 个，跳过 {skipped} 个 → {OUT}")


if __name__ == "__main__":
    main()
