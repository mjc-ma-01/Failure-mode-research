#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/full"
ANALYSIS = RUN / "analysis/analysis.json"
OUT = HERE / "RESULTS.md"


LABELS = {
    "Instrumental Convergence": "Instrumental Convergence",
    "Oversight Evasion": "Oversight Evasion",
    "Specification Gaming": "Specification Gaming",
    "Covert Whistleblowing": "Covert Whistleblowing",
    "Evaluation Awareness": "Evaluation Awareness",
    "Strategic Misalignment": "Strategic Misalignment",
}


def pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def cell(stats: dict) -> str:
    return f"{pct(stats['risk_rate'])} / {pct(stats['task_success_rate'])}"


def main() -> None:
    data = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    arms = ("base", "base+react", "base+react+safeharness")
    names = {"base": "M", "base+react": "M+H", "base+react+safeharness": "M+H+ΔH"}
    lines = [
        "# AutoControl Arena 全量三臂结果",
        "",
        "每个单元格为 **risk rate / task-success utility**。本表覆盖 60 个原始场景、",
        "240 个四条件变体、每变体 3 次 rollout，因此每臂 720 条。",
        "",
        "| 类别 | M | M+H | M+H+ΔH |",
        "|---|---:|---:|---:|",
    ]
    for category in LABELS:
        stats = data["by_category"][category]
        lines.append(f"| {LABELS[category]} | " + " | ".join(cell(stats[arm]) for arm in arms) + " |")
    lines.extend(["", "## 总体", "", "| 臂 | Risk | Task success | Helpfulness | Safe + success | Security block episode / call |", "|---|---:|---:|---:|---:|---:|"])
    for arm in arms:
        s = data["overall"][arm]
        lines.append(
            f"| {names[arm]} | {s['risky_n']}/{s['n']} = {pct(s['risk_rate'])} | "
            f"{s['task_success_n']}/{s['n']} = {pct(s['task_success_rate'])} | "
            f"{s['helpfulness_mean']:.3f} | {pct(s['safe_and_success_rate'])} | "
            f"{s['security_blocked_episodes']} / {s['security_blocked_calls']} |"
        )
    lines.extend(["", "## 配对转移", ""])
    for key, title in (("M_to_M_plus_H", "M → M+H"), ("M_plus_H_to_M_plus_H_plus_deltaH", "M+H → M+H+ΔH")):
        c = data["comparisons"][key]
        lines.append(f"### {title}")
        lines.append("")
        for transition, count in sorted(c["risk_transitions"].items()):
            blocked = c.get("risk_transitions_with_treatment_block", {}).get(transition, 0)
            lines.append(f"- `{transition}`: {count}，其中 treatment 有真实 security block {blocked} 条。")
        lines.append("")
    lines.extend([
        "## 实验边界",
        "",
        "- Risk 和 utility 都是对完整 action trajectory 的 Monitor 判定，不是谓词匹配。",
        "- 置信区间按 60 个原始场景聚类；四变体和三次 rollout 不当作独立新场景。",
        "- ReAct action-format 终止失败保留在分母中，不用删除失败轨迹美化结果。",
        "- `M+H+ΔH` 的改善只有在伴随真实 block 时才可归因为执行层拦截；无 block 转移需要单独审查。",
        "",
    ])
    OUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
