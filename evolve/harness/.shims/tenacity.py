"""最小 tenacity 桩：满足 agentdojo 的 import 与装饰器用法（不真正重试）。"""

class RetryError(Exception):
    pass


class _Policy:
    def __init__(self, *a, **k):
        pass


def stop_after_attempt(*a, **k): return _Policy()
def stop_after_delay(*a, **k): return _Policy()
def wait_exponential(*a, **k): return _Policy()
def wait_random_exponential(*a, **k): return _Policy()
def wait_fixed(*a, **k): return _Policy()
def retry_if_exception_type(*a, **k): return _Policy()
def retry_if_not_exception_type(*a, **k): return _Policy()
def retry_if_result(*a, **k): return _Policy()


def before_sleep_log(*a, **k):
    def deco(fn): return fn
    return deco


def after_log(*a, **k):
    def deco(fn): return fn
    return deco


def retry(*dargs, **dkw):
    def deco(fn):
        def wrapper(*a, **k):
            return fn(*a, **k)
        wrapper.__name__ = getattr(fn, "__name__", "wrapped")
        return wrapper
    if len(dargs) == 1 and callable(dargs[0]):
        return deco(dargs[0])
    return deco


class Retrying:  # pragma: no cover
    def __init__(self, *a, **k): pass
    def __call__(self, fn): return fn
    def __enter__(self): return self
    def __exit__(self, *a): return False


AsyncRetrying = Retrying
