"""Contacts tool family. Read-only; exists so recipient resolution is a real step."""

from __future__ import annotations

from typing import Any

from agentfw.core.types import Confidentiality, Effect, ResourceClass, Verb
from agentfw.sandbox.registry import ok, register
from agentfw.sandbox.world import World

FAMILY = "contacts"


def _declare(world: World, args: dict[str, Any]) -> list[Effect]:
    return [Effect(verb=Verb.READ, resource_class=ResourceClass.CONTACTS)]


@register(
    "contacts_search",
    family=FAMILY,
    description="Look up contacts by name, email or organisation substring.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
    declare=_declare,
)
def contacts_search(world: World, args: dict[str, Any]):
    q = str(args["query"]).lower()
    rows = [
        r
        for r in world.query("SELECT * FROM contacts ORDER BY name")
        if q in r["name"].lower() or q in r["email"].lower() or q in r["org"].lower()
    ]
    if not rows:
        return ok("No matching contacts.", data={"contacts": []}, effects=_declare(world, args))
    lines = [
        f"{r['name']} <{r['email']}>" + (f" ({r['org']})" if r["org"] else "") for r in rows
    ]
    return ok(
        "\n".join(lines),
        data={"contacts": [r["email"] for r in rows]},
        effects=_declare(world, args),
        confidentiality=Confidentiality.PRIVATE,
        origin="contacts",
    )
