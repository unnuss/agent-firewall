"""Command line entry point.

agentfw validate                 # scenarios load, tools exist, declarations agree
agentfw generate                 # expand pair templates into the held-out suite
agentfw run experiments/e00_undefended/config.yaml
agentfw report experiments/e00_undefended/results
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
    client = OpenAIChatClient(
        args.model,
        base_url=args.base_url,
        api_key=args.api_key or "local",
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

    rep = sub.add_parser("report")
    rep.add_argument("results")
    rep.add_argument("--title", default="E-00 — undefended baseline")
    rep.set_defaults(fn=cmd_report)

    pf = sub.add_parser("preflight")
    pf.add_argument("--base-url", default="http://localhost:8000/v1")
    pf.add_argument("--model", required=True)
    pf.add_argument("--api-key")
    pf.add_argument("--max-tokens", type=int, default=256)
    pf.add_argument(
        "--no-temperature",
        action="store_true",
        help="omit temperature (some servers reject it)",
    )
    pf.set_defaults(fn=cmd_preflight)

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
