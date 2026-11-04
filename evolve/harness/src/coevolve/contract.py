"""数据契约：任务/环境/模型/harness/Δ。

关键约定：
  * harness 只通过四个面作用于系统：system prompt、工具调用前、工具调用后、工具定义。
  * harness 绝不能读 oracle（危害判定）——它只能读"运行时可见的状态事实"。
  * 每一步都在**隔离副本**上做一次反事实执行，用来得到 proposed_harm（绕过 harness 会怎样）。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass
class Decision:
    """harness 对一次工具调用的裁决。"""

    action: str = "allow"                 # allow | modify | block
    arguments: Optional[dict] = None      # modify 时的新参数
    reason: str = ""
    check: str = ""                       # 触发这条裁决的检查名
    surface: str = "hook"                 # prompt | hook | middleware | tool

    @classmethod
    def allow_(cls, check: str = "") -> "Decision":
        return cls("allow", None, "", check)

    @classmethod
    def block(cls, reason: str, check: str = "") -> "Decision":
        return cls("block", None, reason, check)


@dataclass(frozen=True)
class Check:
    """一条可执行检查（harness 的最小积木）。

    只允许读三样东西：proposal（这次要做什么）、state（运行时可见状态事实）、
    done（这一步之前已经成功执行过哪些工具）。
    """

    name: str
    when_tool: str = ""                   # 精确匹配某个工具
    when_any_prefix: str = ""             # 或：匹配任一前缀（"|" 分隔），如 "send|upload"
    when_role: str = ""                   # 或：按角色触发（read/act/report，角色由任务声明）
    require: tuple[str, ...] = ()         # 前置账：必须先成功执行过这些工具
    require_any_prefix: str = ""          # 或：前置账 = 任一前缀（"read|get|list"）
    require_role: str = ""                # 或：前置账 = 必须先执行过该角色的工具
    deny_if: str = ""                     # 表达式，为真则拒绝
    action: str = "block"                 # block | warn
    reason: str = ""
    surface: str = "hook"                 # hook | middleware

    def evaluate(self, tool: str, arguments: dict, state: dict, done: set) -> Optional[Decision]:
        triggered = False
        if self.when_tool and tool == self.when_tool:
            triggered = True
        if self.when_any_prefix and any(tool.startswith(p) for p in self.when_any_prefix.split("|")):
            triggered = True
        if self.when_role:
            roles = state.get("roles") or {}
            if tool in roles.get(self.when_role, []):
                triggered = True
        if not triggered:
            return None
        for need in self.require:
            if need not in done:
                return Decision.block(
                    f"{self.reason or 'missing required step'}: {need} not executed before {tool}",
                    self.name,
                )
        if self.require_any_prefix:
            prefixes = tuple(self.require_any_prefix.split("|"))
            available = state.get("tools")
            if available is not None and not any(str(t).startswith(prefixes) for t in available):
                # 该来源根本没有可满足的读取类工具 → 本条不适用（放行），避免把合法路径堵死
                return None
            if not any(str(d).startswith(prefixes) for d in done):
                return Decision.block(
                    f"{self.reason or 'missing required read'}: no prior {self.require_any_prefix} call before {tool}",
                    self.name,
                )
        if self.require_role:
            roles = state.get("roles") or {}
            need = set(roles.get(self.require_role, []))
            if need and not (need & set(done)):
                return Decision.block(
                    f"{self.reason or 'missing required read'}: no prior {self.require_role}-role call before {tool}",
                    self.name,
                )
        if self.deny_if:
            safe_builtins = {
                "str": str, "int": int, "float": float, "bool": bool, "len": len,
                "any": any, "all": all, "sorted": sorted, "set": set, "list": list,
                "dict": dict, "tuple": tuple, "abs": abs, "min": min, "max": max,
                "round": round, "sum": sum, "isinstance": isinstance,
            }
            # 沙箱：不给 __builtins__，只注入白名单函数（无 import / open / eval）。
            # 注意必须**合并成一个 globals 字典**：生成器表达式只能看到 globals，看不到独立的 locals。
            scope = {"__builtins__": {}, **safe_builtins, "state": state,
                     "proposal": {"tool": tool, "arguments": arguments}, "done": sorted(done)}
            if eval(self.deny_if, scope):  # noqa: S307
                return Decision.block(self.reason or f"denied by {self.name}", self.name)
        return None


@dataclass
class Harness:
    """一个带版本的 harness 制品（bundle）。"""

    name: str = "H0"
    parent: Optional[str] = None
    prompt_addendum: str = ""
    checks: tuple = ()
    tools: tuple = ()
    notes: str = ""
    guard: object = None       # SHE 式内容层守卫（Rule Bank + Tool Policy 的确定性执行）

    def transform_prompt(self, prompt: str) -> str:
        return prompt if not self.prompt_addendum else f"{prompt}\n\n{self.prompt_addendum}"

    def pre_tool_call(self, tool: str, arguments: dict, state: dict, done: set) -> Decision:
        for check in self.checks:
            decision = check.evaluate(tool, arguments, state, done)
            if decision is not None:
                return decision
        return Decision.allow_()

    def post_tool_call(self, tool: str, result: Any, state: dict) -> Any:
        return result

    def manifest(self) -> dict:
        return {
            "name": self.name,
            "parent": self.parent,
            "prompt_addendum": self.prompt_addendum,
            "checks": [c.__dict__ for c in self.checks],
            "tools": list(self.tools),
            "notes": self.notes,
        }

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.manifest(), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]


def empty_harness() -> Harness:
    return Harness(name="H0")


@dataclass
class HarnessEdit:
    """一次 harness 编辑（Δ）。由提案者写，带 manifest 与回滚条件。"""

    edit_id: str
    surface: str                          # prompt | hook | middleware | tool
    summary: str
    add_checks: tuple = ()
    prompt_addendum: str = ""
    rollback_if: str = ""

    def manifest(self) -> dict:
        return {
            "edit_id": self.edit_id,
            "surface": self.surface,
            "summary": self.summary,
            "add_checks": [c.__dict__ for c in self.add_checks],
            "prompt_addendum": self.prompt_addendum,
            "rollback_if": self.rollback_if,
        }


def apply_edit(parent: Harness, edit: HarnessEdit) -> Harness:
    """产生 Δ-harness：只增不改（父 harness 保持不可变）。"""
    return Harness(
        name=f"{parent.name}+{edit.edit_id}",
        parent=parent.digest(),
        prompt_addendum=(parent.prompt_addendum + "\n" + edit.prompt_addendum).strip(),
        checks=tuple(parent.checks) + tuple(edit.add_checks),
        tools=tuple(parent.tools),
        notes=edit.summary,
    )


@runtime_checkable
class EnvAdapter(Protocol):
    """任务环境：状态机 + 工具 + 结果判定。"""

    task_uid: str
    prompt: str

    def tools(self) -> list: ...
    def call(self, tool: str, arguments: dict) -> Any: ...
    def state_facts(self, proposal: Optional[dict] = None) -> dict: ...
    def snapshot(self) -> "EnvAdapter": ...
    def outcome(self) -> dict: ...


@runtime_checkable
class Model(Protocol):
    """被冻结的模型：给定观测，产出下一步提案。"""

    model_id: str

    def reset(self, seed: int, system_prompt: str) -> None: ...
    def propose(self, observation: str, tools: list) -> dict: ...


@dataclass
class Step:
    index: int
    proposal: dict
    state_facts: dict
    decision: dict
    executed: bool
    observation: str
    counterfactual_harm: bool
    counterfactual_detail: dict = field(default_factory=dict)


@dataclass
class Episode:
    task_uid: str
    arm: str
    harness_name: str
    harness_digest: str
    model_id: str
    seed: int
    steps: list
    outcome: dict
    proposed_harm: bool
    interventions: list
    termination: str
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    ledger: list = field(default_factory=list)
    final_output: str = ""
    state_blob: bytes = b""        # 适配器给的纯状态（pickle）：用于**离线重判**，不必重跑 GPU

    @property
    def judged(self) -> bool:
        """本格的判分是否**可用**（三值判定的第三值）。

        `harm is None` = oracle 没给判定：环境没有可判的危害通道（如 ASB 多数 env）、
        判分函数崩溃、或适配器显式声明 `judged=False`（如 AgentHarm 语义 judge 关闭时）。
        这种格既不能算"通过"，也不能算"修不动"——必须单列，否则会污染四桶表。
        """
        if self.termination == "error":
            return False
        if self.outcome.get("judged") is False:
            return False
        return self.outcome.get("harm") is not None

    @property
    def success(self) -> bool:
        return (self.judged and bool(self.outcome.get("utility"))
                and not self.outcome.get("harm"))

    @property
    def safe(self) -> bool:
        """安全格专用判据：只问"这次有没有落地危害"，不问任务是否完成。

        AgentDojo 的协议就是把 utility 与 attack-success 分开报的；两者不能混成一个指标。
        判分不可用（judged=False）时不算通过。
        """
        return self.judged and not self.outcome.get("harm")

    def to_row(self) -> dict:
        return {
            "task_uid": self.task_uid,
            "arm": self.arm,
            "harness": self.harness_name,
            "harness_digest": self.harness_digest,
            "seed": self.seed,
            "success": self.success,
            "utility": bool(self.outcome.get("utility")),
            "realized_harm": bool(self.outcome.get("harm")),
            "proposed_harm": self.proposed_harm,
            "n_steps": len(self.steps),
            "n_interventions": len(self.interventions),
            "termination": self.termination,
        }

    def to_dump(self) -> dict:
        """完整证据记录（JSON-able）：轨迹 + 最终状态 blob，供 `coevolve.regrade` 离线重判。

        - `state_blob_b64`：适配器给的纯状态（pickle, base64），重判时用它复算 oracle；
        - `steps`：只留判定/审计需要的字段（proposal / executed / observation / decision），
          不含逐 step 的环境快照（体积），需要时用 state_blob 复现。
        """
        import base64
        return {
            "task_uid": self.task_uid,
            "arm": self.arm,
            "harness": self.harness_name,
            "harness_digest": self.harness_digest,
            "model_id": self.model_id,
            "seed": self.seed,
            "termination": self.termination,
            "outcome": self.outcome,
            "final_output": self.final_output,
            "proposed_harm": self.proposed_harm,
            "interventions": self.interventions,
            "ledger": self.ledger,
            "errors": self.errors,
            "tools": self.toolset,
            "steps": [
                {"i": s.index, "proposal": s.proposal, "executed": s.executed,
                 "observation": s.observation, "decision": s.decision,
                 # 反事实：若绕过 harness 单独执行这条动作，是否直接造成危害
                 # （用于把"没被规则覆盖"和"规则覆盖了但语义分不清"区分开）
                 "cf_harm": bool(getattr(s, "counterfactual_harm", False))}
                for s in self.steps
            ],
            "state_blob_b64": (base64.b64encode(self.state_blob).decode()
                               if self.state_blob else None),
        }

    @property
    def toolset(self) -> list:
        """该格可用的工具名（重判时要用它判 Δ 的"适用性"，否则会全记 N/A）。"""
        for s in self.steps:
            t = (getattr(s, "state_facts", None) or {}).get("tools")
            if t:
                return list(t)
        return []
