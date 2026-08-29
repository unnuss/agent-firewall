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
    ("overreach_rate", "**OR** — overreach rate (AF-Auth, low authority)"),
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
