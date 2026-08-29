"""Tool registry and the ToolRouter.

Two things matter here beyond plumbing:

1. **Every tool declares the Effect it produces as a function of its arguments** (D-003).
   ``ToolSpec.declare`` is pure and side-effect free; ``ToolSpec.handler`` performs the
   mutation and returns the effects that actually occurred. Phase 2 wires ``declare`` into
   the reference monitor so a decision can be made *before* anything happens. A test
   asserts the two agree, so the declaration cannot silently drift.

2. **The router is the only holder of world access.** The agent emits proposals; effects
   happen only past the router. In Phase 1 ``guard`` is always ``None`` (undefended,
   baseline B-00), but the seam exists from the first commit so Phase 2 is a wiring change
   rather than a rewrite.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from agentfw.core.types import (
    Confidentiality,
    Effect,
    Integrity,
    Label,
    ProposedAction,
    ToolResult,
)
from agentfw.sandbox.world import World

Handler = Callable[[World, dict[str, Any]], ToolResult]
Declarer = Callable[[World, dict[str, Any]], list[Effect]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    family: str
    description: str
    parameters: dict[str, Any]
    handler: Handler
    declare: Declarer
    # Label the runtime stamps on this tool's output. Set by trusted code, never by
    # anything in the returned content (THREAT_MODEL A4).
    result_integrity: Integrity = Integrity.UNTRUSTED_TOOL

    def required(self) -> list[str]:
        return list(self.parameters.get("required", []))


REGISTRY: dict[str, ToolSpec] = {}


def register(
    name: str,
    *,
    family: str,
    description: str,
    parameters: dict[str, Any],
    declare: Declarer,
    result_integrity: Integrity = Integrity.UNTRUSTED_TOOL,
) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        if name in REGISTRY:
            raise ValueError(f"duplicate tool registration: {name}")
        REGISTRY[name] = ToolSpec(
            name=name,
            family=family,
            description=description,
            parameters=parameters,
            handler=fn,
            declare=declare,
            result_integrity=result_integrity,
        )
        return fn

    return deco


def get_tools(names: list[str]) -> list[ToolSpec]:
    load_all()
    missing = [n for n in names if n not in REGISTRY]
    if missing:
        raise KeyError(f"unknown tools: {missing}")
    return [REGISTRY[n] for n in names]


def load_all() -> dict[str, ToolSpec]:
    """Import every tool module so the registry is populated."""
    from agentfw.sandbox.tools import (  # noqa: F401
        calendar,
        contacts,
        email,
        files,
        payments,
        storage,
        travel,
        web,
    )

    return REGISTRY


class Guard(Protocol):
    """The Phase 2 reference-monitor seam.

    Returns ``None`` to allow, or a refusal string to deny. Phase 1 never installs one.
    """

    def check(self, action: ProposedAction, declared: list[Effect]) -> str | None: ...


@dataclass
class ToolRouter:
    """Executes tool calls against the world. The agent never touches the world directly."""

    world: World
    tools: dict[str, ToolSpec]
    guard: Guard | None = None
    call_count: int = 0
    denials: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def for_tools(
        cls, world: World, names: list[str], guard: Guard | None = None
    ) -> ToolRouter:
        return cls(world=world, tools={t.name: t for t in get_tools(names)}, guard=guard)

    def specs(self) -> list[ToolSpec]:
        return list(self.tools.values())

    def declare(self, action: ProposedAction) -> list[Effect]:
        spec = self.tools.get(action.tool_name)
        if spec is None:
            return []
        try:
            return spec.declare(self.world, action.args)
        except Exception:  # a malformed proposal declares nothing; execution will error
            return []

    def execute(self, action: ProposedAction) -> ToolResult:
        spec = self.tools.get(action.tool_name)
        if spec is None:
            return ToolResult(
                ok=False,
                error=f"unknown tool {action.tool_name!r}",
                content=f"Error: unknown tool {action.tool_name!r}.",
                label=Label(integrity=Integrity.SYSTEM, origin="router"),
            )
        missing = [k for k in spec.required() if k not in action.args]
        if missing:
            return ToolResult(
                ok=False,
                error=f"missing required arguments: {missing}",
                content=f"Error: missing required arguments {missing}.",
                label=Label(integrity=Integrity.SYSTEM, origin="router"),
            )

        if self.guard is not None:
            refusal = self.guard.check(action, self.declare(action))
            if refusal is not None:
                self.denials.append({"action": action.model_dump(), "reason": refusal})
                return ToolResult(
                    ok=False,
                    error="blocked_by_firewall",
                    content=refusal,
                    label=Label(integrity=Integrity.SYSTEM, origin="firewall"),
                )

        self.call_count += 1
        try:
            result = spec.handler(self.world, action.args)
        except Exception as exc:  # tool bugs must not kill an episode
            return ToolResult(
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                content=f"Error: {type(exc).__name__}: {exc}",
                label=Label(integrity=Integrity.SYSTEM, origin="router"),
            )

        for eff in result.effects:
            self.world.record_effect(eff, spec.name, action.args, step=action.step)

        # The runtime — not the content — decides the label on ingested data.
        label = Label(
            integrity=spec.result_integrity,
            confidentiality=result.label.confidentiality,
            origin=result.label.origin or spec.name,
        )
        return result.model_copy(update={"label": label})


# -- small helpers shared by tool modules ------------------------------------


def ok(
    content: str,
    *,
    data: dict[str, Any] | None = None,
    effects: list[Effect] | None = None,
    confidentiality: Confidentiality = Confidentiality.PUBLIC,
    origin: str | None = None,
) -> ToolResult:
    return ToolResult(
        ok=True,
        content=content,
        data=data or {},
        effects=tuple(effects or []),
        label=Label(
            integrity=Integrity.UNTRUSTED_TOOL,
            confidentiality=confidentiality,
            origin=origin,
        ),
    )


def err(message: str) -> ToolResult:
    return ToolResult(
        ok=False,
        error=message,
        content=f"Error: {message}",
        label=Label(integrity=Integrity.SYSTEM, origin="tool"),
    )
