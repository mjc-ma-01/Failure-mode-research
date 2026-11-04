"""google.genai.types 桩：任何未定义名字都返回占位类。"""


class _Placeholder:
    def __init__(self, *a, **k):
        self.args, self.kwargs = a, k


class GenerateContentConfig(_Placeholder):
    pass


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return type(name, (_Placeholder,), {})
