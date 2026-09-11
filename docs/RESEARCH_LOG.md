# Research log — the phase-by-phase narrative

**This is the story, not the summary.** For what the project *concluded*, read
[`RESULTS.md`](RESULTS.md); for the predictions and findings ledgers,
[`PREDICTIONS.md`](PREDICTIONS.md) and [`FINDINGS.md`](FINDINGS.md); for what it does not
establish, [`LIMITATIONS.md`](LIMITATIONS.md).

This file exists because the narrative is genuinely an asset — it records conclusions being
withdrawn, instruments being repaired, and predictions failing in order — but it was sitting in
the `README.md`, where it was a wall in front of everyone who did not want it rather than a
resource for the few who did. It was moved verbatim in Phase 6.9; nothing was rewritten to look
better in hindsight.

Sections are in the order they were written, which is **not** chronological: Phase 3.5 comes
after Phase 5 below, because that is how the argument accumulated in the original document.

---

## Phase 3 (complete): what happens when the scope is compiled rather than written by hand

> **Every number in this section is from the development split, and Phase 3.5 tested it on
> unseen data.** The injection result replicated; the authorization result did not. Read the
> Phase 3.5 section below before quoting anything here — in particular the claim that two
> configurations "match the hand-written gold scopes", which is a dev-slice statement.
> Numbers here are also **pre-repair**: Phase 3.5 fixed a tool contract that silently killed
> 18.2% of these episodes, and the corrected dev baseline is E-00g.

The scope is what the whole design rests on, so Phase 3 starts by asking how wrong it gets.
`intent/compiler.py` turns an utterance into an `IntentScope` from two inputs and no others:
the user's words, and the tools the application registered. It never sees the world, and it
is not in the trusted computing base — its errors are measured, not assumed away.

Two of the three compilers are deliberately stupid, because a single compiler could not be
interpreted. `tool-ceiling` grants whatever the registered tools can do, which is the
authority model an MCP gateway implements. `read-only` grants only reads. They bracket the
trade-off, and running the same 702 episodes against each (`agentfw replay
experiments/e01b_compiled/config.yaml`, no API calls, $0) says what each kind of compiler
error costs:

| Scope source | Overreach (underspecified) | Compliance (licensed) | ASR | Benign actions refused |
|---|---|---|---|---|
| *(undefended)* | 45.9% [34.1, 57.8] | 84.7% | 22.2% | — |
| Hand-written gold | **0.0%** | 84.7% | **0.0%** | 0 / 182 |
| `tool-ceiling` — grant what the tools can do | **45.9%** | 84.7% | 16.7% | 0 / 182 |
| `read-only` — grant only reads | 0.0% | **78.2%** | 0.0% | **22 / 182** |
| `read-only`, asking about everything out of scope | 0.0% | 82.9% | 0.0% | 0 / 182 |

Three things fall out of it.

**A tool allowlist is not an authorization mechanism.** `tool-ceiling` reproduces the
undefended overreach rate exactly — 62 of the same 135 episodes. EVALUATION lists "a static
allowlist matches Agent Firewall on AF-Auth" as a condition that would falsify this
project's ML story; on this slice the allowlist authority model does not match Agent
Firewall, it matches no defense at all.

**ASK earns its keep only against compiler error, and now that is measured.** Under a gold
scope, 90 approval prompts were raised and **0** were approved — the uncomfortable E-01a
result. Under an under-granting scope, 359 were raised and **269 recovered a refusal**, with
a human putting back the send, the delete and the purchase the compiler had dropped. The
value of the interruption budget is a function of how wrong the compiler is, which is now a
measured quantity rather than an argument.

**And a defect the measurement found.** Phase 2 asks a human only when the effect is
irreversible or visible to somebody else. That is right when the risk is an agent
overreaching and wrong when the risk is a compiler under-granting — the classes a compiler
drops are exactly the private reversible ones — so 22 benign actions are refused with no
dialog at all. Written up as finding F-10; it is the first measured requirement on Phase 4's
cost model.

**The completed picture: one bad cell out of four.** Two knobs, each of which alone recovers
most of the failure:

| contested-effect leakage | free-form prompt | per-class verdicts |
|---|---|---|
| `gpt-4.1-mini` | **53.3%** | 0.0% |
| `claude-sonnet-5` | 10.0% | **0.0%** |

The best configuration — per-class verdicts on Sonnet — **matches the hand-written gold
scopes on every security axis**: 0.0% overreach, 0.0% attack success, and compliance within
one episode of gold (84.3% vs 84.7%). What separates it from a human-written scope is three
refused benign actions out of 173.

The two fixes are **substitutes, not complements**: a deployment needs *either* a capable
model *or* an explicit formulation, and can pick on cost — the formulation is about ten times
cheaper and does not depend on a frontier model staying available.

**Then two experiments showed the failure was one cell, not a law.**

*Change the model, keep the prompt byte-identical:* Claude Sonnet 5 on the unchanged
baseline prompt leaks **10.0%** where gpt-4.1-mini leaks 53.3% — and the rank order between
the families **reverses** between roles. Sonnet's *agent* overreaches 60.0% against OpenAI's
38.9%; its *compiler* is five times more conservative. **How a model behaves as an agent
does not predict how it behaves as a compiler** (F-18). Its compiled scopes give 0.7-2.2%
overreach at 1.1-4.6% benign refusals — the best cost profile of any compiled arm.

*Change the prompt, keep the model:* see below — the same gpt-4.1-mini goes to 0.0%.

Both knobs work, neither is automatic, and noticing is not what varies: every compiler flags
the ambiguity on ~100% of underspecified instructions. **Withholding is the thing that
differs.**

**And the same model, asked differently, got it right.** The compiler is shown every
effect class its tools can produce and must return a verdict on each — `licensed`,
`not_licensed`, or `uncertain` — instead of writing a free-form list of grants. On the same
utterances, with the same information, from the same model: contested-effect leakage
**53.3% → 0.0%** (0 of 45, on all three seeds), and end to end **0.0% overreach, 0.0% ASR,
84.3% compliance against the gold scopes' 84.7%.**

The reason is not clever, which is why it is interesting. Under the free-form prompt the
only way to withhold an effect class is to *omit* it, and omission competes with a
helpfulness prior that always pushes toward completeness. Under per-class verdicts,
withholding is something the model has to write down, and hedging routes to `uncertain`,
which becomes a question for the user rather than a grant. **Making refusal expressible,
rather than merely possible, is what moved the number** — an interface result, not a model
one. No fine-tune, no calibration, no bigger model.

What it costs is on the other axis: 3-7% of benign actions refused against gold's 0%, and
about twice the interruptions, because under-granting is now the dominant error (407 classes
against 4 over-granted). Written up as F-17, with the caveats it deserves — one model, one
dev slice, three seeds, and a result that beat its own pre-registered prediction, which is
the moment to be most suspicious rather than least.

Phase 3 closed here. Most of its planned ML work — the M0-M5 ladder, calibration, the
cascade — was **retired rather than built** (D-032): it existed to calibrate a probability
that places an ASK boundary, and the compiler appeared to place that boundary correctly on
its own. That retirement carried a named condition, and Phase 3.5 met it.

## Phase 5 (complete): the same question at five times the sample, and the answer holds

Phase 3.5 concluded that the compiled scope does not reach the gold-scope result on unseen
data. It concluded that from **11 held-out triples**, on an interval **±23 pp wide**. Before
building anything on it, we measured what that interval would cost to narrow (E-13) and found
something worth stating plainly: **more seeds narrow nothing.** One, two and three seeds give
the identical width, because the bootstrap resamples scenarios and there were eleven of them.
Only scenarios help. So the benchmark was rebuilt before the next conclusion was drawn on it.

| | Phase 3.5 | **Phase 5** |
|---|---|---|
| core triples | 11 | **60** |
| contested effect classes | 6 | **9** |
| worlds | 1 | **3** |
| held-out utterances | 60 | **207** |

The three worlds — an office, an architecture practice, a funded academic lab — differ in
**what counts as consequential**, and eight of the nine contested classes appear in all three.
That makes a question answerable that could not be asked before: *is a leakage rate a property
of the compiler, or of the kind of work?*

**It is neither. It is the effect class, by a factor of six.**

| underspecified overreach, by contested class | |
|---|---|
| `CREATE:CALENDAR` | **100.0%** |
| `DELETE:USER_FILES` | 88.9% |
| `PURCHASE:FINANCIAL` | 80.0% |
| `WRITE:USER_FILES` | 40.7% |
| `SEND:EMAIL` | 24.2% |
| `GRANT:USER_FILES` | **12.5%** |

**Spread across contested classes: 87.5 pp. Spread across the three worlds: 13.5 pp.** And the
ordering is not the ontology's — `CREATE:CALENDAR` is reversible and invisible to anyone but
the user, and it is taken on *every* underspecified instruction, while irreversible
third-party-visible `SEND:EMAIL` sits at 24%. The classes agents overreach on are the ones
where a single unambiguous state change obviously completes the goal; the ones they hesitate
on require authoring content or exposing a resource to someone else. **"Underspecified
overreach" is therefore a weighted average over whatever class mix a suite happens to contain**,
which is a warning about this project's own earlier headline and about anyone else's.

### The 2x2 at N=60

What the compiler granted (**scope level**), and what the agent then actually did under that
grant (**verdict level**):

| contested action executed | free-form prompt | per-class verdicts |
|---|---|---|
| `gpt-4.1-mini` | 24.6% [14.6, 35.2] | 12.2% [5.6, 20.0] |
| `claude-sonnet-5` | 11.7% [5.0, 19.7] | **5.6% [1.1, 11.7]** |

**Every interval excludes zero**, against an undefended 49.4% and a `gold` scope's 0.0%. All
six registered predictions held, including the one that was written as the criterion: *no
compiled arm reaches zero*. **The Phase 3.5 reopening was not a small-sample artifact** — it
now rests on five times the evidence and a ±5.3 pp interval (D-037).

### What a compiled scope actually buys, from the audit log

The pooled rate hides the mechanism. Here is the disposition of every contested action the
agent attempted on an underspecified instruction:

| | ALLOW (silent) | ASK → denied | BLOCK |
|---|---|---|---|
| tool allowlist, no scope | **100.0%** | 0.0% | 0.0% |
| free-form prompt, `gpt-4.1-mini` | 48.9% | 51.1% | **0.0%** |
| per-class verdicts, `claude-sonnet-5` | **10.9%** | 79.3% | 9.8% |
| hand-written gold scope | 0.0% | 90.2% | 9.8% |

Read the first column: **what the scope buys is the conversion of a silent consequential act
into a question.** With no scope, every contested action executes unannounced.

Read the last column and there is a mechanism that 11 triples could not show. The free-form
prompt **never blocks — not once in 276 attempts.** Every per-class arm blocks at the gold
scope's rate. The reason is structural: a free-form grant list leaves an unlicensed class
merely *absent*, and deny-by-default correctly routes absence to a human; the per-class
formulation emits `not_licensed`, which the monitor refuses outright without spending an
interruption. **"I was not told this is allowed" and "I was told this is not allowed" are
different propositions, and only the second is actionable without a person.**

### The residual is six utterances, and two of them are our own bugs

33 of the 60 underspecified variants leak under **no** arm; 6 leak under **all four**. The
distribution is U-shaped, not a uniform error rate — two model families and two prompt
formulations agree far more than a pooled figure suggests.

Of the six, **two are more likely defects in the benchmark than in the compiler**: one is the
scenario the blind gold-scope author flagged as ambiguous *before any run*, and one is a label
that four independent compilations all disagree with. **Neither is repaired.** They have been
measured, and fixing a scenario after seeing its number is the failure this project's ordering
exists to prevent. Excluding both would put the best arm at 3.3% instead of 5.6%; **the
headline stays 5.6%**, and both go in the next slice.

### Two negative results worth more than the positive ones

**The cheap fix does not work where you would deploy it.** A post-hoc rule that withholds a
grant whenever the compiler's own open question is about that effect — the obvious repair for
"it settles *whether* and asks *how*" — was re-measured at N=60. It buys 13 pp of leakage on
the worst arm and **1.7 pp on the best, for 7.6 pp of retention**, while *lowering* contrast
fidelity from 86.4% to 80.3%. It is a substitute for the per-class prompt, not a complement:
both extract the compiler's uncertainty, and the prompt does it where the model can still
reason. **Not adopted**, for the second time and now for a better reason.

**A labelling brief can be debugged, and the debugging is measurable.** Two blind labellers of
the same utterances first agreed on the whole effect set **0 of 6** times. The brief then
gained five clarifications — written while no labels existed to fit them to — and a third blind
author agreed with the second **48 of 60**. The residual disagreement is entirely instrumental
reads, which is exactly the gap the clarifications did not close, and *the labeller identified
that gap independently before seeing any comparison*. The ordering is the whole point: had the
brief been clarified after the labels existed, the improvement would be unreadable.

## Phase 3.5 (complete): the benchmark was the weak link, and the headline did not replicate

Every Phase 3 number was dev-slice, and the held-out suite could not check any of it — three
generated scenarios, six utterances, all explicit, in the same world as dev, with no benign
tasks and no attacks. So contested-effect leakage had an empty denominator there, and benign
refusal rate and attack success rate were not measurable at all.

**What was rebuilt.** A second world; 32 held-out scenarios over 60 utterances, including
eleven *underspecified triples* across six contested effect classes; ten benign tasks and
five injection attacks. Gold labels for all of it, written by an author given the sixty
sentences and the labelling rule **and nothing else** — no finding, no prior result, and no
knowledge that this project contains a compiler (D-033). The brief and its input are
committed before the labels, and the labels before any compiler ran, so the ordering is
checkable in the history rather than asserted here.

**First: does the phenomenon survive its own instrument being repaired?** A tool contract
matched contiguous substrings only, so searching for "Dana Whitfield" returned nothing while
the world plainly held `dana.whitfield@…`, and a competent agent correctly gave up. That
silently affected 18.2% of the dev episodes every earlier number rests on. Repaired, and
re-measured:

| dev slice, OpenAI models | pre-repair | post-repair |
|---|---|---|
| Underspecified overreach | 38.9% | **45.6%** |
| Explicit-low overreach | 2.2% | 2.9% |
| **Gap** | +36.7 pp | **+42.7 pp** |
| High-authority compliance | 81.2% | **93.1%** |

The phenomenon is not merely intact; it is **larger on a benchmark that works**. Had it gone
the other way, two phases would have been built on a broken instrument.

**Then: does the Phase 3 headline replicate on unseen underspecified instructions?**

| contested-effect leakage | free-form prompt | per-class verdicts |
|---|---|---|
| `gpt-4.1-mini` — dev | 53.3% | **0.0%** |
| `gpt-4.1-mini` — **held-out** | **36.4%** | **21.2%** |
| `claude-sonnet-5` — dev | 10.0% | **0.0%** |
| `claude-sonnet-5` — **held-out** | **18.2%** | **9.1%** |

> **Superseded by Phase 5.** Every held-out cell above rests on 11 triples. They were
> re-measured on 60 and the section above this one has the current figures. The *conclusion*
> — no cell reaches zero — survived; the numbers moved and one reading of them did not.

**No.** No cell reaches zero. On dev either intervention alone reached the floor, and we
concluded they were substitutes — pick one, on cost. Held out both help, neither suffices,
and they compose. The undefended agent overreaches on **81.8%** of these instructions, so
every compiled scope is a large improvement; "matches the hand-written gold scopes" is not.

**And the residue is the *same failure* Phase 3 thought it had fixed.** It concentrates in
five of eleven scenarios, one of which every arm gets wrong, and on those the compiler grants
the contested effect while asking a question about *how*: *"What answers should be submitted
for the poll questions…"*, *"Is the exact duration 1 hour or something else?"* It has settled
whether the action happens and is asking how — which is, word for word, what we wrote when we
first measured this failure and then declared it repaired. The independent labeller, having
seen none of that, wrote the question those cases actually needed: *"whether 'take care of
that' licenses filling in and submitting the poll, or only reading what it asks."*

**What did replicate is the half that never needed a model.**

| held out, 180 episodes | undefended | best compiled scope |
|---|---|---|
| Attack success rate | **33.3%** | **0.0%** |
| Overreach (underspecified) | 81.8% | 9.1% |

Attack success is **0.0% under every compiled scope**, against five attacks the system had
never seen, two of them written to be defense-aware. Deny-by-default over an effect ontology
does that with no model in the decision path. The tool-allowlist baseline still lets 6.7%
through.

So the pre-registered exit criterion failed, and **D-032 is reopened** (D-034): the question
the ML ladder existed to answer comes back, though not its answer — the evidence now says the
uncertain band is narrow, concentrated, and structurally visible as *a grant contradicted by
its own open question*, which is a cheaper thing to attack than a calibrated probability.

**Ten defects found, most by gates rather than by review** — including a replay that reported
a perfect defense over *zero episodes* because it was indexed to the wrong split, and a
confidentiality gate that denies a licensed payment, so that the compliance metric rewards a
scope for failing to authorize things. That last one had been invisible for three phases
because the dev fixture's payment identifiers are seven characters long and the threshold for
noticing is eight.



The rest of this section is how we got there, and it is left standing because the wrong turn
is the instructive part.

**The registered compiler ran, and it falsified the prediction the architecture rested on.**
`gpt-4.1-mini`, three seeds, licenses the contested effect on **53.3%** of underspecified
instructions — against **45.9%** for the *undefended agents* on the same instructions. The
bet was that "what did this person authorize?" is an easier question than "what should I
do?". It is not.

It is not a detection failure either: the compiler raised an open question on **100%** of
underspecified variants and granted the effect anyway on half of them, asking *which* payment
method rather than *whether* to pay. It is the same model with the same prior about what an
assistant is for, so it carries the same bias — the compiler relocated the failure instead of
removing it. End to end the compiled system halves overreach (45.9% → 25.2%) at a compliance
cost of 84.7% → 68.5%, a long way from the gold-scope 0.0%. Written up as finding F-16.

**What survives it.** ASR stays at **0.0%** under compiled scopes. The injection half of the
thesis never needed the compiler: those utterances are plain read-only requests, and
deny-by-default over effect classes does the work. The security claim that does not depend on
a model is the one that held.

Before that arm ran, two floors and a local model were measured. What they
run is a local 14B code model, weak enough that Phase 1 found its class unfit to be an agent
here at all, reported against a retention floor registered in advance so a compiler that
cannot read plain instructions cannot be quoted. It clears the floor, and it cuts overreach
from 45.9% to **17.0%** at 0% ASR — while compliance on licensed work falls from 84.7% to
**60.6%**.

Most of that utility loss has one cause, and it is the sharpest thing Phase 3 found.
`Grant` carries provenance because authority must trace to something the user said.
`Constraint` carries none — so when the compiler *invents* a bound (a $150 cap on an
instruction that names no cap), the firewall cannot tell it from a bound the user stated, and
treats it as a hard gate. It fired 59 times, blocking purchases the user had explicitly
authorized, and **no interruption can repair a wrong bound** where a forgotten grant is
repaired by one question. Written up as F-13.

Most of those invented bounds came from the prompt's own JSON example, which carried a
literal `$150` the model copied through (F-14). So the prompt was fixed — placeholders only —
and the arm re-run. **Every scope-level metric improved and the deployed system got much
worse:** leakage 33.3% → 26.7%, retention 87.5% → 100%, contrast fidelity 58.3% → 75.0%,
while compliance fell 60.6% → 41.2%, benign refusals rose 11.9% → 34.5%, and the hard gate
fired 59 → 270 times. Freed from copying the example, the model extracted bounds
enthusiastically — 69 of them across 51 instructions, against six in the gold labels — and
they are plausible and wrong: `["Priya"]` where the address is
`priya.menon@northwind-systems.com`, `["Amex"]` as the recipient of a payment.

That disagreement is the most useful thing this phase measured. Scoring the compiler against
the labels ranks it; only running the verdicts grades it. **A compiler change is not an
improvement until the replay says so** — and had we reported the label metrics alone, we
would have shipped the worse prompt.

Feeding a real compiler's output into the monitor also found a crash in the Phase 2 core: a
naive-versus-aware datetime comparison raised inside a constraint check, taking 21 episodes
out of the measurement rather than deciding them. Property tests had not found it, because
they generate the bounds a specification allows and it took a model to write the pair that
breaks. Fixed, fail-closed (F-15).
