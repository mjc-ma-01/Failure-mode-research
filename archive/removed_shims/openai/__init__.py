"""openai 桩包（容器里可能没有该 SDK）。"""
from . import types  # noqa: F401


class _Placeholder:
    def __init__(self, *a, **k):
        pass


class OpenAI(_Placeholder): pass
class AsyncOpenAI(_Placeholder): pass


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return type(name, (_Placeholder,), {})
