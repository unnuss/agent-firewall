"""utterance -> IntentScope.

**The seam this file defends.** A compiler takes exactly two inputs: the text of a USER
turn, and the list of tools the application registered. It never sees a tool result, a web
page, an email body, or anything else the world produced, and it is called once, before the
agent runs. That is not a convention — it is the signature. An attacker who can put text in
front of the compiler can write the user's authorization scope, which is a strictly better
position than being able to hijack the agent, so the input restriction is the security
property this component has and it is enforced by having nowhere to put the other data.

**What a compiler may and may not do to the security argument.** Nothing here is in the
TCB. The scope it emits is the *starting* authority set; monotonicity (P1) still means only
a human can widen it, P2 still asserts every executed effect is in scope, and no compiler
output can produce ``Signal(structural=True)``. What a wrong scope costs is measured, in
E-09a as set error against the gold labels and in E-01b as the verdicts that error produces.

**Three compilers, and two of them are floors.** ``ToolCeilingCompiler`` grants everything
the tool set can produce — the authority a static per-task allowlist confers, which is what
MCP gateways do today. ``ReadOnlyCompiler`` grants only reads. Between them sits every
possible compiler, and the LLM one has to earn its place by beating both on *both* axes at
once: the ceiling is unbeatable on utility and hopeless on security, the read-only floor is
the reverse. Reporting the LLM against a single baseline would let it look good by moving
along the trade-off rather than off it.

**Failure is empty, not partial.** If the API errors, or the model returns something that
does not parse, the compiled scope is *empty* and the error is recorded. An empty scope
authorizes nothing, so a compiler outage degrades to refusing everything rather than to
authorizing whatever half-parsed. Under deny-by-default that is the only sound direction,
and it means a compile error can never be mistaken for a security result: the episodes it
affects are counted separately in every report.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from agentfw.core.scope import Constraint, IntentScope, scope_from_user_turn
from agentfw.core.types import EffectClass
from agentfw.intent import catalog, prompts

# The span id the agent loop gives the user's turn (see eval/scopes.py). A compiled grant
# carries it for the same reason a gold one does: the authority traces to the user's turn,
# and the compiler is a transducer of that turn rather than a source of authority.
USER_TURN_SPAN = "s002"

VALID_CONSTRAINT_KINDS = frozenset(
    {"budget", "recipient", "domain", "time_window", "resource_glob", "magnitude"}
)


class CompiledScope(BaseModel):
    """One compilation, as an artifact on disk.

    Everything needed to reproduce or audit the result is here — which model, which seed,
    which prompt, what it said verbatim — because a compiled scope is data that later
    experiments depend on and a number whose provenance is a lost API call is not evidence.
    """

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    variant_id: str
    compiler: str
    model: str = ""
    seed: int = 0
    prompt_version: int = 0
    prompt_digest: str = ""
    utterance: str = ""
    tools: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    constraints: tuple[dict[str, Any], ...] = ()
    open_questions: tuple[str, ...] = ()
    # Set when the model produced text we could not use. The scope is empty in that case.
    error: str | None = None
    # Classes the model named that are not producible by any tool it was shown. Kept as a
    # diagnostic rather than filtered silently: a compiler hallucinating authority over
    # resources the application does not have is a finding, not noise.
    unsupported_effects: tuple[str, ...] = ()
    usage: dict[str, int] = Field(default_factory=dict)
    latency_s: float = 0.0
    raw: str = ""

    @property
    def effect_classes(self) -> list[EffectClass]:
        return [catalog.parse(e) for e in self.effects]

    def to_scope(self, objective: str) -> IntentScope:
        """Build the IntentScope the firewall will run against.

        A constraint that does not validate is dropped *and* recorded in the scope's own
        open questions. Dropping it is a widening, so it is the one thing here that could
        make the system less safe than the model intended; it is visible rather than
        silent, and E-09a counts it.
        """
        constraints: list[Constraint] = []
        dropped: list[str] = []
        for raw in self.constraints:
            try:
                constraints.append(_build_constraint(raw))
            except Exception as exc:
                dropped.append(f"unusable constraint {raw!r}: {type(exc).__name__}: {exc}")
        return scope_from_user_turn(
            objective,
            self.effect_classes,
            span_id=USER_TURN_SPAN,
            constraints=constraints,
            open_questions=list(self.open_questions) + dropped,
        )


def _build_constraint(raw: dict[str, Any]) -> Constraint:
    data = dict(raw)
    kind = str(data.get("kind", "")).strip().lower()
    if kind not in VALID_CONSTRAINT_KINDS:
        raise ValueError(f"unknown constraint kind {kind!r}")
    data["kind"] = kind
    applies = data.pop("applies_to", None)
    for key in ("allowed_recipients", "allowed_domains", "globs"):
        if key in data and data[key] is not None:
            data[key] = tuple(data[key])
    data.pop("describe_as", None)
    return Constraint(
        applies_to=catalog.parse(applies) if applies else None,
        **{k: v for k, v in data.items() if v is not None},
    )


class Compiler(Protocol):
    """The whole interface. Two inputs, one artifact; nothing else is reachable."""

    name: str

    def compile(self, utterance: str, tools: list[str]) -> CompiledScope: ...


# ---------------------------------------------------------------------------
# Deterministic floors
# ---------------------------------------------------------------------------


class ToolCeilingCompiler:
    """Grant every effect class the available tools can produce.

    This is the authority a static per-task tool allowlist confers, which is roughly what
    an MCP gateway does today (EVALUATION baseline B-01 is the same idea evaluated as a
    defense rather than as a compiler). It has no notion of what the user asked for, so it
    is the upper bound on utility and the lower bound on security, and it costs nothing to
    run.
    """

    name = "tool-ceiling"

    def compile(self, utterance: str, tools: list[str]) -> CompiledScope:
        classes = catalog.classes_for(tools)
        return CompiledScope(
            scenario_id="",
            variant_id="",
            compiler=self.name,
            utterance=utterance,
            tools=tuple(tools),
            effects=tuple(catalog.render(k) for k in classes),
        )


class ReadOnlyCompiler:
    """Grant only reads. The other end of the trade-off: nothing unlicensed can happen,
    and no task that changes anything can be completed."""

    name = "read-only"

    def compile(self, utterance: str, tools: list[str]) -> CompiledScope:
        classes = catalog.read_only(catalog.classes_for(tools))
        return CompiledScope(
            scenario_id="",
            variant_id="",
            compiler=self.name,
            utterance=utterance,
            tools=tuple(tools),
            effects=tuple(catalog.render(k) for k in classes),
        )


# ---------------------------------------------------------------------------
# The LLM compiler
# ---------------------------------------------------------------------------

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """Tolerant of a fenced block or a sentence of preamble; strict about the rest."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        candidate = candidate.partition("\n")[2] if "\n" in candidate else candidate
    match = _JSON_BLOCK.search(candidate)
    if not match:
        raise ValueError("no JSON object in the response")
    return json.loads(match.group(0))


class LLMIntentCompiler:
    """Compile with a chat model, structured output, one call per utterance.

    The client is injected rather than constructed here so the unit tests can drive a
    scripted one and the whole component stays runnable with no network.
    """

    def __init__(self, client: Any, *, name: str = "", seed: int = 0) -> None:
        self.client = client
        self.name = name or f"llm:{getattr(client, 'name', 'unknown')}"
        self.seed = seed

    def compile(self, utterance: str, tools: list[str]) -> CompiledScope:
        messages = prompts.build(utterance, tools)
        base = dict(
            scenario_id="",
            variant_id="",
            compiler=self.name,
            model=str(getattr(self.client, "model", getattr(self.client, "name", ""))),
            seed=self.seed,
            prompt_version=prompts.VERSION,
            prompt_digest=prompts.digest(utterance, tools),
            utterance=utterance,
            tools=tuple(tools),
        )
        started = time.perf_counter()
        try:
            completion = self.client.complete(messages, [])
        except Exception as exc:
            return CompiledScope(
                **base,
                error=f"{type(exc).__name__}: {exc}"[:400],
                latency_s=round(time.perf_counter() - started, 3),
            )
        latency = round(time.perf_counter() - started, 3)
        try:
            payload = extract_json(completion.text)
        except Exception as exc:
            return CompiledScope(
                **base,
                error=f"unparsable response: {type(exc).__name__}: {exc}"[:400],
                raw=completion.text[:2000],
                usage=dict(completion.usage),
                latency_s=latency,
            )
        effects, unsupported = _clean_effects(payload.get("effects"), tools)
        return CompiledScope(
            **base,
            effects=effects,
            unsupported_effects=unsupported,
            constraints=tuple(
                c for c in (payload.get("constraints") or []) if isinstance(c, dict)
            ),
            open_questions=tuple(
                str(q) for q in (payload.get("open_questions") or []) if str(q).strip()
            ),
            usage=dict(completion.usage),
            latency_s=latency,
            raw=completion.text[:2000],
        )


def _clean_effects(raw: Any, tools: list[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Normalise the model's effect list; separate the ones no available tool can produce.

    Two kinds of junk are dropped: strings that are not effect classes at all, and classes
    outside the ontology. Both are recorded as unsupported rather than silently discarded.
    Classes that are well-formed but unreachable with these tools are *kept in the scope* —
    an authorization to do something the application cannot do is harmless and removing it
    would flatter the compiler's precision — and reported separately.
    """
    available = set(catalog.classes_for(tools))
    kept: list[str] = []
    unsupported: list[str] = []
    for item in raw or []:
        text = str(item).strip().upper().replace(" ", "")
        try:
            klass = catalog.parse(text)
        except Exception:
            unsupported.append(str(item)[:60])
            continue
        rendered = catalog.render(klass)
        if rendered in kept:
            continue
        kept.append(rendered)
        if klass not in available:
            unsupported.append(rendered)
    return tuple(kept), tuple(unsupported)
