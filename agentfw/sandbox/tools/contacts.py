"""Contacts tool family. Read-only; exists so recipient resolution is a real step."""

from __future__ import annotations

from typing import Any

from agentfw.core.types import Confidentiality, Effect, ResourceClass, Verb
from agentfw.sandbox import search
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
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Every word of the query must appear in the contact's name, email or "
                    "organisation. Word prefixes count."
                ),
            }
        },
        "required": ["query"],
    },
    declare=_declare,
)
def contacts_search(world: World, args: dict[str, Any]):
    q = str(args["query"])
    all_rows = world.query("SELECT * FROM contacts ORDER BY name")
    rows = [r for r in all_rows if search.matches(q, r["name"], r["email"], r["org"])]
    if not rows:
        return ok(
            search.no_match("contacts", q, "name, email and organisation", len(all_rows)),
            data={"contacts": []},
            effects=_declare(world, args),
        )
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
