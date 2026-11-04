"""anthropic 桩包：满足 `import anthropic` 与 `from anthropic import X`（未定义名字返回占位类）。"""
from . import types  # noqa: F401


class _Placeholder:
    def __init__(self, *a, **k):
        pass


class Anthropic(_Placeholder): pass
class AsyncAnthropic(_Placeholder): pass


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return type(name, (_Placeholder,), {})
