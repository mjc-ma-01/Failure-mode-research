"""transcript() 桩：grading 函数会往里写调试信息，这里全部吞掉。"""


class _Transcript:
    def info(self, *a, **k):
        return None

    def __getattr__(self, name):
        return lambda *a, **k: None


def transcript(*a, **k):
    return _Transcript()
