"""Anthropic Messages API client.

Translates the internal OpenAI-shaped message list into Anthropic content blocks. Written
in Phase 1 per the roadmap; it is *not* exercised by the E-00 run because no
ANTHROPIC_API_KEY was available in the development environment (see PROJECT_STATE section
"Environment notes"). It is covered by a translation unit test only, and that limitation
is recorded rather than papered over.
"""

from __future__ import annotations

import os
from typing import Any

from agentfw.agent.providers.base import Completion, ToolCall, post_json
from agentfw.sandbox.registry import ToolSpec

ANTHROPIC_VERSION = "2023-06-01"


def to_anthropic(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Return (system_prompt, anthropic_messages)."""
    system = ""
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            system = str(m.get("content") or "")
        elif role == "user":
            out.append({"role": "user", "content": [{"type": "text", "text": m["content"]}]})
        elif role == "assistant":
            blocks: list[dict[str, Any]] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for c in m.get("tool_calls") or []:
                import json as _json

                blocks.append(
                    {
                        "type": "tool_use",
                        "id": c["id"],
                        "name": c["function"]["name"],
                        "input": _json.loads(c["function"]["arguments"] or "{}"),
                    }
                )
            out.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": m["tool_call_id"],
                "content": m.get("content") or "",
            }
            if out and out[-1]["role"] == "user":
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
    return system, out


class AnthropicClient:
    def __init__(
        self,
        model: str,
        *,
        base_url: str | None = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
        temperature: float | None = 0.0,
        max_tokens: int = 1024,
    ) -> None:
        self.model = model
        self.name = model
        self.base_url = (
            base_url or os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com"
        ).rstrip("/")
        self.api_key = os.environ.get(api_key_env, "")
        if not self.api_key:
            raise RuntimeError(f"{api_key_env} is not set")
        self.temperature = temperature
        self.max_tokens = max_tokens

    @staticmethod
    def tool_schema(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]

    def complete(self, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> Completion:
        system, msgs = to_anthropic(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": msgs,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = self.tool_schema(tools)
        if self.temperature is not None:
            payload["temperature"] = self.temperature

        data = post_json(
            f"{self.base_url}/v1/messages",
            payload,
            {"x-api-key": self.api_key, "anthropic-version": ANTHROPIC_VERSION},
        )
        text_parts, calls = [], []
        for i, block in enumerate(data.get("content") or []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                calls.append(
                    ToolCall(
                        id=str(block.get("id") or f"call_{i}"),
                        name=str(block.get("name", "")),
                        arguments=dict(block.get("input") or {}),
                    )
                )
        usage = data.get("usage") or {}
        prompt_t = int(usage.get("input_tokens", 0))
        completion_t = int(usage.get("output_tokens", 0))
        return Completion(
            text="".join(text_parts),
            tool_calls=tuple(calls),
            usage={
                "prompt_tokens": prompt_t,
                "completion_tokens": completion_t,
                "total_tokens": prompt_t + completion_t,
            },
            stop_reason=str(data.get("stop_reason") or ""),
        )
