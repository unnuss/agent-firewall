"""Turn an episodes.jsonl into report.json and report.md.

CLAUDE.md requires every table in the README to be regenerable by one command; this is
that command's back end. Nothing here computes a number — it only formats what
``metrics.py`` produced, so a table and the JSON behind it cannot disagree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentfw.eval import metrics
from agentfw.eval.runner import EpisodeResult, load_results

HEADLINE_ORDER = [
    ("overreach_rate", "**OR** — overreach rate, episode level (AF-Auth, low authority)"),
    ("overreach_incidence", "**Incidence** — scenarios with >=1 overreach"),
    ("compliance_rate_high", "Compliance (AF-Auth, high authority)"),
    ("asr", "**ASR** — attack success rate (AF-Inject)"),
    ("btc_benign", "**BTC** — benign task completion"),
    ("btc_under_attack", "BTC under attack (AF-Inject side task)"),
    ("btc_auth_low", "BTC (AF-Auth, low-authority half)"),
    ("btc_auth_high", "BTC (AF-Auth, high-authority half)"),
    ("cup_auth", "CuP (AF-Auth, both halves)"),
]


def _fmt(entry: dict[str, Any]) -> str:
    if entry["n_episodes"] == 0:
        return "n/a"
    v, (lo, hi) = entry["value"], entry["ci95"]
    return f"{v * 100:.1f}% [{lo * 100:.1f}, {hi * 100:.1f}]"


def _n(entry: dict[str, Any]) -> str:
    return f"{entry['n_success']}/{entry['n_episodes']}"


def build(results: list[EpisodeResult]) -> dict[str, Any]:
    return {
        "n_episodes": len(results),
        "n_usable": len(metrics.usable(results)),
        "models": sorted({e.model_id for e in results}),
        "seeds": sorted({e.seed for e in results}),
        "scenarios": len({e.scenario_id for e in results}),
        "overall": metrics.compute(results),
        "by_model": metrics.by_model(results),
        "by_family": metrics.by_family(results),
        "by_scenario": metrics.by_scenario(results),
        "cost": metrics.cost_report(results),
        "errors": metrics.error_report(results),
    }


def to_markdown(rep: dict[str, Any], title: str = "E-00 — undefended baseline") -> str:
    models = rep["models"]
    lines: list[str] = [f"# {title}", ""]
    lines.append(
        f"{rep['n_usable']} usable episodes of {rep['n_episodes']} run · "
        f"{rep['scenarios']} scenarios · models: {', '.join(models)} · "
        f"seeds: {', '.join(str(s) for s in rep['seeds'])}"
    )
    lines += [
        "",
        "Intervals are percentile bootstrap 95% CIs, resampled over **scenarios** "
        "(not episodes), because repeats of the same scenario are correlated.",
        "",
        "## Headline",
        "",
        "| Metric | All models | " + " | ".join(models) + " |",
        "|---|---|" + "---|" * len(models),
    ]
    for key, label in HEADLINE_ORDER:
        row = [label, f"{_fmt(rep['overall'][key])} ({_n(rep['overall'][key])})"]
        for m in models:
            entry = rep["by_model"][m][key]
            row.append(f"{_fmt(entry)} ({_n(entry)})")
        lines.append("| " + " | ".join(row) + " |")

    ov = rep["overall"]
    if ov.get("by_specificity"):
        lines += [
            "",
            "## The ambiguity contrast (D-018)",
            "",
            "Same worlds, same contested effects, same authority level. The only thing that",
            "differs is whether the user's ask names the action.",
            "",
            "| Low-authority utterance | Episode-level OR | Scenario-level incidence |",
            "|---|---|---|",
        ]
        for spec in ("underspecified", "explicit"):
            e = ov["by_specificity"].get(spec)
            if e:
                lines.append(
                    f"| {spec} | {_fmt(e['episode_rate'])} ({_n(e['episode_rate'])}) | "
                    f"{_fmt(e['scenario_incidence'])} ({_n(e['scenario_incidence'])}) |"
                )
        con = ov.get("ambiguity_contrast", {})
        if con:
            lines += [
                "",
                f"Within the {con['n_scenarios_with_both_low_variants']} scenarios carrying "
                "both low-authority variants, the underspecified wording overreached at "
                f"{con['underspecified_rate'] * 100:.1f}% and the explicit wording at "
                f"{con['explicit_rate'] * 100:.1f}%.",
            ]
            flipped = con.get("scenarios_where_underspecified_overreached_and_explicit_did_not")
            if flipped:
                lines += [
                    "",
                    f"Scenarios where ambiguity alone flipped the outcome ({len(flipped)}):",
                    "",
                ]
                lines += [f"- `{f}`" for f in flipped]

    if ov.get("by_role"):
        lines += [
            "",
            "## Core versus control (D-018)",
            "",
            "Controls are the original explicit-escalation pairs, retained because their",
            "negative result is evidence: a defense must not take credit for a baseline",
            "that was already at zero.",
            "",
            "| Role | Episode-level OR | Scenario-level incidence |",
            "|---|---|---|",
        ]
        for role in ("core", "control"):
            e = ov["by_role"].get(role)
            if e:
                lines.append(
                    f"| {role} | {_fmt(e['episode_rate'])} ({_n(e['episode_rate'])}) | "
                    f"{_fmt(e['scenario_incidence'])} ({_n(e['scenario_incidence'])}) |"
                )

    unc = ov.get("uncertainty_check")
    if unc:
        c_lo, c_hi = unc["clustered_ci95"]
        n_lo, n_hi = unc["naive_iid_ci95"]
        lines += [
            "",
            "## Uncertainty accounting (D-018 point 6)",
            "",
            "- Reported interval, **clustered by scenario**: "
            f"[{c_lo * 100:.1f}, {c_hi * 100:.1f}]",
            f"- Naive episode-level iid interval: [{n_lo * 100:.1f}, {n_hi * 100:.1f}]",
            f"- Width ratio (design effect): **{unc['design_effect_width_ratio']:.2f}x**",
            "",
            "The naive figure is shown only for contrast and is never quoted as a result.",
            "Seeds and models within one scenario are not independent observations, so an",
            "episode-level bootstrap understates uncertainty by roughly that factor.",
        ]

    lines += ["", "## Overreach by sub-family (AF-Auth, low-authority half)", ""]
    lines += ["| Family | OR | n |", "|---|---|---|"]
    fam_names = {
        "B1": "B1 consequence escalation",
        "B2": "B2 constraint violation",
        "B3": "B3 scope creep",
        "B4": "B4 ambiguity",
        "B5": "B5 collateral effect",
    }
    for fam in sorted(rep["by_family"]):
        e = rep["by_family"][fam]
        lines.append(f"| {fam_names.get(fam, fam)} | {_fmt(e)} | {_n(e)} |")

    lines += ["", "## Per scenario (AF-Auth)", ""]
    lines += [
        "| Scenario | Fam | Overreach (low) | Compliance (high) | Task done low/high |",
        "|---|---|---|---|---|",
    ]
    for r in rep["by_scenario"]:
        lines.append(
            f"| `{r['scenario_id']}` | {r['family']} | {r['overreach']}/{r['n_low']} | "
            f"{r['compliance']}/{r['n_high']} | {r['task_low']}/{r['n_low']} · "
            f"{r['task_high']}/{r['n_high']} |"
        )

    lines += ["", "## Cost and latency", ""]
    lines += [
        "| Model | Episodes | Prompt tok | Completion tok | Tok/episode "
        "| Median latency | Median steps |",
        "|---|---|---|---|---|---|---|",
    ]
    for m, c in rep["cost"].items():
        lines.append(
            f"| {m} | {c['episodes']} | {c['prompt_tokens']:,} | "
            f"{c['completion_tokens']:,} | {c['tokens_per_episode']:,} | "
            f"{c['median_latency_s']:.1f}s | {c['median_steps']} |"
        )

    if rep["errors"]:
        lines += ["", "## Episode errors", ""]
        lines += ["| Error | Count |", "|---|---|"]
        for k, v in sorted(rep["errors"].items(), key=lambda kv: -kv[1]):
            lines.append(f"| `{k}` | {v} |")
    lines.append("")
    return "\n".join(lines)


def write(results_dir: Path, title: str = "E-00 — undefended baseline") -> dict[str, Any]:
    results = load_results(results_dir / "episodes.jsonl")
    rep = build(results)
    (results_dir / "report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    (results_dir / "report.md").write_text(to_markdown(rep, title), encoding="utf-8")
    return rep
