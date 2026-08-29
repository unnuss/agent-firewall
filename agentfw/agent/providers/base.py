"""Provider abstraction (D-002: no agent framework, we own the tool-call boundary).

One protocol, three implementations (OpenAI-compatible, Anthropic, scripted). The
protocol is deliberately tiny: messages in, text plus tool calls plus usage out. Anything
richer would start hiding the boundary this project exists to study.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from agentfw.sandbox.registry import ToolSpec


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Completion:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: dict[str, int] = field(default_factory=dict)
    stop_reason: str = ""
    latency_s: float = 0.0


class LLMClient(Protocol):
    name: str

    def complete(self, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> Completion: ...


class ProviderError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# HTTP helper — stdlib only, so the provider layer stays inspectable and adds no
# dependency (see DECISIONS D-015).
# ---------------------------------------------------------------------------


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    *,
    timeout: float = 180.0,
    retries: int = 4,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    last: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json", **headers}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:600]
            last = ProviderError(f"HTTP {exc.code} from {url}: {detail}")
            if exc.code in (400, 401, 403, 404, 422):
                raise last from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = ProviderError(f"{type(exc).__name__} from {url}: {exc}")
        time.sleep(min(2**attempt, 16))
    raise last if last else ProviderError(f"request to {url} failed")


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"__unparsed__": str(raw)}
    return parsed if isinstance(parsed, dict) else {"value": parsed}
