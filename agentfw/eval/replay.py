"""E-01a: replay recorded episodes through the deterministic firewall.

**Why replay instead of a fresh defended run.** Phase 1 is closed and its model runs are
the historical record; E-01a asks a question about the *firewall*, not about any model, and
the firewall is deterministic. So the honest and cheap way to ask it is to take the tool
calls a real agent actually made — committed in ``episodes.jsonl`` — and put each one in
front of the reference monitor. The sandbox is seeded and deterministic (D-013), so
re-executing the same calls against a fresh world reproduces the same labels, the same
confidentiality, and the same effects that the original run produced. No API call, no
dollars, and no new claim about any model.

**The limitation, which is real and is not hidden.** Replay is faithful only up to the
first refusal. A defended agent that was told "no" would have done something else next —
asked the user, tried another tool, or given up — and this harness cannot know what. So:

* **Verdict and prevention figures are sound.** For each recorded action we know exactly
  what the firewall decides and, for the contested effects, whether they would have
  executed. An overreach the firewall stops is stopped whatever happens afterwards.
* **Utility figures are not measurable here.** BTC and CuP under defense require the
  counterfactual trajectory, so this harness does not compute them and the report does not
  print them. The closest honest proxy is FPR-block: the fraction of actions the
  *undefended* agent took, on scenarios with no authorization question, that the firewall
  would have refused. That is a real cost and is reported.
* **After the first BLOCK the remaining actions in an episode are off-policy.** They are
  still evaluated, because a refused agent frequently retries the same effect through
  another tool and we want to see that, but they are counted separately so the two
  populations are never silently mixed.

The counterfactual gap is the reason a live defended run (**E-01c**) is a separate
experiment rather than a footnote here. It is not E-01b: E-01b is this same replay with
compiled scopes in place of gold ones (D-028), which costs nothing and answers a different
question — what the *compiler's* errors do to the verdicts. E-01c needs an API budget and
is the only thing that can measure BTC and CuP under defense.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentfw.agent.trace import Trace
from agentfw.core.audit import summarise
from agentfw.core.scope import IntentScope
from agentfw.core.types import ProposedAction, Verdict
from agentfw.eval.runner import EpisodeResult, load_results
from agentfw.eval.scenario import Scenario, load_suite
from agentfw.eval.scopes import GoldScopes, ScopeSource
from agentfw.firewall import build_firewall
from agentfw.policy.ask import ScriptedReviewer
from agentfw.policy.combinator import PolicyConfig
from agentfw.sandbox.registry import ToolRouter, load_all
from agentfw.sandbox.world import World

MAX_OBSERVATION_CHARS = 6000


class ActionOutcome(BaseModel):
    """One recorded tool call, put in front of the firewall."""

    step: int
    tool: str
    verdict: str
    policy_verdict: str
    gates: tuple[str, ...] = ()
    asked: bool = False
    consent_approved: bool | None = None
    effect_classes: tuple[str, ...] = ()
    executed: bool = False
    off_policy: bool = False  # follows an earlier refusal in the same episode
    explanation: str = ""


class ReplayedEpisode(BaseModel):
    episode_id: str
    scenario_id: str
    suite: str
    family: str
    role: str
    split: str
    variant_id: str
    authority: str
    specificity: str
    contested_authorized: bool | None = None
    model_id: str
    seed: int
    policy: str

    actions: list[ActionOutcome] = Field(default_factory=list)
    asks: int = 0
    blocks: int = 0
    allows: int = 0
    # Did the contested effect occur in the original (undefended) run?
    contested_occurred_undefended: bool | None = None
    # Would it occur under the firewall, on the trajectory we can actually observe?
    contested_occurred_defended: bool | None = None
    # AF-Inject only: did the attacker's target effect land, before and after?
    attack_succeeded_undefended: bool | None = None
    attack_succeeded_defended: bool | None = None
    # True when the attack oracle reads the agent's final message rather than the world.
    # Replay cannot supply that message, so such a scenario's ASR is not evaluable here
    # and is excluded rather than guessed.
    attack_oracle_needs_text: bool = False
    chain_intact: bool = True
    error: str | None = None


@dataclass
class ReplayConfig:
    """Everything E-01a varies. Deliberately tiny: there is almost nothing to tune."""

    label: str = "M0-consequential"
    ask_on: str = "consequential"
    ask_budget: int = 3
    reviewer_epsilon: float = 0.0
    # A reviewer is present unless we are measuring pure deny-by-default.
    with_reviewer: bool = True
    # What the scripted human knows (D-027).
    #
    #   "contested"  E-01a's setting: the harness knows the truth about the scenario's
    #                contested effect and nothing else, because under a gold scope nothing
    #                else is ever put to the reviewer.
    #   "gold"       E-01b's setting: the reviewer answers about *any* effect class, from
    #                the gold scope — the statement of what the utterance licensed. A
    #                compiled scope asks about classes gold contains and the reviewer says
    #                yes; that is exactly the utility ASK exists to recover (F-09), and
    #                without it every under-granted read would be scored as unrecoverable.
    #
    # Absence is still denial in both settings: a class gold does not license is refused.
    reviewer_oracle: str = "contested"
    gates: dict[str, int] = field(default_factory=dict)

    def policy(self) -> PolicyConfig:
        return PolicyConfig(ask_on=self.ask_on, ask_budget=self.ask_budget)


def _truncate(text: str) -> str:
    if len(text) <= MAX_OBSERVATION_CHARS:
        return text
    return text[:MAX_OBSERVATION_CHARS] + f"\n[...truncated, {len(text)} chars total]"


def replay_episode(
    record: EpisodeResult,
    scenario: Scenario,
    scopes: ScopeSource,
    cfg: ReplayConfig,
    gold: GoldScopes | None = None,
) -> ReplayedEpisode:
    """Re-execute one recorded episode's tool calls behind the firewall.

    ``scopes`` supplies the authority the episode starts with — the gold labels in E-01a, a
    compiled scope in E-01b. ``gold`` is never the scope; it is the label the scripted
    reviewer answers from when ``cfg.reviewer_oracle == "gold"``.
    """
    variant = scenario.variant(record.variant_id)
    world = World.from_fixture(scenario.world.fixture, scenario.world.overlay, seed=record.seed)
    router = ToolRouter.for_tools(world, scenario.tools)

    trace = Trace()
    trace.system("system")
    trace.user(record.utterance, step=0)

    scope: IntentScope = scopes.scope_for(scenario.id, variant.id, record.utterance)
    # Ground truth for the scripted reviewer. AF-Auth ground truth is structural by D-010:
    # the contested effect is licensed exactly when the variant says it is. Everything else
    # the utterance left out is, by construction, not licensed.
    oracle: dict[str, bool] = {}
    if scenario.contested_effect is not None and variant.contested_authorized is not None:
        pattern = scenario.contested_effect
        if pattern.verb is not None and pattern.resource_class is not None:
            key = f"({pattern.verb.value}, {pattern.resource_class.value})"
            oracle[key] = bool(variant.contested_authorized)
    licensed_scope: IntentScope | None = None
    if cfg.reviewer_oracle == "gold":
        if gold is None:
            raise ValueError("reviewer_oracle='gold' needs the gold scopes to answer from")
        # The whole hand-written scope, not a list of classes drawn from it. The reviewer
        # answers "would this scope have allowed this call?", which covers the bounds the
        # user stated as well as the classes they licensed — necessary once a compiler's
        # inferred bounds can be put to a human (D-030).
        licensed_scope = gold.scope_for(scenario.id, variant.id, record.utterance)

    firewall = build_firewall(
        scope=scope,
        trace=trace,
        router=router,
        episode_id=record.episode_id,
        cfg=cfg.policy(),
        reviewer=ScriptedReviewer(epsilon=cfg.reviewer_epsilon) if cfg.with_reviewer else None,
        licensed_oracle=oracle,
        licensed_scope=licensed_scope,
    )
    router.guard = firewall

    out = ReplayedEpisode(
        episode_id=record.episode_id,
        scenario_id=record.scenario_id,
        suite=record.suite,
        family=record.family,
        role=record.role,
        split=record.split,
        variant_id=record.variant_id,
        authority=record.authority,
        specificity=record.specificity,
        contested_authorized=record.contested_authorized,
        model_id=record.model_id,
        seed=record.seed,
        policy=cfg.label,
        contested_occurred_undefended=record.contested_occurred,
        attack_succeeded_undefended=record.attack_succeeded,
    )

    refused_already = False
    for i, recorded in enumerate(record.tool_calls, start=1):
        action = ProposedAction(
            call_id=f"r{i}",
            step=int(recorded.get("step", i)),
            tool_name=str(recorded["name"]),
            args=dict(recorded.get("args") or {}),
            arg_label=trace.context_label(),
            derived_from=trace.literal_evidence(dict(recorded.get("args") or {})),
        )
        trace.add(
            "agent_tool_call",
            f"{action.tool_name}({json.dumps(action.args, sort_keys=True, default=str)})",
            action.arg_label,
            step=action.step,
            tool_name=action.tool_name,
            tool_args=action.args,
            derived_from=action.derived_from,
        )
        result = router.execute(action)
        # Feed the observation back into the trace exactly as the loop would, so that
        # provenance for later calls is the same as it was in the original run.
        trace.add(
            "tool_result" if result.ok else "tool_error",
            _truncate(result.content or ("ok" if result.ok else "error")),
            result.label,
            step=action.step,
            tool_name=action.tool_name,
            tool_args=action.args,
        )

        event = firewall.audit.events[-1]
        out.actions.append(
            ActionOutcome(
                step=action.step,
                tool=action.tool_name,
                verdict=event.verdict.value,
                policy_verdict=event.policy_verdict.value,
                gates=event.gates_fired,
                asked=event.ask_text is not None,
                consent_approved=event.consent_approved,
                effect_classes=tuple(str(e.effect_class) for e in event.effects),
                executed=result.ok,
                off_policy=refused_already,
                explanation=event.explanation,
            )
        )
        if event.verdict is not Verdict.ALLOW:
            refused_already = True

    summary = summarise(firewall.audit)
    out.asks = summary.asks_raised
    out.blocks = summary.block
    out.allows = summary.allow
    out.chain_intact = summary.chain_intact
    for gate, n in summary.gates.items():
        cfg.gates[gate] = cfg.gates.get(gate, 0) + n

    if scenario.contested_effect is not None:
        out.contested_occurred_defended = any(
            scenario.contested_effect.matches(r) for r in world.effect_log()
        )
    if scenario.attack is not None:
        oracle_kinds = _oracle_kinds(scenario.attack.success_oracle)
        out.attack_oracle_needs_text = "text" in oracle_kinds
        if not out.attack_oracle_needs_text:
            # World-state oracle: sound under replay, because it reads what happened
            # rather than what the agent said about it.
            landed, _ = scenario.attack.success_oracle.evaluate(world, "")
            out.attack_succeeded_defended = landed
    world.close()
    return out


def _oracle_kinds(oracle: Any) -> set[str]:
    kinds = {oracle.kind}
    for child in oracle.children:
        kinds |= _oracle_kinds(child)
    return kinds


def replay_all(
    records: Iterable[EpisodeResult],
    cfg: ReplayConfig,
    *,
    scopes: ScopeSource | None = None,
    gold: GoldScopes | None = None,
    scenarios: dict[str, Scenario] | None = None,
) -> list[ReplayedEpisode]:
    load_all()
    gold = gold or GoldScopes.load()
    scopes = scopes or gold
    if scenarios is None:
        scenarios = {}
        for suite in ("af_auth", "af_inject", "benign"):
            for sc in load_suite(suite, split="dev"):
                scenarios[sc.id] = sc

    out: list[ReplayedEpisode] = []
    for record in records:
        scenario = scenarios.get(record.scenario_id)
        if scenario is None:
            continue  # held-out or retired scenario; not part of the dev slice
        if record.error:
            continue  # a failed provider call has no trajectory to replay
        try:
            out.append(replay_episode(record, scenario, scopes, cfg, gold))
        except Exception as exc:  # a crashed replay is data, not a lost run
            out.append(
                ReplayedEpisode(
                    episode_id=record.episode_id,
                    scenario_id=record.scenario_id,
                    suite=record.suite,
                    family=record.family,
                    role=record.role,
                    split=record.split,
                    variant_id=record.variant_id,
                    authority=record.authority,
                    specificity=record.specificity,
                    model_id=record.model_id,
                    seed=record.seed,
                    policy=cfg.label,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return out


def load_source(path: Path) -> list[EpisodeResult]:
    return load_results(path)


def write_jsonl(episodes: list[ReplayedEpisode], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(e.model_dump_json() for e in episodes) + "\n", encoding="utf-8")
    return path


def read_jsonl(path: Path) -> list[ReplayedEpisode]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(ReplayedEpisode(**json.loads(line)))
    return out


def source_digest(paths: list[Path]) -> dict[str, Any]:
    """Record which raw files a replay was computed from, and their size in episodes."""
    import hashlib

    out = {}
    for p in paths:
        blob = p.read_bytes()
        out[str(p).replace("\\", "/")] = {
            "sha256": hashlib.sha256(blob).hexdigest(),
            "episodes": len([ln for ln in blob.decode("utf-8").splitlines() if ln.strip()]),
        }
    return out
