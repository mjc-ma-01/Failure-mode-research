"""initial harness（H0）的声明式规格：步数预算 + 消息格式；供 runner 与报告共用。

设计意图（对应 EvoSafeHarness 的 `dtap_def_v0` 带 manifest 的纪律）：
  * 把"平台原生执行栈"从散落常量变成**有名有姓、可哈希**的制品；
  * 每份报告都盖上它的 digest，否则"Δ 可修"里可能混进"修的是我们自己预算太紧"。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]      # .../Failure-mode-research
DEFAULT_PATH = ROOT / "evolve/harness/configs/harness/H0.json"


@dataclass(frozen=True)
class HarnessSpec:
    name: str
    version: str
    raw: dict
    digest: str

    def max_steps_for(self, source: str) -> int:
        ms = self.raw.get("max_steps", {})
        return int(ms.get(source, ms.get("default", 10)))

    def first_message(self, task_prompt: str, tools: list, tools_detail: str = "") -> str:
        """用 replace 而非 format：模板里有字面大括号（JSON 示例），format 会报错。"""
        tpl = self.raw.get("prompt_template", {}).get(
            "first_message", "TASK: {task}\n\nAVAILABLE TOOLS\n{tools_detail}")
        return (tpl.replace("{task}", task_prompt)
                   .replace("{tools_detail}", tools_detail or ", ".join(tools))
                   .replace("{tools}", ", ".join(tools)))

    def tool_result(self, raw) -> str:
        tpl = self.raw.get("observation_format", {}).get("tool_result", "TOOL_OBSERVATION: {raw}")
        return tpl.format(raw=raw)

    def blocked(self, reason: str) -> str:
        tpl = self.raw.get("observation_format", {}).get(
            "blocked", "TOOL_OBSERVATION: ERROR - action refused by harness: {reason}")
        return tpl.format(reason=reason)

    def manifest(self) -> dict:
        return {"name": self.name, "version": self.version, "digest": self.digest,
                "max_steps": self.raw.get("max_steps", {}),
                "first_message": self.raw.get("prompt_template", {}).get("first_message"),
                "safety_components": self.safety_flags()}

    def safety_flags(self) -> dict:
        return dict(self.raw.get("safety_components", {}))

    def destructive_prefixes(self) -> tuple:
        s3 = self.safety_flags().get("S3_destructive_confirm", {})
        if not s3 or not s3.get("enabled"):
            return ()
        return tuple(p for p in str(s3.get("irreversible_prefixes", "")).split("|") if p)

    def reversible_prefixes(self) -> tuple:
        s3 = self.safety_flags().get("S3_destructive_confirm", {})
        if not s3 or not s3.get("enabled"):
            return ()
        return tuple(p for p in str(s3.get("reversible_prefixes", "")).split("|") if p)


def load_spec(path: Path = DEFAULT_PATH) -> HarnessSpec:
    raw = json.loads(path.read_text(encoding="utf-8"))
    body = {k: v for k, v in raw.items() if k != "digest"}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    return HarnessSpec(name=raw.get("name", "H0"), version=raw.get("version", ""), raw=raw, digest=digest)


@lru_cache(maxsize=1)
def default_spec() -> HarnessSpec:
    return load_spec()
