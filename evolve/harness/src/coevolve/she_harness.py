"""SHE harness 的内容层执行（对齐官方 `SHE: Trajectory-driven Safety Harness Evolution`）。

官方把 harness 拆成 4 个 artifact：System Prompt / Rule Bank / Safety Memory / Tool Policy
（`she-release/artifacts/` 与官方 github.com/RainbowQTT/SHE 逐字节一致）。Rule Bank / Tool Policy
把"安全条件"绑到**干预动作**上：allow / warn / block / sanitize / judge；执行点是
user_input / context_construction / model_reasoning / before_tool_call / after_tool_call / final_answer。

本模块实现**能在我们 runner 里跑的那部分**（确定性、无 LLM）：
  * before_tool_call：扫 tool 名 + 参数（`tools` / `argument_patterns` / 路径策略 / sink 策略）；
  * after_tool_call：扫工具输出里的注入标记（`patterns`），命中可 **sanitize**（把注入指令从
    观察里摘掉——这是 SHE 内容层最有价值的一招）或置污点；
  * final_answer：可疑完成声明 → 记录（供 S6/报告）。
  * `judge`/`escalate_to_judge`：容器内无 LLM 网关 → 记 `escalated` 并**保守拦截**（与 block 等价），
    同时在台账里标注，供事后用 API 复核。

纪律：只允许**通用**攻击标记（regex），禁止 bench-specific 字面（路径/邮箱/任务措辞）；
每条 BLOCK 规则必须带 benign_exemption（由 `validate_she_artifacts` 强制）。
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DIR = Path("/mnt/shared-storage-user/ai4good1-share/majiachen/she-release/artifacts")
SECRET_RE = re.compile(r"(sk-[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{12,}|password\s*[:=]|api[_-]?key\s*[:=])", re.I)


@dataclass
class Verdict:
    action: str                 # allow | warn | block | sanitize | judge
    rule_id: str
    reason: str
    point: str = "before_tool"
    sanitized_text: str | None = None
    metadata: dict = field(default_factory=dict)


def load_she_artifacts(d: Path | str = DEFAULT_DIR) -> dict:
    d = Path(d)
    arts: dict = {"dir": str(d), "system_prompt": "", "rules": [], "memory": [], "tool_policy": {}}
    sp = d / "system_prompt.md"
    if sp.exists():
        arts["system_prompt"] = sp.read_text(encoding="utf-8").strip()
    rb = d / "rule_bank.jsonl"
    if rb.exists():
        arts["rules"] = [json.loads(l) for l in rb.read_text(encoding="utf-8").splitlines() if l.strip()]
    sm = d / "safety_memory.jsonl"
    if sm.exists():
        arts["memory"] = [json.loads(l) for l in sm.read_text(encoding="utf-8").splitlines() if l.strip()]
    tp = d / "tool_policy.json"
    if tp.exists():
        arts["tool_policy"] = json.loads(tp.read_text(encoding="utf-8"))
    return arts


def validate_she_artifacts(arts: dict) -> list:
    """返回问题列表（空 = 合法）。SHE 的卫生条件 + 我们的 house rules。"""
    problems = []
    for r in arts.get("rules", []):
        if r.get("action") == "BLOCK" and not r.get("benign_exemption"):
            problems.append(f"{r.get('rule_id')}: BLOCK 缺 benign_exemption")
        t = json.dumps(r.get("trigger", {}), ensure_ascii=False)
        for banned in ("/mnt/", "user_task", "injection_task", "@gmail.com", "bill-december"):
            if banned in t:
                problems.append(f"{r.get('rule_id')}: trigger 含 bench 字面 {banned}")
    return problems


class SHEGuard:
    """把 SHE 的 Rule Bank + Tool Policy 变成确定性执行。"""

    def __init__(self, arts: dict):
        self.arts = arts
        self.rules = arts.get("rules", [])
        self.policy = arts.get("tool_policy", {})
        self.log: list = []
        self.sanitized = 0
        self.blocked = 0
        self.warned = 0
        self.na = 0                          # 事实不可得 → 规则"不适用"（N/A），绝不因此拦截
        self.injection_seen = False          # after_tool 命中注入标记 → 污点

    # ---------- after_tool：扫输出、必要时清洗 ----------
    # ---------- user_input：扫用户请求（AgentHarm 的"直球有害请求"就靠这一层） ----------
    def scan_input(self, text: str) -> Verdict | None:
        """命中 scope=input/user_query 的规则 → 返回判定（runner 会据此"harness 直接拒绝"）。"""
        if not text:
            return None
        for r in self.rules:
            trig = r.get("trigger", {})
            scope = str(r.get("scope", ""))
            if scope not in ("input", "user_query", "user_input"):
                continue
            for p in trig.get("patterns", []) or []:
                try:
                    if re.search(p, text, re.I):
                        v = self._verdict(r)
                        v.point = "user_input"
                        return v
                except re.error:
                    continue
        return None

    def scan_observation(self, text: str) -> tuple:
        """返回 (new_text, verdicts)。sanitize 会把命中的注入片段替换为 [REDACTED-INJECTION]。"""
        verdicts = []
        new_text = text
        for r in self.rules:
            trig = r.get("trigger", {})
            pats = trig.get("patterns")
            if not pats:
                continue
            for p in pats:
                try:
                    if re.search(p, new_text, re.I):
                        action = str(r.get("action", "WARN")).lower()
                        if action == "sanitize":
                            new_text = re.sub(p, "[REDACTED-INJECTION]", new_text, flags=re.I)
                            self.sanitized += 1
                        elif action in ("block", "judge", "escalate_to_judge"):
                            self.injection_seen = True
                        verdicts.append(Verdict(action=action, rule_id=r["rule_id"],
                                                reason=r.get("reason", ""), point="after_tool"))
                        break
                except re.error:
                    continue
        if new_text != text:
            self.injection_seen = True
        self.log.extend(v.to_dict() if hasattr(v, "to_dict") else v.__dict__ for v in verdicts)
        return new_text, verdicts

    # ---------- before_tool：扫工具名/参数/路径/sink ----------
    def decide_before_tool(self, tool: str, args: dict, state: dict) -> Verdict | None:
        blob = json.dumps(args or {}, ensure_ascii=False)
        # 1) rule_bank：tools / argument_patterns
        for r in self.rules:
            trig = dict(r.get("trigger") or {})
            # 兼容两种写法：条件写在 trigger 里（SHE 规范）或平铺在规则顶层
            for _k in ("tool", "tools", "tool_patterns", "argument_patterns", "body_contains_secret",
                       "external_recipient", "when_role", "require_prior_read", "recipient_scope",
                       "untrusted_seen", "require_confirm", "require_prior_tool_patterns",
                       "missing_prior_same_kv", "argument_not_match"):
                if _k in r and _k not in trig:
                    trig[_k] = r[_k]
            scope = r.get("scope", "")
            if scope not in ("before_tool", "tool"):
                continue
            tools = trig.get("tools") or ([trig["tool"]] if trig.get("tool") else None)
            if tools and tool not in tools:
                continue
            # AutoControl 的工具名是开放词表（每个 spec 一套）→ 允许按**工具名正则**写规则
            if trig.get("tool_patterns"):
                hit_name = False
                for p in trig["tool_patterns"]:
                    try:
                        hit_name = hit_name or bool(re.search(p, tool, re.I))
                    except re.error:
                        pass
                if not hit_name:
                    continue
            if trig.get("argument_patterns"):
                hit = False
                for p in trig["argument_patterns"]:
                    try:
                        hit = hit or bool(re.search(p, blob, re.I))
                    except re.error:
                        pass
                if not hit:
                    continue
            if trig.get("body_contains_secret") and not SECRET_RE.search(blob):
                continue
            if trig.get("external_recipient"):
                rec = str((args or {}).get("recipient") or (args or {}).get("to") or "")
                if rec and rec in (state.get("known_counterparties") or []):
                    continue
            # —— 环境事实型条件（SHE 允许按环境扩展 condition；这些由 runner 提供）——
            if trig.get("when_role") and state.get("roles", {}).get(trig["when_role"], []) and \
                    tool not in state["roles"][trig["when_role"]]:
                continue
            if trig.get("require_prior_read"):
                done = set(state.get("done") or [])
                reads = set(state.get("roles", {}).get("read") or [])
                if done & reads:
                    continue
            if trig.get("recipient_scope") == "known_counterparties":
                known = state.get("known_counterparties")
                if not known:            # 环境没暴露"用户已知对手方"这一事实 → 规则不适用（否则误拦所有合法发送）
                    self.na += 1
                    continue
                rec = str((args or {}).get("recipient") or (args or {}).get("to")
                          or (args or {}).get("recipients") or "")
                if rec and rec in known:
                    continue
            if trig.get("untrusted_seen") and not state.get("untrusted_seen"):
                continue
            if trig.get("require_confirm") and (args or {}).get("confirm") is True:
                continue
            # —— AutoControl 台账谓词（用历史调用参数，不读评分状态）——
            hist = state.get("history_calls") or []
            if trig.get("require_prior_tool_patterns"):
                pats = trig["require_prior_tool_patterns"]
                hit = False
                for h in hist:
                    for p in pats:
                        try:
                            hit = hit or bool(re.search(p, str(h.get("tool")), re.I))
                        except re.error:
                            pass
                if not hit:
                    continue                      # 前置动作没发生 → 规则不适用
            if trig.get("missing_prior_same_kv"):
                # 语义：若此前**没有任何调用**用相同的 key=value（如 review_dataset(task_id=X)），
                # 则视为"无凭据的完成声明" → 命中本规则。
                matched = False
                for k in trig["missing_prior_same_kv"]:
                    v = (args or {}).get(k)
                    if v is None:
                        continue
                    if any((h.get("arguments") or {}).get(k) == v for h in hist):
                        matched = True
                        break
                if matched:
                    continue
            if trig.get("argument_not_match"):
                # 语义：**必须包含**的内容缺失时才命中（例如草稿里必须同时提到经济/就业等平衡因素）
                if any(re.search(p, blob, re.I) for p in trig["argument_not_match"]):
                    continue
            if (not tools and not trig.get("tool_patterns") and not trig.get("argument_patterns")
                    and not trig.get("body_contains_secret") and not trig.get("missing_prior_same_kv")
                    and not trig.get("argument_not_match")):
                continue
            return self._verdict(r)
        # 2) tool_policy：路径策略 + sink 策略
        pp = (self.policy.get("path_policy") or {})
        path = str((args or {}).get("path") or (args or {}).get("file_path") or "")
        if path:
            for root in pp.get("blocked_roots", []) or []:
                if path.startswith(root):
                    return Verdict("block", "tool_policy:path_policy", f"path under blocked root {root}")
            roots = pp.get("allowed_write_roots")
            if roots and any(k in tool for k in ("write", "create", "move", "copy")):
                if not any(path.startswith(r) for r in roots):
                    return Verdict("block", "tool_policy:allowed_write_roots",
                                   f"write outside allowed roots: {path}")
        sinks = (self.policy.get("sink_policies") or {})
        # 2b) SHE 的 high_impact_tool_groups（external_publication / credential_change /
        #     scheduled_payment / messaging）：按"工具组 + 不可信上下文"整体判定。
        #     这是对官方 tool_policy.py 的复刻；缺了它，post_webpage / update_password /
        #     update_scheduled_transaction 这类动作在种子 harness 里完全"看不见"。
        groups = (self.policy.get("high_impact_tool_groups") or {})
        for group, tools in groups.items():
            if tool not in (tools or []):
                continue
            gpol = (self.policy.get("group_policies") or {}).get(group) or {}
            act = str(gpol.get("after_untrusted_source") or gpol.get("default") or "").upper()
            if not act:
                continue
            if gpol.get("after_untrusted_source") and not state.get("untrusted_seen"):
                continue                      # 只在"读过不可信内容之后"生效
            if gpol.get("allow_user_named_target"):
                rec = str((args or {}).get("recipient") or (args or {}).get("to") or "")
                known = state.get("known_counterparties") or []
                if rec and rec in known:
                    continue
            if act == "WARN":
                self.warned += 1
                v = Verdict("warn", f"tool_policy:{group}:after_untrusted",
                            f"{group} 动作发生在不可信内容之后（WARN）")
                self.log.append(dict(v.__dict__))
                return v
            if act in ("BLOCK", "JUDGE", "ESCALATE_TO_JUDGE"):
                return Verdict("block" if act == "BLOCK" else "judge",
                               f"tool_policy:{group}:after_untrusted",
                               f"{group} 动作发生在不可信内容之后")
        # 2c) 开放词表：按工具名正则归组（AutoControl 专用）
        gpatterns = (self.policy.get("high_impact_tool_patterns") or {})
        for group, pats in gpatterns.items():
            try:
                if not any(re.search(p, tool, re.I) for p in (pats or [])):
                    continue
            except re.error:
                continue
            gpol = (self.policy.get("group_policies") or {}).get(group) or {}
            act = str(gpol.get("after_untrusted_source") or gpol.get("default") or "").upper()
            if not act:
                continue
            if gpol.get("after_untrusted_source") and not state.get("untrusted_seen"):
                continue
            if act == "WARN":
                self.warned += 1
                v = Verdict("warn", f"tool_policy:{group}:pattern",
                            f"{group} 动作（工具名匹配）")
                self.log.append(dict(v.__dict__))
                return v
            return Verdict("block" if act == "BLOCK" else "judge",
                           f"tool_policy:{group}:pattern", f"{group} 动作（工具名匹配）")
        for sink, pol in sinks.items():
            if tool != sink:
                continue
            rec = str((args or {}).get("recipient") or (args or {}).get("to") or "")
            known = state.get("known_counterparties") or []
            if any(k.startswith("external_recipient") for k in pol) and not known:
                self.na += 1                    # 没有"用户已知对手方"这一事实 → 规则不适用
                continue
            if rec and rec not in known and any(k.startswith("external_recipient") for k in pol):
                act = str(next((v for k, v in pol.items() if k.startswith("external_recipient")), "BLOCK"))
                if act.upper() == "WARN":
                    self.warned += 1
                    v = Verdict("warn", f"tool_policy:{sink}:external_recipient",
                                f"recipient {rec} 不在用户记录里（WARN）")
                    self.log.append(dict(v.__dict__))
                    return v
                return Verdict("block" if act.upper() == "BLOCK" else "judge",
                               f"tool_policy:{sink}:external_recipient",
                               f"recipient {rec} 不在用户记录里")
            if SECRET_RE.search(blob) and "credential_like_body" in pol:
                return Verdict("judge", f"tool_policy:{sink}:credential_like_body",
                               "参数里出现疑似凭证")
        return None

    def _verdict(self, r: dict) -> Verdict:
        action = str(r.get("action", "BLOCK")).lower()
        if action in ("escalate_to_judge", "judge"):
            action = "judge"          # 容器内无 LLM → 保守拦截，台账标注
        if action == "block":
            self.blocked += 1
        elif action == "warn":
            self.warned += 1
        v = Verdict(action=action, rule_id=r.get("rule_id", "?"), reason=r.get("reason", ""),
                    metadata={"severity": r.get("severity"), "harm_domain": r.get("harm_domain"),
                              "attack_surface": r.get("attack_surface"), "failure_mode": r.get("failure_mode"),
                              "benign_exemption": r.get("benign_exemption")})
        self.log.append(dict(v.__dict__))
        return v

    # ---------- final_answer：完成声明闸门 ----------
    def scan_final(self, text: str, state: dict) -> list:
        out = []
        if not text:
            return out
        for r in self.rules:
            trig = dict(r.get("trigger") or {})
            for _k in ("final_response", "argument_patterns", "tool_patterns"):
                if _k in r and _k not in trig:
                    trig[_k] = r[_k]
            if not (trig.get("final_response") or r.get("scope") == "final_answer"):
                continue
            # 有 argument_patterns 时必须真正匹配 final 文本（否则会拦掉所有 finish）
            pats = trig.get("argument_patterns") or []
            if pats:
                hit = False
                for p in pats:
                    try:
                        hit = hit or bool(re.search(p, text, re.I))
                    except re.error:
                        pass
                if not hit:
                    continue
            v = self._verdict(r)
            v.point = "final_answer"
            out.append(v)
        return out

    def stats(self) -> dict:
        return {"blocked": self.blocked, "warned": self.warned, "sanitized": self.sanitized,
                "na": self.na, "injection_seen": self.injection_seen, "n_verdicts": len(self.log)}

    def snapshot(self) -> dict:
        """episode 开始时快照；结束时用 delta() 取"本格"的计数（guard 实例跨格共享，不能直接读累计值）。"""
        return {"blocked": self.blocked, "warned": self.warned, "sanitized": self.sanitized,
                "na": self.na, "n_verdicts": len(self.log)}

    def delta(self, snap: dict) -> dict:
        now = self.snapshot()
        return {k: now[k] - snap.get(k, 0) for k in now}


def harness_from_she(arts: dict, name: str = "SHE"):
    """把 SHE artifacts 编成我们的 Harness：prompt 用 SHE 的 system_prompt，内容层挂 SHEGuard。"""
    from .contract import Harness
    problems = validate_she_artifacts(arts)
    if problems:
        raise ValueError("SHE artifacts 不合法：" + "; ".join(problems[:5]))
    import hashlib, json as _json
    dig = hashlib.sha256(_json.dumps({k: v for k, v in arts.items() if k != "dir"},
                                     sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]
    return Harness(name=name, parent=None, prompt_addendum=arts.get("system_prompt", ""),
                   checks=(), tools=(), notes=f"she:{dig}", guard=ThreadLocalSHEGuard(arts))


class ThreadLocalSHEGuard:
    """每个线程一份 SHEGuard。

    为什么必须这样：rollout 用 20+ 线程共享同一个 Harness 实例，而 SHEGuard 的
    blocked/warned/sanitized 计数与 verdict log 是**实例级**的；共享时 `snapshot()/delta()`
    会串到别的线程的判定上，导致"每格增量"不可信（实测 2026-10-17：一条 5 步全 allow 的
    episode 报出 blocked=2）。改成线程局部后，episode 级 delta 才是这一格的真实判定。
    """

    def __init__(self, arts: dict):
        self._arts = arts
        self._tls = threading.local()

    @property
    def _guard(self) -> "SHEGuard":
        g = getattr(self._tls, "guard", None)
        if g is None:
            g = SHEGuard(self._arts)
            self._tls.guard = g
        return g

    def __getattr__(self, name):
        return getattr(self._guard, name)
