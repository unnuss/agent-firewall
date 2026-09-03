"""E-09a's driver: compile every dev utterance, once per (compiler, seed).

One call per (scenario, variant, compiler, seed) and nothing else. The compiler sees the
utterance and the scenario's tool list; the scenario id, the variant id, the contested
effect and the gold scope are attached to the *record* afterwards so the results can be
joined, never passed to the compiler. That ordering is the point — see ``compiler.py`` —
and ``test_intent.py`` asserts the prompt contains none of them.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agentfw.eval.runner import ModelConfig
from agentfw.eval.scenario import Scenario, load_suite
from agentfw.intent.compiler import (
    CompiledScope,
    Compiler,
    LLMIntentCompiler,
    ReadOnlyCompiler,
    ToolCeilingCompiler,
)


class CompilerConfig(BaseModel):
    """One arm of E-09a."""

    label: str
    kind: str = "llm"  # llm | tool-ceiling | read-only
    model: ModelConfig | None = None
    seeds: list[int] = [1, 2, 3]
    # Which registered prompt formulation this arm uses (E-10). Arms differ in exactly one
    # thing, and for the cross-vendor arm that thing is the model, so the prompt is pinned
    # to the baseline there rather than to whichever variant looks best.
    prompt: str = "baseline"
    # Per-arm concurrency, overriding the run-level default. It exists because of a real
    # failure: six workers against a CPU-bound local server queue behind each other, every
    # request blows the provider timeout, and 25 of 86 compilations came back as *empty
    # scopes* — which the metrics correctly score as a compiler that authorized nothing.
    # A harness setting must never be able to masquerade as a compiler's error rate, so a
    # local arm sets this to 1 rather than being quietly slower and wrong.
    max_workers: int | None = None


class CompileRunConfig(BaseModel):
    experiment: str = "E-09a"
    suites: list[str] = ["af_auth", "af_inject", "benign"]
    split: str = "dev"
    max_workers: int = 6
    compilers: list[CompilerConfig] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> CompileRunConfig:
        return cls(**(yaml.safe_load(path.read_text(encoding="utf-8")) or {}))


def build_compiler(cfg: CompilerConfig, seed: int) -> Compiler:
    if cfg.kind == "tool-ceiling":
        return ToolCeilingCompiler()
    if cfg.kind == "read-only":
        return ReadOnlyCompiler()
    if cfg.kind != "llm":
        raise ValueError(f"unknown compiler kind {cfg.kind!r}")
    if cfg.model is None:
        raise ValueError(f"{cfg.label}: an llm compiler needs a model block")
    from agentfw.agent.providers.openai_chat import OpenAIChatClient

    m = cfg.model
    local = m.provider == "local"
    client = OpenAIChatClient(
        m.model,
        base_url=m.base_url
        or ("http://localhost:11434/v1" if local else "https://api.openai.com/v1"),
        api_key_env=m.api_key_env,
        api_key="local" if local else None,
        require_key=not local,
        temperature=m.temperature,
        max_tokens=m.max_tokens,
        seed=seed,
        # Structured output. The parser tolerates a stray fence anyway, but asking for
        # JSON removes the most common failure and costs nothing.
        extra_body={"response_format": {"type": "json_object"}, **m.extra_body},
        extra_headers=m.extra_headers,
    )
    # Imported as `prompt_variants` because this module already has a `variants()`
    # function meaning something else entirely (scenario variants).
    from agentfw.intent import variants as prompt_variants

    return LLMIntentCompiler(
        client, name=f"llm:{m.id}", seed=seed, variant=prompt_variants.get(cfg.prompt)
    )


def variants(suites: list[str], split: str) -> list[tuple[Scenario, Any]]:
    out = []
    for suite in suites:
        for sc in load_suite(suite, split=split):  # type: ignore[arg-type]
            for v in sc.variants:
                out.append((sc, v))
    return out


def compile_all(
    compiler: Compiler,
    pairs: list[tuple[Scenario, Any]],
    *,
    max_workers: int = 6,
) -> list[CompiledScope]:
    def one(item: tuple[Scenario, Any]) -> CompiledScope:
        sc, v = item
        record = compiler.compile(v.utterance, list(sc.tools))
        # Identity is attached here, after compilation, never before it.
        return record.model_copy(update={"scenario_id": sc.id, "variant_id": v.id})

    if max_workers <= 1:
        return [one(p) for p in pairs]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(one, pairs))
