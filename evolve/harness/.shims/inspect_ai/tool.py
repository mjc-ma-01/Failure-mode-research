"""inspect_ai.tool 桩：AgentHarm 的每个工具文件都会 `from inspect_ai.tool import Tool, tool`。"""


class Tool:
    def __init__(self, *a, **k):
        pass


def tool(*dargs, **dkw):
    """既支持 @tool，也支持 @tool(name=...) 的装饰器桩。"""

    def deco(fn):
        return fn

    if len(dargs) == 1 and callable(dargs[0]):
        return deco(dargs[0])
    return deco


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return type(name, (Tool,), {})
