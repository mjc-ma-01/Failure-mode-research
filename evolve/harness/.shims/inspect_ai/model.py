"""消息与 Model 桩：字段形状按 AgentHarm 判分函数实际读取的字段对齐。

实测判分只读：message.role / message.tool_calls / tool_call.function / tool_call.arguments /
message.function（tool 消息）/ message.content / message.text（官方 grading 会取 assistant 的
`.text`；2026-10-15 补，缺它会让 6 个行为的判分函数直接崩掉）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    function: str
    arguments: dict
    id: str = "call_0"


@dataclass
class ChatMessage:
    role: str = "user"
    content: str = ""
    tool_calls: list = field(default_factory=list)
    function: str | None = None

    @property
    def text(self) -> str:
        """官方 grading 用 `message.text` 取纯文本（真实 inspect_ai 会拼 content blocks）。"""
        c = self.content
        return c if isinstance(c, str) else ""


class ChatMessageSystem(ChatMessage):
    def __init__(self, content: str = "", **k):
        super().__init__("system", content)


class ChatMessageUser(ChatMessage):
    def __init__(self, content: str = "", **k):
        super().__init__("user", content)


class ChatMessageAssistant(ChatMessage):
    def __init__(self, content: str = "", tool_calls: list | None = None, **k):
        super().__init__("assistant", content, list(tool_calls or []))


class ChatMessageTool(ChatMessage):
    def __init__(self, content: str = "", function: str | None = None, **k):
        super().__init__("tool", content, [], function)


@dataclass
class GenerateConfig:
    temperature: float = 0.0
    max_tokens: int | None = None


class _Output:
    def __init__(self, completion: str):
        self.completion = completion


class Model:
    """语义 judge 的桩：默认保守返回 'fail'（= 不判为配合）。

    真实运行请用会打 HTTP 的子类（见 adapters/agentharm_env.py 的 JudgeModel）。
    `calls` 记录被调用次数：>0 说明该行为的 rubric 真的依赖语义判分。
    """

    model_id: str = "shim:judge-off"
    calls: int = 0

    async def generate(self, messages: list, config: Any = None) -> _Output:  # noqa: D401
        type(self).calls += 1
        return _Output("fail")
