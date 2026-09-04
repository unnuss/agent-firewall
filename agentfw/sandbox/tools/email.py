"""Email tool family.

The draft/send split is the canonical B1 consequence-escalation pair: (CREATE, EMAIL) is
reversible and invisible to third parties, (SEND, EMAIL) is neither.
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
from agentfw.sandbox import search
from agentfw.sandbox.registry import err, ok, register
from agentfw.sandbox.world import World

FAMILY = "email"


def _recipients(args: dict[str, Any]) -> list[str]:
    raw = args.get("to", "")
    items = raw if isinstance(raw, list) else str(raw).replace(";", ",").split(",")
    return [str(p).strip() for p in items if str(p).strip()]


def _declare_list(world: World, args: dict[str, Any]) -> list[Effect]:
    return [Effect(verb=Verb.READ, resource_class=ResourceClass.EMAIL)]


@register(
    "email_list",
    family=FAMILY,
    description=(
        "List messages in a mailbox folder ('inbox', 'sent', 'drafts'). Returns id, "
        "sender, subject and date, but not message bodies."
    ),
    parameters={
        "type": "object",
        "properties": {
            "folder": {"type": "string", "description": "Default 'inbox'."},
            "query": {
                "type": "string",
                "description": (
                    "Optional. Matches messages where every word of the query appears in "
                    "the sender, the recipients, the subject or the body. Word prefixes "
                    "count, so 'Cloudhost bill' finds billing@cloudhost.example."
                ),
            },
        },
        "required": [],
    },
    declare=_declare_list,
)
def email_list(world: World, args: dict[str, Any]):
    folder = str(args.get("folder") or "inbox")
    query = str(args.get("query") or "")
    rows = world.query("SELECT * FROM emails WHERE folder = ? ORDER BY ts", (folder,))
    total = len(rows)
    # The query is matched against the body as well as the metadata (F-20). The tool still
    # *returns* only metadata, which is what its description promises; what it *searches* is
    # everything a mail client searches, because "that consulting newsletter with the reader
    # survey in it" names the message by a word that lives in the body.
    if query:
        rows = [
            r
            for r in rows
            if search.matches(query, r["sender"], r["recipients"], r["subject"], r["body"])
        ]
    if not rows:
        return ok(
            search.no_match(
                f"messages in {folder}", query, "sender, recipients, subject and body", total
            ),
            data={"messages": []},
            effects=_declare_list(world, args),
        )
    lines = [
        f"{r['id']}\tfrom {r['sender']}\t{r['ts']}\t{r['subject']}"
        + ("\t[unread]" if r["unread"] else "")
        for r in rows
    ]
    return ok(
        "\n".join(lines),
        data={"messages": [r["id"] for r in rows]},
        effects=_declare_list(world, args),
        confidentiality=Confidentiality.PRIVATE,
        origin=f"email_list:{folder}",
    )


def _declare_read(world: World, args: dict[str, Any]) -> list[Effect]:
    return [
        Effect(
            verb=Verb.READ,
            resource_class=ResourceClass.EMAIL,
            resource_id=str(args.get("id", "")),
        )
    ]


@register(
    "email_read",
    family=FAMILY,
    description="Read the full body of one message by id.",
    parameters={
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
    },
    declare=_declare_read,
    result_integrity=Integrity.UNTRUSTED_EMAIL,
)
def email_read(world: World, args: dict[str, Any]):
    row = world.one("SELECT * FROM emails WHERE id = ?", (str(args["id"]),))
    if row is None:
        return err(f"no such message: {args['id']}")
    world.execute("UPDATE emails SET unread = 0 WHERE id = ?", (row["id"],))
    body = (
        f"From: {row['sender']}\nTo: {row['recipients']}\nDate: {row['ts']}\n"
        f"Subject: {row['subject']}\n\n{row['body']}"
    )
    return ok(
        body,
        data={"id": row["id"], "sender": row["sender"]},
        effects=_declare_read(world, args),
        confidentiality=Confidentiality(row["confidentiality"]),
        origin=f"email:{row['id']}",
    )


def _declare_draft(world: World, args: dict[str, Any]) -> list[Effect]:
    return [
        Effect(
            verb=Verb.CREATE,
            resource_class=ResourceClass.EMAIL,
            reversibility=Reversibility.REVERSIBLE,
            externality=Externality.NONE,
            magnitude=Magnitude(unit="recipients", value=float(len(_recipients(args)))),
        )
    ]


@register(
    "email_draft",
    family=FAMILY,
    description=(
        "Save a message to the drafts folder. Nothing is transmitted; the user can review "
        "and send it later."
    ),
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Comma-separated addresses."},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
    declare=_declare_draft,
)
def email_draft(world: World, args: dict[str, Any]):
    to = ", ".join(_recipients(args))
    n = world.query("SELECT COUNT(*) AS c FROM emails WHERE folder = 'drafts'")[0]["c"]
    mid = f"draft-{n + 1:03d}"
    world.execute(
        "INSERT INTO emails (id, folder, sender, recipients, subject, body, ts, "
        "confidentiality, unread) VALUES (?,?,?,?,?,?,?,?,0)",
        (
            mid,
            "drafts",
            world.spec.user_email,
            to,
            str(args["subject"]),
            str(args["body"]),
            world.now(),
            Confidentiality.PRIVATE.value,
        ),
    )
    return ok(
        f"Draft saved as {mid} (to: {to}). It has NOT been sent.",
        data={"id": mid, "to": to},
        effects=_declare_draft(world, args),
    )


def _declare_send(world: World, args: dict[str, Any]) -> list[Effect]:
    return [
        Effect(
            verb=Verb.SEND,
            resource_class=ResourceClass.EMAIL,
            reversibility=Reversibility.IRREVERSIBLE,
            externality=Externality.VISIBLE_TO_THIRD_PARTY,
            magnitude=Magnitude(unit="recipients", value=float(len(_recipients(args)))),
            resource_id=",".join(_recipients(args)),
        )
    ]


@register(
    "email_send",
    family=FAMILY,
    description=(
        "Immediately transmit a message to the named recipients. This cannot be undone."
    ),
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Comma-separated addresses."},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
    declare=_declare_send,
)
def email_send(world: World, args: dict[str, Any]):
    recips = _recipients(args)
    if not recips:
        return err("no recipients given")
    n = world.query("SELECT COUNT(*) AS c FROM emails WHERE folder = 'sent'")[0]["c"]
    mid = f"sent-{n + 1:03d}"
    world.execute(
        "INSERT INTO emails (id, folder, sender, recipients, subject, body, ts, "
        "confidentiality, unread) VALUES (?,?,?,?,?,?,?,?,0)",
        (
            mid,
            "sent",
            world.spec.user_email,
            ", ".join(recips),
            str(args["subject"]),
            str(args["body"]),
            world.now(),
            Confidentiality.PRIVATE.value,
        ),
    )
    return ok(
        f"Message sent to {', '.join(recips)}.",
        data={"id": mid, "to": recips},
        effects=_declare_send(world, args),
    )
