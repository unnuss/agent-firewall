"""Filesystem tool family.

File *contents* are untrusted (a document can be attacker-planted), so results are stamped
UNTRUSTED_DOC. Directory listings are metadata produced by the runtime, so they are
UNTRUSTED_TOOL — still not authoritative, but not attacker-authored prose either.
"""

from __future__ import annotations

import fnmatch
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

FAMILY = "files"


def _live(world: World) -> list[dict[str, Any]]:
    return world.query("SELECT * FROM files WHERE deleted = 0 ORDER BY path")


def _matches(paths: list[dict[str, Any]], pattern: str) -> list[dict[str, Any]]:
    if not pattern or pattern == "*":
        return paths
    return [r for r in paths if fnmatch.fnmatch(r["path"], pattern)]


# -- files_list ---------------------------------------------------------------


def _declare_list(world: World, args: dict[str, Any]) -> list[Effect]:
    return [Effect(verb=Verb.READ, resource_class=ResourceClass.USER_FILES)]


@register(
    "files_list",
    family=FAMILY,
    description=(
        "List files in the user's workspace. Returns path, size in bytes and last "
        "modified time. Does not return file contents."
    ),
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Optional glob, e.g. 'reports/*.pdf'. Defaults to all files.",
            }
        },
        "required": [],
    },
    declare=_declare_list,
)
def files_list(world: World, args: dict[str, Any]):
    rows = _matches(_live(world), str(args.get("pattern") or "*"))
    if not rows:
        return ok("No files matched.", data={"files": []}, effects=_declare_list(world, args))
    lines = [f"{r['path']}\t{r['size_bytes']} bytes\tmodified {r['modified']}" for r in rows]
    return ok(
        "\n".join(lines),
        data={"files": [r["path"] for r in rows]},
        effects=_declare_list(world, args),
        confidentiality=Confidentiality.PRIVATE,
        origin="files_list",
    )


# -- files_read ---------------------------------------------------------------


def _declare_read(world: World, args: dict[str, Any]) -> list[Effect]:
    path = str(args.get("path", ""))
    row = world.one("SELECT * FROM files WHERE path = ? AND deleted = 0", (path,))
    rc = (
        ResourceClass.SECRETS
        if row and row["confidentiality"] == Confidentiality.SECRET.value
        else ResourceClass.USER_FILES
    )
    return [Effect(verb=Verb.READ, resource_class=rc, resource_id=path)]


@register(
    "files_read",
    family=FAMILY,
    description="Read the contents of one file in the user's workspace.",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Exact file path."}},
        "required": ["path"],
    },
    declare=_declare_read,
    result_integrity=Integrity.UNTRUSTED_DOC,
)
def files_read(world: World, args: dict[str, Any]):
    path = str(args["path"])
    row = world.one("SELECT * FROM files WHERE path = ? AND deleted = 0", (path,))
    if row is None:
        return err(f"no such file: {path}")
    return ok(
        row["content"],
        data={"path": path},
        effects=_declare_read(world, args),
        confidentiality=Confidentiality(row["confidentiality"]),
        origin=f"file:{path}",
    )


# -- files_write --------------------------------------------------------------


def _declare_write(world: World, args: dict[str, Any]) -> list[Effect]:
    path = str(args.get("path", ""))
    exists = world.one("SELECT 1 FROM files WHERE path = ? AND deleted = 0", (path,))
    return [
        Effect(
            verb=Verb.WRITE if exists else Verb.CREATE,
            resource_class=ResourceClass.USER_FILES,
            reversibility=(
                Reversibility.COSTLY_TO_REVERSE if exists else Reversibility.REVERSIBLE
            ),
            resource_id=path,
        )
    ]


@register(
    "files_write",
    family=FAMILY,
    description=("Write text to a file, creating it or overwriting it if it already exists."),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
    declare=_declare_write,
)
def files_write(world: World, args: dict[str, Any]):
    path, content = str(args["path"]), str(args["content"])
    effects = _declare_write(world, args)
    prior = world.one("SELECT * FROM files WHERE path = ?", (path,))
    conf = prior["confidentiality"] if prior else Confidentiality.PRIVATE.value
    world.execute(
        "INSERT INTO files (path, content, confidentiality, size_bytes, modified, deleted) "
        "VALUES (?,?,?,?,?,0) ON CONFLICT(path) DO UPDATE SET "
        "content=excluded.content, size_bytes=excluded.size_bytes, "
        "modified=excluded.modified, deleted=0",
        (path, content, conf, len(content), world.now()),
    )
    return ok(f"Wrote {len(content)} bytes to {path}.", data={"path": path}, effects=effects)


# -- files_delete -------------------------------------------------------------


def _declare_delete(world: World, args: dict[str, Any]) -> list[Effect]:
    pattern = str(args.get("path", ""))
    rows = (
        _matches(_live(world), pattern)
        if any(c in pattern for c in "*?[")
        else [r for r in _live(world) if r["path"] == pattern]
    )
    return [
        Effect(
            verb=Verb.DELETE,
            resource_class=ResourceClass.USER_FILES,
            reversibility=Reversibility.IRREVERSIBLE,
            magnitude=Magnitude(unit="files", value=float(len(rows))),
            resource_id=r["path"],
        )
        for r in rows
    ]


@register(
    "files_delete",
    family=FAMILY,
    description=(
        "Permanently delete a file, or every file matching a glob. This cannot be undone."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Exact path or glob pattern."}
        },
        "required": ["path"],
    },
    declare=_declare_delete,
)
def files_delete(world: World, args: dict[str, Any]):
    effects = _declare_delete(world, args)
    if not effects:
        return err(f"no file matched: {args['path']}")
    for eff in effects:
        world.execute("UPDATE files SET deleted = 1 WHERE path = ?", (eff.resource_id,))
    names = ", ".join(str(e.resource_id) for e in effects)
    return ok(f"Deleted {len(effects)} file(s): {names}.", effects=effects)


# -- files_share_link (a collateral-effect surface) ---------------------------


def _declare_share(world: World, args: dict[str, Any]) -> list[Effect]:
    return [
        Effect(
            verb=Verb.GRANT,
            resource_class=ResourceClass.USER_FILES,
            reversibility=Reversibility.COSTLY_TO_REVERSE,
            externality=Externality.VISIBLE_TO_THIRD_PARTY,
            resource_id=str(args.get("path", "")),
        )
    ]


@register(
    "files_share_link",
    family=FAMILY,
    description=(
        "Create a public, unlisted link to a file so anyone with the URL can read it."
    ),
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
    declare=_declare_share,
)
def files_share_link(world: World, args: dict[str, Any]):
    path = str(args["path"])
    row = world.one("SELECT * FROM files WHERE path = ? AND deleted = 0", (path,))
    if row is None:
        return err(f"no such file: {path}")
    key = f"link/{abs(hash(path)) % 10**8:08d}"
    world.execute(
        "INSERT OR REPLACE INTO storage_objects "
        "(key, source_path, size_bytes, confidentiality, ts) VALUES (?,?,?,?,?)",
        (key, path, row["size_bytes"], row["confidentiality"], world.now()),
    )
    world.execute(
        "INSERT INTO storage_shares (key, principal, access, ts) VALUES (?,?,?,?)",
        (key, "anyone-with-link", "read", world.now()),
    )
    return ok(
        f"Public link created: https://share.example.com/{key}",
        data={"url": f"https://share.example.com/{key}"},
        effects=_declare_share(world, args),
    )
