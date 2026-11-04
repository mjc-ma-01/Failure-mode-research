#!/usr/bin/env python3
"""把一个 SHE 实验 workdir 的产物汇总成中文 markdown 报告（seed vs 进化后 harness）。

用法：python summarize_run.py <workdir> [--out report.md]
读取：state.json / result_table.json / rollouts/*.json(.meta.json/.runtime.json)
输出：R0 基线、逐轮门控（σ、是否接受）、heldout 终测表、逐格归因（harness 可解 / 模型侧 / 回归 / 过拦）。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    wd = ROOT / a.workdir
    rt = load(wd / "result_table.json")
    st = load(wd / "state.json")
    meta = None
    for p in sorted((wd / "rollouts").glob("*.meta.json")):
        meta = load(p)
        break

    L = []
    L.append(f"# SHE 实验汇总：`{a.workdir}`\n")
    if meta:
        L.append(f"- victim：`{meta.get('model')}` @ `{meta.get('base_url')}`"
                 f"（seeds={meta.get('seeds')}）")
        L.append(f"- 任务：split 切分 uids / n_tasks={meta.get('n_tasks')}")
    if st:
        L.append(f"- 轮次：epoch={st.get('epoch')} stale={st.get('stale')} anchor=`{st.get('best')}`")
    L.append("")

    if rt:
        L.append("## 终测（held-out，3 seed 多数票）\n")
        has_ua = any("ua" in (v or {}) for v in (rt.get("table") or {}).values())
        L.append("| arm | ASR | σ_ASR | UA | utility | σ_U | plain_U | n |" if has_ua
                 else "| arm | ASR | σ_ASR | utility | σ_U | plain_U | n |")
        L.append("|---|---|---|---|---|---|---|---|" if has_ua else "|---|---|---|---|---|---|---|")
        for k, v in (rt.get("table") or {}).items():
            if has_ua:
                L.append(f"| {k} | {v.get('asr')} | {v.get('sigma_asr')} | {v.get('ua')} | "
                         f"{v.get('utility')} | {v.get('sigma_util')} | {v.get('plain_utility')} | {v.get('n')} |")
            else:
                L.append(f"| {k} | {v.get('asr')} | {v.get('sigma_asr')} | {v.get('utility')} | "
                         f"{v.get('sigma_util')} | {v.get('plain_utility')} | {v.get('n')} |")
        att = rt.get("attribution") or {}
        c = att.get("counts") or {}
        L.append("")
        L.append("## 逐格归因\n")
        L.append(f"- harness 进化修好（seed 被攻破 → best 挡住）：**{c.get('harness_fixed')}** / {c.get('n')}")
        L.append(f"- 两臂都被攻破（**模型侧/进化未解**）：**{c.get('model_side')}**")
        L.append(f"- 回归（seed 挡住 → best 被攻破）：**{c.get('regression')}**")
        if att.get("harness_fixed"):
            L.append("")
            L.append("| 修好的格 | 命中的规则 |")
            L.append("|---|---|")
            for cell, rules in (att["harness_fixed"] or {}).items():
                L.append(f"| `{cell}` | {', '.join(rules) if rules else '-'} |")
        if att.get("model_side"):
            L.append("")
            L.append("模型侧（两臂都被攻破）：")
            for cell in att["model_side"]:
                L.append(f"- `{cell}`")
        if att.get("regression"):
            L.append("")
            L.append("回归：")
            for cell in att["regression"]:
                L.append(f"- `{cell}`")
    else:
        L.append("（还没有 result_table.json：实验未到终测）")

    log = (rt or {}).get("log") or (st or {}).get("log") or []
    if log:
        L.append("")
        L.append("## 进化过程（门控）\n")
        for e in log:
            m = e.get("metrics") or {}
            line = f"- e{e.get('epoch')} {e.get('role')}/{e.get('name', '-')}: " \
                   f"ASR={m.get('asr')} U={m.get('utility')}"
            if "threshold_2sigma" in e:
                line += f"（门限 -{e['threshold_2sigma']}）"
            if "accepted" in e:
                line += f" accepted={e['accepted']}"
            if e.get("confirm"):
                line += f" confirm={e['confirm']}"
            L.append(line)
    txt = "\n".join(L) + "\n"
    out = Path(a.out) if a.out else wd / "SUMMARY.md"
    out.write_text(txt, encoding="utf-8")
    print(txt)
    print(f"[summarize] 写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
