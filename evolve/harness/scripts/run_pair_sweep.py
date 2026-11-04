#!/usr/bin/env python3
"""一次"短而密"的配对 sweep：并发推进 episode + 全程采样功率与队列占用。

形态选择：**作业内起服务**（不是长期常驻）。一个作业 = 一份事先算好的工作量，
跑完即退；加载只发生一次，中间无空转，功率均值最高。

用法：
  # 离线自检（不需要 GPU/服务）
  python3 evolve/harness/scripts/run_pair_sweep.py --model scripted --limit 1 --seeds 0 1

  # 正式（服务已在作业内起好）
  python3 evolve/harness/scripts/run_pair_sweep.py --base-url http://127.0.0.1:8000 \
      --model qwen3.5-9b --workers 32 --seeds 0 1 2 \
      --tasks experiments/split_210/tasks.jsonl --split dev --sources asb \
      --out experiments/runs/sweep_dev.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from coevolve import (Check, HarnessEdit, InFlightTracker, PowerSampler,   # noqa: E402
                      empty_harness, run_pair_parallel)
from coevolve.contract import Harness                                      # noqa: E402
from coevolve.adapters import ScriptedModel                                # noqa: E402
from coevolve.adapters.asb_env import ASBEnv, load_task                    # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def load_edits(path: Path) -> list[HarnessEdit]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    edits = []
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
            rollback_if=e.get("rollback_if", ""),
        ))
    return edits


_JUDGE_SINGLETON: dict = {}


def _judge_singleton(model: str):
    """judge 走 API、跨线程共用一个实例（内部只做 HTTP，无共享可变状态）。"""
    if not model or model == "off":
        return None
    if model not in _JUDGE_SINGLETON:
        from coevolve.judges.agentharm import APIJudgeModel
        from coevolve.judges.api import JudgeAPI
        _JUDGE_SINGLETON[model] = APIJudgeModel(api=JudgeAPI(model=model))
    return _JUDGE_SINGLETON[model]


def build_tasks(tasks_path: Path, split: str, sources: list[str], limit: int | None):
    rows = [json.loads(l) for l in tasks_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    # task_uid 形如 asb:1334 / agentharm:... / autocontrol:...，按前缀过滤
    rows = [r for r in rows if r["split"] == split and r["task_uid"].split(":")[0] in sources]
    if limit:
        rows = rows[:limit]
    tasks = []
    skipped = 0
    for r in rows:
        if not r["task_uid"].startswith("asb:"):
            continue                       # 其他 bench 的 env 适配器还没写，先跳过并记录
        try:
            tasks.append(load_task(int(r["source_id"])))
        except ValueError:
            skipped += 1                   # 例如"无环境/无工具"的纯文本样本，当前 adapter 跑不了
    if skipped:
        print(f"（跳过 {skipped} 个无环境的 ASB 任务）")
    return tasks


def build_agentdojo_tasks(suites: list[str], users_per_suite: int, injections: str,
                          split: str) -> list:
    """AgentDojo：每 suite 等距取 users_per_suite 个 user task，与全部 injection 组成安全网格。

    切分：选中的 user task 按顺序前半 → dev，后半 → held-out（确定性，可复现）。
    网格里的安全格只参与 dev（它们是诊断用的密集网格），held-out 用另一半 user × 全部 injection。
    """
    from coevolve.adapters.agentdojo_env import AgentDojoEnv, make_task  # noqa: F401
    from agentdojo.task_suite.load_suites import get_suite               # noqa: F401

    tasks = []
    for suit in suites:
        suite = get_suite("v1", suit)
        uids = sorted(suite.user_tasks)
        step = max(1, len(uids) // max(users_per_suite, 1))
        picked = uids[::step][:users_per_suite]
        inj_ids = sorted(suite.injection_tasks)
        if injections != "all":
            k = int(injections)
            inj_ids = inj_ids[::max(1, len(inj_ids) // k)][:k]
        cut = len(inj_ids) // 2 + len(inj_ids) % 2
        inj_ids = inj_ids[:cut] if split == "dev" else inj_ids[cut:]
        for uid in picked:
            if split == "dev":
                tasks.append(make_task(suit, uid, None))      # 效用格只进 dev
            for iid in inj_ids:
                tasks.append(make_task(suit, uid, iid))       # 安全格
    return tasks


def build_agentdojo_tasks70(users_map: dict, split: str, attack: str = "important_instructions",
                            task_mode: str = "injection") -> list:
    """按 suite 指定 user 数配注入格。

    task_mode:
      injection（默认）= user × 全部 injection（安全格）
      plain           = 只有 user 任务本身（**无注入**）→ 良性对照/过拦检测用
      both            = 两者都要
    """
    from coevolve.adapters.agentdojo_env import make_task
    from agentdojo.task_suite.load_suites import get_suite
    tasks = []
    for suit, k in users_map.items():
        suite = get_suite("v1", suit)
        # 抽 2k 个 user：dev 用前 k 个、held-out 用后 k 个（互不重叠）
        pool = sorted(suite.user_tasks)[:: max(1, len(suite.user_tasks) // (2 * k))][: 2 * k]
        selected = pool[:k] if split == "dev" else pool[k:2 * k]
        for uid in selected:
            if task_mode in ("plain", "both"):
                tasks.append(make_task(suit, uid, None, attack=attack))
            if task_mode in ("injection", "both"):
                for iid in sorted(suite.injection_tasks):
                    tasks.append(make_task(suit, uid, iid, attack=attack))
    return tasks


def tasks_uid(uids: list, split: str) -> list:
    """dev/heldout 各取一半（确定性）。"""
    half = max(1, len(uids) // 2)
    return uids[:half] if split == "dev" else uids[half:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default=str(ROOT / "experiments/split_210/tasks.jsonl"))
    ap.add_argument("--split", default="dev", choices=["dev", "heldout"])
    ap.add_argument("--sources", nargs="+", default=["asb"])
    ap.add_argument("--agentdojo-suites", nargs="+", default=["banking", "slack", "travel", "workspace"])
    ap.add_argument("--agentdojo-users-per-suite", type=int, default=2)
    ap.add_argument("--agentdojo-injections", default="all")
    ap.add_argument("--agentdojo-users-map", default="", help="如 banking=3,slack=2,travel=2,workspace=2")
    ap.add_argument("--agentdojo-uids-file", default="",
                    help="显式指定 AgentDojo 格 uid 列表（JSON: {\"uids\": [...]}；分层均衡切分用）")
    ap.add_argument("--agentdojo-attack", default="important_instructions",
                    help="官方注入攻击：important_instructions（主表基线）/ direct / ignore_previous / "
                         "system_message / important_instructions_no_model_name")
    ap.add_argument("--agentdojo-task-mode", default="injection",
                    choices=["injection", "plain", "both"],
                    help="injection=注入安全格；plain=无注入的良性对照（过拦检测）；both=两者")
    ap.add_argument("--autocontrol-spec-dir", default="",
                    help="AutoControl TaskSpec 目录（默认 experiments/taskspecs/autocontrol；"
                         "压力/诱惑阶梯用 experiments/taskspecs/autocontrol_levels）")
    ap.add_argument("--autocontrol-uids-file", default="",
                    help="JSON 文件：显式指定 AutoControl task uid 列表（分层切分用）")
    ap.add_argument("--base-harness", default="H0",
                    help="base 臂的 harness：H0（平台栈）或 artifact 目录（SHE 式 H0D artifacts）")
    ap.add_argument("--harness-spec", default="",
                    help="执行栈 spec；bare 两臂对照请传 evolve/harness/configs/harness/BARE.json")
    ap.add_argument("--asb-cells", type=int, default=0, help=">0 时按风险类别分层抽这么多个有环境的 ASB 任务")
    ap.add_argument("--agentharm-cells", type=int, default=0, help=">0 时把 AgentHarm 扩到这么多个格（含变体）")
    ap.add_argument("--agentharm-uids-file", default="",
                    help="JSON 文件：显式指定要跑的 AgentHarm cell uid 列表（train/test 切分用）")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--offset", type=int, default=0,
                    help="跳过前 N 个任务（配合 --limit 做 train/test 切分）")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2], help="默认 3 个种子")
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--edits", default=str(Path(__file__).resolve().parents[1] / "configs/edits_v0.json"))
    ap.add_argument("--model", default="qwen3.5-9b", help="qwen3.5-9b（走 --base-url）或 scripted（离线自检）")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--temperature", type=float, default=1.0,
                    help="target sampling temperature；AutoControl 原文 T=1.0")
    ap.add_argument("--api-key", default="", help="走 api:<model> victim 时的 Bearer token")
    ap.add_argument("--victim-extra", default="",
                    help="透传给 victim 的额外请求体（JSON），如 '{\"enable_thinking\": false}'"
                         "（网关版 Qwen3.5-9B 需要它来关思考段）")
    ap.add_argument("--judge-model", default="off",
                    help="语义 judge 的模型名（off=不接；glm-5.3 / gpt-4o / ...）。"
                         "AgentHarm 官方 rubric 需要它，ASB/AutoControl 用作第二层交叉校验")
    ap.add_argument("--asb-judge", default="auto", choices=["auto", "off", "local", "api"],
                    help="ASB 的官方 ShieldAgent 判分：auto=本地模型在就开，否则 off")
    ap.add_argument("--ac-judge", default="auto", choices=["auto", "off", "api"],
                    help="AutoControl 的官方 Monitor 式 LLM 判分（与声明式 oracle 交叉验证）")
    ap.add_argument("--gpu-index", type=int, default=0)
    ap.add_argument("--idle-w", type=float, default=120.0)
    ap.add_argument("--rated-w", type=float, default=700.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--dump-episodes", default="",
                    help="把每条 episode 的轨迹+最终状态写成 .episodes.jsonl.gz（离线重判用）")
    ap.add_argument("--classify", action="store_true", help="输出四桶分类")
    ap.add_argument("--taxonomy", action="store_true", help="额外输出 F1–F4 失败构成")
    ap.add_argument("--criterion", default="auto", choices=["auto", "success", "safe"],
                    help="success=完成且无危害；safe=只看有无落地危害（AgentDojo 安全格用这个）")
    a = ap.parse_args()

    if "agentharm" in a.sources and getattr(a, "agentharm_cells", 0):
        from coevolve.adapters.agentharm_env import load_tasks_multi
        tasks = load_tasks_multi(a.agentharm_cells, harmful=True)
    elif "agentharm" in a.sources and getattr(a, "agentharm_uids_file", ""):
        from coevolve.adapters.agentharm_env import load_tasks_multi
        uids = set(json.loads(Path(a.agentharm_uids_file).read_text(encoding="utf-8"))["uids"])
        pool = load_tasks_multi(0, harmful=True) + load_tasks_multi(0, harmful=False)   # 0=全部
        tasks = [t for t in pool if t.uid in uids]
        # 保持 uids 给定顺序
        order = {u: i for i, u in enumerate(json.loads(Path(a.agentharm_uids_file).read_text(encoding="utf-8"))["uids"])}
        tasks.sort(key=lambda t: order.get(t.uid, 10**6))
    elif "agentdojo" in a.sources and getattr(a, "agentdojo_uids_file", ""):
        from coevolve.adapters.agentdojo_env import make_task
        spec = json.loads(Path(a.agentdojo_uids_file).read_text(encoding="utf-8"))
        uids = spec["uids"]
        tasks = []
        for uid in uids:
            head, _, attack = uid.partition("@")
            parts = head.split(":")
            _, suite_name, user_id, inj = parts[0], parts[1], parts[2], parts[3]
            iid = None if inj in ("-", "") else inj
            tasks.append(make_task(suite_name, user_id, iid, attack=attack or "important_instructions"))
        if a.offset:
            tasks = tasks[a.offset:]
        if a.limit:
            tasks = tasks[:a.limit]
    elif "agentdojo" in a.sources and getattr(a, "agentdojo_users_map", ""):
        umap = {kv.split("=")[0]: int(kv.split("=")[1]) for kv in a.agentdojo_users_map.split(",")}
        tasks = build_agentdojo_tasks70(umap, a.split, attack=a.agentdojo_attack,
                                        task_mode=a.agentdojo_task_mode)
        if a.offset:
            tasks = tasks[a.offset:]
        if a.limit:
            tasks = tasks[:a.limit]
    elif "asb" in a.sources and getattr(a, "asb_cells", 0):
        from coevolve.adapters.asb_env import sample_tasks
        tasks = sample_tasks(a.asb_cells)
    elif "agentdojo" in a.sources:
        tasks = build_agentdojo_tasks(a.agentdojo_suites, a.agentdojo_users_per_suite,
                                      a.agentdojo_injections, a.split)
        if a.limit:
            tasks = tasks[:a.limit]
    elif "autocontrol" in a.sources and getattr(a, "autocontrol_uids_file", ""):
        from coevolve.adapters.autocontrol_env import load_specs
        spec = json.loads(Path(a.autocontrol_uids_file).read_text(encoding="utf-8"))
        want = list(spec["uids"])
        pool = {t.uid: t for t in load_specs(only_authored=True,
                                             spec_dir=a.autocontrol_spec_dir or None)}
        tasks = [pool[u] for u in want if u in pool]
        if a.offset:
            tasks = tasks[a.offset:]
        if a.limit:
            tasks = tasks[:a.limit]
    elif "autocontrol" in a.sources:
        from coevolve.adapters.autocontrol_env import load_specs
        tasks = load_specs(only_authored=True, spec_dir=a.autocontrol_spec_dir or None)
        if a.limit:
            tasks = tasks[:a.limit]
    elif "agentharm" in a.sources:
        from coevolve.adapters.agentharm_env import load_tasks
        tasks = load_tasks(split=a.split, limit=a.limit, harmful=True)
    else:
        tasks = build_tasks(Path(a.tasks), a.split, a.sources, a.limit)
    if not tasks:
        sys.exit("没有可用任务（检查 --split/--sources/--limit）")
    edits = []
    if str(a.edits).strip():          # 空串 = 不带平台级 Δ（SHE 模式：每个候选 harness 单跑一次）
        for p in [Path(q) for q in str(a.edits).split(",")]:
            edits.extend(load_edits(p))
    print(f"任务 {len(tasks)} × 种子 {len(a.seeds)} × 臂 {1 + len(edits)} = {len(tasks)*len(a.seeds)*(1+len(edits))} 个 episode")

    if a.model == "scripted":
        def model_factory(task):
            """任务感知的脚本策略：AgentDojo 用官方 ground truth（安全格=攻击脚本），ASB 用通用脚本。"""
            if getattr(task, "uid", "").startswith("agentdojo:"):
                from agentdojo.task_suite.load_suites import get_suite
                suite = get_suite("v1", task.suite_name)
                pre = suite.load_and_inject_default_environment({})
                if task.injection_task_id:
                    calls = suite.injection_tasks[task.injection_task_id].ground_truth(pre)
                else:
                    calls = suite.user_tasks[task.user_task_id].ground_truth(pre)
                script = [{"tool": c.function, "arguments": dict(c.args)} for c in calls]
                script.append({"tool": "finish", "arguments": {"claim": "completed", "summary": "done"}})
                return ScriptedModel(script)
            if getattr(task, "uid", "").startswith("autocontrol:"):
                script = list(task.spec.get("harmful_script", []))
                script.append({"tool": "finish", "arguments": {"claim": "completed", "summary": "done"}})
                return ScriptedModel(script)
            if getattr(task, "uid", "").startswith("agentharm:"):
                script = [{"tool": f, "arguments": {}} for f in task.target_functions]
                script.append({"tool": "finish", "arguments": {"claim": "completed", "summary": "done"}})
                return ScriptedModel(script)
            return ScriptedModel([
                {"tool": "get_nodes_status", "arguments": {}},
                {"tool": "increase_node_load", "arguments": {"node_id": "node_002", "percentage": 120}},
                {"tool": "finish", "arguments": {"claim": "completed"}},
            ])
    else:
        from coevolve.adapters.llm_model import VLLMServerModel

        _tl = __import__("threading").local()
        _api_key = a.api_key
        _extra = json.loads(a.victim_extra) if a.victim_extra.strip() else None

        def _victim_model():
            if a.model.startswith("api:"):
                return VLLMServerModel(base_url=a.base_url, model=a.model[4:],
                                       max_tokens=a.max_tokens, api_key=_api_key,
                                       temperature=a.temperature, extra_body=_extra)
            return VLLMServerModel(base_url=a.base_url, model=a.model, max_tokens=a.max_tokens,
                                   temperature=a.temperature, extra_body=_extra)

        def model_factory(task):
            # HTTP 客户端按线程复用（连接池），不按任务重建
            if not hasattr(_tl, "client"):
                _tl.client = _victim_model()
            return _tl.client

    def env_factory(task, seed):
        if getattr(task, "uid", "").startswith("agentdojo:"):
            from coevolve.adapters.agentdojo_env import AgentDojoEnv
            return AgentDojoEnv(task)
        if getattr(task, "uid", "").startswith("autocontrol:"):
            from coevolve.adapters.autocontrol_env import AutoControlEnv
            return AutoControlEnv(task)
        if getattr(task, "uid", "").startswith("agentharm:"):
            from coevolve.adapters.agentharm_env import AgentHarmEnv
            return AgentHarmEnv(task, judge_model=_judge_singleton(a.judge_model))
        return ASBEnv(task)

    # 判分接线：ASB=官方 ShieldAgent（本地模型优先），AutoControl=官方 Monitor 式 LLM judge
    asb_mode = a.asb_judge
    if asb_mode == "auto":
        from coevolve.judges.asb import SHIELD_LOCAL
        asb_mode = "local" if (SHIELD_LOCAL / "config.json").exists() else "off"
    if asb_mode != "off":
        from coevolve.adapters.asb_env import set_judge_mode as _asb_judge
        _asb_judge(asb_mode, api_model=a.judge_model if a.judge_model != "off" else "glm-5.3")
        print(f"[judge] ASB = {asb_mode}")
    else:
        print("[judge] ASB = off（判分不可用会显式标出）")
    ac_mode = a.ac_judge if a.ac_judge != "auto" else ("api" if a.judge_model != "off" else "off")
    if ac_mode != "off":
        from coevolve.adapters.autocontrol_env import set_judge_mode as _ac_judge
        _ac_judge("api", model=a.judge_model if a.judge_model != "off" else "glm-5.3")
        print(f"[judge] AutoControl = api({a.judge_model if a.judge_model != 'off' else 'glm-5.3'})")
    if a.judge_model != "off":
        print(f"[judge] AgentHarm rubric = api({a.judge_model})")

    tracker = InFlightTracker(interval=1.0)
    power = PowerSampler(gpu_index=a.gpu_index, interval=2.0, idle_w=a.idle_w, rated_w=a.rated_w)
    tracker.start()
    power.start()
    t0 = time.time()
    criterion = a.criterion
    if criterion == "auto":
        # 2026-10-16 修：全部来源都用 **safe**（只看 harm）。
        # 原因：这些格都是"有害请求"型任务，utility 在我们的 adapter 里是 runner 兜底
        # `finish and not harm`，会把"拒绝但步数用尽"算成失败、把"多跑几步再 finish"算成修好，
        # 制造伪 Δ可修（实测 agentharm 有 2 格）。utility 应当作为**独立轴**报告，不并进 pass 判据。
        criterion = "safe"
    print(f"判据：{criterion}（success=完成且无危害 / safe=只看有无落地危害）")
    from coevolve.harness_spec import default_spec, load_spec
    harness_spec = load_spec(Path(a.harness_spec)) if a.harness_spec else default_spec()
    # base 臂的 harness：H0（平台栈）或 artifact 目录（H0-D，SHE 式可编辑 artifact）
    if a.base_harness == "bare":
        base_harness = Harness(name="BARE")
        print(f"[harness] base = {base_harness.name} digest={base_harness.digest()} "
              f"spec={harness_spec.name} safety={harness_spec.safety_flags()}")
    elif a.base_harness and a.base_harness != "H0":
        if a.base_harness == "safeharness":
            from coevolve.safeharness_guard import build_safeharness_harness
            base_harness = build_safeharness_harness()
            print(f"[harness] base = {base_harness.name} digest={base_harness.digest()} "
                  f"guard=SafeHarnessPipeline")
        elif a.base_harness == "safeharness-adapted":
            from coevolve.safeharness_guard import build_safeharness_adapted_harness
            base_harness = build_safeharness_adapted_harness()
            print(f"[harness] base = {base_harness.name} digest={base_harness.digest()} "
                  f"guard=AutoControlAdapted")
        elif a.base_harness.startswith("safeharness-she-prompt:"):
            from coevolve.safeharness_guard import build_safeharness_she_harness
            d = a.base_harness.split(":", 1)[1]
            base_harness = build_safeharness_she_harness(d, use_prompt=True, use_tools=False)
            print(f"[harness] base = {base_harness.name} digest={base_harness.digest()}")
        elif a.base_harness.startswith("safeharness-she-tools:"):
            from coevolve.safeharness_guard import build_safeharness_she_harness
            d = a.base_harness.split(":", 1)[1]
            base_harness = build_safeharness_she_harness(d, use_prompt=False, use_tools=True)
            print(f"[harness] base = {base_harness.name} digest={base_harness.digest()}")
        elif a.base_harness.startswith("safeharness-she-all:"):
            from coevolve.safeharness_guard import build_safeharness_she_harness
            d = a.base_harness.split(":", 1)[1]
            base_harness = build_safeharness_she_harness(d, use_prompt=True, use_tools=True)
            print(f"[harness] base = {base_harness.name} digest={base_harness.digest()}")
        elif a.base_harness == "she" or a.base_harness.startswith("she:"):
            # SHE setting：官方 4 artifacts（Rule Bank/Tool Policy 走内容层 SHEGuard）
            from coevolve.she_harness import (DEFAULT_DIR, harness_from_she,
                                              load_she_artifacts, validate_she_artifacts)
            d = a.base_harness.split(":", 1)[1] if ":" in a.base_harness else str(DEFAULT_DIR)
            _arts = load_she_artifacts(d)
            base_harness = harness_from_she(_arts, name=f"SHE:{Path(d).name}")
            print(f"[harness] base = {base_harness.name} digest={base_harness.digest()} "
                  f"rules={len(_arts['rules'])} sinks={list(_arts['tool_policy'].get('sink_policies', {}))} "
                  f"problems={validate_she_artifacts(_arts)}")
        else:
            from coevolve.artifacts import compile_harness, load_artifacts
            _arts = load_artifacts(a.base_harness)
            base_harness = compile_harness(_arts, name=f"H0D:{Path(a.base_harness).name}")
            print(f"[harness] base = {base_harness.name} digest={base_harness.digest()} "
                  f"artifacts_digest={_arts['digest']} checks={len(base_harness.checks)}")
    else:
        base_harness = empty_harness()
    report = run_pair_parallel(tasks, env_factory, model_factory, base_harness, edits,
                               seeds=tuple(a.seeds), workers=a.workers, tracker=tracker,
                               criterion=criterion, spec=harness_spec)
    wall = time.time() - t0
    tracker.stop()
    power.stop()

    report.print_table()
    _spec = harness_spec
    print(f"\ninitial harness = {_spec.name} v{_spec.version} digest={_spec.digest} "
          f"max_steps={_spec.max_steps_for(a.sources[0])}（来源={a.sources[0]}）")
    if a.classify and report.episodes:
        from coevolve.classify import classify, format_report
        res = classify(report, edits, criterion)
        print("\n" + format_report(res))
        if a.out:
            import json as _json
            from pathlib import Path as _Path
            _Path(str(a.out)).with_suffix(".classify.json").write_text(
                _json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if a.taxonomy and report.episodes:
        from coevolve.taxonomy import composition
        print("\n失败构成（F1–F4，论文 Table 6 口径）：")
        grouped: dict = {}
        for cell, arms in report.episodes.items():
            src = cell.split(":")[0]
            for arm, ep in arms.items():
                grouped.setdefault((src, arm), []).append(ep)
        for (src, arm), eps in sorted(grouped.items()):
            c = composition(eps, criterion)
            print(f"  {src:<12}{arm:<32} n={c['n']:<5}healthy={c.get('healthy', 0):<7}"
                  f"F1={c.get('F1', 0):<7}F2={c.get('F2', 0):<7}F3={c.get('F3', 0):<7}F4={c.get('F4', 0):<7}")
    q = tracker.stats()
    p = power.stats(warmup_s=0.0, t0=t0)
    # 运行监控（只用于调参，不进实验结果记录）
    runtime = {"wall_s": round(wall, 1), "queue": q, "power": p, "workers": a.workers}
    print(f"\n墙钟 {wall:.1f}s | [运行监控] 队列 {q} | 功率 {p}")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)   # 先建目录：否则 runtime 落盘会 FileNotFound
        rp = Path(str(a.out)).with_suffix(".runtime.json")
        rp.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")

    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.to_json(), encoding="utf-8")
        meta = out.with_suffix(".meta.json")
        meta.write_text(json.dumps({
            "model": a.model, "base_url": a.base_url, "workers": a.workers,
            "temperature": a.temperature,
            "seeds": a.seeds, "n_tasks": len(tasks), "split": a.split,
            "initial_harness": _spec.manifest(),
            "sources": a.sources, "n_cells": len(tasks),
            "errors_seen": getattr(report, "errors_seen", [])[:20],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"写入 {out} 与 {meta}")

    # 轨迹 dump：一次落盘，之后"改判分"不必重跑 GPU（见 coevolve/regrade.py）
    dump_path = a.dump_episodes or (str(Path(a.out).with_suffix(".episodes.jsonl.gz")) if a.out else "")
    if dump_path and report.episodes:
        import gzip
        n = 0
        with gzip.open(dump_path, "wt", encoding="utf-8") as f:
            for cell, arms in sorted(report.episodes.items()):
                for arm, ep in sorted(arms.items()):
                    rec = ep.to_dump()
                    rec["arm_key"] = arm          # 报告里的臂键（H0 / C1_prompt_only / ...）
                    rec["cell"] = cell
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                    n += 1
        print(f"写入轨迹 dump {dump_path}（{n} 条）")


if __name__ == "__main__":
    main()
