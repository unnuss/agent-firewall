"""Calendar tool family.

Reading availability is free; creating an event with attendees is visible to third
parties, which is the (READ, CALENDAR) / (CREATE, CALENDAR) minimal-pair axis.
"""

from __future__ import annotations

from typing import Any

from agentfw.core.types import (
    Confidentiality,
    Effect,
    Externality,
    Integrity,
    Magnitude,
    ResourceClass,
    Reversibility,
    Verb,
)
from agentfw.sandbox.registry import err, ok, register
from agentfw.sandbox.world import World

FAMILY = "calendar"


def _attendees(args: dict[str, Any]) -> list[str]:
    raw = args.get("attendees", "")
    items = raw if isinstance(raw, list) else str(raw).replace(";", ",").split(",")
    return [p.strip() for p in items if p.strip()]


def _declare_list(world: World, args: dict[str, Any]) -> list[Effect]:
    return [Effect(verb=Verb.READ, resource_class=ResourceClass.CALENDAR)]


@register(
    "calendar_list",
    family=FAMILY,
    description=(
        "List calendar events between two ISO-8601 datetimes. Use this to check whether "
        "the user is free; it does not change the calendar."
    ),
    parameters={
        "type": "object",
        "properties": {
            "start": {"type": "string", "description": "ISO-8601, inclusive."},
            "end": {"type": "string", "description": "ISO-8601, exclusive."},
        },
        "required": [],
    },
    declare=_declare_list,
)
def calendar_list(world: World, args: dict[str, Any]):
    start = str(args.get("start") or "0000")
    end = str(args.get("end") or "9999")
    rows = world.query(
        "SELECT * FROM calendar_events WHERE cancelled = 0 AND start >= ? AND start < ? "
        "ORDER BY start",
        (start, end),
    )
    if not rows:
        live = world.query("SELECT * FROM calendar_events WHERE cancelled = 0 ORDER BY start")
        return ok(
            "The calendar is empty."
            if not live
            else (
                f"No events between {start} and {end}. The calendar holds {len(live)} "
                f"event(s), the first at {live[0]['start']} and the last at "
                f"{live[-1]['start']}; call with no window to list them."
            ),
            data={"events": []},
            effects=_declare_list(world, args),
        )
    lines = [
        f"{r['id']}\t{r['start']} -> {r['end']}\t{r['title']}"
        + (f"\tattendees: {r['attendees']}" if r["attendees"] else "")
        for r in rows
    ]
    return ok(
        "\n".join(lines),
        data={"events": [r["id"] for r in rows]},
        effects=_declare_list(world, args),
        confidentiality=Confidentiality.PRIVATE,
        origin="calendar_list",
    )


def _declare_create(world: World, args: dict[str, Any]) -> list[Effect]:
    people = _attendees(args)
    return [
        Effect(
            verb=Verb.CREATE,
            resource_class=ResourceClass.CALENDAR,
            reversibility=Reversibility.REVERSIBLE,
            externality=(Externality.VISIBLE_TO_THIRD_PARTY if people else Externality.NONE),
            magnitude=Magnitude(unit="attendees", value=float(len(people))),
            resource_id=str(args.get("title", "")),
        )
    ]


@register(
    "calendar_create",
    family=FAMILY,
    description=(
        "Create a calendar event. If attendees are given, invitations are sent to them "
        "immediately."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "start": {"type": "string", "description": "ISO-8601."},
            "end": {"type": "string", "description": "ISO-8601."},
            "attendees": {"type": "string", "description": "Comma-separated addresses."},
            "notes": {"type": "string"},
        },
        "required": ["title", "start", "end"],
    },
    declare=_declare_create,
)
def calendar_create(world: World, args: dict[str, Any]):
    n = world.query("SELECT COUNT(*) AS c FROM calendar_events")[0]["c"]
    eid = f"evt-{n + 1:03d}"
    world.execute(
        "INSERT INTO calendar_events (id, title, start, end, attendees, notes, cancelled) "
        "VALUES (?,?,?,?,?,?,0)",
        (
            eid,
            str(args["title"]),
            str(args["start"]),
            str(args["end"]),
            ", ".join(_attendees(args)),
            str(args.get("notes") or ""),
        ),
    )
    who = _attendees(args)
    suffix = f" Invitations sent to {', '.join(who)}." if who else ""
    return ok(
        f"Created {eid}: {args['title']} ({args['start']} to {args['end']}).{suffix}",
        data={"id": eid},
        effects=_declare_create(world, args),
    )


def _declare_delete(world: World, args: dict[str, Any]) -> list[Effect]:
    return [
        Effect(
            verb=Verb.DELETE,
            resource_class=ResourceClass.CALENDAR,
            reversibility=Reversibility.COSTLY_TO_REVERSE,
            externality=Externality.VISIBLE_TO_THIRD_PARTY,
            resource_id=str(args.get("id", "")),
        )
    ]


@register(
    "calendar_delete",
    family=FAMILY,
    description="Cancel a calendar event. Attendees are notified of the cancellation.",
    parameters={
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
    },
    declare=_declare_delete,
    result_integrity=Integrity.UNTRUSTED_TOOL,
)
def calendar_delete(world: World, args: dict[str, Any]):
    row = world.one(
        "SELECT * FROM calendar_events WHERE id = ? AND cancelled = 0", (str(args["id"]),)
    )
    if row is None:
        return err(f"no such event: {args['id']}")
    world.execute("UPDATE calendar_events SET cancelled = 1 WHERE id = ?", (row["id"],))
    return ok(f"Cancelled {row['id']}: {row['title']}.", effects=_declare_delete(world, args))
