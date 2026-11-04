"""coevolve：model + harness 协同进化的实验框架。

单位是 (model, harness) 系统。核心对照：
    A 臂 = model + initial harness
    B 臂 = model + (initial harness + Δ)
同一批任务、同一批种子跑两臂，逐格比较，得到
    fail→success / fail→fail / success→fail / success→success
失败类型不预先定义，而是从"对各个 Δ 的反应"里实证地浮出来。
"""

from .contract import (
    Check,
    Decision,
    EnvAdapter,
    Episode,
    Harness,
    HarnessEdit,
    Model,
    Step,
    apply_edit,
    empty_harness,
)
from .paired import PairReport, run_pair
from .parallel import InFlightTracker, PowerSampler, run_pair_parallel
from .runner import run_episode

__all__ = [
    "Check", "Decision", "EnvAdapter", "Episode", "Harness", "HarnessEdit",
    "Model", "Step", "apply_edit", "empty_harness",
    "PairReport", "run_pair", "run_episode",
    "InFlightTracker", "PowerSampler", "run_pair_parallel",
]
