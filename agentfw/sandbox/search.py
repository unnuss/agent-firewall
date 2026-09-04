"""The query contract shared by every searchable sandbox tool (F-20, F-21).

**Why this module exists.** `email_list`'s `query` used to match a contiguous substring of
the subject or the sender, and nothing else. So the way people name people --- "Dana
Whitfield", "Cloudhost billing", "Priya Menon" --- matched nothing at all, because the world
stores `dana.whitfield@vantage-health.example`. The agent then correctly reported it could
not find the message and stopped. That killed half the held-out episodes outright (E-00h
compliance 11.1%, below D-019's floor) and it silently touched 11.4% of the dev ones too.

Nothing about that was a model failure or a scenario defect. It was a *tool contract that is
satisfiable in principle and unsatisfiable in practice* --- the same class of benchmark lie
as F-01's trivially-true oracles, on the tool side rather than the oracle side.

**The contract, stated once and applied everywhere.**

1. A query matches a record when **every** word in the query matches **some** word in the
   record's indexed text. Words are split on any non-alphanumeric run, so
   `dana.whitfield@vantage-health.example` indexes as
   `{dana, whitfield, vantage, health, example}` and the query "Dana Whitfield" matches it.
2. A query word matches an indexed word when the indexed word **starts with** it, so
   "Cloudhost bill" finds `billing@cloudhost.example`. Prefix rather than equality because
   people type the stem; not substring, because that is how the original contract managed to
   match nothing useful and everything useless at the same time.
3. An empty query matches everything. That is what "no filter" means.

This is not a new invention. `web_search` in this same sandbox has always scored on terms
rather than substrings, so the repair brings two tools **into line with an existing correct
contract** rather than introducing a third one.

**A tool that finds nothing must say what it searched.** ``no_match`` renders the miss so
that it is distinguishable from an empty world. `storage_list` used to answer "Bucket is
empty." when a *prefix* failed to match --- a statement that is simply false, and one a
competent agent has no reason to doubt. A message that cannot be told apart from "there is
nothing here" turns a recoverable miss into a dead end, which is F-20's real lesson.

**What this contract deliberately does not do.** It does not stem, spell-correct, rank, or
score. It over-returns rather than under-returns: a query whose words all appear somewhere
will match, even if the match is incidental (searching "consulting" in a mailbox where every
message is addressed to `alex@rivera-consulting.com` returns all of them). That direction is
chosen on purpose. An over-broad result is visible to the agent and recoverable in one more
step; an empty result is indistinguishable from an empty world and is not.
"""

from __future__ import annotations

import re

_SPLIT = re.compile(r"[^a-z0-9]+")


def words(text: str) -> set[str]:
    """Index one field into the words a query can match against."""
    return {w for w in _SPLIT.split(str(text).lower()) if w}


def terms(query: str) -> list[str]:
    """Split a query into the words that must all match. Empty query -> no terms."""
    return [w for w in _SPLIT.split(str(query or "").lower()) if w]


def matches(query: str, *fields: str) -> bool:
    """Does every word of ``query`` prefix some word of some field?"""
    want = terms(query)
    if not want:
        return True
    have = set()
    for f in fields:
        have |= words(f)
    return all(any(h.startswith(t) for h in have) for t in want)


def no_match(what: str, query: str, searched: str, total: int) -> str:
    """The message a search returns when it matched nothing.

    Names the query, the fields that were searched, and how many records exist unfiltered,
    so "your words did not match" is never confusable with "there is nothing here".
    """
    if total <= 0:
        return f"No {what}."
    return (
        f"No {what} matching {query!r}. Searched {searched}. "
        f"There are {total} {what} in total; call with no query to see them all."
    )
