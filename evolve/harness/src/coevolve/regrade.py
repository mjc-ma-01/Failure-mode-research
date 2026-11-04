"""离线重判：用 dump 里的轨迹 + 最终状态重算 oracle，**不重跑 GPU**。

为什么需要：一轮 sweep 的产物在旧版本里只有判定标量（success/harm/...），判分口径一改就
只能重跑。现在 `run_pair_sweep.py --dump-episodes` 会落一份 `*.episodes.jsonl.gz`，每行：

    {task_uid, arm, seed, termination, outcome, steps, ledger, state_blob_b64, ...}

`regrade()` 用 `state_blob_b64` 重建环境（各 adapter 的 `from_state_blob`），调用**当前**
的 `outcome()`，再走同一个 `classify()` —— 于是"改判分"变成纯离线动作。

用法（见 scripts/regrade.py）：
    python scripts/regrade.py <dump.jsonl.gz> [--criterion auto] [--out x.json]
"""
from __future__ import annotations

import base64
import gzip
import json
import pickle
from pathlib import Path

from .contract import Episode, Step


class _StepLike:
    """dump 里的 step 记录 → 适配器 set_trajectory 需要的鸭子对象。"""

    def __init__(self, d: dict):
        self.index = d.get("i", 0)
        self.proposal = d.get("proposal") or {}
        self.executed = bool(d.get("executed"))
        self.observation = d.get("observation") or ""
        self.decision = d.get("decision") or {}
        self.state_facts = {}


def _restore(source: str, blob: dict):
    if source == "asb":
        from .adapters.asb_env import ASBEnv
        return ASBEnv.from_state_blob(blob)
    if source == "agentdojo":
        from .adapters.agentdojo_env import AgentDojoEnv
        return AgentDojoEnv.from_state_blob(blob)
    if source == "autocontrol":
        from .adapters.autocontrol_env import AutoControlEnv
        return AutoControlEnv.from_state_blob(blob)
    if source == "agentharm":
        from .adapters.agentharm_env import AgentHarmEnv
        return AgentHarmEnv.from_state_blob(blob)
    raise ValueError(f"未知来源 {source}")


def reraise_outcome(rec: dict) -> dict:
    """重算一条 episode 的 outcome（不改轨迹、不改 harness）。失败 → 判分不可用。"""
    blob_b64 = rec.get("state_blob_b64")
    if not blob_b64:
        return dict(rec.get("outcome") or {}, judged=False,
                    detail={"error": "dump 里没有 state_blob（旧版本产物，无法离线重判）"})
    source = rec["task_uid"].split(":", 1)[0]
    try:
        env = _restore(source, pickle.loads(base64.b64decode(blob_b64)))
        # 把跑时的轨迹塞回环境：ASB 的 ShieldAgent 判分读 dialog，缺了它就只能判空对话
        if hasattr(env, "set_trajectory"):
            env.set_trajectory([_StepLike(s) for s in (rec.get("steps") or [])])
            if rec.get("final_output"):
                env._final = rec["final_output"]
        out = dict(env.outcome())
    except Exception as exc:
        return {"harm": None, "utility": None, "severe": None, "judged": False,
                "detail": {"error": f"regrade_failed: {type(exc).__name__}: {str(exc)[:160]}"}}
    # 与 runner.run_episode 同一条兜底规则：环境不给 utility 时，用"是否 finish 且无危害"
    if out.get("utility") is None:
        out["utility"] = bool(rec.get("termination") == "finish" and not out.get("harm"))
    return out


def load_dump(path: str | Path) -> list:
    p = Path(path)
    opener = gzip.open if str(p).endswith(".gz") else open
    with opener(p, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class Report(dict):
    """classify() 只依赖 `report.episodes`（cell → {arm: Episode}）。"""

    def __init__(self, episodes: dict):
        super().__init__()
        self.episodes = episodes
        self.errors_seen: list = []


def rebuild_report(records: list) -> Report:
    """把 dump 记录还原成 {cell: {arm: Episode}}，供 classify() 直接吃。"""
    episodes: dict = {}
    for rec in records:
        tools = rec.get("tools") or []
        ep = Episode(
            task_uid=rec["task_uid"], arm=rec["arm"], harness_name=rec.get("harness", rec["arm"]),
            harness_digest=rec.get("harness_digest", ""), model_id=rec.get("model_id", ""),
            seed=rec["seed"],
            # 用一条"证据步"承载工具集：Δ 的适用性判定（guard_matches）要靠它
            steps=[Step(index=0, proposal={}, state_facts={"tools": tools}, decision={},
                        executed=False, observation="", counterfactual_harm=False)],
            outcome=reraise_outcome(rec),
            proposed_harm=bool(rec.get("proposed_harm")),
            interventions=rec.get("interventions", []),
            termination=rec.get("termination", "finish"), ledger=rec.get("ledger", []))
        cell = rec.get("cell") or f"{rec['task_uid']}#{rec['seed']}"
        episodes.setdefault(cell, {})[rec.get("arm_key") or rec["arm"]] = ep
    return Report(episodes)


def regrade_file(path: str | Path, edits, criterion: str = "auto") -> dict:
    """读 dump → 重判 → 重新分类；返回 classify() 的结果结构。"""
    from .classify import classify
    records = load_dump(path)
    report = rebuild_report(records)
    srcs = {c.split(":", 1)[0] for c in report.episodes}
    if criterion == "auto":
        criterion = "safe" if ({"agentdojo", "autocontrol"} & srcs) else "success"
    result = classify(report, edits, criterion)
    result["n_episodes"] = len(records)
    result["regraded_from"] = str(path)
    return result
