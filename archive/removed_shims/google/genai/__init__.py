"""占位桩：只为让 agentdojo 的 import 通过（不使用其 pipeline）。"""

from . import errors, types  # noqa: F401


class _Placeholder:
    def __init__(self, *a, **k): pass


class Client(_Placeholder):
    def __init__(self, *a, **k):
        raise RuntimeError('google.genai 桩：本框架不使用 agentdojo 的生成式 pipeline')


def __getattr__(name):          # 任何未定义的属性都返回占位类，避免 import 期报错
    if name.startswith("__"):
        raise AttributeError(name)
    return type(name, (_Placeholder,), {})
