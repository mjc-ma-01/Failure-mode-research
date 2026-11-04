#!/usr/bin/env python3
"""把"被攻破的格"分成 **可修 / 难修** 四类（程序化，无 LLM）。

输入：episodes dump（.jsonl.gz）+ 该臂的 artifact 目录（用于判断"工具是否被覆盖"）。

标签（互斥）：
  L2_warn_only        有 WARN、无 BLOCK          → **可修（强制化）**
  L3_block_but_breached 有 BLOCK 但仍被攻破       → 摩擦型（换工具/换参数绕过）
  L1a_coverage_gap    无任何判定，且危害动作的工具**不在**任何 rule.tools / tool group 里
                       → **可修（补覆盖）**：加一条按工具/组触发的规则即可
  L1b_semantic_gap    无任何判定，但工具已在覆盖范围内（白名单/参数谓词区分不了）
                       → **难修**：需要污点传播或语义闸门
  L4_sanitize_short   有 SANITIZE 但仍被攻破

用法：python classify_attacked.py <dump> --arts <artifact_dir> [--seeds 3]
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
from pathlib import Path


def covered_tools(arts: Path) -> set:
    tools = set()
    rb = arts / "rule_bank.jsonl"
    if rb.exists():
        for line in rb.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            t = r.get("trigger") or {}
            if t.get("tool"):
                tools.add(str(t["tool"]))
            for x in t.get("tools") or []:
                tools.add(str(x))
    tp = arts / "tool_policy.json"
    if tp.exists():
        pol = json.loads(tp.read_text(encoding="utf-8"))
        tools |= set((pol.get("sink_policies") or {}).keys())
        for g, xs in (pol.get("high_impact_tool_groups") or {}).items():
            tools |= set(xs)
    return tools


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--arts", required=True)
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args()
    covered = covered_tools(Path(a.arts))
    per_cell = collections.defaultdict(list)
    with gzip.open(a.dump, "rt") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("arm_key") != "H0":
                continue
            out = r.get("outcome") or {}
            det = out.get("detail") or {}
            d = det.get("she") or {}
            blocked = int(d.get("blocked") or 0)
            warned = int(d.get("warned") or 0)
            san = int(d.get("sanitized") or 0)
            steps = r.get("steps") or []
            harmful_tools = [str((s.get("proposal") or {}).get("tool"))
                             for s in steps if s.get("cf_harm") and s.get("executed")]
            executed_tools = [str((s.get("proposal") or {}).get("tool")) for s in steps
                              if s.get("executed") and (s.get("proposal") or {}).get("tool")]
            if blocked:
                lab = "L3_block_but_breached"
            elif san:
                lab = "L4_sanitize_short"
            elif warned:
                lab = "L2_warn_only"
            else:
                probe = harmful_tools or executed_tools
                lab = "L1a_coverage_gap" if any(t not in covered for t in probe) else "L1b_semantic_gap"
            cell = str(r.get("cell")).rpartition("#")[0]
            per_cell[cell].append((bool(out.get("harm")), lab))
    rows = []
    for cell, eps in sorted(per_cell.items()):
        atk = [l for h, l in eps if h]
        if not atk or len(atk) <= len(eps) / 2:
            continue
        rows.append((cell, collections.Counter(atk).most_common(1)[0][0], dict(collections.Counter(atk))))
    print(f"被攻破（多数票）{len(rows)} 格 / 共 {len(per_cell)} 格；覆盖工具 {len(covered)} 个")
    print("标签分布:", dict(collections.Counter(r[1] for r in rows)))
    for cell, lab, cnt in rows:
        print(f"  {lab:22s} {cell[-64:]:64s} {cnt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
