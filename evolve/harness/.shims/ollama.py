"""占位桩：只为让 agentdojo 的 import 通过（不使用其 pipeline）。"""

class _Placeholder:
    def __init__(self, *a, **k): pass


class Client(_Placeholder): pass


def __getattr__(name):          # 任何未定义的属性都返回占位类，避免 import 期报错
    if name.startswith("__"):
        raise AttributeError(name)
    return type(name, (_Placeholder,), {})
