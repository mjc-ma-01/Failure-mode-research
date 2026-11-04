#!/usr/bin/env python3
"""GPU 利用率标定（按实验室口径：功率）。

实验室定义（《实验室算力资源精细化管理宣贯》）：

    利用率 = (实际功率 - 静息功率) / (额定功率 - 静息功率)     门槛线 40%
    H200：静息≈120W、额定 700W → 40% 对应 352W

注意：这是**功率口径**，不是 nvidia-smi 的 utilization.gpu。推理服务常常 SM 很忙但功率上不去，
所以本脚本以功率为准，SM 利用率只作诊断量。

用法（拿到卡、服务起来之后）：
  python3 evolve/harness/scripts/calibrate_util.py --base-url http://127.0.0.1:8000 \
      --model qwen3.5-9b --concurrency 1 4 8 16 32 64 --seconds 60 --warmup 10
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

H200_IDLE_W = 120.0
H200_RATED_W = 700.0


def sample_gpu(stop: threading.Event, gpu_index: int, out: list) -> None:
    cmd = ["nvidia-smi", f"--id={gpu_index}",
           "--query-gpu=utilization.gpu,power.draw,memory.used",
           "--format=csv,noheader,nounits"]
    while not stop.is_set():
        try:
            line = subprocess.check_output(cmd, text=True, timeout=5).strip()
            util, power, mem = [p.strip() for p in line.split(",")]
            out.append({"t": time.time(), "util": float(util), "power": float(power), "mem_mb": float(mem)})
        except Exception:
            pass
        stop.wait(1.0)


def make_prompt(target_tokens: int) -> str:
    filler = "The quick brown fox jumps over the lazy dog. " * 4
    body = "You are an agent. Reply with exactly one JSON action.\nCONTEXT:\n" + filler
    while len(body) // 4 < target_tokens:
        body += filler
    return body


def one_call(base_url: str, model: str, prompt: str, max_tokens: int, timeout: float) -> dict:
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0.7, "max_tokens": max_tokens}
    req = urllib.request.Request(f"{base_url}/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    usage = data.get("usage") or {}
    return {"ok": True, "seconds": time.perf_counter() - t0,
            "completion_tokens": usage.get("completion_tokens", 0)}


def lab_util(power_w: float, idle_w: float, rated_w: float) -> float:
    """实验室口径：(实际 - 静息) / (额定 - 静息)。"""
    return (power_w - idle_w) / (rated_w - idle_w) if rated_w > idle_w else 0.0


def run_level(base_url: str, model: str, concurrency: int, seconds: float, warmup: float,
              prompt_tokens: int, max_tokens: int, gpu_index: int, timeout: float,
              idle_w: float, rated_w: float) -> dict:
    prompt = make_prompt(prompt_tokens)
    samples: list = []
    stop = threading.Event()
    mon = threading.Thread(target=sample_gpu, args=(stop, gpu_index, samples), daemon=True)
    mon.start()

    results: list = []
    t0 = time.time()
    t_end = t0 + seconds

    def worker() -> None:
        while time.time() < t_end:
            try:
                results.append(one_call(base_url, model, prompt, max_tokens, timeout))
            except Exception as exc:
                results.append({"ok": False, "error": str(exc)[:120]})

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        list(pool.map(lambda _: worker(), range(concurrency)))

    stop.set()
    mon.join(timeout=3)

    def agg(points: list) -> dict:
        if not points:
            return {"n": 0, "mean_power": None, "p50_power": None, "mean_sm": None,
                    "lab_util": None, "pass_40": None}
        mp = statistics.mean(p["power"] for p in points)
        return {
            "n": len(points),
            "mean_power": round(mp, 1),
            "p50_power": round(statistics.median(p["power"] for p in points), 1),
            "mean_sm": round(statistics.mean(p["util"] for p in points), 1),
            "lab_util": round(100 * lab_util(mp, idle_w, rated_w), 1),
            "pass_40": mp >= idle_w + 0.40 * (rated_w - idle_w),
        }

    steady = [s for s in samples if s["t"] - t0 >= warmup]
    ok = [r for r in results if r.get("ok")]
    return {
        "concurrency": concurrency, "raw": agg(samples), "steady": agg(steady),
        "requests": len(results), "errors": sum(1 for r in results if not r.get("ok")),
        "out_tokens_per_s": round(sum(r["completion_tokens"] for r in ok) / seconds, 1) if ok else 0.0,
        "median_latency_s": round(statistics.median([r["seconds"] for r in ok]), 3) if ok else None,
        "max_mem_mb": max((s["mem_mb"] for s in samples), default=None),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--model", default="qwen3.5-9b")
    ap.add_argument("--concurrency", type=int, nargs="+", default=[1, 4, 8, 16, 32, 64])
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--warmup", type=float, default=10.0, help="稳态统计前丢弃的秒数")
    ap.add_argument("--prompt-tokens", type=int, default=2000)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--gpu-index", type=int, default=0)
    ap.add_argument("--idle-w", type=float, default=H200_IDLE_W, help="静息功率（H200≈120W）")
    ap.add_argument("--rated-w", type=float, default=H200_RATED_W, help="额定功率（H200=700W）")
    ap.add_argument("--target-util", type=float, default=0.50,
                    help="目标利用率（实验室官方线 0.40；若 rjob 按 50%% 执行则用 0.50）")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--out", default="", help="把每档结果与推荐并发写进 JSON")
    a = ap.parse_args()

    floor_w = a.idle_w + 0.40 * (a.rated_w - a.idle_w)
    target_w = a.idle_w + a.target_util * (a.rated_w - a.idle_w)
    print(f"标定 {a.base_url} | {a.seconds:.0f}s/档（前 {a.warmup:.0f}s 丢弃）| prompt≈{a.prompt_tokens} tok, out≤{a.max_tokens} tok")
    print(f"实验室口径 (P-{a.idle_w:.0f})/({a.rated_w:.0f}-{a.idle_w:.0f})；40% 官方线={floor_w:.0f}W，"
          f"目标 {a.target_util*100:.0f}% 线={target_w:.0f}W")
    hdr = (f"{'并发':>5}{'稳态均功率W':>12}{'实验室利用率%':>14}{'SM util%':>10}"
           f"{'峰值显存MB':>12}{'请求':>7}{'错误':>6}{'输出tok/s':>11}{'中位延迟s':>11}{'≥40%':>7}")
    print(hdr); print("-" * len(hdr))
    rows = []
    for c in a.concurrency:
        r = run_level(a.base_url, a.model, c, a.seconds, a.warmup, a.prompt_tokens, a.max_tokens,
                      a.gpu_index, a.timeout, a.idle_w, a.rated_w)
        rows.append(r)
        s = r["steady"]
        print(f"{c:>5}{(s['mean_power'] or 0):>12.1f}{(s['lab_util'] or 0):>14.1f}{(s['mean_sm'] or 0):>10.1f}"
              f"{r['max_mem_mb'] or 0:>12.0f}{r['requests']:>7}{r['errors']:>6}{r['out_tokens_per_s']:>11.1f}"
              f"{(r['median_latency_s'] or 0):>11}{('是' if s['pass_40'] else '否'):>7}")

    ok = [r for r in rows if (r["steady"]["lab_util"] or 0) >= a.target_util * 100]
    chosen = None
    print()
    if ok:
        best = min(ok, key=lambda r: r["concurrency"])
        chosen = best["concurrency"]
        print(f"结论：并发 ≥ {best['concurrency']} 时稳态功率 {best['steady']['mean_power']}W，"
              f"实验室利用率 {best['steady']['lab_util']}% ≥ 目标 {a.target_util*100:.0f}%。")
    else:
        print(f"结论：到 {a.concurrency[-1]} 并发仍未达 {a.target_util*100:.0f}%（官方 40% 线 = {floor_w:.0f}W）。")
        print("补救顺序：① 提高并发与 --max-num-seqs ② 关掉 prefix caching（省算力但降功率，"
              "对功率口径反而不利）③ judge 请求并入同一服务 ④ 组采样 n=4 ⑤ 离线批处理打包 (episode,step)")
    print("\n提醒：实验室按周期内长期均值考核（示例 [T-15,T-1]），模型加载/排队/收尾都计入；"
          "本脚本同时给出 raw（含预热）与 steady（丢预热）两档。")
    if a.out:
        import json as _json
        from pathlib import Path as _Path
        _Path(a.out).write_text(_json.dumps(
            {"target_util": a.target_util, "chosen_concurrency": chosen, "rows": rows},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入 {a.out}")


if __name__ == "__main__":
    main()
