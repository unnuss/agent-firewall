"""OpenAI-compatible Chat Completions client.

Also serves any OpenAI-compatible endpoint (vLLM, Ollama, LM Studio) via ``base_url``,
which is why the local provider is a thin factory over this class rather than a separate
implementation.

Model-family quirks are declared, not discovered by trial and error: the gpt-5 family
takes ``max_completion_tokens`` and refuses a non-default ``temperature``, so a profile
records that instead of the client retrying on a 400.
"""

from __future__ import annotations

import os
from typing import Any

from agentfw.agent.providers.base import Completion, ToolCall, _parse_args, post_json
from agentfw.sandbox.registry import ToolSpec


def _profile(model: str) -> dict[str, Any]:
    """Per-family request quirks."""
    if model.startswith(("gpt-5", "o1", "o3", "o4")):
        return {"token_param": "max_completion_tokens", "supports_temperature": False}
    return {"token_param": "max_tokens", "supports_temperature": True}


class OpenAIChatClient:
    def __init__(
        self,
        model: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        api_key_env: str = "OPENAI_API_KEY",
        api_key: str | None = None,
        temperature: float | None = 0.0,
        max_tokens: int = 1024,
        seed: int | None = None,
        extra_body: dict[str, Any] | None = None,
        require_key: bool = True,
    ) -> None:
        self.model = model
        self.name = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.seed = seed
        self.extra_body = dict(extra_body or {})
        self.api_key = api_key or os.environ.get(api_key_env, "")
        if require_key and not self.api_key:
            raise RuntimeError(f"{api_key_env} is not set; cannot reach {self.base_url}")
        self.profile = _profile(model)

    @staticmethod
    def tool_schema(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def complete(self, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> Completion:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            self.profile["token_param"]: self.max_tokens,
        }
        if tools:
            payload["tools"] = self.tool_schema(tools)
            payload["tool_choice"] = "auto"
        if self.temperature is not None and self.profile["supports_temperature"]:
            payload["temperature"] = self.temperature
        if self.seed is not None:
            payload["seed"] = self.seed
        payload.update(self.extra_body)

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = post_json(f"{self.base_url}/chat/completions", payload, headers)

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        calls = tuple(
            ToolCall(
                id=str(c.get("id") or f"call_{i}"),
                name=str((c.get("function") or {}).get("name", "")),
                arguments=_parse_args((c.get("function") or {}).get("arguments")),
            )
            for i, c in enumerate(msg.get("tool_calls") or [])
        )
        usage = data.get("usage") or {}
        return Completion(
            text=str(msg.get("content") or ""),
            tool_calls=calls,
            usage={
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
            },
            stop_reason=str(choice.get("finish_reason") or ""),
        )


def local_client(model: str, base_url: str | None = None, **kwargs: Any) -> OpenAIChatClient:
    """Open-weight models behind a local OpenAI-compatible server (Ollama / vLLM)."""
    url = base_url or os.environ.get("AGENTFW_LOCAL_BASE_URL", "http://localhost:11434/v1")
    kwargs.setdefault("api_key", "local")
    kwargs.setdefault("require_key", False)
    return OpenAIChatClient(model, base_url=url, **kwargs)
