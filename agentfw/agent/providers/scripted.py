"""A scripted client: deterministic, offline, free.

Used by the unit tests so the agent loop, the router and the oracles can be tested without
touching a provider. Also useful as a smoke-test backend for new scenarios.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from agentfw.agent.providers.base import Completion, ToolCall
from agentfw.sandbox.registry import ToolSpec

Step = Completion | Callable[[list[dict[str, Any]]], Completion]


class ScriptedClient:
    def __init__(self, steps: Sequence[Step], name: str = "scripted") -> None:
        self.steps = list(steps)
        self.name = name
        self.calls = 0
        self.seen: list[list[dict[str, Any]]] = []

    def complete(self, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> Completion:
        self.seen.append(list(messages))
        if self.calls >= len(self.steps):
            self.calls += 1
            return Completion(text="Done.", stop_reason="stop")
        step = self.steps[self.calls]
        self.calls += 1
        out = step(messages) if callable(step) else step
        return out


def say(text: str) -> Completion:
    return Completion(text=text, stop_reason="stop")


def call(name: str, args: dict[str, Any], *, text: str = "", cid: str = "c1") -> Completion:
    return Completion(
        text=text,
        tool_calls=(ToolCall(id=cid, name=name, arguments=args),),
        stop_reason="tool_calls",
    )
