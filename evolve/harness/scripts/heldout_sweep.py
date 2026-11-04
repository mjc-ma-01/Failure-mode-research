#!/usr/bin/env python3
"""held-out 横扫：把 **seed + 所有候选 harness + 已接受 anchor** 一次性在 held-out 上评测。

目的：严格门控（2σ）可能把"有效但幅度不够大"的候选全部否掉；横扫给出不受门控影响的
证据——哪些格子的注入能被 Δharness 挡住、哪些两臂都挡不住（模型侧）。

用法（宿主机 API 通道）：
  python heldout_sweep.py --workdir experiments/she_ad_api2 \
    --seed-dir evolve/harness/configs/harness/SHE_agentdojo_seed_allwarn \
    --offset 32 --seeds 0 1 2 --workers 20
输出：<workdir>/heldout_sweep/{table.json, TABLE.md}
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evolve/harness/src"))
sys.path.insert(0, str(ROOT / "evolve/harness/scripts"))

from she_evolve_v2 import arm_metrics          # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--seed-dir", required=True)
    ap.add_argument("--offset", type=int, default=32)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--gateway", default="/mnt/shared-storage-user/majiachen/.config/fmr/proposer.json")
    ap.add_argument("--victim-model", default="api:Qwen/Qwen3.5-9B")
    ap.add_argument("--victim-extra", default='{"enable_thinking": false}')
    a = ap.parse_args()

    wd = ROOT / a.workdir
    out_dir = wd / "heldout_sweep"
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(Path(a.gateway).read_text(encoding="utf-8"))

    variants = [{"name": "seed", "kind": "she", "dir": str(ROOT / a.seed_dir)}]
    for p in sorted(wd.glob("cand_e*")):
        if (p / "rule_bank.jsonl").exists():
            variants.append({"name": p.name, "kind": "she", "dir": str(p)})
    for p in sorted(wd.glob("H_best*")):
        if p.name == "H_best" or (p / "rule_bank.jsonl").exists():
            variants.append({"name": p.name, "kind": "she", "dir": str(p)})
    # 去重（同名 dir）
    seen, uniq = set(), []
    for v in variants:
        if v["name"] in seen:
            continue
        seen.add(v["name"])
        uniq.append(v)
    variants = uniq
    print(f"[sweep] {len(variants)} 个臂：{[v['name'] for v in variants]}", flush=True)

    man = {"split": "heldout", "limit": a.limit, "offset": a.offset, "task_mode": "injection",
           "seeds": a.seeds, "out_dir": str(out_dir), "variants": variants, "edits": ""}
    mp = out_dir / "manifest_heldout_sweep.json"
    mp.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    cmd = [sys.executable, str(ROOT / "evolve/harness/scripts/she_rollout.py"),
           "--manifest", str(mp), "--base-url", cfg["base_url"], "--workers", str(a.workers),
           "--model", a.victim_model, "--api-key", cfg["api_key"],
           "--victim-extra", a.victim_extra, "--max-tokens", "512"]
    print("[sweep] rollout: " + " ".join(cmd[:6]) + " ...", flush=True)
    subprocess.run(cmd, check=True, cwd=str(ROOT))

    # 汇总 + 归因（相对 seed 臂）
    table = {}
    for v in variants:
        p = out_dir / f"heldout_{v['name']}.json"
        if not p.exists():
            continue
        m = arm_metrics(p)
        table[v["name"]] = {"asr": m["asr"], "sigma_asr": m["sigma_asr"], "utility": m["utility"],
                            "sigma_util": m["sigma_util"], "n": m["n"],
                            "attacked_by_cell": m["attacked_by_cell"], "util_by_cell": m["util_by_cell"]}
    ref = table.get("seed", {})
    lines = ["# held-out 横扫（seed vs 各候选 harness）\n",
             "| arm | ASR | σ_ASR | utility | σ_U | 相对 seed 的 ΔASR | 新挡住的格 |",
             "|---|---|---|---|---|---|---|"]
    detail = {}
    for name, t in table.items():
        fixed = [c for c, atk in (ref.get("attacked_by_cell") or {}).items()
                 if atk and not (t.get("attacked_by_cell") or {}).get(c, False)]
        d = (t["asr"] - ref["asr"]) if (ref.get("asr") is not None and t.get("asr") is not None) else None
        lines.append(f"| {name} | {t['asr']} | {t['sigma_asr']} | {t['utility']} | {t['sigma_util']} | "
                     f"{'%+.4f' % d if d is not None else '-'} | {len(fixed)} |")
        detail[name] = {"newly_blocked": fixed}
        print(f"[sweep] {name}: ASR={t['asr']} U={t['utility']} 新挡住={len(fixed)}")
    (out_dir / "table.json").write_text(json.dumps({"table": {k: {kk: vv for kk, vv in v.items()
                                                                  if kk not in ("attacked_by_cell", "util_by_cell")}
                                                            for k, v in table.items()},
                                                    "detail": detail},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "TABLE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"[sweep] 写入 {out_dir/'table.json'} 与 TABLE.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
