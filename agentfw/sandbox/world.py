"""The deterministic sandbox world (D-013).

SQLite in-memory, seedable, snapshot/restore per episode, no real network. Every mutating
tool records the Effect it produced into ``effect_log``; that log is what the scenario
oracles read, which is why oracle judgements are machine-checkable rather than LLM-judged
(EVALUATION section 2.1).

Fidelity gap versus a VM-backed world is a stated limitation, not a hidden one.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agentfw.core.types import Confidentiality, Effect, Magnitude

FIXTURE_DIR = Path(__file__).parent / "fixtures"

SCHEMA = """
CREATE TABLE files (
    path TEXT PRIMARY KEY, content TEXT NOT NULL, confidentiality TEXT NOT NULL,
    size_bytes INTEGER NOT NULL, modified TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE emails (
    id TEXT PRIMARY KEY, folder TEXT NOT NULL, sender TEXT NOT NULL,
    recipients TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
    ts TEXT NOT NULL, confidentiality TEXT NOT NULL, unread INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE calendar_events (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL,
    attendees TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
    cancelled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE contacts (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, org TEXT NOT NULL DEFAULT ''
);
CREATE TABLE web_pages (
    url TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
    keywords TEXT NOT NULL DEFAULT ''
);
CREATE TABLE http_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL, body TEXT NOT NULL,
    ts TEXT NOT NULL
);
CREATE TABLE payment_methods (
    id TEXT PRIMARY KEY, label TEXT NOT NULL, kind TEXT NOT NULL, last4 TEXT NOT NULL,
    limit_usd REAL NOT NULL DEFAULT 5000
);
CREATE TABLE purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT, method_id TEXT NOT NULL, amount_usd REAL NOT NULL,
    merchant TEXT NOT NULL, description TEXT NOT NULL, ts TEXT NOT NULL
);
CREATE TABLE storage_objects (
    key TEXT PRIMARY KEY, source_path TEXT NOT NULL, size_bytes INTEGER NOT NULL,
    confidentiality TEXT NOT NULL, ts TEXT NOT NULL
);
CREATE TABLE storage_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL, principal TEXT NOT NULL,
    access TEXT NOT NULL, ts TEXT NOT NULL
);
CREATE TABLE flights (
    id TEXT PRIMARY KEY, origin TEXT NOT NULL, destination TEXT NOT NULL,
    date TEXT NOT NULL, carrier TEXT NOT NULL, price_usd REAL NOT NULL,
    depart TEXT NOT NULL, arrive TEXT NOT NULL, refundable INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, flight_id TEXT NOT NULL,
    payment_method_id TEXT NOT NULL, price_usd REAL NOT NULL, ts TEXT NOT NULL
);
CREATE TABLE effect_log (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, step INTEGER NOT NULL, tool TEXT NOT NULL,
    args_json TEXT NOT NULL, verb TEXT NOT NULL, resource_class TEXT NOT NULL,
    reversibility TEXT NOT NULL, externality TEXT NOT NULL,
    magnitude_unit TEXT, magnitude_value REAL, resource_id TEXT, ts TEXT NOT NULL
);
"""

_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "files": ("path", "content", "confidentiality", "size_bytes", "modified", "deleted"),
    "emails": (
        "id",
        "folder",
        "sender",
        "recipients",
        "subject",
        "body",
        "ts",
        "confidentiality",
        "unread",
    ),
    "calendar_events": ("id", "title", "start", "end", "attendees", "notes", "cancelled"),
    "contacts": ("id", "name", "email", "org"),
    "web_pages": ("url", "title", "body", "keywords"),
    "payment_methods": ("id", "label", "kind", "last4", "limit_usd"),
    "storage_objects": ("key", "source_path", "size_bytes", "confidentiality", "ts"),
    "flights": (
        "id",
        "origin",
        "destination",
        "date",
        "carrier",
        "price_usd",
        "depart",
        "arrive",
        "refundable",
    ),
}


class WorldSpec(BaseModel):
    """Declarative initial state. Fixtures are YAML files with exactly these keys."""

    name: str = "unnamed"
    clock_start: str = "2026-03-16T09:00:00+00:00"
    user_name: str = "Alex Rivera"
    user_email: str = "alex@rivera-consulting.com"
    files: list[dict[str, Any]] = Field(default_factory=list)
    emails: list[dict[str, Any]] = Field(default_factory=list)
    calendar_events: list[dict[str, Any]] = Field(default_factory=list)
    contacts: list[dict[str, Any]] = Field(default_factory=list)
    web_pages: list[dict[str, Any]] = Field(default_factory=list)
    payment_methods: list[dict[str, Any]] = Field(default_factory=list)
    storage_objects: list[dict[str, Any]] = Field(default_factory=list)
    flights: list[dict[str, Any]] = Field(default_factory=list)

    def merged_with(self, overlay: WorldSpec | dict[str, Any] | None) -> WorldSpec:
        """Overlay rows onto this spec. Rows with a matching primary key replace."""
        if overlay is None:
            return self.model_copy(deep=True)
        ov = overlay if isinstance(overlay, WorldSpec) else WorldSpec(**overlay)
        out = self.model_dump()
        for table, cols in _TABLE_COLUMNS.items():
            pk = cols[0]
            base_rows = {r[pk]: dict(r) for r in out[table]}
            for row in getattr(ov, table):
                base_rows[row[pk]] = {**base_rows.get(row[pk], {}), **row}
            out[table] = list(base_rows.values())
        for scalar in ("name", "clock_start", "user_name", "user_email"):
            explicit = ov.model_fields_set
            if scalar in explicit:
                out[scalar] = getattr(ov, scalar)
        return WorldSpec(**out)


_DEFAULTS: dict[str, dict[str, Any]] = {
    "files": {"confidentiality": "PRIVATE", "deleted": 0},
    "emails": {"folder": "inbox", "confidentiality": "PRIVATE", "unread": 1, "recipients": ""},
    "calendar_events": {"attendees": "", "notes": "", "cancelled": 0},
    "contacts": {"org": ""},
    "web_pages": {"keywords": ""},
    "payment_methods": {"limit_usd": 5000.0},
    "storage_objects": {"confidentiality": "PRIVATE"},
    "flights": {"refundable": 0},
}


class World:
    """A single episode's world. Not thread-safe; one per episode."""

    def __init__(self, spec: WorldSpec, seed: int = 0) -> None:
        self.spec = spec
        self.seed = seed
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._clock = datetime.fromisoformat(spec.clock_start)
        if self._clock.tzinfo is None:
            self._clock = self._clock.replace(tzinfo=UTC)
        self._load(spec)
        self.conn.commit()

    # -- construction ------------------------------------------------------

    @classmethod
    def from_fixture(
        cls,
        fixture: str,
        overlay: dict[str, Any] | None = None,
        seed: int = 0,
    ) -> World:
        spec = load_fixture(fixture)
        return cls(spec.merged_with(overlay), seed=seed)

    def _load(self, spec: WorldSpec) -> None:
        for table, cols in _TABLE_COLUMNS.items():
            rows = getattr(spec, table)
            for raw in rows:
                row = {**_DEFAULTS.get(table, {}), **raw}
                if table == "files":
                    row.setdefault("size_bytes", len(row.get("content", "")))
                    row.setdefault("modified", self.spec.clock_start)
                if table == "emails":
                    row.setdefault("ts", self.spec.clock_start)
                if table == "storage_objects":
                    row.setdefault("ts", self.spec.clock_start)
                    row.setdefault("size_bytes", 0)
                values = [row.get(c) for c in cols]
                missing = [c for c, v in zip(cols, values, strict=True) if v is None]
                if missing:
                    raise ValueError(f"fixture row for {table} missing {missing}: {raw}")
                placeholders = ",".join("?" * len(cols))
                self.conn.execute(
                    f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) "
                    f"VALUES ({placeholders})",
                    values,
                )

    # -- clock -------------------------------------------------------------

    def now(self) -> str:
        """Deterministic clock: advances a fixed step every time it is read."""
        self._clock += timedelta(seconds=37)
        return self._clock.isoformat()

    # -- effects -----------------------------------------------------------

    def record_effect(
        self, effect: Effect, tool: str, args: dict[str, Any], step: int = -1
    ) -> None:
        self.conn.execute(
            "INSERT INTO effect_log (step, tool, args_json, verb, resource_class, "
            "reversibility, externality, magnitude_unit, magnitude_value, resource_id, ts) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                step,
                tool,
                json.dumps(args, sort_keys=True, default=str),
                effect.verb.value,
                effect.resource_class.value,
                effect.reversibility.value,
                effect.externality.value,
                effect.magnitude.unit if effect.magnitude else None,
                effect.magnitude.value if effect.magnitude else None,
                effect.resource_id,
                self._clock.isoformat(),
            ),
        )
        self.conn.commit()

    def effect_log(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM effect_log ORDER BY seq").fetchall()
        return [dict(r) for r in rows]

    def effects(self) -> list[Effect]:
        out = []
        for r in self.effect_log():
            mag = (
                Magnitude(unit=r["magnitude_unit"], value=r["magnitude_value"])
                if r["magnitude_unit"] is not None
                else None
            )
            out.append(
                Effect(
                    verb=r["verb"],
                    resource_class=r["resource_class"],
                    reversibility=r["reversibility"],
                    externality=r["externality"],
                    magnitude=mag,
                    resource_id=r["resource_id"],
                )
            )
        return out

    # -- snapshot ----------------------------------------------------------

    def snapshot(self) -> bytes:
        return self.conn.serialize()

    def restore(self, blob: bytes) -> None:
        self.conn.deserialize(blob)

    # -- helpers used by tools --------------------------------------------

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def confidentiality_of_rows(self, rows: list[dict[str, Any]]) -> Confidentiality:
        best = Confidentiality.PUBLIC
        for r in rows:
            c = Confidentiality(r.get("confidentiality", "PUBLIC"))
            if c.rank() > best.rank():
                best = c
        return best

    def close(self) -> None:
        self.conn.close()


_FIXTURE_CACHE: dict[str, WorldSpec] = {}


def load_fixture(name: str) -> WorldSpec:
    if name not in _FIXTURE_CACHE:
        path = FIXTURE_DIR / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"no world fixture named {name!r} in {FIXTURE_DIR}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        _FIXTURE_CACHE[name] = WorldSpec(**data)
    return _FIXTURE_CACHE[name].model_copy(deep=True)
