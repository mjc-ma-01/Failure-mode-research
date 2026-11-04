#!/usr/bin/env python3
"""AutoControl 规格审计：每个 TaskSpec 用**两条已知轨迹**做双向验证。

  * harmful_script（规格自带的"危害路径"）→ 期望 oracle.harm=True 且 judge 说 unsafe
  * reference_solution（"正确路径"）        → 期望 oracle.harm=False 且 judge 不说 unsafe

两份都过 → 该格的判分在"正例/反例"两侧都可复现；任一侧不一致 → 标为 FLAG，
该规格的判定**不可信**（要么谓词错、要么脚本错），需要人来改规格。

用法：
  python evolve/harness/scripts/audit_autocontrol_specs.py [--workers 8] [--judge glm-5.3] [--limit N]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evolve/harness/src"))

from coevolve.adapters.autocontrol_env import load_specs                       # noqa: E402
from coevolve.judges.api import JudgeAPI                                       # noqa: E402
from autocontrol_probe import evaluate_spec                                    # noqa: E402


def audit_one(task, api: JudgeAPI) -> dict:
    """四探针标准（见 autocontrol_probe）——v2 规格和老规格都吃。"""
    rep = evaluate_spec(task.spec, api=api, use_judge=True)
    return {**rep, "risk_category": task.risk_category, "source": task.spec.get("source")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--judge", default="glm-5.3")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    ap.add_argument("--tag-unverified", action="store_true",
                    help="把没通过四探针的规格 status 改成 unverified（sweep 只吃 status=authored）")
    a = ap.parse_args()

    tasks = load_specs(only_authored=True)
    if a.limit:
        tasks = tasks[:a.limit]
    api = JudgeAPI(model=a.judge)
    t0 = time.time()
    print(f"审计 {len(tasks)} 个 TaskSpec（judge={a.judge}, workers={a.workers}）…")
    out = []
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for i, rec in enumerate(pool.map(lambda t: audit_one(t, api), tasks), 1):
            out.append(rec)
            mark = "OK  " if not rec["flags"] else "FLAG"
            print(f"  [{i}/{len(tasks)}] {mark} {rec['task_uid']:<48} {','.join(rec['flags'])}")
    counts = collections.Counter(f for r in out for f in r["flags"])
    print(f"\n用时 {time.time() - t0:.0f}s | judge 调用 {api.calls} | 错误 {api.errors}")
    print("旗标统计:", dict(counts))
    print(f"完全通过: {sum(1 for r in out if not r['flags'])}/{len(out)}")
    if a.tag_unverified:
        from coevolve.adapters.autocontrol_env import TASKSPEC_DIR
        tagged = []
        untagged = []
        for rec in out:
            p = TASKSPEC_DIR / f"{rec['task_uid'].split(':', 1)[1]}.json"
            if not p.exists():
                continue
            spec = json.loads(p.read_text(encoding="utf-8"))
            if rec["flags"]:
                if spec.get("status") != "unverified":
                    spec["status"] = "unverified"
                    spec["unverified_reason"] = rec["flags"]
                    p.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
                    tagged.append(p.stem)
            elif spec.get("status") == "unverified":      # 重新通过 → 摘掉标记
                spec["status"] = "authored"
                spec.pop("unverified_reason", None)
                p.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
                untagged.append(p.stem)
        print(f"[tag] 标记 unverified：{len(tagged)} 个 → {tagged[:8]}{'…' if len(tagged) > 8 else ''}")
        if untagged:
            print(f"[tag] 恢复 authored：{len(untagged)} 个 → {untagged}")
    path = Path(a.out) if a.out else ROOT / "experiments/runs" / f"spec_audit_autocontrol_{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"judge": a.judge, "n": len(out), "records": out},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    print("写入", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
