"""按需伪造第三方模型 SDK 及其子模块（meta_path finder，惰性、可回退）。

用途：AgentDojo 的 `agent_pipeline` 在 import 时会 eager-import 各家 SDK
（anthropic / openai / cohere / google.genai），容器里没有这些包，而解析器支持
`import a.b.c` 的子模块链、单纯放一个 `types.py` 是不够的（会报
"'a.types' is not a package"）。这个 finder 让**缺失**的 SDK 及任意子模块可导入；
属性访问返回占位类（例如 `anthropic.types.text_block_param.TextBlockParam`）。

两条规矩：
  * 先按正常 sys.path 找真包，找到就**放行**（绝不劫持真实依赖）；
  * 找不到才合成占位模块，并挂上 `__path__` 以便继续合成更深的子模块。

只在导入 agentdojo 适配器**之前**调用 `install()`，避免污染其它进程（例如 rjob CLI）。
"""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import sys
import types

ROOTS = ("anthropic", "openai", "cohere", "google", "mistralai", "groq", "together",
         "ollama", "litellm", "vertexai")

_IN_PROGRESS: set[str] = set()


def _covered(name: str) -> bool:
    if name in ROOTS:
        return True
    return any(name.startswith(root + ".") for root in ROOTS)


class _Placeholder:
    def __init__(self, *a, **k):
        pass


class _StubLoader(importlib.abc.Loader):
    """合成模块：任何属性访问都返回（并缓存）一个占位类。"""

    def create_module(self, spec):
        mod = types.ModuleType(spec.name)
        mod.__path__ = []                      # 允许继续合成子模块
        mod.__file__ = f"<fmr-stub:{spec.name}>"

        def __getattr__(attr, _mod=mod):
            if attr.startswith("__"):
                raise AttributeError(attr)
            # 小写名字多半是真子模块（types / _types / chat / errors / ...）：
            # `from google.genai import types` 这种写法若返回占位类，后面 `types.Schema` 就断了。
            full = f"{_mod.__name__}.{attr}"
            if attr[:1].islower() and _covered(full) and full not in _IN_PROGRESS:
                _IN_PROGRESS.add(full)
                try:
                    return importlib.import_module(full)
                except Exception:
                    pass
                finally:
                    _IN_PROGRESS.discard(full)
            obj = type(attr, (_Placeholder,), {})
            setattr(_mod, attr, obj)
            return obj

        mod.__getattr__ = __getattr__
        return mod

    def exec_module(self, module):
        sys.modules[module.__name__] = module


class _StubFinder:
    def find_spec(self, name, path=None, target=None):
        if not _covered(name):
            return None
        try:
            if importlib.machinery.PathFinder.find_spec(name, path) is not None:
                return None                    # 真包/真模块存在 → 交给正常机制
        except Exception:
            pass
        return importlib.util.spec_from_loader(name, _StubLoader(), is_package=True)


def install() -> None:
    if not any(isinstance(f, _StubFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _StubFinder())
