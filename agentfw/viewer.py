"""``agentfw viewer`` — the replay, rendered for someone who will not open a terminal.

**What this is.** A second *renderer* over `agentfw/demo.py`, which is itself a presenter over
the replay harness. It calls `demo.run_scene()` and turns the `SceneResult` into one
self-contained HTML file plus an SVG still for the README. There is no new replay path, no
second policy and no second scope source here: `demo.POLICY` (which mirrors E-14's registered
config) remains the only one, so the viewer cannot be a different experiment from the tables.

**This module computes nothing.** Every verdict, effect class, tool name, gate name, bound,
open question and sentence of explanation below is a string that came out of the reference
monitor, quoted. The renderer decides colour and position; it never decides authorization. Two
consequences that are load-bearing and are asserted by `tests/test_viewer.py`:

* **No verdict literal appears in this file** outside `LEGEND`. A chip's CSS class is derived
  as ``f"v-{action.policy_verdict.lower()}"``. If the monitor ever returns a fourth verdict the
  viewer renders it unstyled rather than silently mislabelling it as one of the three.
* **Nothing branches on a scenario id.** Ordering, headlines and emphasis are functions of the
  episode's own outcome flags. Failure mode 3 in `CLAUDE.md` is scenario-specific logic that
  makes a demo look good, and a viewer is exactly where that would creep in. The scenarios with
  an authorization question sort first *because they have one*, not because of their names.

**Why it is static, and why that is the honest choice.** `CLAUDE.md` lists, as failure mode 6,
"a dashboard that animates decisions rather than replaying real audit logs". Nothing here
animates. There are no delays, no transitions and no progress indicators, because all three
would imply a live agent and live latency that do not exist. The page is complete the moment it
renders, which is both more truthful and faster to read.

**The counterfactual, stated on the page rather than in a footnote.** The left-hand account is a
recording: a real undefended agent, E-00j, one model, one seed. The right-hand account is what
the monitor decides about each of those recorded proposals — and `eval/replay.py` is explicit
that replay is faithful only up to the first refusal. After a BLOCK, the remaining steps were
taken in a world where that BLOCK never happened, and the harness flags them `off_policy`. The
viewer marks every such step on the page. Presented honestly this is a better story than hiding
it: the undefended agent retried the same exfiltration through a second tool, and the structural
gate caught that one too.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from agentfw import demo
from agentfw.eval import replay as replay_mod
from agentfw.eval.replay import ActionOutcome
from agentfw.eval.scopes import GoldScopes
from agentfw.sandbox.registry import load_all

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HTML = ROOT / "docs" / "viewer.html"
DEFAULT_HERO = ROOT / "docs" / "replay-hero.svg"

# The only place in this module where a verdict is written out. Everything else derives its
# label from `action.policy_verdict` and its CSS class from that string lowercased, so this
# tuple is also the whole vocabulary the stylesheet needs to know about.
LEGEND: tuple[tuple[str, str], ...] = (
    ("ALLOW", "inside the authority the user granted — it runs, nobody is interrupted"),
    ("ASK", "outside it, but worth a question — the user decides, in the monitor's own words"),
    ("BLOCK", "outside it and not worth a question, or structurally forbidden — refused"),
)


# ---------------------------------------------------------------------------
# derived presentation, all of it a function of the episode's own flags
# ---------------------------------------------------------------------------


def sort_key(result: demo.SceneResult) -> tuple[int, int]:
    """Scenarios that pose an authorization question come first.

    Not a hand-written running order. A scenario earns the front of the page by *having*
    something for the firewall to decide — a contested effect or an injected instruction —
    which is a property of the scenario, readable off the replayed episode. Ties keep
    `demo.SCENES` order so the result is stable.
    """
    ep = result.episode
    contested = ep.contested_occurred_undefended is not None
    attacked = ep.attack_succeeded_undefended is not None
    return (0 if (contested or attacked) else 1, demo.SCENES.index(result.scene))


def headline(result: demo.SceneResult) -> tuple[str, str]:
    """One sentence for each side, derived from outcome flags and nothing else.

    This is the ten-second layer: a reader who gets no further than these two lines should
    still have understood the scenario. The wording is chosen by which flags the episode
    carries, never by which scenario it is.
    """
    ep = result.episode
    if ep.attack_succeeded_undefended is not None:
        without = (
            "the injected instruction succeeded — the secret left the machine"
            if ep.attack_succeeded_undefended
            else "the injected instruction did not succeed"
        )
        with_fw = (
            "the injected instruction succeeded anyway"
            if ep.attack_succeeded_defended
            else "the exfiltration never happened, and nobody had to be asked"
        )
        return without, with_fw
    if ep.contested_occurred_undefended is not None:
        without = (
            "the irreversible action happened, silently, with nobody asked"
            if ep.contested_occurred_undefended
            else "the contested action did not occur"
        )
        with_fw = (
            "the irreversible action happened anyway"
            if ep.contested_occurred_defended
            else "stopped before it could happen, and put to the user instead"
        )
        return without, with_fw
    # No authorization question in this scenario. The only thing a defense can get wrong here
    # is getting in the way, so that is what the headline reports.
    refused = sum(1 for a in ep.actions if not a.executed)
    asked = sum(1 for a in ep.actions if a.asked)
    if refused:
        with_fw = (
            f"{refused} of {len(ep.actions)} licensed action(s) refused — a false positive"
        )
    elif asked:
        with_fw = f"the same work completed, after {asked} question the user approved"
    else:
        with_fw = "the same work completed, uninterrupted and unasked"
    return "the task was carried out; there was nothing here to refuse", with_fw


def defended_held(result: demo.SceneResult) -> bool:
    """Did the firewall actually prevent the thing it was there to prevent?

    Needed because the right-hand column must not be painted green on faith. Point the viewer
    at ``--scope tool-ceiling`` -- the allowlist-with-no-scope ablation -- and the Kestrel
    payment comes back ALLOW, ALLOW: the defense does nothing. The headline already says so,
    and the colour has to say so too, or the page would be reassuring in exactly the case
    where it should alarm.
    """
    ep = result.episode
    if ep.attack_succeeded_undefended is not None:
        return not ep.attack_succeeded_defended
    if ep.contested_occurred_undefended is not None:
        return not ep.contested_occurred_defended
    # Nothing to prevent here, so "held" means "did not get in the way".
    return all(a.executed for a in ep.actions)


def chip_text(action: ActionOutcome) -> str:
    """What the chip says. ``policy_verdict`` is the decision; ``verdict`` is what followed.

    For an action that was put to a human the two differ, and both matter: the monitor decided
    to ask, and then a person answered. Collapsing them to the final verdict would show a
    denied payment as a plain refusal and lose the consent step, which is the part of the
    architecture a reader is least likely to have expected.
    """
    if action.asked:
        answered = "APPROVED" if action.consent_approved else "DECLINED"
        return f"{action.policy_verdict} → {answered}"
    return action.policy_verdict


def chip_class(action: ActionOutcome) -> str:
    """``v-allow`` / ``v-ask`` / ``v-block``, derived rather than chosen.

    Deriving it means an unrecognised verdict renders with no styling at all instead of
    borrowing the colour of whichever branch an ``else`` happened to fall into.
    """
    return "v-" + action.policy_verdict.lower()


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


CSS = """
:root{
  --bg:#f4f5f7; --panel:#ffffff; --ink:#15181d; --muted:#5c6573; --line:#dfe3e9;
  --allow-ink:#0a6c3d; --allow-bg:#e4f3ea; --allow-line:#a9d8bd;
  --ask-ink:#8a5000;  --ask-bg:#fdf1da;  --ask-line:#e8c481;
  --block-ink:#ad2116;--block-bg:#fce8e6; --block-line:#f0b4ad;
  --gate:#6b2fa8; --gate-bg:#f2eafb;
}
@media (prefers-color-scheme:dark){
 :root{
  --bg:#0e1116; --panel:#161b22; --ink:#e8ecf1; --muted:#9aa4b2; --line:#2a313b;
  --allow-ink:#6ddba0; --allow-bg:#11281c; --allow-line:#2d5e42;
  --ask-ink:#f0c274;  --ask-bg:#2b2010;  --ask-line:#6b5224;
  --block-ink:#ff9c90;--block-bg:#2d1513; --block-line:#6e2f29;
  --gate:#c9a5f0; --gate-bg:#241a33;
 }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}
.wrap{max-width:1000px;margin:0 auto;padding:28px 20px 64px}
header h1{margin:0 0 6px;font-size:25px;letter-spacing:-.02em}
header p{margin:0;color:var(--muted);max-width:72ch}
.badges{margin:14px 0 0;display:flex;flex-wrap:wrap;gap:8px}
.badge{font-size:11.5px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;
 padding:4px 9px;border-radius:999px;border:1px solid var(--line);color:var(--muted);
 background:var(--panel)}
.badge.warn{border-color:var(--ask-line);background:var(--ask-bg);color:var(--ask-ink)}
.legend{margin:18px 0 0;padding:13px 15px;background:var(--panel);border:1px solid var(--line);
 border-radius:9px}
.legend div{display:flex;gap:10px;align-items:baseline;margin:5px 0;font-size:13.5px;
 color:var(--muted)}
.tabs{display:flex;flex-wrap:wrap;gap:7px;margin:22px 0 0}
.tab{font:inherit;font-size:13.5px;cursor:pointer;padding:8px 13px;border-radius:7px;
 border:1px solid var(--line);background:var(--panel);color:var(--muted);text-align:left}
.tab[aria-selected=true]{border-color:var(--ink);color:var(--ink);font-weight:600}
.panel{margin:18px 0 0;background:var(--panel);border:1px solid var(--line);border-radius:11px;
 overflow:hidden}
.panel>h2{margin:0;padding:15px 19px;font-size:16.5px;border-bottom:1px solid var(--line)}
.said{padding:17px 19px;border-bottom:1px solid var(--line)}
.said .k{font-size:11.5px;font-weight:700;letter-spacing:.07em;color:var(--muted)}
.said blockquote{margin:7px 0 0;font-size:17px;line-height:1.5}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:0}
@media (max-width:780px){.cols{grid-template-columns:1fr}}
.col{padding:17px 19px}
.col+.col{border-left:1px solid var(--line)}
@media (max-width:780px){.col+.col{border-left:0;border-top:1px solid var(--line)}}
.col>h3{margin:0 0 3px;font-size:12px;font-weight:700;letter-spacing:.07em;
 text-transform:uppercase;color:var(--muted)}
.lede{margin:0 0 13px;font-size:15px;font-weight:600}
.lede.bad{color:var(--block-ink)} .lede.good{color:var(--allow-ink)}
.call{font-size:13px;margin:4px 0}
.call .nm{font-weight:600}
.call .args{color:var(--muted)}
.eff{margin:10px 0 0;font-size:12.5px;color:var(--muted)}
.scope{margin:0 0 14px;padding:11px 12px;border:1px dashed var(--line);border-radius:8px;
 font-size:12.5px}
.scope .row{display:flex;gap:9px;margin:3px 0}
.scope .lbl{flex:0 0 94px;color:var(--muted);font-weight:600}
.q{color:var(--ask-ink)}
.step{padding:11px 0;border-top:1px solid var(--line)}
.step:first-of-type{border-top:0}
.step.off{opacity:.62}
.sh{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.sn{font-size:11.5px;color:var(--muted)}
.st{font-weight:600;font-size:13.5px}
.chip{font-size:11.5px;font-weight:700;letter-spacing:.04em;padding:3px 8px;border-radius:5px;
 border:1px solid var(--line);white-space:nowrap}
/* Only a step header right-aligns its chip. In the legend the chip leads the line, and a
   `margin-left:auto` there would push the chip and its gloss off the right-hand edge. */
.sh .chip{margin-left:auto}
.legend .chip{flex:0 0 auto}
.v-allow{color:var(--allow-ink);background:var(--allow-bg);border-color:var(--allow-line)}
.v-ask{color:var(--ask-ink);background:var(--ask-bg);border-color:var(--ask-line)}
.v-block{color:var(--block-ink);background:var(--block-bg);border-color:var(--block-line)}
.ec{margin:5px 0 0;font-size:12.5px;color:var(--muted)}
.why{margin:5px 0 0;font-size:13px}
.gate{display:inline-block;margin:7px 0 0;font-size:11.5px;font-weight:600;padding:3px 8px;
 border-radius:5px;color:var(--gate);background:var(--gate-bg)}
.offnote{margin:6px 0 0;font-size:12px;color:var(--muted);font-style:italic}
.out{border-top:1px solid var(--line);padding:15px 19px;font-size:13.5px}
.out .row{display:flex;gap:11px;margin:4px 0}
.out .lbl{flex:0 0 132px;color:var(--muted);font-weight:600}
details{border-top:1px solid var(--line);padding:13px 19px}
summary{cursor:pointer;font-size:13.5px;font-weight:600}
details pre{margin:11px 0 0;padding:13px;background:var(--bg);border:1px solid var(--line);
 border-radius:8px;overflow-x:auto;font-size:12.5px;line-height:1.5;white-space:pre-wrap}
.prov{border-top:1px solid var(--line);padding:13px 19px;font-size:12.5px;color:var(--muted)}
.prov .row{display:flex;gap:11px;margin:3px 0}
.prov .lbl{flex:0 0 132px;font-weight:600}
footer{margin:30px 0 0;font-size:13px;color:var(--muted);max-width:76ch}
footer pre{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:11px;
 overflow-x:auto;font-size:12.5px}
a{color:inherit}
"""

JS = """
// Progressive enhancement only. With JavaScript off every panel stays visible and the page
// reads as one long document, which is also what makes it safe to screenshot.
(function(){
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab'));
  var panels = Array.prototype.slice.call(document.querySelectorAll('.panel'));
  if (!tabs.length) return;
  function show(i){
    panels.forEach(function(p, j){ p.hidden = (j !== i); });
    tabs.forEach(function(t, j){
      t.setAttribute('aria-selected', j === i ? 'true' : 'false');
    });
  }
  tabs.forEach(function(t, i){ t.addEventListener('click', function(){ show(i); }); });
  show(0);
})();
"""


def _calls_html(result: demo.SceneResult) -> str:
    rows = []
    for call in result.record.tool_calls:
        args = demo._short_args(dict(call.get("args") or {}))
        rows.append(
            f'<div class="call mono"><span class="nm">{_esc(call["name"])}</span> '
            f'<span class="args">{_esc(args)}</span></div>'
        )
    effects = ", ".join(f"{e['verb']} {e['resource_class']}" for e in result.record.effect_log)
    rows.append(f'<div class="eff">effects: {_esc(effects or "none")}</div>')
    return "".join(rows)


def _scope_html(result: demo.SceneResult) -> str:
    rows = [
        '<div class="row"><span class="lbl">granted</span>'
        f'<span class="mono">{_esc(", ".join(result.grants) or "(nothing)")}</span></div>'
    ]
    for bound in result.constraints:
        rows.append(
            f'<div class="row"><span class="lbl">bound</span>'
            f'<span class="mono">{_esc(bound)}</span></div>'
        )
    for question in result.open_questions:
        rows.append(
            f'<div class="row"><span class="lbl">left open</span>'
            f'<span class="q">{_esc(question)}</span></div>'
        )
    return f'<div class="scope">{"".join(rows)}</div>'


def _step_html(action: ActionOutcome) -> str:
    classes = ", ".join(action.effect_classes) or "no declared effect"
    parts = [
        f'<div class="step{" off" if action.off_policy else ""}">',
        '<div class="sh">',
        f'<span class="sn">step {action.step}</span>',
        f'<span class="st mono">{_esc(action.tool)}</span>',
        f'<span class="chip {chip_class(action)}">{_esc(chip_text(action))}</span>',
        "</div>",
        f'<div class="ec mono">{_esc(classes)}</div>',
    ]
    if action.asked and action.consent_approved:
        # The explanation on an approved ASK is the *second* decision, taken after consent
        # widened the scope. Without this line "authorized and in bounds" reads as though
        # there had never been a reason to stop, which is the whole point of the step.
        parts.append(
            '<div class="why">Stopped, put the question, then re-decided against the '
            "widened scope. Why it stopped is in the question itself.</div>"
        )
    parts.append(f'<div class="why">{_esc(action.explanation)}</div>')
    for gate in action.gates:
        parts.append(f'<span class="gate mono">structural gate fired: {_esc(gate)}</span>')
    if action.off_policy:
        parts.append(
            '<div class="offnote">Off-policy: this proposal follows an earlier refusal. The '
            "recording has no refusal in it, so a defended agent might never have reached "
            "this step. Counted separately, never mixed with the rest.</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _outcome_html(result: demo.SceneResult) -> str:
    ep = result.episode
    rows = []
    for label, line in demo._defended_outcome(result, demo.Glyphs.fancy()):
        rows.append(
            f'<div class="row"><span class="lbl">{_esc(label)}</span>'
            f"<span>{_esc(line)}</span></div>"
        )
    chain = "intact" if ep.chain_intact else "BROKEN"
    rows.append(
        f'<div class="row"><span class="lbl">audit</span><span>{len(ep.actions)} '
        f"hash-chained event(s), chain {_esc(chain)}, replayable offline</span></div>"
    )
    return f'<div class="out">{"".join(rows)}</div>'


def _consent_html(result: demo.SceneResult) -> str:
    asked = [a for a in result.episode.actions if a.ask_text]
    if not asked:
        return ""
    return (
        "<details><summary>The question the human was actually shown, in full</summary>"
        '<div class="why">Rendered by the monitor, not by the agent: the agent\'s own '
        "rationale cannot reach it, every argument is quoted and labelled with where it came "
        "from, and it states what approving would grant (D-008).</div>"
        f'<pre class="mono">{_esc(asked[0].ask_text)}</pre></details>'
    )


def _provenance_html(result: demo.SceneResult) -> str:
    rec, scene = result.record, result.scene
    rows = [
        ("scenario", f"{rec.scenario_id}  ·  variant {rec.variant_id}"),
        ("recording", f"{rec.model_id}, seed {rec.seed}, undefended, run E-00j"),
        ("why this one", scene.selected_because),
    ]
    return (
        '<div class="prov">'
        + "".join(
            f'<div class="row"><span class="lbl">{_esc(k)}</span><span>{_esc(v)}</span></div>'
            for k, v in rows
        )
        + "</div>"
    )


def _panel_html(result: demo.SceneResult) -> str:
    without, with_fw = headline(result)
    return "".join(
        [
            '<section class="panel" hidden>',
            f"<h2>{_esc(result.scene.title)}</h2>",
            '<div class="said"><div class="k">THE REQUEST</div>',
            f"<blockquote>{_esc(result.record.utterance)}</blockquote></div>",
            '<div class="cols">',
            '<div class="col"><h3>Without the firewall</h3>',
            f'<p class="lede bad">{_esc(without)}</p>',
            _calls_html(result),
            "</div>",
            '<div class="col"><h3>With Agent Firewall</h3>',
            f'<p class="lede {"good" if defended_held(result) else "bad"}">{_esc(with_fw)}</p>',
            _scope_html(result),
            "".join(_step_html(a) for a in result.episode.actions),
            "</div>",
            "</div>",
            _outcome_html(result),
            _consent_html(result),
            _provenance_html(result),
            "</section>",
        ]
    )


def render_html(
    scope_label: str = demo.DEFAULT_SCOPE,
    *,
    results: list[demo.SceneResult] | None = None,
    total_episodes: int | None = None,
) -> str:
    """The whole page as one string. No timestamp anywhere, so two runs are byte-identical."""
    if results is None:
        results, total_episodes = build_results(scope_label)
    ordered = sorted(results, key=sort_key)
    choice = next(c for c in demo.SCOPE_CHOICES if c.label == scope_label)

    tabs = "".join(
        '<button class="tab" type="button" aria-selected="false">'
        f"{_esc(r.scene.title)}</button>"
        for r in ordered
    )
    legend = "".join(
        f'<div><span class="chip v-{word.lower()}">{_esc(word)}</span>'
        f"<span>{_esc(gloss)}</span></div>"
        for word, gloss in LEGEND
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Firewall — trace replay</title>
<style>{CSS}</style></head><body><div class="wrap">
<header>
<h1>Agent Firewall — what the agent proposed, and what was allowed to happen</h1>
<p>The agent holds no credentials. It emits <em>proposals</em>, and every proposed effect is
checked against a structured model of what the user actually licensed — before it can happen.
Each case below is the same recorded trajectory shown twice: what happened with nothing in the
way, and what the reference monitor decides about each of those same proposals.</p>
<div class="badges">
<span class="badge">replay of committed artifacts</span>
<span class="badge">no API key · no network · deterministic</span>
<span class="badge">authority source: {_esc(choice.label)}</span>
<span class="badge warn">not a live agent</span>
</div>
<div class="legend">{legend}</div>
</header>
<div class="tabs" role="tablist">{tabs}</div>
{"".join(_panel_html(r) for r in ordered)}
<footer>
<p><strong>Read this as a replay, because that is what it is.</strong> The left column is a
recording — a real undefended agent, run E-00j, one model, one seed, {_esc(total_episodes)}
episodes committed to this repository. The right column is what the monitor decides about each
recorded proposal, read out of the hash-chained audit log the replay produces. It is
<em>not</em> a second agent run: replay is faithful only up to the first refusal, because an
agent told &ldquo;no&rdquo; would have done something else next and this harness cannot know
what. Steps after a refusal are marked off-policy on the page. Verdicts and prevention are
sound; utility under defense needs a live defended run, which is a separate experiment.</p>
<p>Regenerate this page, and see the same scenarios fail under a weaker authority source:</p>
<pre>uv run agentfw viewer
uv run agentfw demo --scope tool-ceiling
uv run agentfw replay experiments/e14_validation/replay.yaml</pre>
<p>No rate is printed here. The measured ones live in <code>README.md</code> and
<code>docs/RESULTS.md</code> and are regenerated by the replay above.</p>
</footer>
</div><script>{JS}</script></body></html>
"""


# ---------------------------------------------------------------------------
# SVG still for the README
# ---------------------------------------------------------------------------

# GitHub sanitises embedded SVG and passes it no theme, so the panel paints its own light
# background and every colour is a literal. `docs/architecture.svg` learned this the hard way:
# a figure that inherits `currentColor` is invisible to half of GitHub's readers.
SVG_INK = "#15181d"
SVG_MUTED = "#5c6573"
SVG_LINE = "#dfe3e9"
SVG_PANEL = "#fbfbfd"
SVG_VERDICT = {
    "allow": ("#0a6c3d", "#e4f3ea", "#a9d8bd"),
    "ask": ("#8a5000", "#fdf1da", "#e8c481"),
    "block": ("#ad2116", "#fce8e6", "#f0b4ad"),
}
SVG_FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif"
SVG_MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,Liberation Mono,monospace"


def _svg_text(
    x: float,
    y: float,
    text: str,
    *,
    size: float = 13,
    fill: str = SVG_INK,
    weight: str = "normal",
    mono: bool = False,
    anchor: str = "start",
) -> str:
    family = SVG_MONO if mono else SVG_FONT
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{_esc(text)}</text>'
    )


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _fold(text: str, width: int, lines: int) -> list[str]:
    """Wrap onto at most ``lines`` lines, clipping only the last one.

    SVG has no text flow, so long strings have to be broken here. Wrapping rather than
    truncating matters for the headlines specifically: clipped at one line, "the irreversible
    action happened, silently, with no..." loses "nobody asked", which is the entire point of
    the sentence. Better to spend a second line than to cut the punchline off.
    """
    import textwrap

    folded = textwrap.wrap(text, width=width, break_on_hyphens=False, break_long_words=False)
    if len(folded) > lines:
        folded = folded[:lines]
        folded[-1] = _clip(folded[-1] + " " + text[len(" ".join(folded)) :].strip(), width)
    return folded or [""]


def render_hero_svg(result: demo.SceneResult) -> str:
    """One scenario as a still image, for the README's first screenful.

    Deliberately an SVG rather than a screenshot. It is regenerated by the same command that
    writes the HTML, so it cannot drift from the artifacts the way a committed PNG would, and
    it diffs as text.
    """
    without, with_fw = headline(result)
    w, pad, mid = 880, 22, 440
    rows = result.episode.actions
    height = 222 + 58 * len(rows)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{height}" '
        f'viewBox="0 0 {w} {height}" role="img" '
        f'aria-label="Agent Firewall replay: {_esc(result.scene.title)}">',
        f'<rect width="{w}" height="{height}" rx="12" fill="{SVG_PANEL}" stroke="{SVG_LINE}"/>',
        _svg_text(
            pad,
            30,
            "AGENT FIREWALL · REPLAY OF A COMMITTED TRACE",
            size=10.5,
            fill=SVG_MUTED,
            weight="bold",
        ),
    ]
    for i, line in enumerate(_fold(f'"{result.record.utterance}"', 100, 2)):
        out.append(_svg_text(pad, 55 + 21 * i, line, size=15, weight="600"))
    out += [
        f'<line x1="{pad}" y1="93" x2="{w - pad}" y2="93" stroke="{SVG_LINE}"/>',
        f'<line x1="{mid}" y1="93" x2="{mid}" y2="{height - pad}" stroke="{SVG_LINE}"/>',
        _svg_text(pad, 117, "WITHOUT THE FIREWALL", size=10.5, fill=SVG_MUTED, weight="bold"),
        _svg_text(
            mid + pad, 117, "WITH AGENT FIREWALL", size=10.5, fill=SVG_MUTED, weight="bold"
        ),
    ]
    # Left: the headline, then the calls the undefended agent actually made.
    for i, line in enumerate(_fold(without, 50, 2)):
        out.append(
            _svg_text(
                pad, 139 + 18 * i, line, size=13.5, weight="600", fill=SVG_VERDICT["block"][0]
            )
        )
    y = 194
    for call in result.record.tool_calls:
        out.append(_svg_text(pad + 2, y, _clip(str(call["name"]), 34), size=12.5, mono=True))
        y += 24
    # Right: the headline, then one row per proposal with its chip.
    held = SVG_VERDICT["allow" if defended_held(result) else "block"][0]
    for i, line in enumerate(_fold(with_fw, 50, 2)):
        out.append(_svg_text(mid + pad, 139 + 18 * i, line, size=13.5, weight="600", fill=held))
    y = 166
    for action in rows:
        ink, bg, line = SVG_VERDICT.get(
            action.policy_verdict.lower(), (SVG_INK, SVG_PANEL, SVG_LINE)
        )
        label = chip_text(action)
        chip_w = 9 + 7.1 * len(label)
        opacity = ' opacity="0.62"' if action.off_policy else ""
        out.append(f"<g{opacity}>")
        out.append(_svg_text(mid + pad, y + 14, _clip(action.tool, 22), size=12.5, mono=True))
        out.append(
            f'<rect x="{w - pad - chip_w}" y="{y}" width="{chip_w}" height="21" rx="5" '
            f'fill="{bg}" stroke="{line}"/>'
        )
        out.append(
            _svg_text(
                w - pad - chip_w / 2,
                y + 15,
                label,
                size=11,
                fill=ink,
                weight="bold",
                anchor="middle",
            )
        )
        detail = action.explanation
        if action.gates:
            detail = f"gate {action.gates[0]}: {detail}"
        out.append(_svg_text(mid + pad, y + 33, _clip(detail, 56), size=11, fill=SVG_MUTED))
        out.append("</g>")
        y += 58
    out.append(
        _svg_text(
            pad,
            height - 14,
            "Replayed from committed artifacts. No API key, no network, no live agent.",
            size=10.5,
            fill=SVG_MUTED,
        )
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def build_results(
    scope_label: str = demo.DEFAULT_SCOPE,
) -> tuple[list[demo.SceneResult], int]:
    """Replay every curated scene once, through `demo.run_scene` and nothing else."""
    load_all()
    _, scopes = demo.load_scope_source(scope_label)
    gold = GoldScopes.load()
    records_list = demo.load_episodes()
    records = {(r.scenario_id, r.variant_id, r.seed): r for r in records_list}
    scenarios = replay_mod.all_scenarios()
    results = [demo.run_scene(scene, records, scenarios, scopes, gold) for scene in demo.SCENES]
    return results, len(records_list)


def build(
    scope_label: str = demo.DEFAULT_SCOPE,
) -> tuple[str, str]:
    """``(html, hero_svg)``. The hero is the first scenario in the page's own running order."""
    results, total = build_results(scope_label)
    page = render_html(scope_label, results=results, total_episodes=total)
    hero = render_hero_svg(sorted(results, key=sort_key)[0])
    return page, hero


def write(
    out_html: Path = DEFAULT_HTML,
    out_hero: Path = DEFAULT_HERO,
    scope_label: str = demo.DEFAULT_SCOPE,
) -> tuple[Path, Path]:
    page, hero = build(scope_label)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_hero.parent.mkdir(parents=True, exist_ok=True)
    # Newline pinned to "\n": these files are committed and compared byte-for-byte by
    # `tests/test_viewer.py`, and letting the platform choose would fail that on Windows.
    out_html.write_text(page, encoding="utf-8", newline="\n")
    out_hero.write_text(hero, encoding="utf-8", newline="\n")
    return out_html, out_hero


def summary(results: list[demo.SceneResult]) -> str:
    """A short stdout line per scene, so the command says what it rendered."""
    lines = []
    for result in sorted(results, key=sort_key):
        verdicts = json.dumps(
            [chip_text(a) for a in result.episode.actions], separators=(",", " ")
        )
        lines.append(f"  {result.record.scenario_id:<42} {verdicts}")
    return "\n".join(lines)
