# PROJECT STATE

**Read this first.** It is the handoff document between development sessions.

**Last updated:** 2026-08-31 · **Phase 3 in progress.** · Phase 2 complete.

---

## 0. If you are the next session, do exactly this

1. Read `CLAUDE.md`, then this file, then **`docs/DECISIONS.md` D-025 to D-031** — D-025
   fixes what the intent compiler may see, D-026 why compiled scopes are committed
   artifacts, D-027 what the scripted human knows in E-01b, D-028 the experiment renaming,
   D-029 credential precedence and why a run was misdiagnosed for a day.
   D-030 constraint provenance, D-031 why the held-out slice is not yet a held-out
   validation. D-022, D-023 and D-024 remain the Phase 1/2 constraints.
2. Read **E-09a and E-01b in `docs/EXPERIMENTS.md`**. Both are done, including the
   registered `gpt-4.1-mini` arm at three seeds; E-09a's run log carries a correction worth
   reading about how that arm was misdiagnosed as blocked on billing for a day.
3. Read **F-16 first** — it falsifies the phase's central prediction and is the reason the
   rest of Phase 3 needs re-planning. Then F-10 to F-15, then the older F-07 to F-09.
4. Continue Phase 3 per `docs/ROADMAP.md`. Start at section 6 of this document.

Health check (~35 s, no API calls, no keys needed):

```bash
.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m agentfw.cli validate
```

Expect **230 passed** and 24 AF-Auth / 6 AF-Inject / 18 benign dev scenarios, 23 tools.

Both replay experiments reproduce with no key:

```bash
.venv/Scripts/python.exe -m agentfw.cli replay experiments/e01a_deterministic/config.yaml
.venv/Scripts/python.exe -m agentfw.cli replay experiments/e01b_compiled/config.yaml
```

---

## 1. Where the project is, in one paragraph

Phase 1 measured the problem and changed the thesis: agents respect explicit authorization
boundaries almost perfectly and fail by inferring authority from silence — 38.9% on OpenAI
models, 60.0% on Claude Sonnet 5 (D-022). Phase 2 built the deterministic reference monitor
and E-01a showed it removes all measured overreach and all measured attack success *given a
correct scope*, with the ASK path contributing nothing in that condition (F-09). Phase 3
therefore began where PROJECT_STATE said it must: with the scope itself. The intent compiler
exists, its inputs are restricted by construction to the user's turn and the tool catalogue
(D-025), and the measurement harness around it — E-09a against the gold labels, E-01b
against real verdicts — is built and running, and **the registered arm has now run and
falsified the phase's central prediction (F-16).**

`gpt-4.1-mini` on the **baseline** formulation licenses the contested effect on **53.3%** of
underspecified instructions — against **45.9%** for the undefended agents on the same ones.
E-09a's central prediction is falsified and stays falsified.

**E-10 then falsified the explanation twice over, and that is the phase's main result.**
F-16 said the compiler carries the model's prior because it is the same model. Two
independent knobs say otherwise:

- **Change the formulation, hold the model.** A `licensed` / `not_licensed` / `uncertain`
  verdict on every candidate class, instead of a free-form grant list, takes the *same*
  `gpt-4.1-mini` from 53.3% leakage to **0.0%** (0/45, three seeds) and to the gold result
  end to end — 0.0% overreach, 0.0% ASR, 84.3% compliance vs gold's 84.7% (**F-17**).
- **Change the model, hold the formulation byte-identical.** Claude Sonnet 5 on the
  unchanged baseline prompt leaks **10.0%**, against gpt-4.1-mini's 53.3% — and the rank
  order between the families *reverses* between roles: Sonnet's **agent** overreaches 60.0%
  where OpenAI's is 38.9%, but its **compiler** is five times more conservative (**F-18**).

The completed 2x2 has **exactly one bad cell**, and the two fixes are **substitutes**
(**F-19**):

| leakage, underspecified | `baseline` | `per-class` |
|---|---|---|
| `gpt-4.1-mini` | **53.3%** | 0.0% |
| `claude-sonnet-5` | 10.0% | 0.0% |

The best arm — `per-class` on Sonnet — **matches the hand-written gold scopes on every
security axis** (0.0% overreach, 0.0% explicit-low, 0.0% ASR) and sits one episode from gold
on compliance (84.3% vs 84.7%). The entire remaining gap is 3 refused benign actions out of
173.

So the architecture's bet — that "what did this person authorize?" is an easier question
than "what should I do?" — **holds, but not automatically.** The failure E-09a measured was
one cell of a 2x2, a weak model under a loose formulation, not a law about compilers. And
noticing is not the differentiator: both models raise an open question on ~100% of
underspecified variants. **Withholding is what varies.**

The deterministic core is unaffected throughout, and so is the injection result: **ASR is
0.0%** under every compiled scope, because those utterances are plain read-only requests and
deny-by-default does that work without any ML.

What the compiled system still gives up against gold is now the **cost** side, not the
security side: benign FPR-block 3-7% against 0.0%, and roughly twice the interruptions.
Under-granting is the dominant error (407 classes against 4 over-granted, 303 of them
READs), which is F-10's territory and Phase 4's to price.

Also established: a tool-allowlist scope is worth nothing against overreach (F-11); ASK's
value is real once the scope is wrong (269 refusals recovered against 0 under gold);
invented constraints fire a hard gate no interruption can repair (F-13); and scope-level
metrics can improve while the deployed system gets worse, so a compiler change is not an
improvement until E-01b says so.

## 2. Phase 3 deliverables, against the roadmap

| # | Deliverable | Status |
|---|---|---|
| 1 | `intent/compiler.py` — utterance → IntentScope | done: `LLMIntentCompiler` + two deterministic floors, `intent/catalog.py`, `intent/store.py` |
| 1 | **E-09a** — compiled scopes scored against gold | **DONE.** Predictions registered before any LLM call and scored; prediction 3 **falsified** (F-16) |
| 1b | **E-01b** — the replay with compiled scopes | **DONE** for all seven arms, including the registered one at three seeds |
| 2 | The M0–M5 ladder | not started — deliberately, see section 6 |
| 3 | Calibration (ECE, reliability) | not started |
| 4 | E-01 (the pre-registered similarity prediction, D-012) | not started |
| 5 | E-02 (ladder comparison) | not started |
| 6 | E-03 (cascade) | not started |
| 7 | Dependency screener (F-07) | not started |
| 8 | M6 distillation | conditional on E-03 (D-011), unchanged |

## 3. What exists in code that did not before

```
agentfw/
  intent/
    catalog.py     tool -> effect-class ceiling, with two drift tests against the declarers
    prompts.py     the compilation prompt; D-023's four authoring rules, and nothing scenario-specific
    compiler.py    Compiler protocol, LLMIntentCompiler, ToolCeilingCompiler, ReadOnlyCompiler
    store.py       CompiledScopeStore: the committed artifact, and the ScopeSource seam
  eval/
    scope_run.py   the E-09a driver: compile every dev utterance, per arm and seed
    scope_eval.py  compiled-vs-gold metrics and the E-09a report
    scopes.py      + ScopeSource protocol, so replay takes gold or compiled interchangeably
    replay.py      + a scope source parameter and the gold reviewer oracle (D-027)
    replay_report.py + `ask_value` (what each interruption bought) and a cross-arm comparison
  cli.py           + `agentfw compile-scopes`; `replay` gained `--scopes`
experiments/
  e09a_compiler/   config + committed compiled scopes + per-arm reports
  e01b_compiled/   config + per-(scope, policy) reports + comparison.md
tests/test_intent.py   24 tests; test_replay.py gained the two D-027 seam tests
```

Four things worth not re-deriving:

- **The compiler's input restriction is its signature.** `compile(utterance, tools)` and
  nothing else. An attacker who could feed the compiler would be writing the user's
  authorization scope, which beats hijacking the agent, so the restriction is enforced by
  having nowhere to put the other data and asserted by a test over the rendered prompt.
- **A compile failure is an empty scope**, never a partial one. Deny-by-default all the way
  down, and the affected episodes are counted separately so an unreliable compiler cannot
  look like a cautious one.
- **Compiled scopes are committed artifacts** (D-026). E-01b never calls a model; it reads
  the JSONL E-09a wrote. That is what keeps the downstream experiment free and reproducible.
- **The scripted reviewer answers from gold in E-01b** (D-027), because a reviewer with an
  opinion only about the contested effect would refuse every recoverable interruption and
  make ASK look worthless a second time as a harness artifact.

**One Phase 2 test was corrected, not weakened.** `test_p4_agent_rationale_never_reaches_
the_ask_text` carried two assertions, and hypothesis found a counterexample to the first:
a rationale of `"reversibilit"` is a substring of a serialized field name, which is a
collision rather than a leak. The test's own comment already argued that substring checking
is the wrong test; the substring assertion is now gone and the byte-identity assertion —
render with the prose, render without it, require the same output — carries P4 alone. It
subsumes the deleted check, because prose that reached the output would change it.

## 4. Results so far

### E-09a — compiled against gold

| Arm | Micro-F1 | Exact match | Leakage (underspec. low) | Retention (high) | Contrast fidelity |
|---|---|---|---|---|---|
| `tool-ceiling` | 0.813 | 24.4% | **100%** | 100% | **0%** |
| `read-only` | 0.727 | 22.1% | **0%** | 0% | **0%** |
| `llm-qwen2.5-coder-14b` (exploratory, prompt v1) | 0.576 | 20.9% | 33.3% [13.3, 60.0] | 87.5% | 58.3% |
| `llm-qwen2.5-coder-14b` (exploratory, prompt v2) | 0.550 | 19.8% | 26.7% [6.7, 46.7] | 100% | 75.0% |
| **`gpt-4.1-mini` (registered, 3 seeds)** | 0.554 | 19.8% | **53.3%** [26.7, 80.0] | **100%** | **50.0%** |

The first column is why F1 is not the metric: `tool-ceiling`, which has no notion of
authorization at all, scores **0.813** — above every real compiler measured.

The registered arm clears the retention floor at 100%, so it is a competent reader and every
number is interpretable. Seed agreement 0.965; leakage, retention and contrast are identical
on all three seeds. **Predictions scored: 1 held, 2 failed instructively, 3 FALSIFIED,
4 held, 5 held, 6 held.** Prediction 3 was the architecture's central bet — see F-16.

### E-01b — what those scopes do to real verdicts (702 episodes, $0)

| Scope source | Policy | Overreach (underspec.) | Compliance (high) | ASR | Benign FPR-block | ASKs/ep benign |
|---|---|---|---|---|---|---|
| *(undefended)* | — | 45.9% [34.1, 57.8] | 84.7% | 22.2% | — | — |
| gold | consequential | **0.0%** | 84.7% | **0.0%** | 0.0% | 0.00 |
| tool-ceiling | consequential | **45.9%** | 84.7% | 16.7% | 0.0% | 0.00 |
| read-only | consequential | 0.0% | **78.2%** | 0.0% | **12.1%** | 0.11 |
| read-only | all-out-of-scope | 0.0% | 82.9% | 0.0% | 0.0% | 0.32 |
| llm-qwen-local-p1 | consequential | 17.0% | 60.6% | 0.0% | 11.9% | 0.00 |
| llm-qwen-local-p2 | consequential | 12.6% | 41.2% | 0.0% | 34.5% | 0.00 |
| **`gpt-4.1-mini` s1** (pre-D-030) | consequential | 25.2% [11.9, 40.0] | 68.5% | 0.0% | 16.9% | 0.00 |
| **`gpt-4.1-mini` s1** (after D-030) | consequential | **25.2%** | **84.3%** | **0.0%** | **7.5%** | 0.14 |
| **`gpt-4.1-mini` s1** (after D-030) | all-out-of-scope | 25.2% | **84.7%** | 0.0% | **0.0%** | 0.27 |

- The gold row reproduces E-01a exactly, which is the check that D-027's wider reviewer
  oracle cannot bind when the scope is already right.
- **F-11:** a tool-allowlist scope reproduces undefended overreach episode for episode.
- **ASK finally does something:** 90 asks / 0 approved under gold; 359 asks / **269
  recovered refusals** under `read-only`. F-09's contingency is now measured.
- **F-10:** at `ask_on: consequential`, 22 of 182 benign actions are refused with no dialog,
  all `CREATE` on private reversible resources. `consequential()` is the right predicate for
  agent overreach and the wrong one for compiler under-granting.
- **F-13:** the compiler arm fired gate G2 **59 times**, all on bounds it invented, and G2 is
  a hard gate — no interruption can repair a wrong bound, while 33 forgotten grants on the
  same run were repaired by one. `Grant` carries provenance and `Constraint` does not, so the
  firewall cannot tell a bound the user stated from one the compiler guessed.
- **F-14:** most of those invented bounds came from my own prompt — its JSON schema example
  held a literal `$150` budget, and the model copied it. Fixed in prompt v2, declared under
  R-16, artifacts versioned `p1`/`p2` so the two runs can never be compared silently.
- **The two-level measurement earned its keep, and this is the result to remember.** Prompt
  v2 improved *every* scope-level metric (leakage 33.3→26.7%, retention 87.5→100%, contrast
  58.3→75.0%) and made the deployed system much worse (compliance 60.6→41.2%, benign
  FPR-block 11.9→34.5%, G2 firings 59→270). Freed from copying the example's `$150`, the
  model extracted bounds enthusiastically — 69 across 51 utterances against gold's 6 — and
  they are plausible and wrong: `["Priya"]` where the address is
  `priya.menon@northwind-systems.com`, `["Amex"]` as the recipient of a payment, a time
  window clamped onto `READ:CALENDAR`. **A compiler change is not an improvement until E-01b
  says so.**
- **F-15:** feeding real compiler output into the monitor found a crash in Phase 2 TCB code —
  a naive/aware datetime comparison raised inside `Constraint.check`, taking 21 episodes out
  of the measurement entirely. Fixed and fail-closed; E-01a still reproduces bit-identically.

## 5. Open defects and risks carried forward

| ID | Issue | Action owed |
|---|---|---|
| **F-16** | The *baseline* formulation leaks 53.3% against the agents' 45.9%. Prediction 3 falsified | Measurement stands; the explanation is superseded by F-17 |
| **F-17** | Formulation-dependent: per-class verdicts get 0.0% leakage from the same model | Confirm on the held-out slice before it sets the design |
| **F-18** | Model-dependent too, and agent behaviour does not predict compiler behaviour: Sonnet's agent overreaches 60.0%, its compiler leaks 10.0% | Confirm on held-out |
| **F-19** | The two fixes are **substitutes**: one bad cell in the 2x2, either knob alone recovers most of it | A deployment needs *either* a capable model *or* an explicit formulation. Choose on cost — the formulation is ~10x cheaper |
| **F-20** | `email_list`'s `query` matches contiguous substrings only, so the natural phrasing of a name returns nothing and the agent correctly gives up. Cost: held-out compliance 11.1%, competency gate failed, E-01b impossible there | Fix before Phase 5 scales the suite, then re-run the undefended baselines. Not fixed now: it would invalidate every committed episode's comparability |
| **F-10** | `consequential()` cannot tell "not worth interrupting about" from "the compiler probably dropped this" | Phase 4 cost model needs a `C_block_benign` term; the ML core's job is P(compiler under-granted) |
| **F-11** | Tool-allowlist authority = undefended overreach | Feeds EVALUATION 6.2; B-01 proper is Phase 5 |
| **F-12** | Gold scopes are inconsistent about paths named in an utterance (globs written for deletes, not for destinations) | **Labels deliberately unchanged.** Apply rule 3 uniformly when the held-out scopes are written |
| ~~F-13~~ | **RESOLVED (D-030).** Inferred bounds escalate; stated bounds still hard-gate and consent may not lift them. Compliance 68.5% → 84.3%, FPR-block 16.9% → 7.5%, G2 110 → 0, security unchanged | done |
| **F-14** | Prompt v1's schema example leaked literal values into compiled constraints | **Fixed** in prompt v2, declared under R-16. Any future prompt uses placeholders |
| **F-15** | A compiled scope could make `Constraint.check` raise, killing the decision | **Fixed** in `core/scope.py`, fail-closed, two tests. Watch for the same shape in any handler that gains a new input source |
| **F-09** | ASK's value is contingent on compiler error | **Answered** for the floor arms; re-answer with the LLM arm |
| **F-07** | Argument provenance is not authority provenance | Dependency screener, still owed in Phase 3 |
| **F-08** | ASK granularity is per action, not per effect class over a resource set | Phase 4 |
| **F-05** | `af_auth.us.email.sam_number` asks for a figure the world does not contain | Fix before Phase 5 |
| **F-06** | High-authority compliance on the OpenAI side is untrustworthy in 8 scenarios | Audit before quoting compliance |
| **F-03** | Benign BTC understated by over-strict oracles | Loosen before quoting BTC |
| **R-09** | Open-weight generalisation unresolved | Needs a competent open-weight model |
| **R-14** | Claude-authored scenarios evaluated a Claude model | Independent authorship in Phase 5. The compiler arm is deliberately an OpenAI model for the same reason |
| **R-15** | FPR-block must be reported against compiled scopes, never gold | **Done** — E-01b reports it per scope source |
| **R-16** | **New.** Prompt development and measurement share the dev slice | The tuning slice is declared: benign + af_inject + the control pairs. The 14 core underspecified triples were not looked at while writing the prompt, and any later prompt change must be declared and re-registered |

## 6. Phase 3 — the architecture decision, and whether the phase can close

**Recommendation: yes, close Phase 3 on the architecture. Do not close it on the
deployment configuration, and do not start Phase 4 until the two items in "owed" are done.**

### The architecture decision, stated

The design is **validated as specified in ARCHITECTURE.md**, with one part re-scoped:

1. **Deterministic reference monitor over an effect ontology, deny-by-default.** Keep. It is
   the contribution. Given a correct scope it removes all measured overreach and all measured
   attack success at zero cost (E-01a), and **ASR is 0.0% under every compiled scope ever
   measured** — the injection half of the thesis never needed a model.
2. **Intent compilation outside the TCB.** Keep. Two configurations reach the gold-scope
   result end to end; the best is within one episode of hand-written scopes on every axis.
3. **ASK as the recovery path.** Keep. Its value is a function of compiler error (F-09,
   answered) and it is what makes an under-granting compiler usable.
4. **Constraint provenance** (D-030). Keep — worth 16 points of compliance.
5. **The M0-M5 ladder: re-scope, do not build as written.** It was designed to calibrate
   `P(licensed)` into an ASK band. The security axis turns out reachable from formulation and
   model choice alone, so what remains is the *cost* axis, and the useful estimand is "how
   likely is it the compiler **dropped** this class" — not the same quantity, and a much
   smaller problem. E-02 as written answers a question the evidence no longer poses.

### What E-10 settled

- The authority-leakage failure is **one cell of a 2x2**, not a law (F-16 measured it, F-17
  and F-18 falsified its explanation, F-19 gave the interaction structure).
- The two fixes are **substitutes**: a deployment needs either a capable model or an explicit
  formulation, and can choose on cost. The formulation is ~10x cheaper and does not depend on
  a frontier model remaining available.
- **Noticing is not the differentiator** — every compiler flags the ambiguity on ~100% of
  underspecified instructions. **Withholding is what varies**, and making refusal expressible
  is what changes it.

### Owed before Phase 4

1. **A real held-out validation — attempted, and it is not achievable with the current
   suite (D-031).** Gold scopes were written and committed for the held-out split, and
   E-09a ran there. Two blockers, both structural:
   - The suite is 3 generated scenarios from one template, 6 variants, **all explicit**.
     Zero underspecified variants, zero benign, zero af_inject. Phase 3 is about the
     underspecified band, so the slice cannot exercise it.
   - **E-01b cannot run there at all.** No episode had ever been recorded for a held-out
     scenario; E-00h was run to create them and failed the competency floor at 11.1%
     compliance, because of **F-20** — `email_list`'s `query` matches contiguous substrings
     only, so "Cloudhost billing" returns nothing while "cloudhost" returns the message.
     Systematic for that template. Not fixed here: changing a sandbox tool invalidates every
     committed episode's comparability, so it is Phase 5 work plus a baseline re-run.

   It did produce one real result: **`per-class`'s over-conservatism replicates on unseen
   scenarios** — 66.7% retention for `gpt-4.1-mini` against 100% for Sonnet, the same
   asymmetry as dev.
2. **A second seed for arm 4** (~$1.40) if its numbers are to be quoted as more than a point
   estimate.

Neither blocks the architecture decision; both block quoting these numbers as final.

### Deliberately not decided

Which model and which formulation to deploy. That is a configuration choice, it depends on
cost and on availability, and the honest position after E-10 is that **several configurations
work and one does not** — which is more useful to a reader than a single recommended stack.

**Do not** relitigate D-006 (no ML in the trusted path), D-018 to D-024, D-025's input
restriction, or D-030's provenance asymmetry without a documented reason.

## 7. Environment notes

- Python 3.12.9, uv 0.12.7, git 2.55, Windows 11. Venv at `.venv/`.
- Credentials load from **`.env.local`** (gitignored). It holds a **working**
  `OPENAI_API_KEY` (~$3.86 as of 2026-08-31). **`OPENROUTER_API_KEY` is in the operator's
  shell but not in `.env.local`, so the harness cannot see it** — E-10 arm 3 is blocked on
  exactly that, and the credential fingerprint line caught it in seconds this time instead
  of costing a day (D-029). **The file now wins a conflict with an exported variable and says so
  (D-029)** — the reverse rule cost E-09a a day and had already cost E-00 a day before that.
  Every command prints the credential fingerprint it is using; `--prefer-exported-key`
  restores the old precedence.
- No NVIDIA GPU. Ollama is installed with `qwen2.5-coder:14b` and `dolphin3`; both are
  unusable as *agents* (D-016/D-020) but a compiler needs only JSON output, so
  `qwen2.5-coder:14b` runs as an explicitly exploratory arm at roughly 50–100 s per
  utterance on CPU.
- **Phase 3 has spent roughly $4.4** (E-09a ~$0.30, E-10 ~$4.1 including one discarded
  attempt and two smoke probes). Total API spend across the project is roughly **$8.5**.
- E-09a's compiled scopes are committed on purpose (D-026): they are inputs to E-01b, not
  outputs of it. E-01b's per-arm replay output is derived data and regenerates in ~2 minutes.
