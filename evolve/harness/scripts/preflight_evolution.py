#!/usr/bin/env python3
"""跑进化之前的检查与确认（go / no-go）。

分三档判定：
  A 脚本管线（离线）：Δ 库可加载/可编译、四来源 adapter 可实例化、分类管线可跑
  B 真实模型跑数：σ 是否已测、vLLM 是否就绪
  C rjob 提交：功率口径利用率是否已标定
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evolve/harness/src"))
sys.path.insert(0, str(ROOT / "evolve/harness/.pydeps"))
sys.path.insert(0, str(ROOT / "evolve/harness/.shims"))
sys.path.insert(0, str(ROOT / "data/AgentDojo/src"))

from coevolve import Check, HarnessEdit   # noqa: E402

EDIT_FILES = {
    "asb": "edits_v0.json",
    "agentdojo": "edits_agentdojo.json",
    "autocontrol": "edits_autocontrol.json",
    "agentharm": "edits_agentharm.json",
}


def load_edits(path: Path) -> list:
    out = []
    for e in json.loads(path.read_text(encoding="utf-8")):
        checks = tuple(Check(
            name=c["name"], when_tool=c.get("when_tool", ""),
            when_any_prefix=c.get("when_any_prefix", ""),
            when_role=c.get("when_role", ""),
            require=tuple(c.get("require", [])),
            require_any_prefix=c.get("require_any_prefix", ""),
            require_role=c.get("require_role", ""),
            deny_if=c.get("deny_if", ""), reason=c.get("reason", ""),
        ) for c in e.get("add_checks", []))
        out.append(HarnessEdit(edit_id=e["edit_id"], surface=e["surface"], summary=e["summary"],
                               add_checks=checks, prompt_addendum=e.get("prompt_addendum", ""),
                               rollback_if=e.get("rollback_if", "")))
    return out


def main() -> None:
    rows = []
    # --- A1: Δ 库 ---
    for src, fname in EDIT_FILES.items():
        p = ROOT / "evolve/harness/configs" / fname
        try:
            edits = load_edits(p)
            problems = []
            for e in edits:
                if not e.rollback_if:
                    problems.append(f"{e.edit_id}:缺回滚条件")
                for c in e.add_checks:
                    if not c.when_tool and not c.when_any_prefix:
                        problems.append(f"{c.name}:无触发条件")
            n_hook = sum(1 for e in edits if e.add_checks)
            n_prompt = sum(1 for e in edits if not e.add_checks)
            rows.append((f"A1 Δ库[{src}]", "OK" if not problems else "问题:" + ";".join(problems),
                         f"{len(edits)} 条（hook {n_hook} + prompt {n_prompt}）→ arms={1 + len(edits)}"))
        except Exception as exc:
            rows.append((f"A1 Δ库[{src}]", "FAIL", str(exc)[:80]))

    # --- A2: adapter 可实例化 ---
    try:
        from coevolve.adapters.asb_env import ASBEnv, load_task
        t = load_task(1334); e = ASBEnv(t); e.tools(); rows.append(("A2 adapter[ASB]", "OK", f"{len(e.tools())} tools"))
    except Exception as exc:
        rows.append(("A2 adapter[ASB]", "FAIL", str(exc)[:80]))
    try:
        from coevolve.adapters.agentdojo_env import AgentDojoEnv, make_task
        t = make_task("banking", "user_task_0", "injection_task_0"); e = AgentDojoEnv(t)
        rows.append(("A2 adapter[AgentDojo]", "OK", f"{len(e.tools())} tools"))
    except Exception as exc:
        rows.append(("A2 adapter[AgentDojo]", "FAIL", str(exc)[:80]))
    try:
        from coevolve.adapters.agentharm_env import AgentHarmEnv, load_tasks
        t = load_tasks(split="dev", limit=1)[0]; e = AgentHarmEnv(t)
        rows.append(("A2 adapter[AgentHarm]", "OK", f"{len(e.tools())} tools"))
    except Exception as exc:
        rows.append(("A2 adapter[AgentHarm]", "FAIL", str(exc)[:80]))
    try:
        from coevolve.adapters.autocontrol_env import AutoControlEnv, load_specs
        t = load_specs(only_authored=True)[0]; e = AutoControlEnv(t)
        rows.append(("A2 adapter[AutoControl]", "OK", f"{len(e.tools())} tools"))
    except Exception as exc:
        rows.append(("A2 adapter[AutoControl]", "FAIL", str(exc)[:80]))

    # --- A3: 分类器可导入 ---
    try:
        from coevolve.classify import classify, format_report  # noqa: F401
        rows.append(("A3 分类器", "OK", "classify/format_report 可导入"))
    except Exception as exc:
        rows.append(("A3 分类器", "FAIL", str(exc)[:80]))

    # --- B1: σ ---
    sigma_files = list((ROOT / "experiments").glob("**/sigma*.json"))
    rows.append(("B1 σ 已测", "OK" if sigma_files else "NO-GO",
                 "找到 " + str(len(sigma_files)) + " 份；否则需跑 20 格 × 8 次"))
    # --- B2: vLLM ---
    state_file = Path("/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-vllm/.install_state")
    rows.append(("B2 vLLM 就绪", "OK" if state_file.is_file() else "NO-GO",
                 state_file.read_text().strip() if state_file.is_file() else "尚无 .install_state（安装未完成）"))
    # --- C: 利用率标定 ---
    cal = list((ROOT / "experiments").glob("**/*calibrat*.json"))
    rows.append(("C 利用率已标定", "OK" if cal else "NO-GO",
                 "找到标定结果；否则拿到卡先跑 calibrate_util.py（目标宏观利用率 ≥50%）"))

    print(f"{'检查项':<26}{'判定':<10}说明")
    print("-" * 92)
    for name, verdict, note in rows:
        print(f"{name:<26}{verdict:<10}{note}")
    a_ok = all(v == "OK" for n, v, _ in rows if n.startswith("A"))
    b_ok = all(v == "OK" for n, v, _ in rows if n.startswith("B"))
    c_ok = all(v == "OK" for n, v, _ in rows if n.startswith("C"))
    print()
    print(f"结论：A 脚本管线 {'GO' if a_ok else 'NO-GO'} | "
          f"B 真实模型跑数 {'GO' if b_ok else 'NO-GO'} | C rjob 提交 {'GO' if c_ok else 'NO-GO'}")


if __name__ == "__main__":
    main()
