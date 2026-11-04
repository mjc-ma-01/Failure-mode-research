"""AutoControl-Arena 适配器：**声明式 mock 环境**（官方仓库没有可执行环境）。

每个场景一份 TaskSpec（JSON，放在 experiments/taskspecs/autocontrol/）：
  prompt / initial_state / tools[{name, effect}] / harm / utility / preconditions / scope

`effect` 是受限 Python 语句（spec 由我们仓库内作者撰写，属可信输入；模型输出不走这里）。
判定只读状态与历史 → 完全确定性，可离线用脚本模型自检。
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
TASKSPEC_DIR = ROOT / "experiments/taskspecs/autocontrol"

SAFE_BUILTINS = {
    "str": str, "int": int, "float": float, "bool": bool, "len": len, "any": any,
    "all": all, "sorted": sorted, "set": set, "list": list, "dict": dict, "tuple": tuple,
    "abs": abs, "min": min, "max": max, "round": round, "sum": sum, "isinstance": isinstance,
    "enumerate": enumerate, "range": range, "zip": zip,
}

_JUDGE_MODE: dict = {"mode": "off", "require_judge": False}


def set_judge_mode(mode: str = "off", model: str = "glm-5.3", require_judge: bool = False) -> None:
    """mode: off | api（官方 Monitor 协议走 API judge）；require_judge=True 时 judge 失败即判分不可用。"""
    _JUDGE_MODE.update({"mode": mode, "model": model, "require_judge": require_judge})
    _JUDGE_MODE.pop("api", None)


@dataclass
class AutoControlTask:
    uid: str
    prompt: str
    spec: dict
    spec_path: str
    risk_category: str = ""
    domain: str = ""
    status: str = "draft"


def load_specs(only_authored: bool = True, spec_dir=None) -> list:
    """读 TaskSpec 目录；默认只取 status=authored 的（draft 是转换器产出的骨架，不可跑）。"""
    tasks = []
    base = Path(spec_dir) if spec_dir else TASKSPEC_DIR
    if not base.is_absolute():          # 相对路径先锚到项目根（否则 relative_to(ROOT) 会炸）
        base = ROOT / base
    for path in sorted(base.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if only_authored and spec.get("status") != "authored":
            continue
        tasks.append(AutoControlTask(
            uid=spec["task_uid"], prompt=spec["prompt"], spec=spec,
            spec_path=str(path.relative_to(ROOT)),
            risk_category=spec.get("risk_category", ""), domain=spec.get("domain", ""),
            status=spec.get("status", "draft"),
        ))
    return tasks


class AutoControlEnv:
    """状态机：state（dict）+ history（动作序列）+ 声明式 harm/utility 谓词。"""

    def __init__(self, task: AutoControlTask):
        self.task = task
        self.spec = task.spec
        self._initial = copy.deepcopy(self.spec.get("initial_state", {}))
        self.state = copy.deepcopy(self._initial)
        self.history: list = []
        self._final = ""

    # --- EnvAdapter ---
    def tools(self) -> list:
        return [t["name"] for t in self.spec.get("tools", [])]

    def call(self, tool: str, arguments: dict):
        spec_tool = next((t for t in self.spec.get("tools", []) if t["name"] == tool), None)
        if spec_tool is None:
            raise RuntimeError(f"未声明的工具: {tool}")
        # 同样：合并成单一 globals，保证 effect 里的推导式也能看到 state/args
        env = {"__builtins__": {}, **SAFE_BUILTINS,
               "state": self.state, "args": arguments, "history": self.history}
        try:
            exec(spec_tool.get("effect", "pass"), env)  # noqa: S102
        except Exception as exc:
            raise RuntimeError(f"effect 执行失败: {exc}") from exc
        self.history.append({"tool": tool, "arguments": dict(arguments)})
        return {"ok": True, "note": spec_tool.get("observation", "")}

    def snapshot(self) -> "AutoControlEnv":
        clone = object.__new__(AutoControlEnv)
        clone.task, clone.spec = self.task, self.spec
        clone._initial = copy.deepcopy(self._initial)
        clone.state = copy.deepcopy(self.state)
        clone.history = copy.deepcopy(self.history)
        clone._final = self._final
        return clone

    def state_facts(self, proposal: dict | None = None) -> dict:
        facts = {"task": self.task.uid, "state": copy.deepcopy(self.state),
                 "tools": [t["name"] for t in self.spec.get("tools", [])],
                 "history": [h["tool"] for h in self.history],
                 # 台账谓词要用"历史调用的参数"（例如 mark_completed 前是否 review 过同一个 task_id）
                 "history_calls": [{"tool": h.get("tool"),
                                    "arguments": copy.deepcopy(h.get("arguments") or {})}
                                   for h in self.history]}
        from ..roles import classify_tools
        facts["roles"] = classify_tools(facts["tools"])
        if proposal:
            facts["proposal"] = {"tool": proposal.get("tool"),
                                 "arguments": dict(proposal.get("arguments") or {})}
        return facts

    def state_blob(self) -> dict:
        """离线重判用：spec 路径 + 最终 state/history/final（纯 JSON，跨进程无依赖）。"""
        return {"kind": "autocontrol", "task_uid": self.task.uid,
                "spec_path": self.task.spec_path, "state": copy.deepcopy(self.state),
                "history": copy.deepcopy(self.history), "final": self._final,
                # 规格指纹：跑完之后若有人改了 specs，重判必须拒绝（否则谓词与状态对不上）
                "spec_sha": _spec_sha(self.spec), "harm_expr": self.spec.get("harm", ""),
                "utility_expr": self.spec.get("utility", "")}

    @classmethod
    def from_state_blob(cls, blob: dict) -> "AutoControlEnv":
        spec_path = ROOT / blob["spec_path"]
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if blob.get("spec_sha") and _spec_sha(spec) != blob["spec_sha"]:
            raise RuntimeError(
                f"spec_drift: {blob['spec_path']} 在跑完之后被改过（blob={blob['spec_sha']}，now={_spec_sha(spec)}）"
                "——本格无法离线重判，请重跑该格")
        task = AutoControlTask(uid=spec["task_uid"], prompt=spec["prompt"], spec=spec,
                               spec_path=blob["spec_path"],
                               risk_category=spec.get("risk_category", ""),
                               domain=spec.get("domain", ""), status=spec.get("status", ""))
        env = object.__new__(cls)
        env.task, env.spec = task, spec
        env._initial = copy.deepcopy(spec.get("initial_state", {}))
        env.state = copy.deepcopy(blob["state"])
        env.history = copy.deepcopy(blob["history"])
        env._final = blob.get("final", "")
        return env


    def set_final_output(self, text: str) -> None:
        self._final = text or ""

    def _eval(self, expr: str) -> bool:
        if not expr:
            return False
        env = {"__builtins__": {}, **SAFE_BUILTINS,
               "state": self.state, "history": self.history, "final": self._final}
        return bool(eval(expr, env))  # noqa: S307

    def outcome(self) -> dict:
        oracle_unsafe = self._eval(self.spec.get("harm", ""))
        utility = self._eval(self.spec.get("utility", ""))
        judge = self._run_judge()
        judge_valid = bool(judge.get("valid"))
        judge_label = judge.get("label")
        strict = bool(oracle_unsafe and judge_valid and judge_label == "unsafe")
        # 口径（2026-10-16 用户指定）：分歧时以 judge 为准；oracle 只作记录与兜底
        harm = bool(judge_label == "unsafe") if judge_valid else oracle_unsafe
        disagreement = bool(judge_valid and
                            ((oracle_unsafe and judge_label != "unsafe") or
                             ((not oracle_unsafe) and judge_label == "unsafe")))
        detail = {"harm_expr": self.spec.get("harm", ""),
                  "utility_expr": self.spec.get("utility", ""),
                  "history": [h["tool"] for h in self.history],
                  "status": self.task.status,
                  "oracle_unsafe": bool(oracle_unsafe),
                  "judge_label": judge_label, "judge_valid": judge_valid,
                  "judge_score": judge.get("suspicion_score"),
                  "judge_helpfulness": judge.get("helpfulness"),
                  "judge_evidence": judge.get("evidence"),
                  "judge_backend": judge.get("backend"),
                  "judge_reason": (judge.get("reason") or judge.get("error") or "")[:500],
                  "strict_unsafe": strict, "disagreement": disagreement,
                  "label_source": "judge_primary" if judge_valid else "oracle_only"}
        if not judge_valid and _JUDGE_MODE.get("require_judge"):
            return {"harm": None, "severe": None, "utility": utility, "judged": False,
                    "detail": {**detail, "judged_note": "judge 不可用（require_judge）"}}
        return {"harm": bool(harm), "severe": bool(harm), "utility": utility, "detail": detail,
                "judged": True}

    def _run_judge(self) -> dict:
        mode = _JUDGE_MODE.get("mode", "off")
        if mode == "off":
            return {}
        from ..judges import autocontrol as ac_judge
        from ..judges.api import JudgeAPI
        api = _JUDGE_MODE.setdefault("api", JudgeAPI(model=_JUDGE_MODE.get("model", "glm-5.3")))
        return ac_judge.judge_trajectory(self.spec, self.history, self._final, api=api)


def _spec_sha(spec: dict) -> str:
    """规格指纹：离线重判时用来拒绝"跑完又改了 specs"的漂移。"""
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
