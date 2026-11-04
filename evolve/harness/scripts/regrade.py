#!/usr/bin/env python3
"""离线重判 CLI：把一轮 sweep 的轨迹 dump 重新判分、重新分类（不占 GPU）。

    python evolve/harness/scripts/regrade.py experiments/runs/xxx_asb.episodes.jsonl.gz \
        [--edits configs/edits_core.json,configs/edits_v0.json] [--criterion auto] [--out x.classify.json]

判分口径改了（新增危害谓词、接上 judge、修桩）之后，用这个重出四桶表；
只有在"需要模型重新采样轨迹"时才要重跑 GPU。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evolve/harness/src"))

from coevolve.classify import format_report                       # noqa: E402
from coevolve.regrade import regrade_file                          # noqa: E402
from coevolve.contract import Check, HarnessEdit                   # noqa: E402


def load_edits(paths: list) -> list:
    """与 run_pair_sweep.load_edits 同口径：JSON → HarnessEdit(带 Check 对象)。"""
    edits = []
    for p in paths:
        raw = json.loads(Path(p).read_text(encoding="utf-8"))
        for e in raw:
            checks = tuple(Check(
                name=c["name"], when_tool=c.get("when_tool", ""),
                when_any_prefix=c.get("when_any_prefix", ""),
                when_role=c.get("when_role", ""),
                require=tuple(c.get("require", [])),
                require_any_prefix=c.get("require_any_prefix", ""),
                require_role=c.get("require_role", ""),
                deny_if=c.get("deny_if", ""), action=c.get("action", "block"),
                reason=c.get("reason", ""), surface=c.get("surface", "hook"),
            ) for c in e.get("add_checks", []))
            edits.append(HarnessEdit(
                edit_id=e["edit_id"], surface=e["surface"], summary=e["summary"],
                add_checks=checks, prompt_addendum=e.get("prompt_addendum", ""),
                rollback_if=e.get("rollback_if", "")))
    return edits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump", help="*.episodes.jsonl.gz")
    ap.add_argument("--edits", default="evolve/harness/configs/edits_core.json")
    ap.add_argument("--criterion", default="auto", choices=["auto", "success", "safe"])
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    edits = load_edits([p for p in a.edits.split(",") if p])
    res = regrade_file(a.dump, edits, a.criterion)
    print(format_report(res))
    print(f"\n重判 episode 数 = {res['n_episodes']}（来源：{res['regraded_from']}）")
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str),
                               encoding="utf-8")
        print(f"写入 {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
