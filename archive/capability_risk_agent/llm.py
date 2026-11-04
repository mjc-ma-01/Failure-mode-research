from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .json_utils import loads_json_maybe_fenced


Message = dict[str, str]


@dataclass
class OpenAIChatClient:
    model: str
    temperature: float = 0.2
    max_tokens: int = 4096
    base_url: str | None = None
    api_key: str | None = None
    timeout: float = 180.0

    def __post_init__(self) -> None:
        from openai import OpenAI

        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required unless you use --dry-run or --heuristic.")
        base_url = self.base_url or os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
        if base_url:
            parsed = urlparse(base_url)
            if parsed.scheme and parsed.netloc and parsed.path.rstrip("/") in {"", "/"}:
                base_url = base_url.rstrip("/") + "/v1"
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": self.timeout}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)

    def complete_text(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature if temperature is None else temperature,
            max_tokens=max_tokens or self.max_tokens,
        )
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            return _content_from_dict_response(response)
        content = response.choices[0].message.content
        return content or ""

    def complete_json(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        use_response_format: bool = True,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if use_response_format:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception:
            if not use_response_format:
                raise
            kwargs.pop("response_format", None)
            response = self._client.chat.completions.create(**kwargs)
        if isinstance(response, str):
            content = response
        elif isinstance(response, dict):
            content = _content_from_dict_response(response)
        else:
            content = response.choices[0].message.content or ""
        try:
            return loads_json_maybe_fenced(content)
        except Exception:
            repair_messages = [
                {
                    "role": "system",
                    "content": "Return valid JSON only. Repair malformed JSON without adding new facts.",
                },
                {
                    "role": "user",
                    "content": "Repair this into valid JSON only:\n" + content[:12000],
                },
            ]
            repair_kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": repair_messages,
                "temperature": 0,
                "max_tokens": max_tokens or self.max_tokens,
            }
            try:
                repaired_response = self._client.chat.completions.create(**repair_kwargs)
                if isinstance(repaired_response, str):
                    repaired = repaired_response
                elif isinstance(repaired_response, dict):
                    repaired = _content_from_dict_response(repaired_response)
                else:
                    repaired = repaired_response.choices[0].message.content or ""
                return loads_json_maybe_fenced(repaired)
            except Exception:
                raise


def _content_from_dict_response(response: dict[str, Any]) -> str:
    try:
        return response["choices"][0]["message"]["content"] or ""
    except Exception:
        pass
    for key in ("content", "text", "response", "answer", "output"):
        value = response.get(key)
        if isinstance(value, str):
            return value
    return str(response)
