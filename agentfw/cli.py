"""Command line entry point.

agentfw validate                 # scenarios load, tools exist, declarations agree
agentfw generate                 # expand pair templates into the held-out suite
agentfw run experiments/e00_undefended/config.yaml
agentfw report experiments/e00_undefended/results
agentfw compile-scopes experiments/e09a_compiler/config.yaml  # E-09a, one call per utterance
agentfw replay experiments/e01a_deterministic/config.yaml     # E-01a, no model calls
agentfw replay experiments/e01b_compiled/config.yaml          # E-01b, no model calls
agentfw smoke                    # one scripted episode, no network, no key
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentfw.config import load_local_env
from agentfw.eval import report as report_mod
from agentfw.eval.generator import expand_dir, write_suite
from agentfw.eval.runner import RunConfig, env_report, run
from agentfw.eval.scenario import SUITE_DIR, load_suite
from agentfw.sandbox.registry import REGISTRY, load_all


def cmd_validate(args: argparse.Namespace) -> int:
    load_all()
    scenarios = load_suite(split=None)
    problems: list[str] = []
    for sc in scenarios:
        unknown = [t for t in sc.tools if t not in REGISTRY]
        if unknown:
            problems.append(f"{sc.id}: unknown tools {unknown}")
        if sc.suite == "af_auth" and sc.contested_effect is None:
            problems.append(f"{sc.id}: missing contested_effect")
    counts: dict[str, int] = {}
    for sc in scenarios:
        counts[f"{sc.suite}/{sc.split}"] = counts.get(f"{sc.suite}/{sc.split}", 0) + 1
    for k in sorted(counts):
        print(f"  {k}: {counts[k]} scenarios")
    print(f"  tools registered: {len(REGISTRY)}")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("OK")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    scenarios = expand_dir()
    out = Path(args.out) if args.out else SUITE_DIR / "af_auth" / "generated_heldout.yaml"
    n = write_suite(scenarios, out)
    print(f"wrote {n} generated scenarios to {out}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg = RunConfig.from_yaml(Path(args.config))
    if args.seeds:
        cfg.seeds = [int(s) for s in args.seeds.split(",")]
    if args.models:
        keep = set(args.models.split(","))
        cfg.models = [m for m in cfg.models if m.id in keep]
    if args.suites:
        cfg.suites = args.suites.split(",")  # type: ignore[assignment]
    if args.filter:
        cfg.scenario_filter = args.filter
    if args.workers:
        cfg.max_workers = args.workers
    out_dir = Path(args.out) if args.out else Path(args.config).parent / "results"
    print(f"[env] {json.dumps(env_report())}")
    run(cfg, out_dir)
    rep = report_mod.write(out_dir, title=f"{cfg.experiment} — {cfg.defense}")
    print(f"\n[report] {out_dir / 'report.md'}")
    print(report_mod.to_markdown(rep).split("## Overreach")[0])
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    """E-01a and E-01b: put committed Phase 1 trajectories in front of the firewall.

    No provider is constructed and no key is read, in either experiment. E-01b's compiled
    scopes are read from the committed artifacts E-09a produced, so the whole thing stays a
    function of files already in the repository — which is what makes it reproducible by
    anyone who clones it.
    """
    import yaml

    from agentfw.eval import replay as replay_mod
    from agentfw.eval import replay_report
    from agentfw.eval.scopes import GoldScopes
    from agentfw.intent.store import CompiledScopeStore

    cfg_path = Path(args.config)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    out_dir = Path(args.out) if args.out else cfg_path.parent / "results"

    sources = [Path(p) for p in cfg.get("sources", [])]
    missing = [p for p in sources if not p.exists()]
    if missing:
        print(f"missing source runs: {missing}")
        return 1
    records = []
    for src in sources:
        records += replay_mod.load_source(src)
    print(f"[replay] {len(records)} source episodes from {len(sources)} run(s)")

    policies = cfg.get("policies") or [{"label": "M0-consequential"}]
    if args.policy:
        policies = [p for p in policies if p.get("label") == args.policy]
        if not policies:
            print(f"no policy named {args.policy!r} in {cfg_path}")
            return 1

    gold = GoldScopes.load()
    scope_sources = cfg.get("scope_sources") or [{"label": "gold", "kind": "gold"}]
    if args.scopes:
        scope_sources = [s for s in scope_sources if s.get("label") == args.scopes]
        if not scope_sources:
            print(f"no scope source named {args.scopes!r} in {cfg_path}")
            return 1

    written: list[tuple[str, str, Path]] = []
    reports: dict[str, dict] = {}
    for spec in scope_sources:
        slabel = str(spec.get("label", "gold"))
        kind = str(spec.get("kind", "gold"))
        if kind == "gold":
            scopes: object = gold
            missing_note = ""
        elif kind == "compiled":
            path = Path(str(spec["path"]))
            if not path.exists():
                print(f"missing compiled scopes: {path} (run `agentfw compile-scopes` first)")
                return 1
            store = CompiledScopeStore.load(path, label=slabel)
            scopes = store
            missing_note = f", {len(store.errors)} compile errors"
        else:
            print(f"unknown scope source kind {kind!r}")
            return 1

        for raw in policies:
            rcfg = replay_mod.ReplayConfig(**raw)
            episodes = replay_mod.replay_all(records, rcfg, scopes=scopes, gold=gold)
            errors = sum(1 for e in episodes if e.error)
            print(
                f"[replay] {slabel}/{rcfg.label}: {len(episodes)} replayed, "
                f"{errors} errors{missing_note}, gates={rcfg.gates}"
            )
            stem = f"{slabel}__{rcfg.label}" if len(scope_sources) > 1 else rcfg.label
            replay_mod.write_jsonl(episodes, out_dir / f"{stem}.jsonl")
            reports[stem] = replay_report.write(
                episodes,
                out_dir / stem,
                extra={
                    "experiment": cfg.get("experiment", "E-01a"),
                    "policy": raw,
                    "scope_source": spec,
                    "sources": replay_mod.source_digest(sources),
                },
            )
            written.append((slabel, rcfg.label, out_dir / stem / "report.md"))

    if len(reports) > 1:
        summary = replay_report.comparison_markdown(reports, title=cfg.get("experiment", ""))
        (out_dir / "comparison.md").write_text(summary, encoding="utf-8")
        print(summary)
        print(f"[replay] comparison: {out_dir / 'comparison.md'}")

    print(f"{NEWLINE}[replay] wrote {out_dir}")
    for slabel, plabel, path in written:
        print(f"  {slabel} / {plabel}: {path}")
    return 0


def cmd_compile_scopes(args: argparse.Namespace) -> int:
    """E-09a: compile every dev utterance into an IntentScope and score it against gold.

    The deterministic arms (`tool-ceiling`, `read-only`) need no key and no network. The
    LLM arms cost one short completion per utterance; `--dry-run` prints the plan and the
    estimated call count without spending anything.
    """
    from agentfw.eval import scope_eval, scope_run
    from agentfw.eval.scopes import GoldScopes
    from agentfw.intent import prompts
    from agentfw.intent.store import CompiledScopeStore

    cfg_path = Path(args.config)
    cfg = scope_run.CompileRunConfig.from_yaml(cfg_path)
    out_dir = Path(args.out) if args.out else cfg_path.parent / "results"
    pairs = scope_run.variants(cfg.suites, cfg.split)
    if args.filter:
        pairs = [(s, v) for s, v in pairs if args.filter in s.id]
    if args.limit:
        pairs = pairs[: args.limit]

    arms = cfg.compilers
    if args.compiler:
        arms = [a for a in arms if a.label == args.compiler]
        if not arms:
            print(f"no compiler labelled {args.compiler!r} in {cfg_path}")
            return 1

    planned = sum(len(pairs) * (len(a.seeds) if a.kind == "llm" else 1) for a in arms)
    print(f"[compile] {len(pairs)} utterances x {len(arms)} arm(s) = {planned} compilations")
    if args.dry_run:
        for a in arms:
            print(f"  {a.label}: kind={a.kind} seeds={a.seeds if a.kind == 'llm' else [0]}")
        return 0

    gold = GoldScopes.load()
    scenarios = {s.id: s for s, _ in pairs}
    for arm in arms:
        seeds = arm.seeds if arm.kind == "llm" else [0]
        by_seed: dict[int, list] = {}
        for seed in seeds:
            compiler = scope_run.build_compiler(arm, seed)
            workers = arm.max_workers or cfg.max_workers
            records = scope_run.compile_all(compiler, pairs, max_workers=workers)
            # LLM artifacts carry the prompt version in the filename. A prompt change
            # produces a different experiment, and two runs of different prompts must not
            # be able to land on the same path and quietly overwrite each other (R-16).
            stem = (
                f"{arm.label}.p{prompts.VERSION}.s{seed}"
                if arm.kind == "llm"
                else f"{arm.label}.s{seed}"
            )
            store_path = out_dir / f"{stem}.jsonl"
            CompiledScopeStore.write(records, store_path)
            rows = scope_eval.compare_all(records, scenarios, gold)
            by_seed[seed] = rows
            usage = CompiledScopeStore(records).usage()
            failed = sum(1 for r in records if r.error)
            rep = scope_eval.write(
                rows,
                out_dir / stem,
                label=f"{arm.label} (seed {seed})"
                + (f", prompt v{prompts.VERSION}" if arm.kind == "llm" else ""),
                extra={"usage": usage, "compile_failures": failed, "arm": arm.model_dump()},
            )
            print(
                f"[compile] {arm.label} s{seed}: {len(records)} scopes, {failed} failures, "
                f"F1={rep['effect_sets']['micro_f1']:.3f}, "
                f"leakage={rep['contested']['leakage_underspecified_low']['value'] * 100:.1f}%,"
                f" contrast={rep['contested']['contrast_fidelity']['value'] * 100:.1f}%, "
                f"tokens={usage.get('total_tokens', 0)}"
            )
        if len(seeds) > 1:
            pooled = [r for seed in seeds for r in by_seed[seed]]
            rep = scope_eval.write(
                pooled,
                out_dir / arm.label,
                label=f"{arm.label} (all seeds pooled)",
                extra={"seed_agreement": scope_eval.seed_agreement(by_seed)},
            )
            print(f"[compile] {arm.label} pooled: {out_dir / arm.label / 'report.md'}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    out_dir = Path(args.results)
    rep = report_mod.write(out_dir, title=args.title)
    print(report_mod.to_markdown(rep, args.title))
    return 0


PREFLIGHT_TOOL = "email_list"
NEWLINE = chr(10)


def cmd_preflight(args: argparse.Namespace) -> int:
    """Check an OpenAI-compatible endpoint can really do structured tool calling.

    Worth its own command because the failure it catches is expensive and silent: a served
    model whose chat template lacks a tool-call parser returns the call as *prose*, the
    agent loop sees no tool_calls, every episode ends at step 1, and the run reports 0%
    overreach that means nothing at all. We measured exactly that locally with
    qwen2.5-coder through Ollama. Run this before spending GPU hours.
    """
    from agentfw.agent.providers.base import ProviderError
    from agentfw.agent.providers.openai_chat import OpenAIChatClient
    from agentfw.sandbox.registry import get_tools

    load_all()
    tools = get_tools([PREFLIGHT_TOOL])
    import os

    key = args.api_key or (os.environ.get(args.api_key_env) if args.api_key_env else None)
    client = OpenAIChatClient(
        args.model,
        base_url=args.base_url,
        api_key=key or "local",
        require_key=False,
        temperature=None if args.no_temperature else 1.0,
        max_tokens=args.max_tokens,
    )
    print(f"[preflight] {args.model} at {args.base_url}")

    checks: list[tuple[str, bool, str]] = []
    messages = [
        {"role": "system", "content": "You are an assistant with tools. Call one when needed."},
        {"role": "user", "content": "List the messages in my inbox."},
    ]
    try:
        first = client.complete(messages, tools)
    except ProviderError as exc:
        print(f"  FAIL  endpoint unreachable: {exc}")
        return 1

    checks.append(
        (
            "returns a structured tool call, not prose",
            bool(first.tool_calls),
            f"finish_reason={first.stop_reason!r} text={first.text[:80]!r}",
        )
    )
    name_ok = bool(first.tool_calls) and first.tool_calls[0].name == PREFLIGHT_TOOL
    checks.append(
        ("calls the tool it was given", name_ok, str([c.name for c in first.tool_calls]))
    )
    args_ok = bool(first.tool_calls) and isinstance(first.tool_calls[0].arguments, dict)
    args_ok = args_ok and "__unparsed__" not in first.tool_calls[0].arguments
    checks.append(
        (
            "arguments parse as a JSON object",
            args_ok,
            str([c.arguments for c in first.tool_calls]),
        )
    )

    # Second turn: a template that cannot accept a tool result back breaks the loop even
    # when the first call looks fine.
    if first.tool_calls:
        call = first.tool_calls[0]
        import json as _json

        messages += [
            {
                "role": "assistant",
                "content": first.text or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": _json.dumps(call.arguments),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": "m-001 | from sam | Q3 numbers",
            },
        ]
        try:
            second = client.complete(messages, tools)
            checks.append(
                (
                    "accepts a tool result and answers",
                    bool(second.text or second.tool_calls),
                    f"text={second.text[:80]!r}",
                )
            )
        except ProviderError as exc:
            checks.append(("accepts a tool result and answers", False, str(exc)[:200]))

    width = max(len(c[0]) for c in checks)
    for label, okay, detail in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {label.ljust(width)}   {detail}")
    passed = all(c[1] for c in checks)
    print(
        NEWLINE
        + "[preflight] "
        + (
            "READY — this endpoint can run E-00c."
            if passed
            else "NOT READY — fix the tool-call parser before spending GPU time."
        )
    )
    if not passed:
        print("            For vLLM you almost certainly need --enable-auto-tool-choice")
        print("            together with the right --tool-call-parser for the model family.")
    return 0 if passed else 1


def _per_million(pricing: dict, key: str) -> str:
    """OpenRouter quotes price per token; humans reason in dollars per million."""
    try:
        return f"${float(pricing.get(key, 0)) * 1e6:,.2f}"
    except (TypeError, ValueError):
        return "?"


def cmd_models(args: argparse.Namespace) -> int:
    """List candidate models from an OpenAI-compatible catalogue, with tool support.

    Exists so model ids, native tool-calling support and price are read from the provider
    at the moment of use rather than from documentation that ages. OpenRouter advertises
    `supported_parameters`; a model that does not list `tools` cannot run this benchmark,
    and finding that out here costs nothing.
    """
    import json
    import os
    import urllib.request

    key = os.environ.get(args.api_key_env, "")
    req = urllib.request.Request(f"{args.base_url.rstrip('/')}/models")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    rows = []
    for m in data.get("data", []):
        mid = str(m.get("id", ""))
        if args.grep and args.grep.lower() not in mid.lower():
            continue
        params = m.get("supported_parameters") or []
        pricing = m.get("pricing") or {}
        rows.append(
            (
                mid,
                "tools" in params,
                m.get("context_length"),
                _per_million(pricing, "prompt"),
                _per_million(pricing, "completion"),
            )
        )
    if not rows:
        print("no models matched")
        return 1
    rows.sort(key=lambda r: (not r[1], r[0]))
    width = min(max(len(r[0]) for r in rows), 60)
    print(f"{'model'.ljust(width)}  tools  ctx      $/Mtok in   $/Mtok out")
    for mid, tools, ctx, pin, pout in rows[: args.limit]:
        flag = "yes  " if tools else "NO   "
        print(
            f"{mid[:width].ljust(width)}  {flag}  {str(ctx or '?').ljust(7)}  "
            f"{pin.rjust(9)}   {pout.rjust(10)}"
        )
    print(
        f"{NEWLINE}Models marked NO cannot run this benchmark: without native structured "
        f"tool calling every episode ends at step one."
    )
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Put two runs side by side on the contrast that matters."""
    from agentfw.eval import metrics
    from agentfw.eval.runner import load_results

    rows = []
    for spec in args.results:
        label, _, path = spec.partition("=")
        if not path:
            label, path = Path(label).parent.name, label
        eps = metrics.usable(load_results(Path(path) / "episodes.jsonl"))
        low = metrics.auth_low(eps)
        cell = {"label": label, "n": len(eps)}
        for spec_kind in ("underspecified", "explicit"):
            sel = metrics.by_key(low, "specificity", spec_kind)
            r = metrics.rate(spec_kind, sel, lambda e: e.contested_occurred, n_boot=4000)
            inc = metrics.scenario_incidence(sel, lambda e: e.contested_occurred, n_boot=4000)
            cell[spec_kind] = (r, inc)
        gate = metrics.competency_gate(eps)
        cell["compliance"] = metrics.rate(
            "compliance", metrics.auth_high(eps), lambda e: e.contested_occurred, n_boot=4000
        )
        cell["gate"] = gate["passed"]
        rows.append(cell)

    print(
        "| Run | Episodes | Underspecified OR | Explicit-low OR "
        "| Gap | Incidence (u/e) | Compliance |"
    )
    print("|---|---|---|---|---|---|---|")
    for c in rows:
        u, ui = c["underspecified"]
        e, ei = c["explicit"]
        gap = (u.value - e.value) * 100
        print(
            f"| {c['label']} | {c['n']} | {u.pct()} | {e.pct()} | "
            f"**{gap:+.1f} pp** | {ui.k}/{ui.n} vs {ei.k}/{ei.n} | "
            f"{c['compliance'].pct()}{'' if c['gate'] else ' **(below floor)**'} |"
        )
    print(
        NEWLINE + "Rows marked (below floor) failed the pre-registered competency gate "
        "and are not evidence either way."
        + NEWLINE
        + "The replication question is whether the gap column stays large "
        "and positive "
        "outside the OpenAI family."
        + NEWLINE
        + "A low compliance figure means the model was not "
        "competent enough for its overreach rate to be interpretable."
    )
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    from agentfw.agent.loop import run_episode
    from agentfw.agent.providers.scripted import ScriptedClient, call, say
    from agentfw.sandbox.registry import ToolRouter
    from agentfw.sandbox.world import World

    world = World.from_fixture("office_baseline")
    router = ToolRouter.for_tools(world, ["email_list", "email_read", "email_draft"])
    client = ScriptedClient(
        [
            call("email_list", {"folder": "inbox"}),
            call("email_read", {"id": "m-001"}, cid="c2"),
            call(
                "email_draft",
                {"to": "sam.okafor@northwind-systems.com", "subject": "Q3", "body": "71%"},
                cid="c3",
            ),
            say("Drafted a reply to Sam with the utilisation figure."),
        ]
    )
    ep = run_episode(
        client=client, world=world, router=router, utterance="Draft a reply to Sam."
    )
    print(f"steps={ep.steps} stop={ep.stop_reason} tools={[c['name'] for c in ep.tool_calls]}")
    print(f"effects={[(r['verb'], r['resource_class']) for r in world.effect_log()]}")
    print(f"labels={sorted({s.label.integrity.value for s in ep.trace.spans})}")
    print(f"final={ep.final_text}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="agentfw")
    p.add_argument(
        "--override-env",
        action="store_true",
        help="let .env.local override an already-set environment variable",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate").set_defaults(fn=cmd_validate)

    g = sub.add_parser("generate")
    g.add_argument("--out")
    g.set_defaults(fn=cmd_generate)

    r = sub.add_parser("run")
    r.add_argument("config")
    r.add_argument("--out")
    r.add_argument("--seeds")
    r.add_argument("--models")
    r.add_argument("--suites")
    r.add_argument("--filter")
    r.add_argument("--workers", type=int)
    r.set_defaults(fn=cmd_run)

    rp = sub.add_parser("replay")
    rp.add_argument("config")
    rp.add_argument("--out")
    rp.add_argument("--policy", help="run only the policy with this label")
    rp.add_argument("--scopes", help="run only the scope source with this label")
    rp.set_defaults(fn=cmd_replay)

    cs = sub.add_parser("compile-scopes")
    cs.add_argument("config")
    cs.add_argument("--out")
    cs.add_argument("--compiler", help="run only the arm with this label")
    cs.add_argument("--filter", help="substring match on the scenario id")
    cs.add_argument("--limit", type=int, help="compile at most this many utterances")
    cs.add_argument(
        "--dry-run",
        action="store_true",
        help="print the plan and the call count without calling anything",
    )
    cs.set_defaults(fn=cmd_compile_scopes)

    rep = sub.add_parser("report")
    rep.add_argument("results")
    rep.add_argument("--title", default="E-00 — undefended baseline")
    rep.set_defaults(fn=cmd_report)

    pf = sub.add_parser("preflight")
    pf.add_argument("--base-url", default="http://localhost:8000/v1")
    pf.add_argument("--model", required=True)
    pf.add_argument("--api-key")
    pf.add_argument(
        "--api-key-env", default="OPENROUTER_API_KEY", help="env var holding the credential"
    )
    pf.add_argument("--max-tokens", type=int, default=256)
    pf.add_argument(
        "--no-temperature",
        action="store_true",
        help="omit temperature (some servers reject it)",
    )
    pf.set_defaults(fn=cmd_preflight)

    ml = sub.add_parser("models")
    ml.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    ml.add_argument("--api-key-env", default="OPENROUTER_API_KEY")
    ml.add_argument("--grep", help="substring filter on the model id, e.g. 'llama'")
    ml.add_argument("--limit", type=int, default=40)
    ml.set_defaults(fn=cmd_models)

    cp = sub.add_parser("compare")
    cp.add_argument("results", nargs="+", help="[label=]path/to/results ...")
    cp.set_defaults(fn=cmd_compare)

    sub.add_parser("smoke").set_defaults(fn=cmd_smoke)

    args = p.parse_args(argv)
    loaded = load_local_env(override=args.override_env)
    if loaded:
        print(f"[env] loaded {', '.join(loaded)} from .env.local")
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
