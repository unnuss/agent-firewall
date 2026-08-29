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

    sub.add_parser("smoke").set_defaults(fn=cmd_smoke)

    args = p.parse_args(argv)
    loaded = load_local_env(override=args.override_env)
    if loaded:
        print(f"[env] loaded {', '.join(loaded)} from .env.local")
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
