#!/usr/bin/env python3
"""OpenAI 兼容的最小推理服务（transformers 后端，带**微批处理**）。

用途：容器里 vLLM 与 CUDA 版本不匹配时的兜底。微批处理保证 GPU 不空转（利用率要求 >50%）。
用法：python3 serve_transformers.py --port 8000 --ckpt <snapshot> [--max-batch 32]
"""
from __future__ import annotations

import argparse
import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REQ_Q: "queue.Queue[dict]" = queue.Queue()


def worker(model, tok, max_batch: int, max_new_tokens_default: int) -> None:
    import torch
    while True:
        first = REQ_Q.get()
        batch = [first]
        t0 = time.time()
        while len(batch) < max_batch and time.time() - t0 < 0.05:      # 50ms 攒批
            try:
                batch.append(REQ_Q.get(timeout=0.01))
            except queue.Empty:
                break
        prompts, max_new = [], max_new_tokens_default
        for item in batch:
            msgs = item["messages"]
            try:      # Qwen3.5 默认 thinking 会吃大量 token，且输出叙述而非 JSON
                text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                               enable_thinking=False)
            except TypeError:
                text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            prompts.append(text)
            max_new = max(max_new, int(item.get("max_tokens") or max_new_tokens_default))
        try:
            enc = tok(prompts, return_tensors="pt", padding=True, truncation=True, max_length=32768).to(model.device)
            with torch.no_grad():
                out = model.generate(**enc, max_new_tokens=max_new, do_sample=False)
            texts = tok.batch_decode(out[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
        except Exception as exc:                                     # 单批失败不拖垮服务
            texts = [f"ERROR {exc}"] * len(batch)
        for item, text in zip(batch, texts):
            item["result"] = {"choices": [{"message": {"role": "assistant", "content": text},
                                           "finish_reason": "stop"}]}
            item["event"].set()


class Handler(BaseHTTPRequestHandler):
    model_id = "qwen3.5-9b-local"

    def log_message(self, *a):     # 静音
        pass

    def do_GET(self):
        if self.path.startswith("/health"):
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok"); return
        self.send_response(404); self.end_headers()

    def do_POST(self):
        if not self.path.startswith("/v1/chat/completions"):
            self.send_response(404); self.end_headers(); return
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        item = {"messages": body.get("messages", []), "max_tokens": body.get("max_tokens"),
                "event": threading.Event(), "result": None}
        REQ_Q.put(item)
        item["event"].wait(timeout=600)
        payload = json.dumps(item["result"] or {"choices": [{"message": {"content": ""}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--max-batch", type=int, default=32)
    ap.add_argument("--max-new-tokens", type=int, default=256)
    a = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    print(f"[serve_transformers] loading {a.ckpt}", flush=True)
    tok = AutoTokenizer.from_pretrained(a.ckpt, trust_remote_code=True, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(a.ckpt, dtype=torch.bfloat16,
                                                device_map="auto", trust_remote_code=True)
    model.eval()
    threading.Thread(target=worker, args=(model, tok, a.max_batch, a.max_new_tokens), daemon=True).start()
    print(f"[serve_transformers] ready on :{a.port} (micro-batch={a.max_batch})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
