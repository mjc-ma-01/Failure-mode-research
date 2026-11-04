"""配对实验：model+initial harness vs model+Δharness。

产出（本项目分类的实证来源）：
  * 转移表：fail→success / fail→fail / success→fail / success→success
  * 每个 (任务,种子) 的 Δ 反应向量
  * 失败"类型" = 反应向量相同的等价类（不预设 risk 分类）
"""
from __future__ import annotations

import collections
import json
from dataclasses import dataclass, field

from .contract import apply_edit
from .runner import run_episode


def _transition(before: bool, after: bool) -> str:
    if not before and after:
        return "fail2success"
    if not before and not after:
        return "fail2fail"
    if before and not after:
        return "success2fail"
    return "success2success"


def _pair_transition(ep0, ep1, criterion: str) -> str:
    """判分不可用的臂不许进转移表：否则"测不了"会被读成 fail2fail（修不动）。"""
    if not ep0.judged or not ep1.judged:
        return "unjudged"
    ok0 = ep0.safe if criterion == "safe" else ep0.success
    ok1 = ep1.safe if criterion == "safe" else ep1.success
    return _transition(ok0, ok1)


@dataclass
class PairReport:
    base_harness: str
    edits: list
    rows: list = field(default_factory=list)
    cell_vectors: dict = field(default_factory=dict)
    transitions: dict = field(default_factory=dict)
    episodes: dict = field(default_factory=dict)      # cell -> {arm: Episode}，供 F1–F4 标注
    errors_seen: list = field(default_factory=list)   # 单格失败记录（不中断整轮）

    def summary(self) -> dict:
        return {
            "base_harness": self.base_harness,
            "edits": self.edits,
            "transitions": {k: dict(v) for k, v in self.transitions.items()},
            "n_cells": len(self.cell_vectors),
        }

    def print_table(self) -> None:
        print(f"\n配对实验：base={self.base_harness}  单元格={len(self.cell_vectors)}")
        header = (f"{'Δ':<30}{'fail→success':>14}{'fail→fail':>12}{'success→fail':>14}"
                  f"{'success→success':>17}{'判分不可用':>12}")
        print(header)
        print("-" * len(header))
        for e in self.edits:
            c = self.transitions[e]
            print(f"{e:<30}{c['fail2success']:>14}{c['fail2fail']:>12}{c['success2fail']:>14}"
                  f"{c['success2success']:>17}{c.get('unjudged', 0):>12}")

    def failure_profile(self) -> dict:
        groups = collections.defaultdict(list)
        for cell, vec in self.cell_vectors.items():
            key = tuple(sorted((e, t) for e, t in vec.items()))
            groups[key].append(cell)
        return {
            " | ".join(f"{e}:{t}" for e, t in key): cells
            for key, cells in sorted(groups.items(), key=lambda kv: -len(kv[1]))
        }

    def to_json(self) -> str:
        return json.dumps(
            {"summary": self.summary(), "rows": self.rows,
             "cells": self.cell_vectors, "profiles": self.failure_profile()},
            ensure_ascii=False, indent=2,
        )


def run_pair(tasks, env_factory, model, base, edits, seeds=(0,), criterion: str = "success") -> PairReport:
    """跑配对实验。

    tasks: 元素需有 .uid / .prompt；env_factory(task, seed) 返回全新环境。
    """
    report = PairReport(base_harness=base.name, edits=[e.edit_id for e in edits])
    for e in edits:
        report.transitions[e.edit_id] = collections.Counter()

    for task in tasks:
        for seed in seeds:
            ep0 = run_episode(task, env_factory(task, seed), model, base, seed)
            cell = f"{task.uid}#{seed}"
            vec = {}
            for e in edits:
                delta_h = apply_edit(base, e)
                ep1 = run_episode(task, env_factory(task, seed), model, delta_h, seed)
                t = _pair_transition(ep0, ep1, criterion)
                vec[e.edit_id] = t
                report.transitions[e.edit_id][t] += 1
                report.rows.append({
                    "cell": cell, "edit": e.edit_id, "transition": t,
                    "base": ep0.to_row(), "delta": ep1.to_row(),
                })
            report.cell_vectors[cell] = vec
    return report
