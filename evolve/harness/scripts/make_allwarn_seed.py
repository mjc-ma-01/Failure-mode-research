#!/usr/bin/env python3
"""把一份 SHE seed 变成 **全 WARN 起点**（规则可见但不拦截）——用来测量"进化能学回多少拦截"。

用法：python make_allwarn_seed.py <src_dir> <dst_dir>
  * rule_bank.jsonl：action BLOCK → WARN（保留 trigger/benign_exemption 等所有字段）
  * tool_policy.json：把所有 "BLOCK" 值改成 "WARN"；名字加 -allwarn
  * system_prompt.md / safety_memory.jsonl 原样拷贝
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def main() -> int:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    n_rules = 0
    with (src / "rule_bank.jsonl").open(encoding="utf-8") as fi, \
            (dst / "rule_bank.jsonl").open("w", encoding="utf-8") as fo:
        for line in fi:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("action") == "BLOCK":
                r["action"] = "WARN"
                n_rules += 1
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    pol = json.loads((src / "tool_policy.json").read_text(encoding="utf-8"))

    def relax(o):
        if isinstance(o, dict):
            return {k: ("WARN" if v == "BLOCK" else relax(v)) for k, v in o.items()}
        if isinstance(o, list):
            return [relax(v) for v in o]
        return o

    pol = relax(pol)
    pol["name"] = str(pol.get("name", src.name)) + "-allwarn"
    pol["notes"] = ("SHE seed（全 WARN 起点）：规则可见但不拦截，用来测「进化能从失败里学回多少拦截」；"
                    "over-refusal 由良性孪生格监控。")
    (dst / "tool_policy.json").write_text(json.dumps(pol, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(src / "system_prompt.md", dst / "system_prompt.md")
    if (src / "safety_memory.jsonl").exists():
        shutil.copy2(src / "safety_memory.jsonl", dst / "safety_memory.jsonl")
    print(f"[allwarn] {src} → {dst}（BLOCK→WARN 规则 {n_rules} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
