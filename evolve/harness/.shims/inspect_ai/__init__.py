"""inspect_ai 桩：只满足 AgentHarm 官方 grading 函数的 import 与调用（我们不跑它的 pipeline）。"""


class _Placeholder:
    def __init__(self, *a, **k):
        self.args, self.kwargs = a, k


def __getattr__(name):
    """未知 API（Task/task/solver 等）一律给占位符——我们只需要判分那两个文件。"""
    if name.startswith("__"):
        raise AttributeError(name)
    return type(name, (_Placeholder,), {})
