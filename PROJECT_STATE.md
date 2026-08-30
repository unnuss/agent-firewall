# PROJECT STATE

**Read this first.** It is the handoff document between development sessions.

**Last updated:** 2026-08-30 · **Phase 2 COMPLETE.** · **Next: Phase 3.**

---

## 0. If you are the Phase 3 session, do exactly this

1. Read `CLAUDE.md`, then this file, then **`docs/DECISIONS.md` D-022, D-023, D-024** —
   D-022 fixes what may be assumed from the Phase 1 evidence, D-023 fixes what E-01a's
   numbers do and do not mean, D-024 explains the one behavioural rule added by measurement.
2. Read **E-01a in `docs/EXPERIMENTS.md`**, and in particular the paragraph beginning "The
   finding that matters". It changes what Phase 3 should do first.
3. Skim findings **F-07, F-08, F-09** in `docs/EXPERIMENTS.md`. F-07 and F-09 both point at
   Phase 3 work.
4. Build Phase 3 per `docs/ROADMAP.md`. Start at section 6 of this document.

Health check (~5 s, no API calls, no keys needed):

```bash
.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m agentfw.cli validate
```

Expect **168 passed** and 24 AF-Auth / 6 AF-Inject / 18 benign scenarios, 23 tools.

E-01a reproduces in about 40 seconds, also with no key:

```bash
.venv/Scripts/python.exe -m agentfw.cli replay experiments/e01a_deterministic/config.yaml
```

---

## 1. Where the project is, in one paragraph

Phase 1 measured the problem and **changed the thesis**: agents respect explicit
authorization boundaries almost perfectly, and fail by inferring authority from silence —
38.9% on OpenAI models, 60.0% on Claude Sonnet 5 (D-022). Phase 2 built the deterministic
reference monitor that turns that inference into a decision point: effect mapping, scope
monotonicity, structural monitors, a hash-chained audit log, consent-integrity ASK
rendering, and P1–P4 as property tests. E-01a then measured the monitor on its own and
produced a result that **sharpens what Phase 3 has to prove**: given a correct scope, the
deterministic core removes all measured overreach at zero utility cost — and the ASK path
contributes nothing, because a correct scope leaves nothing to ask about. The value of
every ML component in this project is therefore bounded by how far a *compiled* scope
diverges from a gold one, and nobody has measured that yet.

## 2. Phase 2 deliverables, against the roadmap

| # | Deliverable | Status |
|---|---|---|
| 1 | `core/labels.py`, `core/effects.py`, `core/scope.py`, `core/audit.py` | done |
| 2 | Label propagation through the trace; the (tool, args) → Effect mapper | done |
| 3 | `IntentScope` with `expand_via_consent` as the only widening path | done, property-tested |
| 4 | `PolicyCombinator`: structural gates + a placeholder fixed rule | done |
| 5 | Consent-integrity ASK rendering (D-008); scripted reviewer oracle | done |
| 6 | Hash-chained audit log with offline replay | done |
| 7 | Property tests for P1–P4 (hypothesis) | done |
| 8 | **E-01a: deterministic-only evaluation** | done — see section 4 |

Two things were added that the roadmap did not ask for, both because measurement forced
them: **D-023** (gold scopes — Phase 2 has no scope source otherwise) and **D-024**
(remember a refused ASK — without it one scenario drained the interruption budget on
repeats of a question already answered).

## 3. What exists in code

```
agentfw/
  core/
    types.py       effect ontology, label lattices, TraceSpan, ProposedAction, Verdict
    labels.py      lattice ops, Destination classification, literal-evidence provenance
    effects.py     EffectMapper (fail-closed), consequential(), describe()
    scope.py       Constraint, Grant, Declassification, ConsentRecord, IntentScope
    audit.py       AuditEvent, sha256 chain, verify(), offline replay
  monitors/
    base.py        Signal with the structural flag — D-006 as a type
    integrity.py   the narrowed structural rule (see F-07)
    flow.py        the deterministic P3 declassification gate only
  policy/
    combinator.py  ordered BLOCK-only gates, then the placeholder rule
    ask.py         firewall-rendered ASK (P4) + ScriptedReviewer(epsilon)
  firewall.py      the Guard implementation; asserts P2 before every ALLOW
  eval/
    scopes.py      gold-scope loader; scopes_data/dev.yaml holds the labels
    replay.py      E-01a: recorded trajectories re-run behind the firewall
    replay_report.py
  sandbox/ agent/ eval/  (Phase 1, unchanged except two additions below)
```

Phase 1 code changed in exactly three places, each deliberate:

- **`ToolRouter.declare_for`** — a strict declarer that raises. `declare` swallowed
  exceptions and returned `[]`, which under deny-by-default authorizes vacuously. That was
  a fail-open path in the seam Phase 2 depends on. `declare` keeps its old behaviour for
  Phase 1 callers; the firewall uses `declare_for` and turns any failure into gate G0.
- **`run_episode(trace=...)`** — the caller may supply the Trace so a firewall installed in
  the router reads the same spans the loop writes. Provenance the monitor cannot see is
  provenance it cannot act on.
- **`Verdict` in `core/types.py`** — every layer mentions it.

Four things worth not re-deriving:

- **The ASK is resolved synchronously inside `Guard.check`.** The Phase 1 seam is
  two-valued and stays that way; ASK is a step on the way to one of the two answers, not a
  third thing the router understands. This is also how a real deployment behaves.
- **`policy_verdict` and `verdict` are different fields** in an audit event. The first is
  what the combinator decided from the recorded inputs and is what `replay` reproduces; the
  second is the outcome after a human answered, which is not a function of those inputs.
  Collapsing them makes the log either unreplayable or untrue.
- **The integrity monitor denies only at public destinations.** See F-07 — this is not
  timidity, it is the boundary of what labels can establish without a screener.
- **Refusals are remembered (D-024).** A refused effect class is not put to the user twice
  in one episode.

## 4. E-01a, and the finding Phase 3 has to act on

702 episodes replayed from E-00b and E-00f, 48 dev scenarios, three models, **no API calls
and no dollars**. Full write-up in `docs/EXPERIMENTS.md`.

| Slice | Undefended | Deterministic core |
|---|---|---|
| AF-Auth low, underspecified | 45.9% [34.1, 57.8] | **0.0%** |
| AF-Auth low, explicit | 1.4% [0.0, 4.3] | **0.0%** |
| AF-Auth high (licensed — must survive) | 84.7% [75.5, 92.6] | **84.7%**, unchanged |
| ASR (AF-Inject) | 22.2% [2.8, 44.4] | **0.0%** |
| Benign actions refused | — | **0 / 182** |
| Benign episodes interrupted | — | **0 / 108** |
| ASKs per episode (underspecified low) | — | 0.60 |

**Read the caveats before quoting any of this.** The scope is a hand-written gold label
(D-023), so this measures *enforcement given a correct scope*, not authorization reasoning.
And it is a replay: after an episode's first refusal the trajectory is off-policy, so BTC
and CuP under defense are **not measurable** and are not reported.

**The uncomfortable result.** The `M0-no-ask` arm — pure deny-by-default, no human at all,
zero interruptions — scores **identically on every row**. Given a correct scope, ASK buys
nothing, because every ASK is answered "no" by construction. ASK's value is entirely in
recovering utility that deny-by-default destroys when the compiled scope is wrong, and
E-01a cannot see that because the scopes are correct by construction (F-09).

**So the first thing Phase 3 should measure is compiler/gold divergence**, because that
quantity bounds the value of everything in Phases 3 and 4. If the compiler reproduces gold
scopes closely, Phase 4's headline trade-off curve will be flat.

## 5. Open defects and risks carried into Phase 3

| ID | Issue | Action owed |
|---|---|---|
| **F-09** | E-01a cannot measure what ASK is for; its value is contingent on compiler error | Measure compiler/gold divergence **first** in Phase 3 |
| **F-07** | Argument provenance is not authority provenance; the deterministic integrity rule cannot separate a legitimate reply from an exfiltration at a third-party destination | This *is* the dependency screener's job (ARCHITECTURE 4.1 mechanism 2) |
| **F-08** | ASK granularity is per action, but the decision is about an effect class over a set of resources | Phase 4, with the cost model |
| **F-05** | `af_auth.us.email.sam_number` asks for a Q3 figure the world does not contain | Fix before Phase 5 |
| **F-06** | High-authority compliance on the OpenAI side is not trustworthy — 8 scenarios below 4/6 | Audit before quoting compliance |
| **F-03** | Benign BTC understated by over-strict oracles | Loosen before quoting BTC |
| **R-09** | Open-weight generalisation unresolved; blocks T3 attacks and the saliency spike | Needs a competent open-weight model |
| **R-13** | Three non-OpenAI models failed the competency floor; our harness may be harder for them | Investigate if a 4th fails |
| **R-14** | Claude-authored scenarios evaluated a Claude model | Independent authorship in Phase 5 |
| **R-15** | **New.** E-01a's 0% FPR-block depends on gold-scope authoring rule 2 (D-023). A stricter rule would raise it, and the compiler will not follow the rule exactly | Report FPR-block against compiled scopes, never against gold, once Phase 3 lands |

## 6. Phase 3 — exact starting point

**Goal (ROADMAP Phase 3):** intent compilation and the authorization model — the
intellectually strongest part of the project.

**Start here, in this order.**

1. **`intent/compiler.py`, and measure it against the gold scopes immediately.** Effect-set
   precision/recall and constraint-extraction accuracy, per D-023's labels. This is
   deliverable 1 in the roadmap and it is also the answer to F-09, so it comes first rather
   than alongside.
2. Re-run E-01a with compiled scopes instead of gold ones (call it **E-01b**). The delta
   between the two is the size of the opportunity for everything downstream. If it is
   small, say so loudly and re-plan Phase 4.
3. Then the M0–M5 ladder, E-01 (the pre-registered similarity prediction, D-012), E-02, E-03.

**What Phase 2 tells Phase 3 to expect.** The structural floor is high and cheap: 0% ASR,
0% overreach, 0 interruptions on benign work — *when the scope is right*. There is no
headroom above that on these metrics. The ML core's entire job is to make the scope right,
and its contribution should be reported as "how much of the gold-scope result does a
compiled scope retain", not as an improvement over the undefended baseline.

**Also owed in Phase 3:** the dependency screener (F-07), which is the component that
separates a legitimate reply from an exfiltration when both draw their destination from
untrusted content. Phase 2 narrowed the structural rule rather than guessing; the screener
is what un-narrows it safely.

**Do not** relitigate D-018, D-019, D-021, D-022 (Phase 1), or D-006 (no ML in the trusted
path) without a documented reason. In particular, no ML component may produce a
`Signal(structural=True)`; the combinator ignores non-structural signals when deciding to
BLOCK, and a test asserts it.

## 7. Environment notes

- Python 3.12.9, uv 0.12.7, git 2.55, Windows 11. Venv at `.venv/`.
- Credentials load from **`.env.local`** (gitignored). `OPENAI_API_KEY` and
  `OPENROUTER_API_KEY`. `--override-env` is a top-level flag.
- No NVIDIA GPU. Local Ollama models cannot do reliable tool calling (D-016/D-020).
- `ANTHROPIC_API_KEY` unset; the Anthropic native provider is unit-tested for message
  translation but has never touched the live API. E-00f reached Claude through OpenRouter.
- **Phase 2 spent $0.** Total API spend across the project is still roughly **$4**.
- `.gitignore` was repaired this phase. A bad append had blanket-ignored
  `experiments/**/results/`, leaving E-00's raw `episodes.jsonl` uncommitted while section
  4 of this document claimed it was in the repository. It is committed now. E-01a's
  per-policy replay output is deliberately *not* committed: it is derived data that
  regenerates from committed inputs in seconds with no API access.
