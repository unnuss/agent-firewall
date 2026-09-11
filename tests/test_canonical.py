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


# ---------------------------------------------------------------------------
# the README is a front door, and a front door that lies is worse than a long one
# ---------------------------------------------------------------------------

README = canonical.ROOT / "README.md"


def _readme_without_comments() -> str:
    return re.sub(r"<!--.*?-->", "", README.read_text(encoding="utf-8"), flags=re.S)


def test_every_readme_link_resolves():
    """HTML-commented links are excluded: the GIF placeholder is deliberately not a file yet."""
    broken = []
    for match in re.finditer(r"\]\(([^)]+)\)", _readme_without_comments()):
        target = match.group(1)
        if target.startswith(("http", "#")):
            continue
        if not (canonical.ROOT / target.split("#")[0]).exists():
            broken.append(target)
    assert not broken, f"README links to files that do not exist: {broken}"


def test_the_readme_headline_matches_the_generated_numbers():
    """The front door must not drift from the artifacts.

    Written after the Phase 7 draft of this README got two figures wrong — it claimed 82.8%
    undefended task completion where the artifact says 83.3%, and "0 of 30" benign
    interruptions where the compiled arm actually interrupts 9 of 30. Both were carried over
    from an older table measured on a different arm. A number in the front door is exactly
    where that kind of error does the most damage.
    """
    import json

    readme = _readme_without_comments()
    e00j = json.loads(
        (canonical.EXPERIMENTS / "e00j_heldout_baseline" / "results" / "report.json").read_text(
            encoding="utf-8"
        )
    )
    best = json.loads(
        canonical._e14_verdict_path("perclass-sonnet-s1").read_text(encoding="utf-8")
    )

    must_appear = {
        "undefended underspecified overreach": e00j["overall"]["by_specificity"][
            "underspecified"
        ]["episode_rate"]["value"],
        "undefended explicit-low overreach": e00j["overall"]["by_specificity"]["explicit"][
            "episode_rate"
        ]["value"],
        "undefended ASR": e00j["overall"]["asr"]["value"],
        "defended contested executed": best["contested"]["underspecified_low"]["defended"][
            "value"
        ],
        "defended high-authority completion": best["contested"]["high_authority"]["defended"][
            "value"
        ],
        "undefended high-authority completion": best["contested"]["high_authority"][
            "undefended"
        ]["value"],
    }
    for label, value in must_appear.items():
        rendered = f"{value * 100:.1f}%"
        assert rendered in readme, f"README is missing {label} ({rendered})"


def test_the_readme_states_the_benign_interruption_cost_correctly():
    """The cost row is the one a sceptical reader checks first."""
    import json

    best = json.loads(
        canonical._e14_verdict_path("perclass-sonnet-s1").read_text(encoding="utf-8")
    )
    gold = json.loads(canonical._e14_verdict_path("gold").read_text(encoding="utf-8"))
    compiled = best["interruptions"]["benign"]["episodes_with_an_ask"]["n_success"]
    total = best["interruptions"]["benign"]["n"]
    hand_written = gold["interruptions"]["benign"]["episodes_with_an_ask"]["n_success"]

    readme = _readme_without_comments()
    assert f"{compiled} of {total}" in readme, (
        f"README must state the real benign interruption cost, {compiled} of {total}"
    )
    assert f"{hand_written} of\n30" in readme or f"{hand_written} of {total}" in readme, (
        "README should also state the hand-written-scope figure, which shows the "
        "interruptions are compiler error rather than architecture"
    )


def test_the_retracted_headline_is_only_quoted_as_a_correction():
    """81.8% is superseded, and it may appear *only* framed as the correction it became.

    The first version of this test banned the figure outright and failed, correctly: the
    README quotes it deliberately, because "this project corrected its own headline by 32
    points" is one of the strongest things it has to say. The rule is not silence, it is
    context — the same rule `RESULTS.md` is held to.
    """
    readme = _readme_without_comments()
    if "81.8%" not in readme:
        return
    window_start = readme.index("81.8%")
    window = readme[max(0, window_start - 400) : window_start + 400].lower()
    assert any(w in window for w in ("wrong by", "superseded", "corrected", "re-measured")), (
        "81.8% appears in the README without being framed as a correction"
    )
    assert "49.4%" in window, "the retracted figure must appear beside the one that replaced it"
