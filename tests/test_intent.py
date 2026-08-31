"""The Phase 3 intent compiler, and the measurement built on it.

Three kinds of test here, and only the first is ordinary plumbing.

1. **The compiler does what it says.** Parsing, failure modes, the two deterministic floors.
2. **The compiler cannot see what it must not see** (D-025). The prompt is checked against
   every scenario id, variant id, contested effect and gold scope in the dev slice, because
   a compiler that had quietly been handed the label would produce a beautiful and
   completely empty result, and nothing else in the pipeline would notice.
3. **The measurement cannot flatter the compiler.** A metric that scored an empty scope as
   perfect, or that treated a missing read and an extra purchase as the same error, would
   be worse than no metric. The direction of each error is asserted.
"""

from __future__ import annotations

import json

import pytest

from agentfw.agent.providers.base import Completion
from agentfw.core.scope import ec
from agentfw.core.types import Verb
from agentfw.eval import scope_eval, scope_run
from agentfw.eval.scenario import load_suite
from agentfw.eval.scopes import GoldScopes
from agentfw.intent import catalog, prompts
from agentfw.intent.compiler import (
    CompiledScope,
    LLMIntentCompiler,
    ReadOnlyCompiler,
    ToolCeilingCompiler,
    extract_json,
)
from agentfw.intent.store import CompiledScopeStore, MissingCompiledScope
from agentfw.sandbox.registry import REGISTRY, load_all


class FakeClient:
    """One canned completion, or an exception. The compiler never touches a network."""

    name = "fake"
    model = "fake-1"

    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.seen: list[list[dict[str, str]]] = []

    def complete(self, messages, tools):
        self.seen.append(messages)
        if isinstance(self.payload, Exception):
            raise self.payload
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return Completion(text=text, usage={"total_tokens": 42}, stop_reason="stop")


@pytest.fixture(scope="module")
def dev_pairs():
    load_all()
    return scope_run.variants(["af_auth", "af_inject", "benign"], "dev")


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------


def test_every_registered_tool_is_classified() -> None:
    """A new tool without a catalogue entry must break the build, not be guessed at."""
    load_all()
    assert set(REGISTRY) == set(catalog.TOOL_EFFECTS)


def test_catalogue_covers_what_the_declarers_actually_produced() -> None:
    """The ceiling has to be a real ceiling.

    Checked against the committed E-00 corpus rather than against the declarers' source, so
    the assertion is about behaviour that really happened rather than about code that looks
    like it agrees.
    """
    from pathlib import Path

    from agentfw.core.effects import EffectMapper
    from agentfw.core.types import Integrity, Label, ProposedAction
    from agentfw.eval.runner import load_results
    from agentfw.sandbox.registry import ToolRouter
    from agentfw.sandbox.world import World

    load_all()
    scenarios = {
        s.id: s
        for suite in ("af_auth", "af_inject", "benign")
        for s in load_suite(suite, split="dev")
    }
    path = Path("experiments/e00b_revised/results/episodes.jsonl")
    if not path.exists():  # pragma: no cover - the corpus is committed
        pytest.skip("E-00b corpus not present")
    seen: dict[str, set[str]] = {}
    world = World.from_fixture("office_baseline")
    for record in load_results(path)[:400]:
        scenario = scenarios.get(record.scenario_id)
        if scenario is None:
            continue
        router = ToolRouter.for_tools(world, scenario.tools)
        mapper = EffectMapper(router.declare_for)
        for i, recorded in enumerate(record.tool_calls, start=1):
            action = ProposedAction(
                call_id=f"t{i}",
                step=i,
                tool_name=str(recorded["name"]),
                args=dict(recorded.get("args") or {}),
                arg_label=Label(integrity=Integrity.AGENT_DERIVED),
            )
            mapping = mapper.map(action)
            if not mapping.ok:
                continue
            for e in mapping.effects:
                seen.setdefault(action.tool_name, set()).add(catalog.render(e.effect_class))
    world.close()
    for tool, classes in sorted(seen.items()):
        listed = {catalog.render(k) for k in catalog.TOOL_EFFECTS[tool]}
        assert classes <= listed, f"{tool} produced {classes - listed}, not in the catalogue"


# ---------------------------------------------------------------------------
# The floors
# ---------------------------------------------------------------------------


def test_tool_ceiling_grants_everything_the_tools_can_do() -> None:
    out = ToolCeilingCompiler().compile("anything at all", ["email_send", "files_read"])
    assert set(out.effects) == {"SEND:EMAIL", "READ:USER_FILES", "READ:SECRETS"}


def test_read_only_grants_no_mutating_class() -> None:
    out = ReadOnlyCompiler().compile("delete everything", ["files_delete", "files_list"])
    assert all(catalog.parse(e).verb is Verb.READ for e in out.effects)


def test_a_floor_ignores_the_utterance_entirely() -> None:
    """The floors are floors precisely because they do not read; a floor that varied with
    the utterance would be a compiler and would need to be evaluated as one."""
    tools = ["email_send", "email_list"]
    a = ToolCeilingCompiler().compile("send it", tools)
    b = ToolCeilingCompiler().compile("do not send anything, ever", tools)
    assert a.effects == b.effects


# ---------------------------------------------------------------------------
# The LLM compiler
# ---------------------------------------------------------------------------


def test_parses_a_clean_response() -> None:
    client = FakeClient(
        {
            "effects": ["READ:EMAIL", "CREATE:EMAIL"],
            "constraints": [
                {
                    "kind": "recipient",
                    "applies_to": "SEND:EMAIL",
                    "allowed_recipients": ["priya@example.com"],
                }
            ],
            "open_questions": ["whether to send"],
        }
    )
    out = LLMIntentCompiler(client).compile("draft a reply", ["email_list", "email_draft"])
    assert out.error is None
    assert set(out.effects) == {"READ:EMAIL", "CREATE:EMAIL"}
    assert out.open_questions == ("whether to send",)
    scope = out.to_scope("draft a reply")
    assert scope.authorized_effects == {ec("READ", "EMAIL"), ec("CREATE", "EMAIL")}
    assert len(scope.constraints) == 1


def test_a_fenced_response_still_parses() -> None:
    client = FakeClient('```json\n{"effects": ["READ:EMAIL"]}\n```')
    out = LLMIntentCompiler(client).compile("check my mail", ["email_list"])
    assert out.effects == ("READ:EMAIL",)


@pytest.mark.parametrize(
    "payload",
    [RuntimeError("provider exploded"), "I am afraid I cannot help with that."],
)
def test_failure_produces_an_empty_scope_and_says_so(payload: object) -> None:
    """Fail closed. An empty scope authorizes nothing, which is the only sound direction
    for a component that sits in front of a deny-by-default monitor."""
    out = LLMIntentCompiler(FakeClient(payload)).compile("anything", ["email_list"])
    assert out.error
    assert out.effects == ()
    assert out.to_scope("anything").authorized_effects == frozenset()


def test_junk_effect_strings_are_recorded_not_silently_dropped() -> None:
    client = FakeClient({"effects": ["READ:EMAIL", "FLY:MOON", "not an effect"]})
    out = LLMIntentCompiler(client).compile("x", ["email_list"])
    assert out.effects == ("READ:EMAIL",)
    assert set(out.unsupported_effects) == {"FLY:MOON", "not an effect"}


def test_a_class_no_tool_can_produce_is_kept_but_flagged() -> None:
    """Authority over something the application cannot do is harmless, and removing it
    would flatter precision. It is reported instead."""
    client = FakeClient({"effects": ["READ:EMAIL", "PURCHASE:FINANCIAL"]})
    out = LLMIntentCompiler(client).compile("x", ["email_list"])
    assert "PURCHASE:FINANCIAL" in out.effects
    assert "PURCHASE:FINANCIAL" in out.unsupported_effects


def test_an_unusable_constraint_is_dropped_loudly() -> None:
    """Dropping a constraint widens authority, so it may never be silent."""
    client = FakeClient(
        {"effects": ["SEND:EMAIL"], "constraints": [{"kind": "vibes", "applies_to": "x"}]}
    )
    scope = LLMIntentCompiler(client).compile("x", ["email_send"]).to_scope("x")
    assert scope.constraints == ()
    assert any("unusable constraint" in q for q in scope.open_questions)


def test_extract_json_rejects_prose() -> None:
    with pytest.raises(ValueError):
        extract_json("there is no object here")


# ---------------------------------------------------------------------------
# D-025: what the compiler is allowed to see
# ---------------------------------------------------------------------------


def test_the_prompt_never_contains_the_label(dev_pairs) -> None:
    """The whole experiment turns on this. If any of the answers reached the prompt, the
    compiler would be scoring itself against something it had been told."""
    gold = GoldScopes.load()
    for scenario, variant in dev_pairs:
        rendered = json.dumps(prompts.build(variant.utterance, list(scenario.tools)))
        assert scenario.id not in rendered
        if scenario.contested_effect is not None:
            pattern = scenario.contested_effect
            if pattern.verb is not None and pattern.resource_class is not None:
                assert (
                    f"{pattern.verb.value}:{pattern.resource_class.value}"
                    not in (rendered.split('"role": "user"')[-1])
                )
        raw = gold.data.get(scenario.id, {}).get(variant.id, {})
        for question in raw.get("open_questions", []) or []:
            assert question not in rendered


def test_the_compiler_signature_takes_only_utterance_and_tools() -> None:
    import inspect

    for cls in (ToolCeilingCompiler, ReadOnlyCompiler, LLMIntentCompiler):
        params = list(inspect.signature(cls.compile).parameters)
        assert params == ["self", "utterance", "tools"], cls.__name__


def test_identity_is_attached_after_compilation(dev_pairs) -> None:
    """``compile_all`` must stamp the scenario id onto the record, never pass it in."""
    seen: list[tuple[str, list[str]]] = []

    class Recorder:
        name = "recorder"

        def compile(self, utterance: str, tools: list[str]) -> CompiledScope:
            seen.append((utterance, list(tools)))
            return CompiledScope(scenario_id="", variant_id="", compiler=self.name)

    records = scope_run.compile_all(Recorder(), dev_pairs[:3], max_workers=1)
    assert all(r.scenario_id for r in records)
    assert all("af_auth" not in utterance for utterance, _ in seen)


# ---------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------


def test_store_round_trips_and_raises_on_a_gap(tmp_path) -> None:
    record = CompiledScope(
        scenario_id="s.one", variant_id="a", compiler="fake", effects=("READ:EMAIL",)
    )
    path = CompiledScopeStore.write([record], tmp_path / "scopes.jsonl")
    store = CompiledScopeStore.load(path)
    assert store.scope_for("s.one", "a", "obj").authorized_effects == {ec("READ", "EMAIL")}
    with pytest.raises(MissingCompiledScope):
        store.scope_for("s.one", "b", "obj")


# ---------------------------------------------------------------------------
# The measurement
# ---------------------------------------------------------------------------


def _comparison(
    gold: list[str],
    compiled: list[str],
    *,
    variant_id: str = "a",
    gold_constraints: list[dict] | None = None,
    compiled_constraints: list[dict] | None = None,
    gold_open_questions: list[str] | None = None,
    compiled_open_questions: list[str] | None = None,
    error: str | None = None,
) -> scope_eval.VariantComparison:
    load_all()
    scenario = next(
        s for s in load_suite("af_auth", split="dev") if s.id == "af_auth.travel.book_flight"
    )
    record = CompiledScope(
        scenario_id=scenario.id,
        variant_id=variant_id,
        compiler="fake",
        effects=tuple(compiled),
        constraints=tuple(compiled_constraints or ()),
        open_questions=tuple(compiled_open_questions or ()),
        error=error,
    )
    gold_raw = {
        "effects": gold,
        "constraints": gold_constraints or [],
        "open_questions": gold_open_questions or [],
    }
    return scope_eval.compare_one(record, scenario, gold_raw)


def test_over_and_under_granting_are_not_the_same_error() -> None:
    over = _comparison(["READ:PUBLIC_WEB"], ["READ:PUBLIC_WEB", "PURCHASE:FINANCIAL"])
    under = _comparison(["READ:PUBLIC_WEB", "READ:CALENDAR"], ["READ:PUBLIC_WEB"])
    assert over.over == ("PURCHASE:FINANCIAL",) and over.under == ()
    assert under.under == ("READ:CALENDAR",) and under.over == ()


def test_a_failed_compilation_scores_as_an_empty_scope() -> None:
    """Not as a missing observation. A compiler outage is a refusal to authorize anything,
    and the metric has to see it that way or an unreliable compiler looks like a cautious
    one."""
    row = _comparison(["READ:PUBLIC_WEB"], ["READ:PUBLIC_WEB"], error="boom")
    assert row.compiled == () and row.under == ("READ:PUBLIC_WEB",)


def test_contested_leakage_is_read_from_the_scenario_not_from_gold() -> None:
    row = _comparison(["READ:PUBLIC_WEB"], ["READ:PUBLIC_WEB", "PURCHASE:FINANCIAL"])
    assert row.contested == "PURCHASE:FINANCIAL"
    assert row.contested_in_gold is False
    assert row.contested_in_compiled is True


BUDGET_150 = {"kind": "budget", "applies_to": "PURCHASE:FINANCIAL", "max_usd": 150.0}
BUDGET_900 = {"kind": "budget", "applies_to": "PURCHASE:FINANCIAL", "max_usd": 900.0}


def test_constraint_matching_separates_the_kind_from_the_bound() -> None:
    same = _comparison(
        ["PURCHASE:FINANCIAL"],
        ["PURCHASE:FINANCIAL"],
        gold_constraints=[BUDGET_150],
        compiled_constraints=[BUDGET_150],
    )
    assert same.constraints_kind_matched == 1
    assert same.constraints_bound_matched == 1


def test_a_wrong_bound_matches_the_kind_but_not_the_bound() -> None:
    """A budget of $900 where the user said $150 is not a near miss, it is the difference
    between the constraint doing its job and not existing."""
    row = _comparison(
        ["PURCHASE:FINANCIAL"],
        ["PURCHASE:FINANCIAL"],
        gold_constraints=[BUDGET_150],
        compiled_constraints=[BUDGET_900],
    )
    assert row.constraints_kind_matched == 1
    assert row.constraints_bound_matched == 0


def test_contrast_fidelity_punishes_both_failure_directions() -> None:
    """A compiler that grants everything and one that grants nothing must both score 0."""
    load_all()
    scenarios = {s.id: s for s in load_suite("af_auth", split="dev")}
    gold = GoldScopes.load()
    pairs = [(s, v) for s in scenarios.values() for v in s.variants]

    for compiler in (ToolCeilingCompiler(), ReadOnlyCompiler()):
        records = scope_run.compile_all(compiler, pairs, max_workers=1)
        rows = scope_eval.compare_all(records, scenarios, gold)
        rep = scope_eval.build(rows, label=compiler.name)
        assert rep["contested"]["contrast_fidelity"]["value"] == 0.0

    ceiling = scope_eval.build(
        scope_eval.compare_all(
            scope_run.compile_all(ToolCeilingCompiler(), pairs, max_workers=1),
            scenarios,
            gold,
        )
    )
    floor = scope_eval.build(
        scope_eval.compare_all(
            scope_run.compile_all(ReadOnlyCompiler(), pairs, max_workers=1), scenarios, gold
        )
    )
    # ...and they fail it in opposite directions, which is what makes them a bracket.
    assert ceiling["contested"]["leakage_underspecified_low"]["value"] == 1.0
    assert ceiling["contested"]["retention_high"]["value"] == 1.0
    assert floor["contested"]["leakage_underspecified_low"]["value"] == 0.0
    assert floor["contested"]["retention_high"]["value"] == 0.0


def test_seed_agreement_is_one_when_seeds_agree() -> None:
    row = _comparison(["READ:EMAIL"], ["READ:EMAIL"])
    out = scope_eval.seed_agreement({1: [row], 2: [row]})
    assert out["mean_pairwise_jaccard"] == 1.0
    assert out["identical_fraction"] == 1.0
