"""The labeled trace.

The single rule this module exists to enforce: **a label is stamped when data enters the
trace, by the runtime, from the identity of the source** — never parsed out of the content
and never revised later on the basis of what the content says (THREAT_MODEL A4).

Everything the firewall will read in Phase 2 comes from here, so retro-fitting provenance
later is impossible by construction rather than merely discouraged.
"""

from __future__ import annotations

from typing import Any

from agentfw.core.types import (
    Confidentiality,
    Integrity,
    Label,
    SpanKind,
    TraceSpan,
    meet_all,
)

# Argument values shorter than this are too likely to collide by chance to count as
# literal provenance evidence.
MIN_EVIDENCE_LEN = 8


class Trace:
    def __init__(self) -> None:
        self.spans: list[TraceSpan] = []
        self._n = 0

    def add(
        self,
        kind: SpanKind,
        content: str,
        label: Label,
        *,
        step: int,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        derived_from: tuple[str, ...] = (),
        meta: dict[str, Any] | None = None,
    ) -> TraceSpan:
        self._n += 1
        span = TraceSpan(
            id=f"s{self._n:03d}",
            step=step,
            kind=kind,
            label=label,
            content=content,
            tool_name=tool_name,
            tool_args=tool_args,
            derived_from=derived_from,
            meta=meta or {},
        )
        self.spans.append(span)
        return span

    # -- convenience constructors, one per ingestion point --------------------

    def system(self, content: str) -> TraceSpan:
        return self.add(
            "system_prompt",
            content,
            Label(integrity=Integrity.SYSTEM, origin="system_prompt"),
            step=0,
        )

    def user(self, content: str, step: int = 0) -> TraceSpan:
        return self.add(
            "user_turn",
            content,
            Label(integrity=Integrity.USER, origin="user"),
            step=step,
        )

    def agent_text(self, content: str, step: int) -> TraceSpan:
        return self.add(
            "agent_text",
            content,
            Label(integrity=Integrity.AGENT_DERIVED, origin="agent"),
            step=step,
        )

    # -- provenance helpers ---------------------------------------------------

    def ingested(self) -> list[TraceSpan]:
        """Spans that carry data the model has seen. Excludes the model's own text."""
        return [
            s for s in self.spans if s.kind in ("tool_result", "user_turn", "system_prompt")
        ]

    def context_label(self) -> Label:
        """Conservative taint of everything the model has read so far.

        Sound over-approximation: if any untrusted content is in context, the model could
        in principle have been influenced by it. Phase 3 replaces this with a screener.
        """
        labels = [s.label for s in self.ingested()]
        if not labels:
            return Label(
                integrity=Integrity.SYSTEM,
                confidentiality=Confidentiality.PUBLIC,
                origin="empty",
            )
        return meet_all(labels)

    def literal_evidence(self, args: dict[str, Any]) -> tuple[str, ...]:
        """Span ids containing an argument value verbatim. Evidence, not authority."""
        needles = [
            v.strip()
            for v in (str(x) for x in args.values())
            if len(v.strip()) >= MIN_EVIDENCE_LEN
        ]
        if not needles:
            return ()
        hits = [s.id for s in self.ingested() if any(n in s.content for n in needles)]
        return tuple(hits)

    def to_json(self) -> list[dict[str, Any]]:
        return [s.model_dump(mode="json") for s in self.spans]
