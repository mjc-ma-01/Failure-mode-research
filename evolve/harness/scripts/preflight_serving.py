#!/usr/bin/env python3
"""服务栈预检：决定用哪条后端跑 Qwen3.5-9B，并给出可执行的下一步命令。

检查项（都不需要 GPU；带 --load 才会真正加载模型）：
  1. ckpt 是否可读、revision、config 指纹、权重分片数；
  2. transformers 版本 + 是否有 qwen3_5 实现（原生支持 → 有兜底路径）；
  3. vLLM 是否安装、版本、是否注册了 qwen3_5 架构；
  4. torch/CUDA 可用性；
  5. --load 时用 transformers 做一次最小生成，确认模型真的能跑。

用法：
  python3 evolve/harness/scripts/preflight_serving.py            # 只体检
  python3 evolve/harness/scripts/preflight_serving.py --load     # 真加载（需要卡）
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

CKPT = Path("/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B")


def check_ckpt() -> dict:
    from coevolve.adapters.llm_model import resolve_ckpt
    info = resolve_ckpt(CKPT)
    snap = Path(info["model_dir"])
    shards = sorted(p.name for p in snap.glob("model.safetensors-*"))
    cfg = json.loads((snap / "config.json").read_text())
    return {**info, "shards": len(shards), "arch": cfg.get("architectures"),
            "model_type": cfg.get("model_type"),
            "n_layers": cfg.get("text_config", {}).get("num_hidden_layers")}


def check_transformers() -> dict:
    spec = importlib.util.find_spec("transformers")
    if spec is None:
        return {"installed": False}
    import transformers
    has_qwen35 = importlib.util.find_spec("transformers.models.qwen3_5") is not None
    return {"installed": True, "version": transformers.__version__, "qwen3_5": has_qwen35,
            "path": str(Path(transformers.__file__).parent)}


def check_vllm() -> dict:
    spec = importlib.util.find_spec("vllm")
    if spec is None:
        return {"installed": False, "hint": "pip install vllm（建议项目内 venv，勿动全局环境）"}
    out = {"installed": True}
    try:
        root = Path(spec.origin).parent
        hits = [p.name for p in (root / "model_executor/models").glob("*qwen3_5*")] if (root / "model_executor/models").is_dir() else []
        registry = (root / "model_executor/models/registry.py")
        text = registry.read_text() if registry.is_file() else ""
        out.update({"version": getattr(__import__("vllm"), "__version__", "?"),
                    "qwen3_5_files": hits,
                    "registered": "Qwen3_5" in text or "qwen3_5" in text})
    except Exception as exc:
        out["probe_error"] = str(exc)[:200]
    return out


def check_cuda() -> dict:
    try:
        import torch
        return {"torch": torch.__version__, "cuda_available": torch.cuda.is_available(),
                "n_gpus": torch.cuda.device_count() if torch.cuda.is_available() else 0}
    except Exception as exc:
        return {"torch": None, "error": str(exc)[:120]}


def smoke_load(model_dir: str) -> dict:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(model_dir, dtype=torch.bfloat16,
                                                device_map="auto", trust_remote_code=True)
    inputs = tok("Reply with exactly one JSON object: {\"tool\": \"ping\"}", return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=16, do_sample=False)
    text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return {"ok": True, "sample": text[:120], "device": str(model.device)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", action="store_true", help="真加载模型做最小生成（需要 GPU）")
    a = ap.parse_args()

    ck = check_ckpt()
    tf = check_transformers()
    vl = check_vllm()
    cu = check_cuda()
    print("== ckpt ==");      print(json.dumps(ck, ensure_ascii=False, indent=2))
    print("== transformers =="); print(json.dumps(tf, ensure_ascii=False))
    print("== vllm ==");      print(json.dumps(vl, ensure_ascii=False))
    print("== cuda ==");      print(json.dumps(cu, ensure_ascii=False))

    print("\n== 判定 ==")
    if vl.get("installed") and vl.get("registered"):
        print("→ vLLM 可用且已注册 qwen3_5：用 `serve_vllm.sh` 起服务，然后按 GPU_UTILIZATION.md 标定。")
    elif vl.get("installed") and not vl.get("registered"):
        print("→ vLLM 已装但未见 qwen3_5 注册：先 `python -c \"from vllm import LLM; LLM('<ckpt>')\"` 试加载；"
              "失败则升级 vLLM 或走 transformers。")
    else:
        print("→ vLLM 未安装。两条路：① 项目内 venv `pip install vllm` 再复检；"
              "② 直接走 transformers 后端（已验证原生支持 qwen3_5）。")
    if tf.get("qwen3_5"):
        print("→ transformers 原生支持 qwen3_5：兜底路径可用（吞吐低于 vLLM，建议离线批处理形态）。")
    if a.load:
        if not cu.get("cuda_available"):
            print("→ --load 跳过：当前无可用 CUDA。")
        else:
            print("→ 最小加载测试:", json.dumps(smoke_load(ck["model_dir"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
