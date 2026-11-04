"""LLM judge 的 API 客户端（OpenAI 兼容 /v1/chat/completions）。

配置复用 proposer 的 json（base_url / api_key），模型名按用途传：
  * AgentHarm 语义 judge：默认 glm-5.3（用户指定；官方默认是 gpt-4o，可切）
  * ASB：官方是本地 ShieldAgent 模型；API 版用同一份官方 prompt（交叉校验用）

注意（实测 2026-10-15）：该网关**不接受** `thinking` 字段（字符串→400，对象→502），
所以不要传；GLM-5.3 会自带 reasoning_content，用 max_tokens 留足预算，取 content 字段。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_PATH = Path("/mnt/shared-storage-user/majiachen/.config/fmr/proposer.json")
JUDGE_CONFIG_PATH = Path("/mnt/shared-storage-user/majiachen/.config/fmr/judge.json")


def load_judge_config(path: Path | None = None) -> dict:
    """judge.json 优先（可单独指定 judge 模型），否则回落到 proposer.json 的连接信息。"""
    for p in (path, JUDGE_CONFIG_PATH, CONFIG_PATH):
        if p and Path(p).exists():
            cfg = json.loads(Path(p).read_text(encoding="utf-8"))
            return {"base_url": cfg["base_url"], "api_key": cfg["api_key"],
                    "judge_model": cfg.get("judge_model", cfg.get("proposer_model", "glm-5.3"))}
    raise FileNotFoundError("找不到 judge 配置（judge.json / proposer.json）")


class JudgeAPI:
    """同步 HTTP judge；线程安全（每次调用独立连接），带重试与调用计数。"""

    _CONSECUTIVE_FAILURES = 0          # 进程级熔断：容器里连不上网关时不要每条 episode 都等超时
    _CIRCUIT_OPEN_AFTER = 3

    def __init__(self, model: str | None = None, base_url: str | None = None,
                 api_key: str | None = None, timeout: float = 240.0, max_retries: int = 3,
                 connect_timeout: float = 8.0):
        cfg = load_judge_config()
        self.model = model or cfg["judge_model"]
        self.base_url = (base_url or cfg["base_url"]).rstrip("/")
        self.api_key = api_key or cfg["api_key"]
        self.timeout = timeout
        self.max_retries = max_retries
        self.connect_timeout = connect_timeout
        self.calls = 0
        self.errors = 0
        self.last_raw = ""

    def chat(self, prompt: str, max_tokens: int = 8000, temperature: float = 0.0,
             system: str = "", extra_body: dict | None = None) -> str:
        """返回 content 文本；失败抛异常（调用方决定是否记 failed）。

        实测坑（2026-10-15）：GLM-5.3 自带 reasoning，reasoning 会吃掉 max_tokens ——
        max_tokens 太小会把 content 截成前几个字符（如 ` {"`）。
        因此：预算默认给足；若返回内容没闭合（可能是截断），自动加倍重试一次。
        """
        if (type(self)._CONSECUTIVE_FAILURES >= type(self)._CIRCUIT_OPEN_AFTER
                and os.environ.get("FMR_JUDGE_NO_CIRCUIT") != "1"):
            raise RuntimeError("judge 熔断中（连续失败 ≥3，见 judge-check）："
                               "容器里连不上网关时请离线重判（coevolve.regrade + judges）")
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        last_exc: Exception | None = None
        budget = max_tokens
        for attempt in range(self.max_retries):
            payload = {"model": self.model, "messages": messages,
                       "temperature": temperature, "max_tokens": budget,
                       **(extra_body or {})}
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/v1/chat/completions",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {self.api_key}"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode())
                self.calls += 1
                type(self)._CONSECUTIVE_FAILURES = 0
                text = (data["choices"][0]["message"].get("content") or "").strip()
                self.last_raw = text
                if text and (text.count("{") > text.count("}") or text.endswith('{"')):
                    budget *= 2                       # 疑似被 reasoning 挤掉 → 加倍再来
                    continue
                return text
            except Exception as exc:               # 网络/网关抖动 → 退避重试
                last_exc = exc
                time.sleep(1.5 * (attempt + 1))
        self.errors += 1
        type(self)._CONSECUTIVE_FAILURES += 1
        if last_exc is not None:
            raise RuntimeError(f"judge API 调用失败: {type(last_exc).__name__}: {last_exc}")
        return self.last_raw                          # 重试用尽：把最后一次内容交回（由 schema 判 invalid）


def parse_json_object(text: str) -> dict | None:
    """从可能带 markdown 围栏/前后文的回复里抠出第一个 JSON 对象。"""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1] if "```" in t[3:] else t
        t = t.lstrip("json").strip()
    start = t.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except Exception:
                    return None
    return None
