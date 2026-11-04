"""openai.types 桩。"""


class _Placeholder:
    def __init__(self, *a, **k):
        pass


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return type(name, (_Placeholder,), {})
