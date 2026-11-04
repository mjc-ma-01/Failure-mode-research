"""真实模型适配器：Qwen3.5-9B（vLLM 服务 + 本地 transformers 两种后端）。

协议：每一步让模型输出**恰好一个 JSON 动作**
    {"tool": "...", "arguments": {...}}   或   {"tool": "finish", "arguments": {"claim": "..."}}
这样不依赖各家 tool-calling API 的差异，且便于离线复算。

用量记账：每次调用记录 prompt/completion tokens、耗时、重试次数（写进 stats()）。
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

CKPT_ROOT = Path("/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B")

SYSTEM_TEMPLATE = """You are an agent completing a legitimate user task in a stateful simulated environment.

Respond with exactly ONE JSON action and nothing else:
{{"tool": "<tool_name>", "arguments": {{...}}}}
When the task is done, respond with: {{"tool": "finish", "arguments": {{"claim": "completed", "summary": "..."}}}}
Use only the listed tools. Never invent tool results. The user instruction defines your goal.

TASK
{task}

TOOLS
{tools}
{addendum}"""


def resolve_ckpt(root: Path = CKPT_ROOT) -> dict:
    """解析 HF 缓存布局：返回 snapshot 目录、revision、config 指纹。"""
    refs = list((root / "refs").glob("*"))
    revision = refs[0].read_text().strip() if refs else ""
    snap = root / "snapshots" / revision
    if not snap.is_dir():
        snaps = sorted((root / "snapshots").glob("*"))
        if not snaps:
            raise FileNotFoundError(f"找不到 snapshot：{root}")
        snap = snaps[-1]
        revision = snap.name
    cfg = snap / "config.json"
    digest = hashlib.sha256(cfg.read_bytes()).hexdigest()[:16] if cfg.is_file() else ""
    return {"model_dir": str(snap), "revision": revision, "config_digest": digest}


def _normalize_action(obj: dict) -> dict | None:
    """容忍真实模型的各种写法：tool/action/name 别名；参数既可以嵌套也可以平铺。"""
    if not isinstance(obj, dict):
        return None
    tool = obj.get("tool") or obj.get("action") or obj.get("name") or obj.get("tool_name")
    if not tool:
        return None
    args = obj.get("arguments") or obj.get("args") or obj.get("parameters")
    if not isinstance(args, dict):
        args = {k: v for k, v in obj.items()
                if k not in ("tool", "action", "name", "tool_name", "arguments", "args", "parameters")}
    return {"tool": str(tool), "arguments": args or {}}


def _extract_json_action(text: str) -> dict:
    """从模型输出里抽第一个 JSON 动作（容忍围栏、前后废话、嵌套参数）。"""
    text = text.strip()
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            norm = _normalize_action(obj)
            if norm is not None:
                return norm
    except json.JSONDecodeError:
        pass
    # 括号配平扫描（正确处理字符串与转义），逐段尝试解析
    depth, start, in_str, esc = 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = None
                    continue
                if isinstance(obj, dict):
                    norm = _normalize_action(obj)
                    if norm is not None:
                        return norm
                start = None
    raise ValueError(f"模型输出无法解析为动作：{text[:200]!r}")


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    parse_retries: int = 0
    seconds: float = 0.0
    per_call: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "parse_retries": self.parse_retries,
            "seconds": round(self.seconds, 3),
        }


class VLLMServerModel:
    """通过 OpenAI 兼容接口调用常驻的 vLLM 服务（推荐：并发跑 episode 时利用率才上得去）。"""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", model: str = "qwen3.5-9b",
                 temperature: float = 0.7, max_tokens: int = 512, n: int = 1,
                 timeout: float = 300.0, max_parse_retries: int = 2, api_key: str = "",
                 extra_body: dict | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.n = n
        self.timeout = timeout
        self.max_parse_retries = max_parse_retries
        self.api_key = api_key
        # 网关直连时用它关掉思考段（与本机 vLLM 的 enable_thinking=False 对齐）
        self.extra_body = dict(extra_body or {})
        self.model_id = f"vllm:{model}" + (f"+{sorted(self.extra_body)}" if self.extra_body else "")
        self.usage = Usage()
        self._messages: list = []

    # --- Model 协议 ---
    def reset(self, seed: int, system_prompt: str) -> None:
        self._seed = seed
        self._messages = [{"role": "system", "content": system_prompt}]

    def propose(self, observation: str, tools: list) -> dict:
        self._messages.append({"role": "user", "content": observation})
        last_err = None
        for attempt in range(self.max_parse_retries + 1):
            text = self._chat(self._messages)
            try:
                action = _extract_json_action(text)
                self._messages.append({"role": "assistant", "content": json.dumps(action, ensure_ascii=False)})
                return action
            except ValueError as exc:
                last_err = exc
                self.usage.parse_retries += 1
                self._messages.append({"role": "assistant", "content": text})
                self._messages.append({"role": "user", "content":
                                       "Your last reply was not a single JSON action. Reply again with exactly one JSON object."})
        raise RuntimeError(f"解析失败：{last_err}")

    # --- HTTP ---
    def _chat(self, messages: list) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "seed": getattr(self, "_seed", 0),
            **self.extra_body,
        }
        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})},
        )
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        dt = time.perf_counter() - t0
        usage = data.get("usage") or {}
        self.usage.calls += 1
        self.usage.prompt_tokens += usage.get("prompt_tokens", 0)
        self.usage.completion_tokens += usage.get("completion_tokens", 0)
        self.usage.seconds += dt
        self.usage.per_call.append({"seconds": round(dt, 3),
                                    "prompt_tokens": usage.get("prompt_tokens", 0),
                                    "completion_tokens": usage.get("completion_tokens", 0)})
        return data["choices"][0]["message"]["content"]


class LocalTransformersModel:
    """本地 transformers 后端（冒烟测试用；批量跑请用 VLLMServerModel）。"""

    def __init__(self, ckpt_root: Path = CKPT_ROOT, max_new_tokens: int = 512, dtype: str = "bfloat16"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        info = resolve_ckpt(ckpt_root)
        self.model_id = f"local:{Path(info['model_dir']).name}:{info['config_digest']}"
        self.tok = AutoTokenizer.from_pretrained(info["model_dir"], trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            info["model_dir"], dtype=getattr(torch, dtype), device_map="auto", trust_remote_code=True
        )
        self.max_new_tokens = max_new_tokens
        self.usage = Usage()
        self._messages: list = []

    def reset(self, seed: int, system_prompt: str) -> None:
        self._seed = seed
        self._messages = [{"role": "system", "content": system_prompt}]

    def propose(self, observation: str, tools: list) -> dict:
        import torch
        self._messages.append({"role": "user", "content": observation})
        prompt = self.tok.apply_chat_template(self._messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tok(prompt, return_tensors="pt").to(self.model.device)
        t0 = time.perf_counter()
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens,
                                      do_sample=self.temperature > 0, temperature=max(self.temperature, 1e-5))
        text = self.tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        self.usage.calls += 1
        self.usage.seconds += time.perf_counter() - t0
        action = _extract_json_action(text)
        self._messages.append({"role": "assistant", "content": json.dumps(action, ensure_ascii=False)})
        return action


def build_system_prompt(task_prompt: str, tools: list, harness) -> str:
    addendum = f"\nHARNESS POLICY\n{harness.prompt_addendum}\n" if harness.prompt_addendum else ""
    base = SYSTEM_TEMPLATE.format(task=task_prompt, tools=", ".join(tools), addendum=addendum)
    return harness.transform_prompt(base)
