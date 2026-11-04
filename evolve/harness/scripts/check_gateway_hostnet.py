#!/usr/bin/env python3
"""容器内网关探针 v2：直连 + 试宿主代理（127.0.0.1:28084）两条路，便于判断 --host-network 是否可用。"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.request

CFG = "/mnt/shared-storage-user/majiachen/.config/fmr/proposer.json"


def tcp(host: str, port: int, timeout: float = 6.0) -> tuple:
    t = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, round(time.time() - t, 2), ""
    except Exception as exc:
        return False, round(time.time() - t, 2), f"{type(exc).__name__}: {exc}"


def main() -> int:
    print("proxy env:", {k: v for k, v in os.environ.items() if "proxy" in k.lower()} or "(无)")
    cfg = json.load(open(CFG, encoding="utf-8"))
    host = cfg["base_url"].split("//", 1)[1].split(":")[0]
    ok1, dt1, err1 = tcp(host, 3888)
    print(f"直连 {host}:3888 → {'OK' if ok1 else 'FAIL'} ({dt1}s) {err1}")
    ok2, dt2, err2 = tcp("127.0.0.1", 28084)
    print(f"宿主代理 127.0.0.1:28084 → {'OK' if ok2 else 'FAIL'} ({dt2}s) {err2}")
    if ok2:
        try:
            os.environ["https_proxy"] = "http://127.0.0.1:28084"
            os.environ["http_proxy"] = "http://127.0.0.1:28084"
            opener = urllib.request.build_opener(urllib.request.ProxyHandler(
                {"http": "http://127.0.0.1:28084", "https": "http://127.0.0.1:28084"}))
            req = urllib.request.Request(f"{cfg['base_url']}/v1/models",
                                         headers={"Authorization": f"Bearer {cfg['api_key']}"})
            with opener.open(req, timeout=20) as r:
                d = json.loads(r.read().decode())
            print(f"经代理 /v1/models OK（模型数 {len(d.get('data', []))}）")
            return 0
        except Exception as exc:
            print(f"经代理 /v1/models FAIL {type(exc).__name__}: {str(exc)[:140]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
