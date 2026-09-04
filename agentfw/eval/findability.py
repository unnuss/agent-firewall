"""The findability gate (F-20, and F-01's lesson applied to the tool side).

**What it is for.** F-01 caught two oracles that were already true before the agent acted,
and the lesson recorded then was that oracle triviality "must be a gate on every generated
scenario, not a review step". F-20 is the same class of defect one layer over: a *tool
contract* that is satisfiable in principle and unsatisfiable in practice for the phrasings a
competent agent actually produces. `email_list`'s query matched contiguous substrings only,
so "Dana Whitfield" found nothing while the world plainly held
`dana.whitfield@vantage-health.example`, and the agent correctly gave up. It cost the
held-out slice its competency gate and it was found by D-019's floor rather than by anyone
reading the suite.

So it becomes a gate too.

**The invariant.** An utterance refers to things in the world. If the words the utterance
uses to refer to a thing return nothing, the scenario is a dead end no matter how good the
agent is. Stated so a machine can check it:

> For every referring phrase in an utterance, if the scenario's world contains a record that
> *does* contain all of that phrase's words, then some search tool in the scenario's own
> tool set must return that record when given the phrase as its query.

The left-hand side is a **generous** matcher over every text column of every record: it
knows nothing about fields, folders or contracts, and it is deliberately not the thing under
test. The right-hand side is the shipped tool, called for real. A gap between them is a
findability defect, and it names the phrase, the record and the tool that failed.

**What it does not do, stated so the gate is not over-trusted.** It cannot see a phrase whose
words are absent from the world altogether --- "that consulting newsletter" where the message
never says "newsletter". That is the F-05 class (the utterance names something the world does
not contain) and no comparison of two matchers can catch it, because both return nothing and
agree. Those are found by reading a failed run, and one of them was: see F-06.

**Candidate phrases.** Capitalised runs of one to three words, which is how people, companies
and documents are written, minus a small stop list so that a sentence-initial "The" is not
mistaken for a proper noun. This under-generates on purpose. A gate that guesses is a gate
nobody trusts, and the cost of a missed candidate is one uncaught defect, while the cost of a
false one is a permanently red test that gets deleted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from agentfw.eval.scenario import Scenario
from agentfw.sandbox import search
from agentfw.sandbox.registry import REGISTRY, load_all
from agentfw.sandbox.world import World

# Sentence-initial and otherwise capitalised words that are not names. Small on purpose:
# every entry is a word that would otherwise generate a candidate no world could satisfy.
# fmt: off
_NOT_A_NAME = {
    "a", "an", "and", "are", "as", "at", "before", "but", "can", "check", "could", "did",
    "do", "does", "draft", "email", "find", "for", "from", "get", "give", "have", "he",
    "her", "his", "how", "i", "if", "in", "is", "it", "its", "just", "let", "look", "make",
    "me", "my", "no", "not", "on", "once", "one", "open", "or", "our", "out", "please",
    "pull", "put", "reply", "send", "she", "so", "someone", "something", "sort", "take",
    "tell", "that", "the", "their", "them", "then", "they", "this", "to", "up", "us",
    "we", "what", "when", "where", "which", "who", "why", "will", "with", "work", "you",
    "your",
}
# fmt: on

# Which tools search which record type, and how to pull the candidate rows out of a world.
# A scenario is only held to a phrase if it actually carries one of these tools.
_SEARCHERS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "email_list": ("emails", "query", ("sender", "recipients", "subject", "body")),
    "contacts_search": ("contacts", "query", ("name", "email", "org")),
}

_CAP_RUN = re.compile(r"(?:\b[A-Z][\w'&-]*(?:\s+|$)){1,3}")


@dataclass(frozen=True)
class Defect:
    scenario_id: str
    variant_id: str
    phrase: str
    tool: str
    record: str
    detail: str

    def __str__(self) -> str:
        return (
            f"{self.scenario_id}::{self.variant_id}: {self.tool}(query={self.phrase!r}) "
            f"does not return {self.record}, which contains every word of the phrase. "
            f"{self.detail}"
        )


def candidates(utterance: str) -> list[str]:
    """Referring phrases an agent would plausibly type as a query."""
    out: list[str] = []
    for run in _CAP_RUN.finditer(utterance):
        words = run.group(0).split()
        # Every prefix of a capitalised run: "Northwind Systems Ltd" also yields "Northwind".
        for n in range(1, len(words) + 1):
            phrase = " ".join(words[:n])
            bare = [w.strip(".,;:?!'\"").lower() for w in words[:n]]
            if all(w in _NOT_A_NAME or len(w) < 3 for w in bare):
                continue
            if phrase not in out:
                out.append(phrase)
    return out


def _rows(world: World, table: str) -> list[dict]:
    if table == "emails":
        return [dict(r) for r in world.query("SELECT * FROM emails ORDER BY id")]
    return [dict(r) for r in world.query(f"SELECT * FROM {table} ORDER BY rowid")]


def _generously_matches(row: dict, phrase: str, fields: tuple[str, ...]) -> bool:
    """Does this record contain every word of the phrase, anywhere in the named fields?

    Deliberately the same word model as the shipped contract but with no notion of which
    field, folder or contract applies. If this is true and the tool returns nothing, the
    tool is the problem.
    """
    return search.matches(phrase, *(str(row.get(f, "")) for f in fields))


def check_scenario(scenario: Scenario, *, matcher=None) -> list[Defect]:
    """Every findability defect in one scenario.

    ``matcher`` lets a test drive the gate with a *frozen historical* contract instead of
    the live tool, which is how we assert the gate would have caught F-20 rather than
    merely asserting it is green today.
    """
    load_all()
    defects: list[Defect] = []
    tools = [t for t in scenario.tools if t in _SEARCHERS]
    if not tools:
        return defects
    world = World.from_fixture(scenario.world.fixture, scenario.world.overlay)
    try:
        for variant in scenario.variants:
            for phrase in candidates(variant.utterance):
                for tool in tools:
                    table, arg, fields = _SEARCHERS[tool]
                    for row in _rows(world, table):
                        if not _generously_matches(row, phrase, fields):
                            continue
                        if table == "emails" and row["folder"] != "inbox":
                            continue  # the default folder is the one an agent searches
                        if matcher is not None:
                            found = matcher(tool, row, phrase)
                        else:
                            result = REGISTRY[tool].handler(world, {arg: phrase})
                            key = "messages" if table == "emails" else "contacts"
                            ident = row["id"] if table == "emails" else row["email"]
                            found = ident in (result.data.get(key) or [])
                        if not found:
                            ident = row["id"] if table == "emails" else row["name"]
                            defects.append(
                                Defect(
                                    scenario.id,
                                    variant.id,
                                    phrase,
                                    tool,
                                    f"{table[:-1]} {ident}",
                                    "A phrasing the utterance itself uses returns nothing, "
                                    "so a competent agent correctly gives up (F-20).",
                                )
                            )
    finally:
        world.close()
    return defects


def check_suite(scenarios: list[Scenario], *, matcher=None) -> list[Defect]:
    out: list[Defect] = []
    for sc in scenarios:
        out += check_scenario(sc, matcher=matcher)
    return out
