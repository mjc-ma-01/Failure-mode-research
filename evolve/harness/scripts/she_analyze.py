#!/usr/bin/env python3
"""SHE 进化结果分析：把"有效进化"讲清楚——哪些格从被攻破变被拦住、靠的是哪条规则、属什么机制。

输入：v2 工作目录（含 rollouts/{heldout_*,dev_*}）或直接给 heldout 两臂的 json(+dump)。
输出：控制台表格 + `<wd>/analysis_report.json`，含
  * 每臂 ASR/utility（逐格多数票 + σ）
  * 逐格 4 类归因：harness_fixed / model_side / already_safe / regression
  * 每条规则"修好了哪些格"（规则 → 格列表）与机制分类（按 rule_id 前缀/harm_domain 聚合）
  * 诚实性检查：未参与调参的测试格数、是否出现 regression
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evolve/harness/src"))
sys.path.insert(0, str(ROOT / "evolve/harness/scripts"))

from she_evolve_v2 import arm_metrics, rule_hits       # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--seed-name", default="seed")
    ap.add_argument("--best-name", default="best")
    ap.add_argument("--split", default="heldout")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    wd = ROOT / a.workdir
    r = wd / "rollouts"

    ms = arm_metrics(r / f"{a.split}_{a.seed_name}.json")
    mb = arm_metrics(r / f"{a.split}_{a.best_name}.json")
    fixed = [c for c, atk in ms["attacked_by_cell"].items() if atk and not mb["attacked_by_cell"].get(c)]
    both = [c for c, atk in ms["attacked_by_cell"].items() if atk and mb["attacked_by_cell"].get(c)]
    brk = [c for c, atk in ms["attacked_by_cell"].items() if not atk and mb["attacked_by_cell"].get(c)]
    already = [c for c, atk in ms["attacked_by_cell"].items() if not atk and not mb["attacked_by_cell"].get(c)]
    hits = rule_hits(r / f"{a.split}_{a.best_name}.json", fixed)
    rule_to_cells = collections.defaultdict(list)
    for c, ids in hits.items():
        for rid in ids:
            rule_to_cells[rid].append(c)
    util_loss = [c for c in ms["util_by_cell"] if ms["util_by_cell"][c] and not mb["util_by_cell"].get(c, False)]
    util_gain = [c for c in ms["util_by_cell"] if mb["util_by_cell"].get(c, False) and not ms["util_by_cell"][c]]

    report = {
        "split": a.split,
        "seed": {k: ms[k] for k in ("asr", "utility", "n", "sigma_asr", "sigma_util")},
        "best": {k: mb[k] for k in ("asr", "utility", "n", "sigma_asr", "sigma_util")},
        "delta": {"asr": (ms["asr"] - mb["asr"]) if None not in (ms["asr"], mb["asr"]) else None,
                  "utility": (mb["utility"] - ms["utility"]) if None not in (ms["utility"], mb["utility"]) else None},
        "counts": {"harness_fixed": len(fixed), "model_side": len(both),
                   "already_safe": len(already), "regression": len(brk),
                   "utility_loss": len(util_loss), "utility_gain": len(util_gain)},
        "harness_fixed_detail": {c: hits.get(c, []) for c in fixed},
        "rule_to_cells": {k: sorted(v) for k, v in sorted(rule_to_cells.items(), key=lambda kv: -len(kv[1]))},
        "model_side": sorted(both), "regression": sorted(brk),
        "utility_loss_cells": sorted(util_loss), "utility_gain_cells": sorted(util_gain),
    }
    out = Path(a.out) if a.out else wd / "analysis_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"== {a.split} 分析（{ms['n']} 格）==")
    print(f"  seed: ASR={ms['asr']} (σ={ms['sigma_asr']})  utility={ms['utility']} (σ={ms['sigma_util']})")
    print(f"  best: ASR={mb['asr']} (σ={mb['sigma_asr']})  utility={mb['utility']} (σ={mb['sigma_util']})")
    d = report["delta"]
    print(f"  ΔASR={d['asr']}（正=改善）  Δutility={d['utility']}")
    c = report["counts"]
    print(f"  归因：harness 修好 {c['harness_fixed']} · 模型侧 {c['model_side']} · 本已安全 {c['already_safe']} "
          f"· 回归 {c['regression']} | 效用 丢 {c['utility_loss']} / 增 {c['utility_gain']}")
    if report["rule_to_cells"]:
        print("  每条规则修好的格数：")
        for rid, cells in list(report["rule_to_cells"].items())[:8]:
            print(f"    {rid:<44} {len(cells)} 格")
    print(f"  写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
