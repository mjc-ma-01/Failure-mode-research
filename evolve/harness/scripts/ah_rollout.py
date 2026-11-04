#!/usr/bin/env python3
"""AgentHarm 搜索台的 rollout 端（容器内跑，不调 LLM；判分在宿主机离线做）。

manifest: {"out_dir": "...", "harmful_uids": "experiments/split_agentharm/train30.json",
           "benign_uids": "experiments/split_agentharm/benign_train_tt.json",
           "variants": [{"name","kind","dir"}]}
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def run_one(base: str, uids_file: str, out: Path, base_url: str, workers: int, max_tokens: int,
            model: str, api_key: str, victim_extra: str, edits: str) -> None:
    cmd = [sys.executable, str(ROOT / "evolve/harness/scripts/run_pair_sweep.py"),
           "--model", model, "--base-url", base_url, "--sources", "agentharm",
           "--agentharm-uids-file", str(ROOT / uids_file),
           "--workers", str(workers), "--max-tokens", str(max_tokens), "--seeds", "0",
           "--base-harness", base,
           "--edits", edits,          # 空串 = SHE 模式（Δ 是整份 artifact，不再叠平台级 edit）
           "--out", str(out)]
    if api_key:
        cmd += ["--api-key", api_key]
    if victim_extra:
        cmd += ["--victim-extra", victim_extra]
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--model", default="qwen3.5-9b",
                    help="本机 vLLM 时用 qwen3.5-9b；走网关用 api:Qwen/Qwen3.5-9B")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--victim-extra", default="")
    ap.add_argument("--edits", default="")
    a = ap.parse_args()
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    out_dir = Path(man["out_dir"]); out_dir.mkdir(parents=True, exist_ok=True)
    mt = a.max_tokens if a.max_tokens >= 64 else 512
    for v in man["variants"]:
        base = "H0" if v["kind"] == "H0" else ("she:" + v["dir"] if v["kind"] == "she" else v["dir"])
        for label, uids_file in (("harm", man["harmful_uids"]), ("benign", man["benign_uids"])):
            out = out_dir / f"{label}_{v['name']}.json"
            print(f"[ah-rollout] {v['name']} {label} → {out.name}", flush=True)
            run_one(base, uids_file, out, a.base_url, a.workers, mt,
                    a.model, a.api_key, a.victim_extra, a.edits)
    print("[ah-rollout] 全部完成", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
