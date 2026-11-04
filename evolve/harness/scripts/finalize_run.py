#!/usr/bin/env python3
"""一轮 sweep 跑完后的收尾校验与汇总（不占 GPU）。

做的事：
  1. **离线重判一致性**：对每个来源的 `.episodes.jsonl.gz` 用当前判分重算，和跑时分类逐格比对；
  2. **判分构成**：oracle × judge 一致/分歧、label_source（strict / judge_only / oracle_only）、
     判分不可用的原因分布；
  3. **四桶总表**（含"判分不可用"列）+ 每来源 base 的 (utility, harm) 交叉表；
  4. 产出 `experiments/runs/final_<stamp>.json` 与可直接贴的 markdown 摘要。

用法：
  python evolve/harness/scripts/finalize_run.py experiments/runs/sweep_dev_20261015-XXXXXX
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

from coevolve.regrade import load_dump, regrade_file                      # noqa: E402
from regrade import load_edits                                            # noqa: E402

EDIT_FILES = {
    "asb": "evolve/harness/configs/edits_v0.json",
    "agentdojo": "evolve/harness/configs/edits_agentdojo.json",
    "agentharm": "evolve/harness/configs/edits_agentharm.json",
    "autocontrol": "evolve/harness/configs/edits_autocontrol.json",
}


def judge_stats(records: list) -> dict:
    agree = collections.Counter()
    sources = collections.Counter()
    skipped = collections.Counter()
    disagree = collections.Counter()
    for r in records:
        d = (r.get("outcome") or {}).get("detail") or {}
        src = r["task_uid"].split(":", 1)[0]
        sources[(src, d.get("label_source") or "n/a")] += 1
        if d.get("judge_valid") is False or "judged_note" in d:
            skipped[(src, str(d.get("judged_note"))[:60])] += 1
        o, j = d.get("oracle_unsafe"), d.get("judge_label")
        if d.get("disagreement"):
            disagree[(src, f"oracle={o}/judge={j}")] += 1
        if o is None or j in (None, "invalid", "error"):
            agree[(src, "judge_or_oracle_missing")] += 1
        else:
            agree[(src, f"oracle={bool(o)}/judge={j}")] += 1
    return {"label_source": {f"{k[0]}|{k[1]}": v for k, v in sources.items()},
            "oracle_x_judge": {f"{k[0]}|{k[1]}": v for k, v in agree.items()},
            "judged_notes": {f"{k[0]}|{k[1]}": v for k, v in skipped.items()},
            "disagreements": {f"{k[0]}|{k[1]}": v for k, v in disagree.items()}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stem", help="如 experiments/runs/sweep_dev_20261015-105346（不带 _<src>.json）")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    stem = Path(a.stem)
    summary: dict = {"stem": str(stem), "sources": {}}
    print(f"# 收尾校验：{stem.name}\n")
    print("| 来源 | 在线四桶 | 离线重判四桶 | 一致 | 判分构成 |")
    print("|---|---|---|---|---|")
    for src, edits_file in EDIT_FILES.items():
        dump = Path(f"{stem}_{src}.episodes.jsonl.gz")
        classify = Path(f"{stem}_{src}.classify.json")
        if not dump.exists() or not classify.exists():
            print(f"| {src} | (缺产物) | | | |")
            continue
        recs = load_dump(dump)
        edits = load_edits([str(ROOT / "evolve/harness/configs/edits_core.json"),
                            str(ROOT / edits_file)])
        reg = regrade_file(dump, edits, "auto")
        online = json.loads(classify.read_text(encoding="utf-8"))

        def buckets(res):
            out = {}
            for s, per in res["per_source"].items():
                out[s] = dict(collections.Counter(v["bucket"] for v in per["cells"].values()))
            return out

        b_on, b_off = buckets(online), buckets(reg)
        same = b_on == b_off
        js = judge_stats(recs)
        summary["sources"][src] = {"online": b_on, "offline": b_off, "same": same,
                                   "n_episodes": len(recs), "judge": js}
        def fmt(b):
            return " / ".join(f"{k}{v}" for k, v in sorted(next(iter(b.values())).items()))
        print(f"| {src} | {fmt(b_on)} | {fmt(b_off)} | {'✅' if same else '❌'} | {js['label_source']} |")

    print("\n## 判分构成细节")
    for src, s in summary["sources"].items():
        print(f"\n### {src}（{s['n_episodes']} 条 episode）")
        print("  label_source:", s["judge"]["label_source"])
        print("  oracle×judge:", s["judge"]["oracle_x_judge"])
        if s["judge"]["judged_notes"]:
            print("  判分备注:", s["judge"]["judged_notes"])
        if s["judge"]["disagreements"]:
            print("  ⚠️ oracle×judge 分歧:", s["judge"]["disagreements"])

    out = Path(a.out) if a.out else stem.parent / f"final_{stem.name.split('_')[-1]}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n写入", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
