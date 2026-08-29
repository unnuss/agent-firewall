"""Core data types.

Phase 1 defines only what the sandbox, the agent loop and the evaluation harness need:
the effect ontology, the label lattices, trace spans, proposed actions and tool results.
The firewall's own types (IntentScope, Verdict, AuditEvent) and the full label algebra
arrive in Phase 2 (core/labels.py, core/scope.py, core/audit.py).

Everything here is deterministic, dependency-free and side-effect-free: this module is TCB
code by ARCHITECTURE.md section 2, so it must stay that way.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


class Integrity(StrEnum):
    """Integrity lattice (PROJECT_SPEC section 6).

    The order is *not* total: the three untrusted-content kinds form an antichain sitting
    below UNTRUSTED_TOOL. rank() collapses them to a common level, which is sound because
    they carry identical authority (namely none).
    """

    SYSTEM = "SYSTEM"
    USER = "USER"
    AGENT_DERIVED = "AGENT_DERIVED"
    UNTRUSTED_TOOL = "UNTRUSTED_TOOL"
    UNTRUSTED_WEB = "UNTRUSTED_WEB"
    UNTRUSTED_EMAIL = "UNTRUSTED_EMAIL"
    UNTRUSTED_DOC = "UNTRUSTED_DOC"

    def rank(self) -> int:
        return _INTEGRITY_RANK[self]

    @property
    def is_untrusted(self) -> bool:
        return self.rank() <= 1


_INTEGRITY_RANK: dict[Integrity, int] = {
    Integrity.UNTRUSTED_WEB: 0,
    Integrity.UNTRUSTED_EMAIL: 0,
    Integrity.UNTRUSTED_DOC: 0,
    Integrity.UNTRUSTED_TOOL: 1,
    Integrity.AGENT_DERIVED: 2,
    Integrity.USER: 3,
    Integrity.SYSTEM: 4,
}

# Deterministic tie-break inside the untrusted-content antichain. Any member is an
# equally sound representative; we fix an order so that meet() is a pure function.
_INTEGRITY_TIEBREAK: tuple[Integrity, ...] = (
    Integrity.UNTRUSTED_WEB,
    Integrity.UNTRUSTED_EMAIL,
    Integrity.UNTRUSTED_DOC,
    Integrity.UNTRUSTED_TOOL,
    Integrity.AGENT_DERIVED,
    Integrity.USER,
    Integrity.SYSTEM,
)


class Confidentiality(StrEnum):
    """Confidentiality lattice; higher = more restricted."""

    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    SECRET = "SECRET"

    def rank(self) -> int:
        return {"PUBLIC": 0, "PRIVATE": 1, "SECRET": 2}[self.value]


class Label(BaseModel):
    """A label attached to a value in the trace.

    Labels are stamped by the runtime at the point data enters the trace and are never
    parsed out of content (THREAT_MODEL A4). ``origin`` is free-form provenance detail for
    the audit log and carries no authority.
    """

    model_config = ConfigDict(frozen=True)

    integrity: Integrity
    confidentiality: Confidentiality = Confidentiality.PUBLIC
    origin: str | None = None

    def meet(self, other: Label) -> Label:
        """Least-trusted integrity, most-restricted confidentiality.

        Named after the integrity lattice, which is the security-relevant half;
        confidentiality is joined in the same step (ARCHITECTURE section 3.2).
        """
        if self.integrity.rank() < other.integrity.rank():
            integrity = self.integrity
        elif other.integrity.rank() < self.integrity.rank():
            integrity = other.integrity
        else:
            integrity = min((self.integrity, other.integrity), key=_INTEGRITY_TIEBREAK.index)
        conf = max((self.confidentiality, other.confidentiality), key=lambda c: c.rank())
        origins = [o for o in (self.origin, other.origin) if o]
        return Label(
            integrity=integrity,
            confidentiality=conf,
            origin="+".join(dict.fromkeys(origins)) or None,
        )


def meet_all(labels: list[Label]) -> Label:
    if not labels:
        return Label(integrity=Integrity.AGENT_DERIVED)
    out = labels[0]
    for lab in labels[1:]:
        out = out.meet(lab)
    return out


# ---------------------------------------------------------------------------
# Effects (D-003)
# ---------------------------------------------------------------------------


class Verb(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    CREATE = "CREATE"
    DELETE = "DELETE"
    SEND = "SEND"
    PUBLISH = "PUBLISH"
    PURCHASE = "PURCHASE"
    EXECUTE = "EXECUTE"
    GRANT = "GRANT"


class ResourceClass(StrEnum):
    PUBLIC_WEB = "PUBLIC_WEB"
    USER_FILES = "USER_FILES"
    SECRETS = "SECRETS"
    EMAIL = "EMAIL"
    CALENDAR = "CALENDAR"
    CONTACTS = "CONTACTS"
    FINANCIAL = "FINANCIAL"
    CLOUD_STORAGE = "CLOUD_STORAGE"
    SYSTEM = "SYSTEM"


class Reversibility(StrEnum):
    REVERSIBLE = "REVERSIBLE"
    COSTLY_TO_REVERSE = "COSTLY_TO_REVERSE"
    IRREVERSIBLE = "IRREVERSIBLE"


class Externality(StrEnum):
    NONE = "NONE"
    VISIBLE_TO_THIRD_PARTY = "VISIBLE_TO_THIRD_PARTY"
    BINDING_ON_USER = "BINDING_ON_USER"


class EffectClass(BaseModel):
    """The unit an IntentScope authorizes (D-003)."""

    model_config = ConfigDict(frozen=True)

    verb: Verb
    resource_class: ResourceClass

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"({self.verb.value}, {self.resource_class.value})"


class Magnitude(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit: str  # "usd", "recipients", "files", "bytes"
    value: float


class Effect(BaseModel):
    """A consequence, decoupled from the tool that produced it."""

    model_config = ConfigDict(frozen=True)

    verb: Verb
    resource_class: ResourceClass
    reversibility: Reversibility = Reversibility.REVERSIBLE
    externality: Externality = Externality.NONE
    magnitude: Magnitude | None = None
    # Which concrete resource the effect landed on; oracles match against this.
    resource_id: str | None = None

    @property
    def effect_class(self) -> EffectClass:
        return EffectClass(verb=self.verb, resource_class=self.resource_class)


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


SpanKind = Literal[
    "system_prompt",
    "user_turn",
    "agent_text",
    "agent_tool_call",
    "tool_result",
    "tool_error",
    "ask",
    "ask_answer",
]


class TraceSpan(BaseModel):
    """One labeled unit of the episode transcript.

    Labels are assigned here, at ingestion, and never revised on the basis of content.
    The firewall (Phase 2) reads spans; it does not read raw provider messages.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    step: int
    kind: SpanKind
    label: Label
    content: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    # ids of spans this span was derived from (argument provenance).
    derived_from: tuple[str, ...] = ()
    meta: dict[str, Any] = Field(default_factory=dict)


class ProposedAction(BaseModel):
    """A tool call the agent wants to make, before anything has happened.

    Provenance is recorded in two forms, because they have different error profiles:

    ``arg_label`` is the **conservative** meet over every span ingested so far in the
    episode. It is sound (it can never under-state taint) and imprecise (one untrusted web
    page taints the rest of the episode). Phase 3's dependency screener exists to sharpen
    exactly this, and the imprecision is the reason it is needed.

    ``derived_from`` is **literal-match evidence**: span ids whose content contains an
    argument value verbatim. Deterministic, TCB-safe, and the thing an audit entry can show
    a human. It under-approximates influence (an argument the model paraphrased leaves no
    literal trace), so it is evidence, never authority.
    """

    model_config = ConfigDict(frozen=True)

    call_id: str
    step: int
    tool_name: str
    args: dict[str, Any]
    rationale: str = ""
    arg_label: Label
    derived_from: tuple[str, ...] = ()


class ToolResult(BaseModel):
    """What a sandbox tool hands back.

    ``label`` is set by the tool implementation (trusted code), not by the content.
    ``effects`` are the consequences that *actually occurred*; a failed call yields none.
    """

    model_config = ConfigDict(frozen=True)

    ok: bool = True
    content: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    label: Label = Label(integrity=Integrity.UNTRUSTED_TOOL)
    effects: tuple[Effect, ...] = ()
    error: str | None = None
