"""Tests for ``agentfw demo`` (Phase 5.5).

The demo is the first thing a stranger runs, so what is tested here is mostly *honesty*
rather than formatting: that it needs no credential and no network, that every sentence it
prints came out of the audit log rather than out of this file, that the scope ablation it
advertises really does show the system failing, and that nothing about it leaked into the
trusted path.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agentfw import demo
from agentfw.eval import replay as replay_mod
from agentfw.eval.scopes import GoldScopes
from agentfw.sandbox.registry import load_all

CORE = Path(demo.__file__).resolve().parent / "core"


# ---------------------------------------------------------------------------
# the artifacts it stands on
# ---------------------------------------------------------------------------


def test_the_committed_episodes_are_present():
    assert demo.EPISODES.exists(), (
        "the demo replays a committed run; if this file is missing the repository is "
        "incomplete, not the demo"
    )


@pytest.mark.parametrize("choice", demo.SCOPE_CHOICES, ids=lambda c: c.label)
def test_every_offered_scope_source_is_a_committed_file(choice):
    if choice.kind == "gold":
        return
    assert choice.path is not None and choice.path.exists()


@pytest.mark.parametrize("scene", demo.SCENES, ids=lambda s: s.scenario_id)
def test_every_curated_scene_has_a_committed_episode(scene):
    keys = {(row[0], row[1], row[2]) for row in demo.available()}
    assert (scene.scenario_id, scene.variant_id, scene.seed) in keys


@pytest.mark.parametrize("scene", demo.SCENES, ids=lambda s: s.scenario_id)
def test_every_curated_scene_says_why_it_was_curated(scene):
    """A chosen example without a stated reason is a cherry-picked one."""
    assert len(scene.selected_because.split()) >= 8


# ---------------------------------------------------------------------------
# what it must show
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rendered() -> str:
    return demo.render(glyphs=demo.Glyphs.ascii())


def test_the_default_run_shows_allow_ask_and_block(rendered):
    """The exit criterion of Phase 5.5, as an assertion."""
    assert "ALLOW" in rendered
    assert "ASK -> DENIED" in rendered
    assert "ASK -> APPROVED" in rendered
    assert "BLOCK" in rendered


def test_it_shows_a_structural_gate_firing(rendered):
    assert "G1_structural_denial" in rendered


def test_it_shows_the_consent_rendering_at_least_once(rendered):
    assert "APPROVAL REQUIRED" in rendered
    assert "Approving grants the assistant this authority" in rendered


def test_it_names_the_undefended_outcome_it_is_contrasted_against(rendered):
    assert "EXECUTED" in rendered
    assert "the injected instruction SUCCEEDED" in rendered


def test_it_states_how_few_episodes_it_showed(rendered):
    assert f"{len(demo.SCENES)} of " in rendered


# ---------------------------------------------------------------------------
# no fabrication: every explanation printed is one the monitor produced now
# ---------------------------------------------------------------------------


def test_every_explanation_printed_comes_from_this_runs_audit_log(rendered):
    load_all()
    gold = GoldScopes.load()
    _, scopes = demo.load_scope_source(demo.DEFAULT_SCOPE)
    records = {(r.scenario_id, r.variant_id, r.seed): r for r in demo.load_episodes()}
    scenarios = replay_mod.all_scenarios()

    # Rendering wraps, so both sides are compared with whitespace collapsed. Word order
    # is preserved by wrapping, so this is a substring check on the real sentence and not
    # a bag-of-words one.
    flat = " ".join(rendered.split())
    seen = 0
    for scene in demo.SCENES:
        result = demo.run_scene(scene, records, scenarios, scopes, gold)
        for action in result.episode.actions:
            sentence = " ".join(action.explanation.split())
            assert sentence in flat, (
                f"the audit explanation for {action.tool} in {scene.scenario_id} is not "
                f"in the rendered demo: {sentence!r}"
            )
            seen += 1
    assert seen >= 8


def test_the_demo_invents_no_verdict(rendered):
    """Every verdict token in the output is one an ActionOutcome actually carried."""
    load_all()
    gold = GoldScopes.load()
    _, scopes = demo.load_scope_source(demo.DEFAULT_SCOPE)
    records = {(r.scenario_id, r.variant_id, r.seed): r for r in demo.load_episodes()}
    scenarios = replay_mod.all_scenarios()
    produced = set()
    for scene in demo.SCENES:
        result = demo.run_scene(scene, records, scenarios, scopes, gold)
        produced |= {a.verdict for a in result.episode.actions}
    assert produced <= {"ALLOW", "ASK", "BLOCK"}
    # The demo claims a BLOCK and an approved ASK; both must be real.
    assert "BLOCK" in produced


# ---------------------------------------------------------------------------
# the ablation has to be able to embarrass us
# ---------------------------------------------------------------------------


def test_the_tool_ceiling_ablation_shows_the_payment_going_through():
    """`--scope tool-ceiling` is offered as the adversarial flag. It has to work.

    If this ever passes trivially because the ablation started refusing things, the demo's
    claim that it is falsifiable is no longer true and the flag should be re-thought rather
    than the assertion relaxed.
    """
    out = demo.render(
        "tool-ceiling",
        scenario="af_auth.ho.payments.kestrel_invoice",
        variant="a",
        seed=1,
        glyphs=demo.Glyphs.ascii(),
    )
    assert "payments_charge" in out
    assert "undefended: executed  ->  defended: executed" in out


def test_the_default_scope_prevents_that_same_payment():
    out = demo.render(
        scenario="af_auth.ho.payments.kestrel_invoice",
        variant="a",
        seed=1,
        glyphs=demo.Glyphs.ascii(),
    )
    assert "undefended: executed  ->  defended: prevented" in out


# ---------------------------------------------------------------------------
# no key, no network
# ---------------------------------------------------------------------------


def test_it_runs_with_every_credential_removed(monkeypatch):
    for var in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    out = demo.render(glyphs=demo.Glyphs.ascii())
    assert "AGENT FIREWALL" in out


def test_it_makes_no_http_call(monkeypatch):
    """The provider layer is stdlib-only (D-015), so blocking urlopen blocks all of it."""
    import urllib.request

    def explode(*args, **kwargs):  # pragma: no cover - only runs on regression
        raise AssertionError("the demo opened a network connection")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    demo.render(glyphs=demo.Glyphs.ascii())


# ---------------------------------------------------------------------------
# it has to survive the console it lands on
# ---------------------------------------------------------------------------


def test_the_ascii_rendering_is_actually_ascii():
    """A fresh clone on Windows gets a cp1252 stdout; ASCII is the safe floor."""
    out = demo.render(glyphs=demo.Glyphs.ascii())
    out.encode("ascii")  # raises if a glyph or a curly quote survived


def test_glyph_detection_falls_back_on_a_narrow_stream():
    class Narrow:
        encoding = "cp1252"

    assert demo.Glyphs.detect(Narrow()).is_ascii

    class Wide:
        encoding = "utf-8"

    assert not demo.Glyphs.detect(Wide()).is_ascii


def test_colour_is_off_when_asked():
    plain = demo.render(glyphs=demo.Glyphs.ascii(), color=False)
    assert "\033[" not in plain


# ---------------------------------------------------------------------------
# selection surface
# ---------------------------------------------------------------------------


def test_an_unknown_scenario_is_an_error_not_an_empty_demo():
    with pytest.raises(SystemExit):
        demo.render(scenario="af_auth.ho.nope.nothing", glyphs=demo.Glyphs.ascii())


def test_an_unknown_scope_is_an_error():
    with pytest.raises(SystemExit):
        demo.render("no-such-arm", glyphs=demo.Glyphs.ascii())


def test_every_committed_episode_is_offered():
    rows = demo.available()
    keys = {(r.scenario_id, r.variant_id, r.seed) for r in demo.load_episodes()}
    assert len(rows) == len(keys)


def test_brief_mode_drops_the_consent_rendering():
    assert "APPROVAL REQUIRED" not in demo.render(
        glyphs=demo.Glyphs.ascii(), ask_text_mode="none"
    )


# ---------------------------------------------------------------------------
# the TCB did not learn about any of this
# ---------------------------------------------------------------------------


def _core_modules() -> list[Path]:
    return sorted(CORE.glob("*.py"))


def test_no_core_module_imports_the_demo_or_the_eval_harness():
    for path in _core_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith("agentfw.demo"), f"{path.name} imports the demo"
                assert not name.startswith("agentfw.eval"), f"{path.name} imports eval"
                assert not name.startswith("agentfw.intent"), f"{path.name} imports intent"


def test_no_core_module_mentions_a_scenario_id_or_a_demo_scene():
    """CLAUDE.md: gold scopes are labels, not logic; nothing in core may read a scenario id."""
    scene_ids = {s.scenario_id for s in demo.SCENES}
    for path in _core_modules():
        text = path.read_text(encoding="utf-8")
        assert "scenario" not in text.lower(), f"{path.name} mentions a scenario"
        for scenario_id in scene_ids:
            assert scenario_id not in text
