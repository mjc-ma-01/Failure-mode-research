"""离线脚本模型：在接真模型之前验证框架。

严格执行剧本，**不读 system prompt**——所以"只加提示词"的 Δ 对它无效，
正好用来演示"提示类 Δ 修不了、检查类 Δ 能修"的差别。
"""
from __future__ import annotations


class ScriptedModel:
    model_id = "scripted:v1"

    def __init__(self, script: list, on_block: dict | None = None):
        self.script = script
        self.on_block = on_block or {"tool": "finish", "arguments": {"claim": "aborted"}}
        self._i = 0
        self._blocked = False

    def reset(self, seed: int, system_prompt: str) -> None:
        self._i = 0
        self._blocked = False

    def propose(self, observation: str, tools: list) -> dict:
        if observation.startswith("TOOL_OBSERVATION: ERROR - action refused"):
            self._blocked = True
        if self._blocked:
            self._i = len(self.script)
            return dict(self.on_block)
        if self._i < len(self.script):
            step = self.script[self._i]
            self._i += 1
            return dict(step)
        return dict(self.on_block)
