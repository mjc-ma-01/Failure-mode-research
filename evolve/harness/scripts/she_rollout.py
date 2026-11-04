#!/usr/bin/env python3
"""SHE 搜索台的 **rollout 端**（在 GPU 作业里跑，无 LLM 调用）。

输入 manifest（JSON）：{"split": "train30|test", "cells": [...], "variants": [{"name","kind","dir"}]}
   kind: "she"（SHE artifacts 目录，内容层 SHEGuard）/ "h0d"（事实型规则）/ "H0"（纯平台栈）
输出：每个 variant 一份 metrics JSON（ASR / utility / 拦截与清洗计数 / 失败证据）。

用法：python she_rollout.py --manifest <m.json> --base-url http://127.0.0.1:8000 [--workers 32]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UMAP = "banking=3,slack=2,travel=2,workspace=2"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--model", default="qwen3.5-9b",
                    help="本机 vLLM 服务时用 qwen3.5-9b；走网关用 api:Qwen/Qwen3.5-9B")
    ap.add_argument("--api-key", default="", help="走网关时的 Bearer token")
    ap.add_argument("--victim-extra", default="",
                    help="透传给 victim 的额外请求体（JSON），如 '{\"enable_thinking\": false}'")
    a = ap.parse_args()

    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    out_dir = Path(man.get("out_dir") or (Path(a.manifest).parent / "rollouts"))
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[she-rollout] split={man['split']} variants={[v['name'] for v in man['variants']]}", flush=True)

    for v in man["variants"]:
        base = "H0" if v["kind"] == "H0" else ("she:" + v["dir"] if v["kind"] == "she" else v["dir"])
        # 文件名必须带 task_mode：否则 plain（无注入）会覆盖 injection 的结果（实测踩坑）
        suffix = "_plain" if man.get("task_mode", "injection") == "plain" else ""
        out = out_dir / f"{man['split']}_{v['name']}{suffix}.json"
        cmd = [sys.executable, str(ROOT / "evolve/harness/scripts/run_pair_sweep.py"),
               "--model", a.model, "--base-url", a.base_url,
               "--sources", "agentdojo", "--split", man["split"],
               "--agentdojo-attack", man.get("attack", "important_instructions"),
               "--agentdojo-task-mode", man.get("task_mode", "injection"),
               "--workers", str(a.workers), "--max-tokens", str(a.max_tokens),
               "--seeds", *[str(s) for s in man.get("seeds", [0])],
               "--base-harness", base,
               # SHE 模式：Δ = 整份 artifact（不同 variant 各跑一次），不再叠平台级 edit
               "--edits", man.get("edits", ""),
               "--out", str(out)]
        if man.get("uids_file"):
            cmd += ["--agentdojo-uids-file", man["uids_file"]]
        else:
            cmd += ["--agentdojo-users-map", UMAP]
        if a.api_key:
            cmd += ["--api-key", a.api_key]
        if a.victim_extra:
            cmd += ["--victim-extra", a.victim_extra]
        if man.get("limit"):
            cmd += ["--limit", str(man["limit"])]
        if man.get("offset"):
            cmd += ["--offset", str(man["offset"])]
        print(f"[she-rollout] variant={v['name']} kind={v['kind']} → {out.name}", flush=True)
        subprocess.run(cmd, check=True, cwd=str(ROOT))
    print("[she-rollout] 全部完成", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
