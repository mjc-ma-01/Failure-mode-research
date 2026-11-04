"""并发执行层：让请求队列常满（实验室是功率口径，队列空=待机≈120W，直接拉低均值）。

工作项 = (任务, 种子, 臂)。所有工作项丢进线程池并发推进；每个线程各自持有一个模型客户端
（HTTP 客户端状态每 episode 会 reset），环境每个工作项都是全新的实例。
"""
from __future__ import annotations

import collections
import statistics
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .contract import apply_edit
from .paired import PairReport, _transition
from .runner import run_episode


class InFlightTracker:
    """采样"同时在飞的模型请求数"，用来证明队列从不空。"""

    def __init__(self, interval: float = 1.0):
        self._n = 0
        self._lock = threading.Lock()
        self._samples: list[int] = []
        self._stop = threading.Event()
        self._interval = interval
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                self._samples.append(self._n)
            self._stop.wait(self._interval)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)

    def inc(self) -> None:
        with self._lock:
            self._n += 1

    def dec(self) -> None:
        with self._lock:
            self._n -= 1

    def stats(self) -> dict:
        s = self._samples or [0]
        return {
            "samples": len(s),
            "mean_in_flight": round(statistics.mean(s), 2),
            "nonempty_frac": round(sum(1 for x in s if x > 0) / len(s), 3),
            "max_in_flight": max(s),
        }


class PowerSampler:
    """全程采样 GPU 功率，作业结束即可判断是否过实验室的 40%/50% 线。"""

    def __init__(self, gpu_index: int = 0, interval: float = 2.0,
                 idle_w: float = 120.0, rated_w: float = 700.0):
        self.gpu_index, self.interval = gpu_index, interval
        self.idle_w, self.rated_w = idle_w, rated_w
        self.samples: list[dict] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        cmd = ["nvidia-smi", f"--id={self.gpu_index}",
               "--query-gpu=utilization.gpu,power.draw", "--format=csv,noheader,nounits"]
        while not self._stop.is_set():
            try:
                util, power = [p.strip() for p in subprocess.check_output(cmd, text=True, timeout=5).split(",")]
                self.samples.append({"t": time.time(), "sm": float(util), "power": float(power)})
            except Exception:
                pass
            self._stop.wait(self.interval)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)

    def lab_util(self, power_w: float) -> float:
        return (power_w - self.idle_w) / (self.rated_w - self.idle_w)

    def stats(self, warmup_s: float = 0.0, t0: float | None = None) -> dict:
        if not self.samples:
            return {"n": 0}
        t0 = t0 or self.samples[0]["t"]
        steady = [s for s in self.samples if s["t"] - t0 >= warmup_s] or self.samples
        p = [s["power"] for s in steady]
        mean_p = statistics.mean(p)
        return {
            "n": len(steady),
            "mean_power_w": round(mean_p, 1),
            "p50_power_w": round(statistics.median(p), 1),
            "mean_sm_util": round(statistics.mean(s["sm"] for s in steady), 1),
            "lab_util_pct": round(100 * self.lab_util(mean_p), 1),
            "frac_above_40pct": round(sum(1 for x in p if x >= self.idle_w + 0.40 * (self.rated_w - self.idle_w)) / len(p), 3),
            "frac_above_50pct": round(sum(1 for x in p if x >= self.idle_w + 0.50 * (self.rated_w - self.idle_w)) / len(p), 3),
        }


def run_pair_parallel(tasks, env_factory, model_factory, base, edits,
                      seeds=(0,), workers: int = 32, tracker: InFlightTracker | None = None,
                      on_done=None, criterion: str = "success", spec=None):
    """并发版配对实验。

    tasks: 元素需有 .uid / .prompt
    env_factory(task, seed) -> EnvAdapter（必须每次返回全新实例）
    model_factory() -> Model（每个线程一个；内部会 reset）
    """
    report = PairReport(base_harness=base.name, edits=[e.edit_id for e in edits])
    for e in edits:
        report.transitions[e.edit_id] = collections.Counter()

    arms = [("__base__", base)] + [(e.edit_id, apply_edit(base, e)) for e in edits]
    work = [(t, s, tag, h) for t in tasks for s in seeds for tag, h in arms]

    local = threading.local()

    def get_model(task):
        """工厂按任务构造；需要复用的后端（如 HTTP 客户端）请在工厂内部自行做线程级缓存。"""
        if not hasattr(local, "models"):
            local.models = {}
        cached = local.models.get(task.uid)
        if cached is None:
            cached = model_factory(task)
            local.models[task.uid] = cached
        return cached

    results: dict = {}          # (uid, seed, tag) -> Episode
    errors_seen: list = []      # 单格失败记录（不中断整轮）
    lock = threading.Lock()

    def run_item(item):
        task, seed, tag, harness = item
        model = get_model(task)
        env = env_factory(task, seed)
        if tracker:
            tracker.inc()
        try:
            ep = run_episode(task, env, model, harness, seed, spec=spec)
        except Exception as exc:
            # 单格失败不再中断整轮：记成"错误格"继续（保证任务完成度）
            from .contract import Episode
            ep = Episode(task_uid=getattr(task, "uid", "?"), arm=harness.name,
                         harness_name=harness.name, harness_digest=harness.digest(),
                         model_id=getattr(model, "model_id", "?"), seed=seed, steps=[],
                         outcome={"harm": None, "utility": None, "severe": None,
                                  "detail": {"error": str(exc)[:200]}},
                         proposed_harm=False, interventions=[], termination="error",
                         errors=[f"{type(exc).__name__}: {str(exc)[:200]}"])
            with lock:
                errors_seen.append(f"{getattr(task, 'uid', '?')}#{seed}/{tag}: {type(exc).__name__}")
        finally:
            if tracker:
                tracker.dec()
        with lock:
            results[(task.uid, seed, tag)] = ep
        if on_done:
            on_done(task, seed, tag, ep)
        return ep

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(run_item, work))

    for task in tasks:
        for seed in seeds:
            base_ep = results[(task.uid, seed, "__base__")]
            vec = {}
            if not edits:
                # SHE 模式：Δ 是**整份 artifact 目录**（每个候选单独一次 rollout），
                # 臂间配对在离线做（arm_metrics 只读 base 行）→ 这里为 base 臂留一行即可。
                ok = base_ep.safe if criterion == "safe" else base_ep.success
                t = "unjudged" if not base_ep.judged else _transition(ok, ok)
                vec["base"] = t
                report.rows.append({
                    "cell": f"{task.uid}#{seed}", "edit": "base", "transition": t,
                    "base": base_ep.to_row(), "delta": base_ep.to_row(),
                })
            for e in edits:
                ep1 = results[(task.uid, seed, e.edit_id)]
                # 判分不可用的臂不许进转移表（否则"测不了"会被读成 fail2fail）
                if not base_ep.judged or not ep1.judged:
                    t = "unjudged"
                else:
                    ok0 = base_ep.safe if criterion == "safe" else base_ep.success
                    ok1 = ep1.safe if criterion == "safe" else ep1.success
                    t = _transition(ok0, ok1)
                vec[e.edit_id] = t
                report.transitions[e.edit_id][t] += 1
                report.rows.append({
                    "cell": f"{task.uid}#{seed}", "edit": e.edit_id, "transition": t,
                    "base": base_ep.to_row(), "delta": ep1.to_row(),
                })
            report.cell_vectors[f"{task.uid}#{seed}"] = vec
            report.episodes[f"{task.uid}#{seed}"] = {
                "H0": base_ep,
                **{e.edit_id: results[(task.uid, seed, e.edit_id)] for e in edits},
            }
    report.errors_seen = errors_seen
    return report
