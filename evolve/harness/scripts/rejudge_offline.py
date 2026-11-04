#!/usr/bin/env python3
"""离线重判（带 judge）：GPU 作业只采轨迹，判分在宿主机做。

为什么：容器里连不上 judge 网关（实测超时）、本地 ShieldAgent 缺 CUDA 库；
而 dump 里有轨迹 + 状态，宿主机有网络 → 判分在这里做，顺带还能反复改判分口径。

用法：
  python evolve/harness/scripts/rejudge_offline.py experiments/runs/sweep_dev_<stamp> \
      [--judge glm-5.3] [--asb local|api|off] [--ac api|off] [--agentharm api|off] [--workers 8]

产出（每个来源）：
  <stem>_<src>.judged.jsonl        —— 每条 episode 的新 outcome（含 oracle/judge/strict/分歧）
  <stem>_<src>.judged.classify.json —— 用新判分重跑的四桶表
"""
from __future__ import annotations

import argparse
import base64
import collections
import json
import pickle
import sys
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evolve/harness/src"))
sys.path.insert(0, str(ROOT / "evolve/harness/scripts"))

from coevolve.contract import Episode, Step                      # noqa: E402
from coevolve.judges.api import JudgeAPI                          # noqa: E402
from coevolve.regrade import Report, load_dump                    # noqa: E402
from regrade import load_edits                                    # noqa: E402

EDIT_FILES = {
    "asb": "evolve/harness/configs/edits_v0.json",
    "agentdojo": "evolve/harness/configs/edits_agentdojo.json",
    "agentharm": "evolve/harness/configs/edits_agentharm.json",
    "autocontrol": "evolve/harness/configs/edits_autocontrol.json",
}


def restore(src: str, rec: dict, judges: dict, api: JudgeAPI):
    blob = pickle.loads(base64.b64decode(rec["state_blob_b64"]))
    steps = [types.SimpleNamespace(index=s.get("i", 0), proposal=s.get("proposal") or {},
                                   executed=bool(s.get("executed")), observation=s.get("observation") or "",
                                   decision=s.get("decision") or {}, state_facts={})
             for s in (rec.get("steps") or [])]
    if src == "asb":
        from coevolve.adapters.asb_env import ASBEnv
        env = ASBEnv.from_state_blob(blob)
        env.set_trajectory(steps)
        env._final = rec.get("final_output", "")
    elif src == "autocontrol":
        from coevolve.adapters.autocontrol_env import AutoControlEnv
        env = AutoControlEnv.from_state_blob(blob)
    elif src == "agentdojo":
        from coevolve.adapters.agentdojo_env import AgentDojoEnv
        env = AgentDojoEnv.from_state_blob(blob)
    elif src == "agentharm":
        from coevolve.adapters.agentharm_env import AgentHarmEnv
        env = AgentHarmEnv.from_state_blob(blob, judge=judges.get("agentharm"))
    else:
        raise ValueError(src)
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stem")
    ap.add_argument("--judge", default="glm-5.3")
    ap.add_argument("--asb", default="api", choices=["api", "local", "off"])
    ap.add_argument("--ac", default="api", choices=["api", "off"])
    ap.add_argument("--agentharm", default="api", choices=["api", "off"])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--from-judged", action="store_true",
                    help="不重判，直接用已有 <stem>_<src>.judged.jsonl 重新分类（改口径时用）")
    ap.add_argument("--sources", default="", help="只处理这些来源（逗号分隔）")
    ap.add_argument("--judge-primary", action="store_true",
                    help="不重跑 judge：直接用已存 detail 里的 judge_label 重算 harm（分歧以 judge 为准）")
    a = ap.parse_args()

    stem = Path(a.stem)
    api = JudgeAPI(model=a.judge)
    judges: dict = {}
    if a.agentharm == "api":
        from coevolve.judges.agentharm import APIJudgeModel
        judges["agentharm"] = APIJudgeModel(api=api)
    if a.asb != "off":
        from coevolve.adapters.asb_env import set_judge_mode as asb_mode
        asb_mode(a.asb, api_model=a.judge)
    if a.ac != "off":
        from coevolve.adapters.autocontrol_env import set_judge_mode as ac_mode
        ac_mode("api", model=a.judge)

    summary = {}
    for src, edits_file in EDIT_FILES.items():
        if a.sources and src not in {s.strip() for s in a.sources.split(",")}:
            continue
        dump = Path(f"{stem}_{src}.episodes.jsonl.gz")
        judged_path = Path(f"{stem}_{src}.judged.jsonl")
        if not dump.exists() and not judged_path.exists():
            print(f"[{src}] 缺 dump，跳过")
            continue
        if a.from_judged:
            recs, outcomes = [], {}
            for l in judged_path.open(encoding="utf-8"):
                d = json.loads(l)
                key = (d.get("cell"), d.get("arm_key"))
                outcomes[key] = d["outcome"]
            meta = {}
            if dump.exists():                      # 工具集/termination 只在 dump 里 → 用它补
                for rec in load_dump(dump):
                    key = (rec.get("cell") or f"{rec['task_uid']}#{rec['seed']}",
                           rec.get("arm_key") or rec["arm"])
                    meta[key] = {"tools": rec.get("tools") or [],
                                 "termination": rec.get("termination") or "finish",
                                 "proposed_harm": bool(rec.get("proposed_harm")),
                                 "interventions": rec.get("interventions") or []}
            if a.judge_primary:
                flipped = 0
                for key, out in outcomes.items():
                    det = out.get("detail") or {}
                    if det.get("judge_valid") and det.get("judge_label") in ("safe", "unsafe"):
                        new_harm = det["judge_label"] == "unsafe"
                        if bool(out.get("harm")) != new_harm:
                            flipped += 1
                        out["harm"] = new_harm
                        out["severe"] = new_harm
                        term = (meta.get(key) or {}).get("termination", "finish")
                        if src == "asb":       # ASB 的 utility 是 runner 兜底：finish 且无危害
                            out["utility"] = bool(term == "finish" and not new_harm)
                        det["label_source"] = ("judge_primary(disagree)" if det.get("disagreement")
                                               else "judge_primary")
                print(f"[{src}] judge-primary 重算：翻了 {flipped} 条 harm")
            print(f"[{src}] 复用已判分 {len(outcomes)} 条 → 只重分类（补齐工具集 {len(meta)} 条）")
        else:
            recs = load_dump(dump)
            print(f"[{src}] {len(recs)} 条 episode → 离线重判（judge={a.judge}）")

        def do(rec):
            try:
                env = restore(src, rec, judges, api)
                out = dict(env.outcome())
            except Exception as exc:
                return rec, {"harm": None, "utility": None, "severe": None, "judged": False,
                             "detail": {"error": f"restore_failed: {type(exc).__name__}: {str(exc)[:160]}"}}
            if out.get("utility") is None:
                out["utility"] = bool(rec.get("termination") == "finish" and not out.get("harm"))
            return rec, out

        episodes: dict = {}
        if a.from_judged:
            for (cell, arm_key), out in outcomes.items():
                m = meta.get((cell, arm_key), {})
                episodes.setdefault(cell, {})[arm_key] = Episode(
                    task_uid=cell.split("#")[0], arm=arm_key, harness_name=arm_key,
                    harness_digest="", model_id="", seed=0,
                    steps=[Step(index=0, proposal={}, state_facts={"tools": m.get("tools", [])},
                                decision={}, executed=False, observation="", counterfactual_harm=False)],
                    outcome=out, proposed_harm=m.get("proposed_harm", False),
                    interventions=m.get("interventions", []),
                    termination=m.get("termination", "finish"), ledger=[])
        else:
            out_path = Path(f"{stem}_{src}.judged.jsonl")
            with ThreadPoolExecutor(max_workers=a.workers) as pool, out_path.open("w", encoding="utf-8") as f:
                done = 0
                for rec, out in pool.map(do, recs):
                    f.write(json.dumps({"cell": rec.get("cell"), "arm_key": rec.get("arm_key"),
                                        "outcome": out}, ensure_ascii=False, default=str) + "\n")
                    done += 1
                    if done % 100 == 0:
                        print(f"    … {done}/{len(recs)}")
                    cell = rec.get("cell") or f"{rec['task_uid']}#{rec['seed']}"
                    episodes.setdefault(cell, {})[rec.get("arm_key") or rec["arm"]] = Episode(
                        task_uid=rec["task_uid"], arm=rec["arm"],
                        harness_name=rec.get("harness", rec["arm"]), harness_digest=rec.get("harness_digest", ""),
                        model_id=rec.get("model_id", ""), seed=rec["seed"],
                        steps=[Step(index=0, proposal={}, state_facts={"tools": rec.get("tools") or []},
                                    decision={}, executed=False, observation="", counterfactual_harm=False)],
                        outcome=out, proposed_harm=bool(rec.get("proposed_harm")),
                        interventions=rec.get("interventions", []),
                        termination=rec.get("termination", "finish"), ledger=rec.get("ledger", []))

        from coevolve.classify import classify, format_report
        edits = load_edits([str(ROOT / "evolve/harness/configs/edits_core.json"),
                            str(ROOT / edits_file)])
        criterion = "safe"      # 四来源统一：只看 harm（utility 作独立轴，见 run_pair_sweep 注释）
        res = classify(Report(episodes), edits, criterion)
        (stem.parent / f"{stem.name}_{src}.judged.classify.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(format_report(res))
        buckets = {}
        for s, per in res["per_source"].items():
            buckets[s] = dict(collections.Counter(v["bucket"] for v in per["cells"].values()))
        summary[src] = buckets
        print(f"[{src}] 新四桶: {buckets}\n")

    out_json = stem.parent / f"judged_summary_{stem.name.split('_')[-1]}.json"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("汇总写入", out_json)
    print("judge 调用:", api.calls, "| 错误:", api.errors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
