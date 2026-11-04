#!/usr/bin/env python3
"""AutoControl-Arena 的分层均衡切分（7 个风险类别，train/held-out 不相交）。

每类按 uid 排序后奇偶交替：偶数下标 → train，奇数下标 → held-out。
产物：experiments/split_autocontrol_balanced/{train,heldout}.json
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evolve/harness/src"))

from coevolve.adapters.autocontrol_env import load_specs   # noqa: E402


def main() -> int:
    specs = load_specs(only_authored=True)
    by_cat = collections.defaultdict(list)
    for t in specs:
        by_cat[t.risk_category].append(t.uid)
    train, held = [], []
    for cat in sorted(by_cat):
        uids = sorted(by_cat[cat])
        train += uids[::2]
        held += uids[1::2]
        print(f"{cat:24s} n={len(uids):2d} train={len(uids[::2])} held={len(uids[1::2])}")
    out = ROOT / "experiments/split_autocontrol_balanced"
    out.mkdir(parents=True, exist_ok=True)
    for name, uids in (("train", train), ("heldout", held)):
        (out / f"{name}.json").write_text(json.dumps({"name": name, "n": len(uids), "uids": uids},
                                                     ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ac] {name:8s} {len(uids)} → {out/(name+'.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
