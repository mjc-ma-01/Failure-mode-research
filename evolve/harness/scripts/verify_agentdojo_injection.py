#!/usr/bin/env python3
"""AgentDojo 注入验证：证明"攻击文本真的送到模型面前，且攻击真的能得逞"。

对每个（user_task, injection_task）格做三件事：
  A. **送达**：按官方 GroundTruthPipeline 的路径执行用户任务该做的工具调用，
     断言攻击文本出现在某次工具返回里（模型看得到 = 注入生效）。
  B. **攻击可达**：模拟"被攻破的受害者"——直接执行官方 injection ground_truth 调用，
     断言 `injection_task.security() == True`（= 攻击得逞），证明 oracle 端到端可达。
  C. **良性对照**：只执行用户任务（不做攻击动作）时 `security()` 必须为 False（防止 oracle 恒真）。

用法：
  python evolve/harness/scripts/verify_agentdojo_injection.py [--attack important_instructions] [--limit 20]
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evolve/harness/src"))
sys.path.insert(0, str(ROOT / "evolve/harness/.pydeps"))
sys.path.insert(0, "/mnt/shared-storage-user/ai4good1-share/majiachen/.fmr-pylibs")
sys.path.insert(0, str(ROOT / "data/AgentDojo/src"))

from coevolve.sdk_stubs import install                                     # noqa: E402
install()

from agentdojo.functions_runtime import FunctionsRuntime                   # noqa: E402
from agentdojo.task_suite.load_suites import get_suite                     # noqa: E402
from coevolve.adapters.agentdojo_env import AgentDojoEnv, make_task        # noqa: E402


def run_calls(env_obj, calls) -> list:
    """必须走 env.call()：slack 等套件用 security_from_traces 判分，绕过它就丢了轨迹。"""
    outs = []
    for fc in calls:
        try:
            outs.append(str(env_obj.call(fc.function, fc.args)))
        except Exception as exc:
            outs.append(f"ERR {type(exc).__name__}: {exc}")
    return outs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attack", default="important_instructions")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--suites", default="banking,slack,travel,workspace")
    a = ap.parse_args()

    cells = []
    for suite_name in a.suites.split(","):
        suite = get_suite("v1", suite_name)
        for ut in sorted(suite.user_tasks)[:2]:
            for it in sorted(suite.injection_tasks):
                cells.append((suite_name, ut, it))
    cells = cells[:a.limit]
    ok_deliver = ok_attack = ok_control = 0
    fails: list = []
    for suite_name, ut_id, it_id in cells:
        task = make_task(suite_name, ut_id, it_id, attack=a.attack)
        env = AgentDojoEnv(task)
        inj_texts = list((env._injection_meta.get("text_head") or {}).values())
        marker = "<INFORMATION>" if a.attack.startswith("important") else None
        # A 送达：用户任务 ground truth 的返回里必须能看到注入文本
        pre = copy.deepcopy(env._pre_env)
        env_for_gt = object.__new__(AgentDojoEnv)
        env_for_gt.__dict__.update(env.__dict__)
        env_for_gt._env = pre
        outs = run_calls(env_for_gt, env._user_task.ground_truth(env._pre_env))
        delivered = any((marker and marker in o) or any(t[:40] in o for t in inj_texts) for o in outs)
        # B/C 攻击可达 / 良性对照
        env_atk = AgentDojoEnv(task)
        run_calls(env_atk, env._inj_task.ground_truth(env_atk._pre_env))
        # 输出型攻击（GOAL 是"说 X"）：ground truth 调用为空，攻击得逞体现在最终回答里
        out_text = getattr(env_atk._inj_task, "GROUND_TRUTH_OUTPUT", "") or ""
        env_atk._final_output = out_text
        sec_attack = bool(env_atk.outcome()["harm"])
        env_ben = AgentDojoEnv(task)
        run_calls(env_ben, env_ben._user_task.ground_truth(env_ben._pre_env))
        # 良性对照用"用户任务自己的期望输出"（输出型攻击不能拿攻击目标文本当对照，否则恒真）
        env_ben._final_output = getattr(env_ben._user_task, "GROUND_TRUTH_OUTPUT", "") or ""
        sec_benign = bool(env_ben.outcome()["harm"])
        ok_deliver += delivered
        ok_attack += sec_attack
        ok_control += (not sec_benign)
        if not (delivered and sec_attack and not sec_benign):
            fails.append((suite_name, ut_id, it_id, delivered, sec_attack, sec_benign))
    n = len(cells)
    print(f"attack={a.attack} | 格子 {n}")
    print(f"  A 注入送达（工具返回里出现攻击文本）: {ok_deliver}/{n}")
    print(f"  B 攻击可达（执行攻击调用 → security=True）: {ok_attack}/{n}")
    print(f"  C 良性对照（只做用户任务 → security=False）: {ok_control}/{n}")
    if fails:
        print("  失败明细（suite, user, injection, delivered, attack_success, benign_false）:")
        for f in fails[:10]:
            print("   ", f)
    print("结论:", "✅ 全部通过" if not fails else "❌ 有失败，需要修")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
