#!/usr/bin/env python3
"""容器内网关连通性探针：TCP 连接 + /v1/models；打印代理环境（不依赖 GPU）。"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.request

CFG = "/mnt/shared-storage-user/majiachen/.config/fmr/proposer.json"


def main() -> int:
    print("proxy env:", {k: v for k, v in os.environ.items() if "proxy" in k.lower()} or "(无)")
    cfg = json.load(open(CFG, encoding="utf-8"))
    host = cfg["base_url"].split("//", 1)[1].split(":")[0]
    port = 3888
    t = time.time()
    try:
        with socket.create_connection((host, port), timeout=8):
            print(f"TCP {host}:{port} OK（{time.time()-t:.1f}s）")
    except Exception as exc:
        print(f"TCP {host}:{port} FAIL {type(exc).__name__}: {exc}")
        return 1
    t = time.time()
    try:
        req = urllib.request.Request(f"{cfg['base_url']}/v1/models",
                                     headers={"Authorization": f"Bearer {cfg['api_key']}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())
        print(f"HTTP /v1/models OK（{time.time()-t:.1f}s，模型数 {len(d.get('data', []))}）")
    except Exception as exc:
        print(f"HTTP /v1/models FAIL {type(exc).__name__}: {str(exc)[:160]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
