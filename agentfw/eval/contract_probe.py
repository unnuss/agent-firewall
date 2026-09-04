"""How much of the committed evidence does the F-20 repair move? (`agentfw probe-contract`)

**Why this exists rather than an assurance.** Repairing `email_list` changes the measuring
apparatus, and every episode in E-00, E-00b, E-00f, E-00h, E-01a and E-01b was recorded
under the old contract. "Some episodes are affected" is not a statement anyone can check.
This turns it into a number: replay every recorded search argument against that episode's own
world under both contracts, and count where the returned rows differ.

It is not a simulation of what the agent would have done next — a changed result set changes
the trajectory, and nothing here pretends to know how. It is a **lower bound on contamination**:
an episode counted here demonstrably saw different evidence than it would see today. Episodes
not counted saw identical tool output at every search, which is the strongest statement
available without paying to re-run them.

The pre-repair contract is frozen in ``LEGACY_*`` below and must never be "kept up to date".
It is a historical record of what produced the committed numbers.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from agentfw.eval.scenario import load_suite
from agentfw.sandbox.registry import REGISTRY, load_all
from agentfw.sandbox.world import World

# Every run whose episodes are committed, in the order they were produced.
SOURCES: list[tuple[str, str, str]] = [
    ("E-00", "dev", "experiments/e00_undefended/results/episodes.jsonl"),
    ("E-00b", "dev", "experiments/e00b_revised/results/episodes.jsonl"),
    ("E-00f", "dev", "experiments/e00f_cross_vendor/results/episodes.jsonl"),
    ("E-00h", "heldout", "experiments/e00h_heldout_baseline/results/episodes.jsonl"),
]


def LEGACY_email_list(rows: list[dict], query: str) -> list[str]:
    """`email_list`'s contract as it stood from Phase 1 to Phase 3.5. Frozen."""
    q = query.lower()
    return (
        [r["id"] for r in rows if q in r["subject"].lower() or q in r["sender"].lower()]
        if q
        else [r["id"] for r in rows]
    )


def LEGACY_contacts_search(rows: list[dict], query: str) -> list[str]:
    """`contacts_search`'s contract as it stood from Phase 1 to Phase 3.5. Frozen."""
    q = query.lower()
    return [
        r["email"]
        for r in rows
        if q in r["name"].lower() or q in r["email"].lower() or q in r["org"].lower()
    ]


def probe(root: Path | None = None) -> dict[str, Any]:
    load_all()
    root = root or Path.cwd()
    scenarios = {s.id: s for s in load_suite(split=None)}
    report: dict[str, Any] = {"runs": [], "note": __doc__.strip().splitlines()[0]}

    for experiment, split, rel in SOURCES:
        path = root / rel
        if not path.exists():
            report["runs"].append({"experiment": experiment, "status": "missing", "path": rel})
            continue
        episodes = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        touched: set[str] = set()
        changes: Counter[tuple[str, str, str, str]] = Counter()
        n_calls = 0
        for ep in episodes:
            scenario = scenarios.get(ep["scenario_id"])
            if scenario is None:
                continue
            world = World.from_fixture(scenario.world.fixture, scenario.world.overlay)
            try:
                sql = "SELECT * FROM emails WHERE folder = ? ORDER BY ts"
                folders = {
                    f: [dict(r) for r in world.query(sql, (f,))]
                    for f in ("inbox", "sent", "drafts")
                }
                contacts = [
                    dict(r) for r in world.query("SELECT * FROM contacts ORDER BY name")
                ]
                for call in ep["tool_calls"]:
                    args = call.get("args") or {}
                    query = str(args.get("query") or "")
                    if not query:
                        continue
                    if call["name"] == "email_list":
                        n_calls += 1
                        folder = str(args.get("folder") or "inbox")
                        before = LEGACY_email_list(folders.get(folder, []), query)
                        live = REGISTRY["email_list"].handler(world, args)
                        after = live.data.get("messages") or []
                    elif call["name"] == "contacts_search":
                        n_calls += 1
                        before = LEGACY_contacts_search(contacts, query)
                        live = REGISTRY["contacts_search"].handler(world, args)
                        after = live.data.get("contacts") or []
                    else:
                        continue
                    if list(before) != list(after):
                        touched.add(ep["episode_id"])
                        key = (
                            call["name"],
                            query,
                            ",".join(before) or "-",
                            ",".join(after) or "-",
                        )
                        changes[key] += 1
            finally:
                world.close()
        report["runs"].append(
            {
                "experiment": experiment,
                "split": split,
                "episodes": len(episodes),
                "queried_calls": n_calls,
                "calls_changed": sum(changes.values()),
                "episodes_touched": len(touched),
                "share_touched": round(len(touched) / len(episodes), 4) if episodes else None,
                "top_changes": [
                    {"tool": t, "query": q, "before": b, "after": a, "count": n}
                    for (t, q, b, a), n in changes.most_common(12)
                ],
            }
        )
    return report


def to_markdown(report: dict[str, Any]) -> str:
    out = [
        "# F-20 contract probe — how much committed evidence the repair moves",
        "",
        "Every recorded `email_list` / `contacts_search` argument set, replayed against its",
        "own scenario world under the frozen pre-repair contract and under the live one.",
        "An episode is *touched* when at least one of its searches would now return",
        "different rows. This is a lower bound on contamination, not a re-simulation.",
        "",
        "| Run | Split | Episodes | Queried calls | Calls changed | Episodes touched |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["runs"]:
        if r.get("status") == "missing":
            out.append(f"| {r['experiment']} | — | *missing* | — | — | — |")
            continue
        pct = f" ({r['share_touched'] * 100:.1f}%)" if r["share_touched"] is not None else ""
        out.append(
            f"| {r['experiment']} | {r['split']} | {r['episodes']} | {r['queried_calls']} "
            f"| {r['calls_changed']} | **{r['episodes_touched']}**{pct} |"
        )
    for r in report["runs"]:
        if r.get("status") == "missing" or not r["top_changes"]:
            continue
        out += ["", f"### {r['experiment']} — what changed", ""]
        for c in r["top_changes"]:
            out.append(
                f"- x{c['count']}  `{c['tool']}({c['query']!r})`: "
                f"`{c['before']}` -> `{c['after']}`"
            )
    return "\n".join(out) + "\n"
