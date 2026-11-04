"""SHE 式 artifact harness：把可局部编辑的 artifact 编成我们的 `Harness`。

与 SHE (`she-release/artifacts/`) 对齐的 4 件：`system_prompt.md` / `rule_bank.jsonl` /
`safety_memory.jsonl` / `tool_policy.json`。本模块只做**编译**：

  artifacts → Harness(prompt_addendum=policy 文本, checks=规则编译出的 Check, notes=digest)

规矩（防过拟合/防脏判分）：
  * 规则只能读运行时可观测事实：`state`（含 roles/tools/known_counterparties/untrusted_seen…）、
    `proposal`（tool/arguments）、`done`（已成功执行过的工具集）；
  * **禁止字面匹配任务文本**（不许出现 bench 的路径/文件名/邮箱等）；
  * 每条 BLOCK 规则必须有 `benign_exemption`（防过拦），否则编译报错；
  * 编译产物带 digest（artifact 内容 hash），写进每份报告。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .contract import Check, Harness

DEFAULT_DIR = Path(__file__).resolve().parents[4] / "evolve/harness/configs/harness/H0D"


def _digest(files: dict) -> str:
    blob = json.dumps({k: v for k, v in sorted(files.items())}, sort_keys=True,
                      ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def load_artifacts(path: Path | str = DEFAULT_DIR) -> dict:
    d = Path(path)
    out = {"dir": str(d), "system_prompt": "", "rules": [], "memory": [], "tool_policy": {},
           "raw": {}}
    sp = d / "system_prompt.md"
    if sp.exists():
        out["system_prompt"] = sp.read_text(encoding="utf-8").strip()
        out["raw"]["system_prompt.md"] = out["system_prompt"]
    rb = d / "rule_bank.jsonl"
    if rb.exists():
        out["rules"] = [json.loads(l) for l in rb.read_text(encoding="utf-8").splitlines() if l.strip()]
        out["raw"]["rule_bank.jsonl"] = rb.read_text(encoding="utf-8")
    sm = d / "safety_memory.jsonl"
    if sm.exists():
        out["memory"] = [json.loads(l) for l in sm.read_text(encoding="utf-8").splitlines() if l.strip()]
        out["raw"]["safety_memory.jsonl"] = sm.read_text(encoding="utf-8")
    tp = d / "tool_policy.json"
    if tp.exists():
        out["tool_policy"] = json.loads(tp.read_text(encoding="utf-8"))
        out["raw"]["tool_policy.json"] = tp.read_text(encoding="utf-8")
    out["digest"] = _digest(out["raw"])
    return out


def _rule_to_check(rule: dict) -> Check:
    """把 SHE 规则编译成我们的 Check（只读 state/proposal/done）。"""
    trig = rule.get("trigger") or {}
    tools = trig.get("tools")
    roles = trig.get("roles")
    require_roles = trig.get("require_roles") or trig.get("require_role")
    require = trig.get("require_tools") or trig.get("require") or []

    deny_terms: list[str] = []
    # 角色门：act 类动作必须已做过 read
    if roles == "act" and require_roles == "read":
        deny_terms.append("not done & {'read'} and state.get('roles', {}).get('read')")
    # 收款人/收件人白名单
    if "require" in trig and isinstance(trig["require"], str) and "known_counterparties" in trig["require"]:
        arg_key = "recipient" if trig.get("tools") and "send_money" in trig["tools"] else "recipient"
        deny_terms.append(
            f"(proposal.get('arguments') or {{}}).get('{arg_key}') not in (state.get('known_counterparties') or [])"
            f" and (proposal.get('arguments') or {{}}).get('{arg_key}') != (state.get('account') or {{}}).get('iban')"
        )
    # 污点后确认门
    if trig.get("untrusted_seen") and trig.get("require_confirm"):
        deny_terms.append("state.get('untrusted_seen') and (proposal.get('arguments') or {}).get('confirm') is not True")

    when_tool = tools[0] if tools and len(tools) == 1 else ""
    when_any = "|".join(tools) if tools and len(tools) > 1 else ""
    when_role = roles if not tools else ""
    return Check(
        name=rule["rule_id"], when_tool=when_tool, when_any_prefix=when_any,
        when_role=when_role, require=tuple(require),
        deny_if=" or ".join(f"({t})" for t in deny_terms) if deny_terms else "",
        action="block", reason=rule.get("reason", "blocked by rule_bank"),
        surface="hook")


def compile_harness(artifacts: dict, name: str = "H0D") -> Harness:
    """按规矩校验后编译；不合规直接报错（宁可不跑，也别跑脏判分）。"""
    rules = artifacts.get("rules") or []
    for r in rules:
        if r.get("action") == "BLOCK" and not r.get("benign_exemption"):
            raise ValueError(f"规则 {r.get('rule_id')} 是 BLOCK 但没有 benign_exemption（防过拦）")
        for banned in ("PROMPT", "instruction", "http", "@", ".txt", ".json", "user_task"):
            if banned in json.dumps(r.get("trigger", {}), ensure_ascii=False):
                raise ValueError(f"规则 {r.get('rule_id')} 的 trigger 像是在做字面匹配：{banned}")
    checks = tuple(_rule_to_check(r) for r in rules if r.get("action") in ("BLOCK", "WARN"))
    return Harness(name=name, parent=None, prompt_addendum=artifacts.get("system_prompt", ""),
                   checks=checks, tools=(), notes=f"artifacts:{artifacts.get('digest')}")


def harness_digest(artifacts: dict) -> str:
    return artifacts.get("digest", "")
