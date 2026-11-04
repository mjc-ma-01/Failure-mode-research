"""AgentHarm 语义 judge：官方 rubric 里的 `semantic_judge(prompt, message, model)` 换成真模型。

约定（对齐官方实现 `benchmark/grading_utils.py::semantic_judge`）：
  * 入参是 (judge prompt, 待判文本)，要求模型**只回 pass / fail**；
  * 回复非 pass/fail → 记 invalid（官方会打印 warning 并把原串当结论 → 我们不这么干）；
  * 每次调用都计数并留原始回复，供审计与"judge 影响面"分析。

与 victim 隔离：victim 是本机 Qwen3.5-9B，judge 走 API（GLM-5.3）；官方默认 judge 是
`openai/gpt-4o-2024-08-06`，可用 `--judge-model gpt-4o` 做交叉校验。
"""
from __future__ import annotations

from ..judges.api import JudgeAPI


class _Output:
    """与 inspect_ai 桩的 `_Output` 同形状（只要求 .completion）。"""

    def __init__(self, completion: str):
        self.completion = completion


class APIJudgeModel:
    """鸭子类型：满足 inspect_ai 桩 `Model.generate(messages, config)` 的异步接口。"""

    def __init__(self, api: JudgeAPI | None = None, max_tokens: int = 4000):
        self.api = api or JudgeAPI()
        self.max_tokens = max_tokens
        self.model_id = f"api:{self.api.model}"
        self.calls = 0
        self.invalid = 0
        self.errors = 0
        self.raw_log: list = []

    async def generate(self, messages, config=None):  # noqa: D401 - 对齐官方接口
        prompt = "\n".join(getattr(m, "content", "") or "" for m in messages)
        self.calls += 1
        try:
            text = self.api.chat(prompt, max_tokens=self.max_tokens)
        except Exception as exc:
            self.errors += 1
            self.raw_log.append({"error": str(exc)[:200]})
            return _Output("fail")                      # 保守：判分失败按"未配合"
        norm = text.strip().lower()
        verdict = "pass" if "pass" in norm[:40] else ("fail" if "fail" in norm[:40] else "")
        if verdict == "":
            self.invalid += 1
        self.raw_log.append({"prompt": prompt[:400], "raw": text[:400], "verdict": verdict})
        return _Output(verdict or "fail")
