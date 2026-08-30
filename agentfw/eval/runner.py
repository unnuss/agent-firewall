"""Episode runner.

One episode = one (scenario, variant, model, seed). The world is rebuilt from the fixture
for every episode, so episodes are independent by construction rather than by careful
cleanup.

Sampling note: episodes run at **temperature 1.0 with a distinct seed per repeat**, not at
temperature 0. EVALUATION section 5 asks for n>=3 seeds and a bootstrap CI, and a greedy
decode repeated three times measures nothing. We want the distribution over agent
behaviour, which is the thing the firewall will have to hold against. (It is also forced:
the gpt-5 family does not accept a non-default temperature.)
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agentfw.agent.loop import run_episode
from agentfw.agent.providers.base import LLMClient
from agentfw.eval.scenario import Scenario, Suite, Variant, load_suite
from agentfw.sandbox.registry import ToolRouter
from agentfw.sandbox.world import World


class ModelConfig(BaseModel):
    id: str
    provider: str = "openai"  # openai | local | anthropic
    model: str
    base_url: str | None = None
    # Which environment variable holds the credential. Lets one config target OpenAI,
    # OpenRouter or any other OpenAI-compatible host without editing code.
    api_key_env: str = "OPENAI_API_KEY"
    extra_headers: dict[str, str] = Field(default_factory=dict)
    max_tokens: int = 2048
    temperature: float | None = 1.0
    extra_body: dict[str, Any] = Field(default_factory=dict)
    # Free-form note for the results file: "frontier" / "open-weight" / ...
    kind: str = ""


class RunConfig(BaseModel):
    experiment: str = "E-00"
    defense: str = "undefended"
    seeds: list[int] = [1, 2, 3]
    models: list[ModelConfig]
    suites: list[Suite] = ["af_auth", "af_inject", "benign"]
    split: str = "dev"
    max_workers: int = 6
    max_steps_override: int | None = None
    save_traces: bool = True
    scenario_filter: str | None = None

    @classmethod
    def from_yaml(cls, path: Path) -> RunConfig:
        return cls(**(yaml.safe_load(path.read_text(encoding="utf-8")) or {}))


class EpisodeResult(BaseModel):
    episode_id: str
    experiment: str
    defense: str
    scenario_id: str
    suite: str
    family: str
    domain: str
    split: str
    variant_id: str
    authority: str
    role: str = "core"
    specificity: str = "explicit"
    contested_authorized: bool | None
    model_id: str
    model_name: str
    model_kind: str
    seed: int
    utterance: str
    steps: int
    stop_reason: str
    latency_s: float
    usage: dict[str, int]
    error: str | None
    tool_calls: list[dict[str, Any]]
    effect_log: list[dict[str, Any]]
    contested_occurred: bool | None = None
    task_completed: bool | None = None
    task_detail: str = ""
    attack_succeeded: bool | None = None
    attack_detail: str = ""
    final_text: str = ""


def build_client(cfg: ModelConfig, seed: int) -> LLMClient:
    if cfg.provider == "anthropic":
        from agentfw.agent.providers.anthropic import AnthropicClient

        return AnthropicClient(
            cfg.model,
            base_url=cfg.base_url,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
    from agentfw.agent.providers.openai_chat import OpenAIChatClient, local_client

    if cfg.provider == "local":
        return local_client(
            cfg.model,
            base_url=cfg.base_url,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            seed=seed,
            extra_body=cfg.extra_body,
        )
    return OpenAIChatClient(
        cfg.model,
        base_url=cfg.base_url or "https://api.openai.com/v1",
        api_key_env=cfg.api_key_env,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        seed=seed,
        extra_body=cfg.extra_body,
        extra_headers=cfg.extra_headers,
    )


@dataclass(frozen=True)
class Job:
    scenario: Scenario
    variant: Variant
    model: ModelConfig
    seed: int

    @property
    def episode_id(self) -> str:
        return f"{self.scenario.id}::{self.variant.id}::{self.model.id}::s{self.seed}"


def build_jobs(cfg: RunConfig, scenarios: list[Scenario]) -> list[Job]:
    jobs = []
    for sc in scenarios:
        for var in sc.variants:
            for m in cfg.models:
                for seed in cfg.seeds:
                    jobs.append(Job(sc, var, m, seed))
    return jobs


def run_job(job: Job, cfg: RunConfig, trace_dir: Path | None) -> EpisodeResult:
    sc, var = job.scenario, job.variant
    world = World.from_fixture(sc.world.fixture, sc.world.overlay, seed=job.seed)
    router = ToolRouter.for_tools(world, sc.tools, guard=None)  # B-00: undefended
    client = build_client(job.model, job.seed)

    ep = run_episode(
        client=client,
        world=world,
        router=router,
        utterance=var.utterance,
        seed=job.seed,
        max_steps=cfg.max_steps_override or sc.max_steps,
    )

    contested = None
    if sc.contested_effect is not None:
        contested = any(sc.contested_effect.matches(r) for r in world.effect_log())
    task_ok, task_detail = (None, "")
    if var.task_oracle is not None:
        task_ok, task_detail = var.task_oracle.evaluate(world, ep.final_text)
    attack_ok, attack_detail = (None, "")
    if sc.attack is not None:
        attack_ok, attack_detail = sc.attack.success_oracle.evaluate(world, ep.final_text)

    result = EpisodeResult(
        episode_id=job.episode_id,
        experiment=cfg.experiment,
        defense=cfg.defense,
        scenario_id=sc.id,
        suite=sc.suite,
        family=sc.family,
        domain=sc.domain,
        split=sc.split,
        variant_id=var.id,
        authority=var.authority,
        role=sc.role,
        specificity=var.specificity,
        contested_authorized=var.contested_authorized,
        model_id=job.model.id,
        model_name=job.model.model,
        model_kind=job.model.kind,
        seed=job.seed,
        utterance=var.utterance,
        steps=ep.steps,
        stop_reason=ep.stop_reason,
        latency_s=round(ep.latency_s, 3),
        usage=ep.usage,
        error=ep.error,
        tool_calls=ep.tool_calls,
        effect_log=world.effect_log(),
        contested_occurred=contested,
        task_completed=task_ok,
        task_detail=task_detail,
        attack_succeeded=attack_ok,
        attack_detail=attack_detail,
        final_text=ep.final_text,
    )

    if trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        safe = job.episode_id.replace("::", "__").replace("/", "_")
        (trace_dir / f"{safe}.json").write_text(
            json.dumps(
                {"episode_id": job.episode_id, "spans": ep.trace.to_json()},
                indent=1,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    world.close()
    return result


def run(
    cfg: RunConfig,
    out_dir: Path,
    *,
    scenarios: list[Scenario] | None = None,
    progress: bool = True,
) -> list[EpisodeResult]:
    if scenarios is None:
        scenarios = []
        for suite in cfg.suites:
            scenarios += load_suite(suite, split=cfg.split)
    if cfg.scenario_filter:
        scenarios = [s for s in scenarios if cfg.scenario_filter in s.id]
    if not scenarios:
        raise SystemExit("no scenarios matched")

    jobs = build_jobs(cfg, scenarios)
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_dir = out_dir / "traces" if cfg.save_traces else None
    results_path = out_dir / "episodes.jsonl"

    done: set[str] = set()
    if results_path.exists():  # resume: never re-spend tokens on a finished episode
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["episode_id"])
    todo = [j for j in jobs if j.episode_id not in done]
    if progress:
        print(
            f"[runner] {len(jobs)} episodes total, {len(done)} already done, "
            f"{len(todo)} to run, {cfg.max_workers} workers"
        )

    results: list[EpisodeResult] = []
    started = time.time()
    with (
        results_path.open("a", encoding="utf-8") as fh,
        ThreadPoolExecutor(max_workers=cfg.max_workers) as pool,
    ):
        futures = {pool.submit(run_job, j, cfg, trace_dir): j for j in todo}
        for i, fut in enumerate(as_completed(futures), start=1):
            job = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:  # a crashed episode is data, not a lost run
                res = _failed_result(job, cfg, f"{type(exc).__name__}: {exc}")
            fh.write(res.model_dump_json() + "\n")
            fh.flush()
            results.append(res)
            if progress and (i % 5 == 0 or i == len(todo)):
                rate = i / max(time.time() - started, 1e-9)
                print(
                    f"[runner] {i}/{len(todo)}  ({rate * 60:.1f}/min)  last={res.episode_id}"
                    + (f"  ERROR={res.error}" if res.error else "")
                )
    return results


def _failed_result(job: Job, cfg: RunConfig, error: str) -> EpisodeResult:
    sc, var = job.scenario, job.variant
    return EpisodeResult(
        episode_id=job.episode_id,
        experiment=cfg.experiment,
        defense=cfg.defense,
        scenario_id=sc.id,
        suite=sc.suite,
        family=sc.family,
        domain=sc.domain,
        split=sc.split,
        variant_id=var.id,
        authority=var.authority,
        role=sc.role,
        specificity=var.specificity,
        contested_authorized=var.contested_authorized,
        model_id=job.model.id,
        model_name=job.model.model,
        model_kind=job.model.kind,
        seed=job.seed,
        utterance=var.utterance,
        steps=0,
        stop_reason="runner_error",
        latency_s=0.0,
        usage={},
        error=error,
        tool_calls=[],
        effect_log=[],
    )


def load_results(path: Path) -> list[EpisodeResult]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(EpisodeResult(**json.loads(line)))
    return out


def env_report() -> dict[str, Any]:
    return {
        "has_openai_key": bool(os.environ.get("OPENAI_API_KEY")),
        "has_anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "local_base_url": os.environ.get("AGENTFW_LOCAL_BASE_URL", "http://localhost:11434/v1"),
    }
