"""What each tool can do, expressed in effect classes.

**Why this file exists at all.** A compiler that reads only the utterance cannot know that
"give him read access to the copy in my cloud bucket" is `(GRANT, CLOUD_STORAGE)` rather
than `(GRANT, USER_FILES)`; that distinction lives in the tool layer, not in English. The
person who wrote the gold scopes had the tool list in front of them (D-023), and a deployed
compiler has the application's registered tools in front of it too. So the catalogue is a
legitimate compiler input, and withholding it would measure a harder problem than the one
the system actually faces.

**Why it is a table rather than a call into the declarers.** ``ToolSpec.declare`` is a
function of *arguments and world state*, and at compile time there are no arguments yet:
`files_write` is CREATE or WRITE depending on whether the path exists, `files_read` is
READ:USER_FILES or READ:SECRETS depending on the file. The catalogue is therefore the
*ceiling* — every class a tool could produce — and it is deliberately an over-approximation
in the one direction that is safe to over-approximate: it tells the compiler what is
possible, never what is authorized.

**Drift protection.** A hand-kept table beside a set of declarers is exactly the sort of
thing that rots. Two tests stop that: every registered tool must appear here, and every
effect class the declarers actually produced across the committed E-00 corpus must be
listed for its tool. If somebody adds a tool or widens a declarer, the tests fail.
"""

from __future__ import annotations

from agentfw.core.scope import ec
from agentfw.core.types import EffectClass, ResourceClass, Verb

# tool name -> every effect class that tool could produce, for any arguments.
TOOL_EFFECTS: dict[str, tuple[EffectClass, ...]] = {
    # calendar
    "calendar_list": (ec("READ", "CALENDAR"),),
    "calendar_create": (ec("CREATE", "CALENDAR"),),
    "calendar_delete": (ec("DELETE", "CALENDAR"),),
    # contacts
    "contacts_search": (ec("READ", "CONTACTS"),),
    # email
    "email_list": (ec("READ", "EMAIL"),),
    "email_read": (ec("READ", "EMAIL"),),
    "email_draft": (ec("CREATE", "EMAIL"),),
    "email_send": (ec("SEND", "EMAIL"),),
    # files. files_read yields READ:SECRETS on a file the world marks SECRET, which is
    # why two classes are listed for one tool.
    "files_list": (ec("READ", "USER_FILES"),),
    "files_read": (ec("READ", "USER_FILES"), ec("READ", "SECRETS")),
    "files_write": (ec("CREATE", "USER_FILES"), ec("WRITE", "USER_FILES")),
    "files_delete": (ec("DELETE", "USER_FILES"),),
    "files_share_link": (ec("GRANT", "USER_FILES"),),
    # cloud storage
    "storage_list": (ec("READ", "CLOUD_STORAGE"),),
    "storage_upload": (ec("CREATE", "CLOUD_STORAGE"),),
    "storage_share": (ec("GRANT", "CLOUD_STORAGE"),),
    # web
    "web_search": (ec("READ", "PUBLIC_WEB"),),
    "web_fetch": (ec("READ", "PUBLIC_WEB"),),
    "web_post": (ec("SEND", "PUBLIC_WEB"),),
    # travel and payments
    "travel_search_flights": (ec("READ", "PUBLIC_WEB"),),
    "travel_book_flight": (ec("PURCHASE", "FINANCIAL"),),
    "payments_list_methods": (ec("READ", "FINANCIAL"),),
    "payments_charge": (ec("PURCHASE", "FINANCIAL"),),
}


class UnknownTool(KeyError):
    """A tool with no catalogue entry. Fail loudly: guessing its authority is worse."""


def classes_for(tools: list[str]) -> list[EffectClass]:
    """Every effect class the given tool set could produce, in a stable order."""
    out: list[EffectClass] = []
    for name in tools:
        try:
            entries = TOOL_EFFECTS[name]
        except KeyError as exc:
            raise UnknownTool(
                f"{name!r} has no entry in intent/catalog.py. Add one rather than letting "
                "the compiler infer authority for a tool nobody has classified."
            ) from exc
        for item in entries:
            if item not in out:
                out.append(item)
    return sorted(out, key=lambda k: (k.verb.value, k.resource_class.value))


def read_only(classes: list[EffectClass]) -> list[EffectClass]:
    return [k for k in classes if k.verb is Verb.READ]


def render(klass: EffectClass) -> str:
    """The wire form used in configs, prompts and the gold scope file."""
    return f"{klass.verb.value}:{klass.resource_class.value}"


def parse(text: str) -> EffectClass:
    verb, _, resource = text.partition(":")
    return ec(verb.strip().upper(), resource.strip().upper())


def catalogue_lines(tools: list[str]) -> list[str]:
    """One line per available tool: name, effect classes, and the tool's own description.

    The description is read from the registry rather than restated here, so the text the
    compiler sees is the same text the agent sees and cannot drift away from it.
    """
    from agentfw.sandbox.registry import REGISTRY, load_all

    load_all()
    lines = []
    for name in tools:
        spec = REGISTRY.get(name)
        classes = " ".join(render(k) for k in TOOL_EFFECTS.get(name, ()))
        desc = " ".join((spec.description if spec else "").split())
        lines.append(f"- {name} [{classes}] — {desc}")
    return lines


ALL_VERBS = tuple(v.value for v in Verb)
ALL_RESOURCE_CLASSES = tuple(r.value for r in ResourceClass)
