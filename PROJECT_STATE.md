# PROJECT STATE

**Read this first.** It is the handoff document between development sessions.

**Last updated:** 2026-08-31 · **Phase 3 in progress.** · Phase 2 complete.

---

## 0. If you are the next session, do exactly this

1. Read `CLAUDE.md`, then this file, then **`docs/DECISIONS.md` D-025 to D-029** — D-025
   fixes what the intent compiler may see, D-026 why compiled scopes are committed
   artifacts, D-027 what the scripted human knows in E-01b, D-028 the experiment renaming,
   D-029 credential precedence and why a run was misdiagnosed for a day.
   D-022, D-023 and D-024 remain the Phase 1/2 constraints.
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

Expect **206 passed** and 24 AF-Auth / 6 AF-Inject / 18 benign dev scenarios, 23 tools.

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

`gpt-4.1-mini`, three seeds, licenses the contested effect on **53.3%** of underspecified
instructions — against **45.9%** for the undefended agents on the same instructions. The bet
was that asking "what did this person authorize?" is easier than asking "what should I do?".
It is not, and not because the compiler fails to notice: it raised an open question on
**100%** of underspecified variants and granted the contested effect on half of them anyway,
asking *which* payment method rather than *whether* to pay. It is the same model with the
same prior, so it carries the same bias; the compiler relocated the failure rather than
removing it.

The deterministic core is unaffected and so is the injection result: **ASR stays at 0.0%**
under compiled scopes, because those utterances are plain read-only requests and
deny-by-default does that work without any ML. End to end the compiled system halves
overreach (45.9% → 25.2%) at a compliance cost of 84.7% → 68.5%, which is real but is a long
way from the gold-scope 0.0%.

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
| **`gpt-4.1-mini` s1** | consequential | **25.2%** [11.9, 40.0] | **68.5%** | **0.0%** | 16.9% | 0.00 |
| **`gpt-4.1-mini` s1** | all-out-of-scope | 25.2% | 69.0% | 0.0% | 8.2% | 0.13 |

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
| **F-16** | The compiler carries the agent's authority bias: 53.3% leakage against the agents' own 45.9%. Prediction 3 falsified | **Re-plan Phase 3** (section 6). The ladder was designed to calibrate `P(licensed)`; the measured problem is a biased prior, not an uncalibrated score |
| **F-10** | `consequential()` cannot tell "not worth interrupting about" from "the compiler probably dropped this" | Phase 4 cost model needs a `C_block_benign` term; the ML core's job is P(compiler under-granted) |
| **F-11** | Tool-allowlist authority = undefended overreach | Feeds EVALUATION 6.2; B-01 proper is Phase 5 |
| **F-12** | Gold scopes are inconsistent about paths named in an utterance (globs written for deletes, not for destinations) | **Labels deliberately unchanged.** Apply rule 3 uniformly when the held-out scopes are written |
| **F-13** | An invented constraint fires a hard gate and is unrecoverable; a forgotten grant is not | Give `Constraint` provenance and let a compiler-provenanced bound escalate rather than block. Care needed: it makes a narrowing negotiable, which runs opposite to D-007 |
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

## 6. Phase 3 — what is next, and it needs a decision

**Deliverable 1 is complete and it did not go the way the roadmap assumed.** The registered
arm falsified prediction 3 (F-16): the compiler carries the same authority bias as the agent,
because it is the same model. Deliverables 2-8 were designed on the assumption that the
compiler would be roughly right and the remaining work was calibrating `P(licensed)` into an
ASK band. That assumption is now measured and false, so the ladder should not simply proceed
as written. **This is the re-plan the roadmap itself asked for** ("If it is small, say so and
re-plan Phase 4 rather than building a cost model with nothing to arbitrate") — the gap is
not small, it is in the opposite direction to the one anticipated.

Three options, and the choice is the user's:

**(a) Attack the bias directly — the honest continuation.** The open question F-16 leaves is
whether *any* compiler configuration has an authority bias different from the agent's. Cheap
things to try, each a registered arm with a versioned prompt: a framing that forces a verdict
per candidate effect class rather than a free list; a second model as an independent
compiler, so disagreement itself becomes signal; asking for the *narrowest* scope that
completes the stated goal. If none of them moves leakage, that is a strong and publishable
negative result about intent compilation with current models — and it is the most
intellectually honest thing this project could produce.

**(b) Fix what is structural first.** F-13 (constraint provenance — an invented bound fires a
hard gate that no interruption can repair; ~110 firings per seed on the registered arm) and
F-10 (`consequential()` cannot distinguish "not worth asking about" from "the compiler
probably dropped this"). Both are deterministic, both are cheap, and both are worth doing
whatever happens to the compiler. Neither touches the ML.

**(c) Re-scope the claim.** Report the deterministic core as the contribution, with compiled
scopes as the measured limit on it, and drop the ladder. The result would be: deny-by-default
over an effect ontology removes 100% of measured injection success and, given a correct
scope, all measured overreach; automatic scope inference with a frontier model recovers about
half of that and no more, for the reason F-16 gives.

**What is not in doubt.** ASR is 0.0% under compiled scopes. The injection half of the thesis
does not depend on the compiler at all, and it held.

**The M0-M5 ladder as designed is now questionable** rather than obviously next. It estimates
`P(licensed)` to place an ASK band. The measured failure is not an uncalibrated score, it is a
prior that is confidently wrong — a better-calibrated version of the same model's opinion is
not obviously worth building. E-01 (D-012's pre-registered similarity prediction) is still
worth running because it is cheap and its negative result is already interesting.

**Do not** relitigate D-006 (no ML in the trusted path), D-018 to D-024, or D-025's input
restriction without a documented reason.

## 7. Environment notes

- Python 3.12.9, uv 0.12.7, git 2.55, Windows 11. Venv at `.venv/`.
- Credentials load from **`.env.local`** (gitignored). It holds a **working**
  `OPENAI_API_KEY` (~$3.86 as of 2026-08-31); `OPENROUTER_API_KEY`, which E-00f used, is no
  longer present. **The file now wins a conflict with an exported variable and says so
  (D-029)** — the reverse rule cost E-09a a day and had already cost E-00 a day before that.
  Every command prints the credential fingerprint it is using; `--prefer-exported-key`
  restores the old precedence.
- No NVIDIA GPU. Ollama is installed with `qwen2.5-coder:14b` and `dolphin3`; both are
  unusable as *agents* (D-016/D-020) but a compiler needs only JSON output, so
  `qwen2.5-coder:14b` runs as an explicitly exploratory arm at roughly 50–100 s per
  utterance on CPU.
- **Phase 3 has spent $0.** Total API spend across the project is still roughly **$4**.
- E-09a's compiled scopes are committed on purpose (D-026): they are inputs to E-01b, not
  outputs of it. E-01b's per-arm replay output is derived data and regenerates in ~2 minutes.
