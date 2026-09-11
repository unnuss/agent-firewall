"""The canonical results tables must stay a function of the committed artifacts.

`CLAUDE.md` requires every table in the README to be regenerable by one command. Phase 6.9 made
that true by generating `docs/RESULTS.md` from the committed `report.json` files. These tests
are what stop it becoming an intention again: if someone edits a number by hand, or an artifact
moves, the suite says so rather than the document quietly disagreeing with the evidence.
"""

from __future__ import annotations

import re

import pytest

from agentfw.eval import canonical

RESULTS = canonical.ROOT / "docs" / "RESULTS.md"


def test_every_artifact_a_table_wants_is_committed():
    """A `(pending)` cell is honest, but an unexpected one means something moved."""
    assert canonical.missing() == []


def test_results_md_is_up_to_date_with_the_artifacts():
    """The committed document must equal what the generator produces right now.

    If this fails, run `agentfw results`. It failing means a number in the document no longer
    matches the artifact it claims to come from — which is exactly the drift the generator
    exists to prevent.
    """
    assert RESULTS.exists(), "docs/RESULTS.md is missing"
    text = RESULTS.read_text(encoding="utf-8")
    assert canonical.BEGIN in text and canonical.END in text
    _, _, rest = text.partition(canonical.BEGIN)
    generated, _, _ = rest.partition(canonical.END)
    assert generated.strip() == canonical.render().strip(), (
        "docs/RESULTS.md's generated region is stale; run `agentfw results`"
    )


def test_every_headline_figure_traces_to_a_value_in_an_artifact():
    """The strong form of "this module computes no rate of its own".

    For each percentage in the headline table, find the value it was lifted from in the
    committed JSON and check it round-trips. An earlier version of this test tried to detect
    arithmetic by scanning the source for `/`, which caught pathlib's path-join operator and
    proved nothing. Comparing the rendered number against the artifact proves the thing the
    source scan was reaching for.
    """
    import json

    e00j = json.loads(
        (canonical.EXPERIMENTS / "e00j_heldout_baseline" / "results" / "report.json").read_text(
            encoding="utf-8"
        )
    )
    best = json.loads(
        canonical._e14_verdict_path("perclass-sonnet-s1").read_text(encoding="utf-8")
    )
    expected = {
        e00j["overall"]["by_specificity"]["underspecified"]["episode_rate"]["value"],
        e00j["overall"]["asr"]["value"],
        best["contested"]["underspecified_low"]["defended"]["value"],
        best["injection"]["asr_defended"]["value"],
    }
    headline = chr(10).join(canonical.headline())
    for value in expected:
        assert f"{value * 100:.1f}%" in headline, (
            f"{value * 100:.1f}% is in the artifacts but not in the rendered headline"
        )


def test_the_headline_pair_is_present_and_not_a_placeholder():
    rendered = canonical.render()
    assert "Unlicensed consequential action executed" in rendered
    assert "Prompt-injection attack succeeded" in rendered
    headline = rendered.split("## 2.")[0]
    assert canonical.PENDING not in headline, "the headline must never render (pending)"


def test_superseded_numbers_are_flagged_wherever_the_document_quotes_them():
    """E-00i's 81.8% may appear, but never without being marked superseded."""
    text = RESULTS.read_text(encoding="utf-8")
    if "81.8%" in text:
        assert "superseded" in text.lower()


def test_the_apparatus_boundary_is_stated_in_the_document():
    text = RESULTS.read_text(encoding="utf-8").lower()
    assert "pre-repair" in text and "post-repair" in text


@pytest.mark.parametrize(
    "doc",
    ["RESULTS.md", "PREDICTIONS.md", "FINDINGS.md", "LIMITATIONS.md", "RESEARCH_LOG.md"],
)
def test_the_consolidated_documents_exist_and_are_substantial(doc: str):
    path = canonical.ROOT / "docs" / doc
    assert path.exists(), f"docs/{doc} is missing"
    assert len(path.read_text(encoding="utf-8").splitlines()) > 40


def test_every_finding_referenced_anywhere_appears_in_the_ledger():
    """A finding cited in the docs but absent from FINDINGS.md is an unindexed claim."""
    ledger = (canonical.ROOT / "docs" / "FINDINGS.md").read_text(encoding="utf-8")
    indexed = set(re.findall(r"F-\d{2}", ledger))
    referenced: set[str] = set()
    for path in sorted((canonical.ROOT / "docs").glob("*.md")):
        if path.name == "FINDINGS.md":
            continue
        referenced |= set(re.findall(r"F-\d{2}", path.read_text(encoding="utf-8")))
    missing = sorted(referenced - indexed)
    assert not missing, f"findings cited but not in the ledger: {missing}"


def test_every_prediction_number_is_in_the_prediction_ledger():
    ledger = (canonical.ROOT / "docs" / "PREDICTIONS.md").read_text(encoding="utf-8")
    numbered = {int(n) for n in re.findall(r"^\| (\d{1,2}) \|", ledger, re.M)}
    assert numbered == set(range(1, 49)), sorted(set(range(1, 49)) - numbered)
