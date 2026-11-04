#!/usr/bin/env python3
"""AutoControl-Arena rollout 端（容器内跑）：按 manifest 逐 variant 跑 run_pair_sweep。

manifest: {"out_dir", "uids_file", "spec_dir", "seeds":[...], "variants":[{"name","kind","dir"}]}
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--model", default="qwen3.5-9b")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--victim-extra", default="")
    a = ap.parse_args()
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    out_dir = Path(man["out_dir"]); out_dir.mkdir(parents=True, exist_ok=True)
    for v in man["variants"]:
        base = "H0" if v["kind"] == "H0" else ("she:" + v["dir"] if v["kind"] == "she" else v["dir"])
        out = out_dir / f"{man.get('split','train')}_{v['name']}.json"
        cmd = [sys.executable, str(ROOT / "evolve/harness/scripts/run_pair_sweep.py"),
               "--model", a.model, "--base-url", a.base_url, "--sources", "autocontrol",
               "--autocontrol-uids-file", str(ROOT / man["uids_file"]),
               "--autocontrol-spec-dir", man.get("spec_dir", "experiments/taskspecs/autocontrol"),
               "--workers", str(a.workers), "--max-tokens", str(a.max_tokens),
               "--seeds", *[str(s) for s in man.get("seeds", [0])],
               "--base-harness", base, "--edits", "", "--out", str(out)]
        if a.api_key:
            cmd += ["--api-key", a.api_key]
        if a.victim_extra:
            cmd += ["--victim-extra", a.victim_extra]
        print(f"[ac-rollout] {v['name']} → {out.name}", flush=True)
        subprocess.run(cmd, check=True, cwd=str(ROOT))
    print("[ac-rollout] 完成", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
