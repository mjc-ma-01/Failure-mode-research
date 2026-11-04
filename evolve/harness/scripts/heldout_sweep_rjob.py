#!/usr/bin/env python3
"""held-out 横扫（GPU 作业版）：seed + 指定候选/anchor 一次评测完，输出表。

用法：
  python heldout_sweep_rjob.py --workdir experiments/she_ad_balanced \
      --seed-dir evolve/harness/configs/harness/SHE_agentdojo_seed_allwarn \
      --arms seed,H_best_e1,cand_e2_1,H_best_e2 [--tag sweep1]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evolve/harness/src"))
sys.path.insert(0, str(ROOT / "evolve/harness/scripts"))

from she_evolve_v2 import arm_metrics                       # noqa: E402
from she_orchestrator import submit_and_wait               # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--seed-dir", required=True)
    ap.add_argument("--arms", required=True, help="逗号分隔：seed / H_best_e1 / cand_e2_1 ...")
    ap.add_argument("--uids", default="experiments/split_agentdojo_balanced/heldout.json")
    ap.add_argument("--plain-uids", default="experiments/split_agentdojo_balanced/plain_heldout.json")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--tag", default="sweep")
    a = ap.parse_args()
    wd = ROOT / a.workdir
    out_dir = wd / "heldout_sweep"
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = []
    for name in [x.strip() for x in a.arms.split(",") if x.strip()]:
        d = ROOT / a.seed_dir if name == "seed" else wd / name
        if not (d / "rule_bank.jsonl").exists():
            print(f"[sweep] 跳过不存在的臂 {name} ({d})")
            continue
        variants.append({"name": name, "kind": "she", "dir": str(d)})
    print(f"[sweep] {len(variants)} 臂: {[v['name'] for v in variants]}", flush=True)

    man = {"split": "heldout", "limit": 0, "offset": 0, "task_mode": "injection",
           "seeds": a.seeds, "out_dir": str(out_dir), "variants": variants, "edits": "",
           "uids_file": str(ROOT / a.uids)}
    submit_and_wait(man, a.tag)
    man_p = {"split": "heldout", "limit": 0, "offset": 0, "task_mode": "plain",
             "seeds": [a.seeds[0]], "out_dir": str(out_dir), "variants": variants, "edits": "",
             "uids_file": str(ROOT / a.plain_uids)}
    submit_and_wait(man_p, f"{a.tag}_plain")

    table, cells = {}, {}
    for v in variants:
        p = out_dir / f"heldout_{v['name']}.json"
        if not p.exists():
            continue
        m = arm_metrics(p)
        mp_path = out_dir / f"heldout_{v['name']}_plain.json"
        mp = arm_metrics(mp_path) if mp_path.exists() else {}
        table[v["name"]] = {"asr": m["asr"], "ua": m.get("ua"), "utility": m["utility"],
                            "sigma_asr": m["sigma_asr"], "n": m["n"],
                            "plain_utility": mp.get("utility")}
        cells[v["name"]] = m["attacked_by_cell"]
    ref = cells.get("seed") or {}
    lines = ["| arm | ASR | UA | utility | plain_U | 相对 seed 新挡住 |", "|---|---|---|---|---|---|"]
    for name, t in table.items():
        fixed = [c for c, atk in ref.items() if atk and not cells[name].get(c, False)]
        lines.append(f"| {name} | {t['asr']} | {t['ua']} | {t['utility']} | {t['plain_utility']} | {len(fixed)} |")
    (out_dir / "TABLE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "table.json").write_text(json.dumps({"table": table, "cells": cells},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print(f"[sweep] 写入 {out_dir/'TABLE.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
