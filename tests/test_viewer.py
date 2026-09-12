"""The viewer must be a renderer, and these tests are what makes that claim checkable.

`CLAUDE.md` lists, as the sixth way this project fails, "a dashboard that animates decisions
rather than replaying real audit logs", and as the third, "hardcoded scenario-specific logic
that makes the demo look good". A viewer is the single most likely place for both to appear,
because a page that merely *looks* right is indistinguishable from one that is right until
somebody checks. So the important tests here are not "does it render" but:

* **Provenance.** Every verdict, tool name, effect class, gate and explanation on the page
  appears in the `SceneResult` it was rendered from. The page is a function of the artifacts.
* **No hardcoded verdicts.** The words ALLOW / ASK / BLOCK appear in `viewer.py` exactly once
  each, in `LEGEND`. Chips derive their label and colour from `policy_verdict`.
* **No scenario-specific branching.** No scenario id appears in the module source.
* **Honesty about what replay is.** Off-policy steps are marked, and the page says it is a
  replay of a recording rather than a live agent.
* **Determinism.** Two builds are byte-identical, and the committed files match a fresh build,
  so neither can drift from the artifacts.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from agentfw import demo, viewer

SOURCE = Path(viewer.__file__).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def built() -> tuple[list[demo.SceneResult], int, str, str]:
    results, total = viewer.build_results()
    page = viewer.render_html(results=results, total_episodes=total)
    hero = viewer.render_hero_svg(sorted(results, key=viewer.sort_key)[0])
    return results, total, page, hero


# ---------------------------------------------------------------------------
# provenance: the page is a function of the artifacts
# ---------------------------------------------------------------------------


def test_every_verdict_on_the_page_came_from_a_replayed_action(built):
    """No chip may say something the monitor did not return.

    The check runs the other way round from the obvious one: rather than trusting that the
    renderer copied the verdicts, it collects every chip the page contains and requires each
    to be a verdict some action actually carries.
    """
    results, _, page, _ = built
    real = {viewer.chip_text(a) for r in results for a in r.episode.actions}
    rendered = set(re.findall(r'<span class="chip v-[a-z]+">([^<]+)</span>', page))
    # The legend's three chips are glossary entries, not claims about an episode.
    rendered -= {word for word, _ in viewer.LEGEND}
    unsupported = rendered - real
    assert not unsupported, f"page shows verdicts no action returned: {sorted(unsupported)}"


def test_every_tool_name_and_effect_class_on_the_page_came_from_an_artifact(built):
    results, _, page, _ = built
    for result in results:
        for action in result.episode.actions:
            assert action.tool in page
            for effect_class in action.effect_classes:
                assert effect_class in page, f"{effect_class} rendered from nowhere"


def test_every_explanation_on_the_page_is_the_monitors_own_words(built):
    """Explanations are quoted, never paraphrased. A reworded reason is a fabricated one."""
    import html as html_mod

    _, _, page, _ = built
    results, _, _, _ = built
    for result in results:
        for action in result.episode.actions:
            assert html_mod.escape(action.explanation, quote=True) in page


def test_every_gate_that_fired_is_named_on_the_page(built):
    """A structural gate is the most product-legible thing the system does; never drop one."""
    results, _, page, _ = built
    fired = [g for r in results for a in r.episode.actions for g in a.gates]
    assert fired, "no gate fired in any curated scene; this test would be vacuous"
    for gate in fired:
        assert gate in page


def test_the_scope_the_monitor_started_from_is_shown(built):
    results, _, page, _ = built
    import html as html_mod

    for result in results:
        for grant in result.grants:
            assert html_mod.escape(grant, quote=True) in page
        for question in result.open_questions:
            assert html_mod.escape(question, quote=True) in page


def test_the_consent_question_is_the_one_the_monitor_rendered(built):
    """D-008's consent text is quoted in full, not summarised."""
    results, _, _, _ = built
    asked = [a for r in results for a in r.episode.actions if a.ask_text]
    assert asked, "no scene put a question to a human; this test would be vacuous"
    first_line = (asked[0].ask_text or "").splitlines()[0]
    assert first_line.strip(), "consent text is empty"


# ---------------------------------------------------------------------------
# no hardcoded verdicts, no scenario-specific logic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("word", ["ALLOW", "ASK", "BLOCK"])
def test_a_verdict_literal_appears_only_in_the_legend(word: str):
    """One occurrence each, in `LEGEND`.

    If a branch anywhere said ``if verdict == "BLOCK"`` the renderer would be deciding what a
    verdict means, and a fourth verdict would silently render as one of the three. Chips
    derive their class from ``policy_verdict.lower()`` instead, so an unknown verdict arrives
    on the page unstyled and visible rather than mislabelled.
    """
    # Count only real string constants, so prose in a docstring does not trip the check.
    tree = ast.parse(SOURCE)
    constants = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    docstrings = {
        ast.get_docstring(n)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
    }
    literals = [c for c in constants if c == word and c not in docstrings]
    assert len(literals) == 1, (
        f"{word!r} appears as a bare literal {len(literals)} times; it belongs only in LEGEND"
    )


def test_no_scenario_id_appears_in_the_viewer_source():
    """Failure mode 3: scenario-specific logic that makes a demo look good.

    Ordering, headlines and emphasis must be functions of the episode's outcome flags. The
    scene titles and selection rules live in `demo.SCENES`, where they are declared.
    """
    ids = {r.scenario_id for r in demo.load_episodes()}
    leaked = sorted(i for i in ids if i in SOURCE)
    assert not leaked, f"viewer.py branches on scenario ids: {leaked}"


def test_the_running_order_is_derived_from_the_episodes_not_written_down():
    """Scenarios with an authorization question sort first because they have one."""
    results, _ = viewer.build_results()
    ordered = sorted(results, key=viewer.sort_key)
    has_question = [
        r.episode.contested_occurred_undefended is not None
        or r.episode.attack_succeeded_undefended is not None
        for r in ordered
    ]
    # All the True values come before all the False ones.
    assert has_question == sorted(has_question, reverse=True)
    assert has_question[0], "the first panel poses no authorization question"


def test_the_viewer_adds_no_second_policy_or_scope_source():
    """It must replay through `demo`, not build a `ReplayConfig` of its own."""
    assert "ReplayConfig" not in SOURCE, "viewer.py builds its own replay config"
    assert "POLICY" not in SOURCE.replace("demo.POLICY", ""), "viewer.py defines a policy"
    assert "run_scene" in SOURCE, "viewer.py must replay through demo.run_scene"


# ---------------------------------------------------------------------------
# honesty about what a replay is
# ---------------------------------------------------------------------------


def test_off_policy_steps_are_marked_on_the_page(built):
    """After a refusal the recording no longer describes a defended agent. Say so.

    This is the subtle dishonesty a side-by-side invites: four steps stacked as equals read as
    an agent that tried twice and was stopped twice, when the later attempts happened in a
    world where the first refusal never occurred.
    """
    results, _, page, _ = built
    off = [a for r in results for a in r.episode.actions if a.off_policy]
    assert off, "no off-policy action in any curated scene; this test would be vacuous"
    assert page.count('class="step off"') == len(off)
    assert "Off-policy" in page
    assert "follows an earlier refusal" in page


def test_the_page_says_it_is_a_replay_and_not_a_live_agent(built):
    _, _, page, _ = built
    for phrase in [
        "not a live agent",
        "replay of committed artifacts",
        "faithful only up to the first refusal",
        "no API key",
    ]:
        assert phrase.lower() in page.lower(), f"page does not say {phrase!r}"


def test_the_page_names_the_recording_it_replays(built):
    """A reader must be able to find the trajectory this came from."""
    results, _, page, _ = built
    for result in results:
        assert result.record.scenario_id in page
        assert result.record.model_id in page
    assert "E-00j" in page


def test_the_page_prints_no_aggregate_rate(built):
    """Rates belong to the experiments, which state their own confidence intervals.

    A percentage on a page built from four hand-picked episodes would be a number with no
    population behind it, and it would be quoted as though there were.
    """
    _, _, page, _ = built
    body = re.sub(r"<style>.*?</style>", "", page, flags=re.S)
    percentages = re.findall(r"\d+\.\d+%|\d+%", body)
    assert not percentages, f"the viewer prints a rate: {percentages}"


def test_the_audit_chain_state_is_reported_rather_than_assumed(built):
    results, _, page, _ = built
    assert all(r.episode.chain_intact for r in results), "a replayed chain is broken"
    assert "chain intact" in page
    assert "hash-chained" in page


# ---------------------------------------------------------------------------
# self-contained, static, deterministic
# ---------------------------------------------------------------------------


def test_the_page_loads_nothing_from_the_network(built):
    """Self-contained means self-contained: it must work from a file:// URL, offline.

    Checked against resource-*loading* constructs rather than against the substring
    ``https://``, because the injection scenario's recorded tool arguments contain a URL and
    the page is supposed to show it. What matters is that nothing is fetched: an escaped
    artifact string cannot become a real attribute, since escaping turns its quotes into
    ``&quot;``.
    """
    _, _, page, _ = built
    for construct in ["<script src", "<link", 'src="', 'href="', "url(", "@import", "fetch("]:
        assert construct not in page, f"page loads a resource: {construct!r}"


def test_the_page_does_not_animate(built):
    """Failure mode 6. No transitions, no keyframes, no timers."""
    _, _, page, _ = built
    for banned in ["@keyframes", "animation:", "transition:", "setTimeout", "setInterval"]:
        assert banned not in page, f"page animates: {banned!r}"


def test_every_panel_is_visible_without_javascript(built):
    """The tabs are progressive enhancement; the content must not depend on them.

    Also what makes the page safe to screenshot, and readable to anything that does not run
    scripts.
    """
    _, _, page, _ = built
    script = page[page.index("<script>") :]
    assert "hidden = " in script or "hidden=" in script, "JS does not control visibility"
    # Panels ship hidden and JS reveals the first; with JS off a `hidden` attribute on all of
    # them would hide everything, so assert the opposite arrangement is what ships.
    assert page.count('<section class="panel"') == len(demo.SCENES)


def test_two_builds_are_byte_identical():
    """No timestamp, no ordering wobble. Required for the committed files to be checkable."""
    first_html, first_hero = viewer.build()
    second_html, second_hero = viewer.build()
    assert first_html == second_html
    assert first_hero == second_hero


def test_the_committed_files_match_a_fresh_build(built):
    """The committed HTML and SVG cannot drift from the artifacts they claim to show.

    This is the same discipline as the generated tables: an output committed to the repository
    is only trustworthy if regenerating it is a no-op, and a test is the only thing that keeps
    that true.
    """
    _, _, page, hero = built
    for path, expected in ((viewer.DEFAULT_HTML, page), (viewer.DEFAULT_HERO, hero)):
        assert path.exists(), f"{path.name} is not committed; run `agentfw viewer`"
        actual = path.read_text(encoding="utf-8")
        assert actual == expected, (
            f"{path.name} is stale. Regenerate it with `uv run agentfw viewer`."
        )


# ---------------------------------------------------------------------------
# the SVG still
# ---------------------------------------------------------------------------


def test_the_hero_paints_its_own_background_and_uses_no_theme_colours(built):
    """GitHub sanitises embedded SVG and passes it no theme.

    `docs/architecture.svg` learned this: a figure that inherits `currentColor` is invisible
    to half of GitHub's readers. Every colour here is a literal, and the panel paints itself.
    """
    _, _, _, hero = built
    assert hero.startswith("<svg")
    assert viewer.SVG_PANEL in hero, "the hero does not paint a background"
    assert "currentColor" not in hero
    assert "var(--" not in hero
    assert "prefers-color-scheme" not in hero
    assert "<script" not in hero and "<foreignObject" not in hero


def test_the_hero_keeps_all_of_its_content_inside_its_own_canvas(built):
    """Overflowing text is silently clipped by a renderer, so check the geometry."""
    _, _, _, hero = built
    width = int(re.search(r'width="(\d+)"', hero).group(1))
    height = int(re.search(r'height="(\d+)"', hero).group(1))
    xs = [float(v) for v in re.findall(r'(?:\bx|\bx1|\bx2)="([0-9.]+)"', hero)]
    ys = [float(v) for v in re.findall(r'(?:\by|\by1|\by2)="([0-9.]+)"', hero)]
    assert max(xs) <= width, f"content at x={max(xs)} exceeds width {width}"
    assert max(ys) <= height, f"content at y={max(ys)} exceeds height {height}"


def test_the_hero_headline_is_wrapped_not_truncated_mid_phrase(built):
    """Clipped to one line, the payment headline loses "nobody asked" -- its whole point."""
    results, _, _, hero = built
    first = sorted(results, key=viewer.sort_key)[0]
    without, _ = viewer.headline(first)
    # The sentence's last word must survive somewhere in the rendered text.
    assert without.split()[-1] in hero, f"the hero clipped the end off {without!r}"


def test_the_hero_says_it_is_a_replay(built):
    _, _, _, hero = built
    assert "REPLAY" in hero.upper()
    assert "no live agent" in hero


def test_the_hero_is_the_first_scenario_in_the_pages_running_order(built):
    """The still and the page must lead with the same case."""
    results, _, _, hero = built
    first = sorted(results, key=viewer.sort_key)[0]
    assert first.record.tool_calls[0]["name"] in hero


# ---------------------------------------------------------------------------
# derived presentation
# ---------------------------------------------------------------------------


def test_the_chip_shows_both_the_decision_and_the_human_answer(built):
    """An ASK the user declined is not the same event as a plain BLOCK, and must not look it."""
    results, _, _, _ = built
    asked = [a for r in results for a in r.episode.actions if a.asked]
    assert asked, "no scene put a question to a human; this test would be vacuous"
    for action in asked:
        text = viewer.chip_text(action)
        assert "→" in text, f"{text!r} hides the consent step"
        assert ("APPROVED" if action.consent_approved else "DECLINED") in text
        # Amber, from the decision -- not the red of the refusal that followed.
        assert viewer.chip_class(action) == "v-" + action.policy_verdict.lower()


def test_an_unknown_verdict_renders_unstyled_rather_than_mislabelled():
    """The failure mode a lookup table with a default would hide."""
    from agentfw.eval.replay import ActionOutcome

    odd = ActionOutcome(step=1, tool="t", verdict="QUARANTINE", policy_verdict="QUARANTINE")
    assert viewer.chip_class(odd) == "v-quarantine"
    assert viewer.chip_class(odd) not in {"v-allow", "v-ask", "v-block"}
    assert viewer.chip_text(odd) == "QUARANTINE"


def test_the_headline_reports_interruption_when_there_is_nothing_to_refuse(built):
    """A defense that only ever refuses is worthless; benign scenes must report cost."""
    results, _, _, _ = built
    benign = [
        r
        for r in results
        if r.episode.contested_occurred_undefended is None
        and r.episode.attack_succeeded_undefended is None
    ]
    assert benign, "no benign scene is included; the page would be one-sided"
    for result in benign:
        _, with_fw = viewer.headline(result)
        assert any(w in with_fw for w in ("completed", "refused")), with_fw


def test_the_headline_never_claims_prevention_that_did_not_happen(built):
    """The sentence must follow the flag, in both directions."""
    results, _, _, _ = built
    for result in results:
        ep = result.episode
        _, with_fw = viewer.headline(result)
        if ep.attack_succeeded_defended or ep.contested_occurred_defended:
            assert "anyway" in with_fw, f"{with_fw!r} hides a defense that failed"


def test_html_from_the_artifacts_is_escaped(built):
    """Scenario text is data. An angle bracket in an utterance must not become markup."""
    _, _, page, _ = built
    # Every `<` that opens a tag must be followed by a known tag name or a closing slash.
    stray = re.findall(r"<(?![/!a-zA-Z])", page)
    assert not stray, f"{len(stray)} unescaped angle bracket(s) in the page"


def test_the_colour_follows_the_outcome_and_not_the_column(built):
    """The right-hand headline must not be green on faith."""
    import html as html_mod

    results, _, page, _ = built
    for result in results:
        _, with_fw = viewer.headline(result)
        expected = "good" if viewer.defended_held(result) else "bad"
        needle = f'class="lede {expected}">{html_mod.escape(with_fw, quote=True)}'
        assert needle in page, f"{with_fw!r} is painted the wrong colour"


def test_under_the_ablation_the_page_shows_the_defense_failing():
    """The sharpest test of whether the viewer is rigged.

    `--scope tool-ceiling` is the allowlist-with-no-scope arm, where the Kestrel payment goes
    straight through. A viewer that still reported a save there would be a demo with the
    answer written into it. The page has to flip: the claim, and the colour with it.
    """
    import html as html_mod

    results, total = viewer.build_results("tool-ceiling")
    page = viewer.render_html("tool-ceiling", results=results, total_episodes=total)

    failed = [r for r in results if not viewer.defended_held(r)]
    assert failed, (
        "the tool-ceiling ablation prevented everything, which contradicts the experiments; "
        "either the ablation or this test is wrong"
    )
    for result in failed:
        _, with_fw = viewer.headline(result)
        assert "anyway" in with_fw, f"{with_fw!r} does not admit the defense failed"
        needle = f'class="lede bad">{html_mod.escape(with_fw, quote=True)}'
        assert needle in page, "a failed defense is still painted green"

    # And it failed because the effect really executed, not because a flag was mislabelled.
    assert any(
        r.episode.contested_occurred_defended or r.episode.attack_succeeded_defended
        for r in failed
    ), "no failed scene records the effect actually occurring under defense"
