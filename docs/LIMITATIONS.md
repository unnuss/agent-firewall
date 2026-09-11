# Limitations

**Everything this project does not establish, in one place, stated plainly.** If a claim you
want to make is not supported, it should be findable here rather than by reading 4,700 lines of
experiment log.

Ordered by how much they should change your reading of the results.

---

## 1. Authorship is the largest threat to every number here (R-14)

**The scenarios, the gold labels and the compiler prompts were written with Claude's help, and
some of the models evaluated are Claude models.**

D-033 removes *context* contamination — the held-out labeller saw no result, no run and no
compiler output, and the labelling brief was committed before any label existed. It does **not**
remove authorship. A benchmark whose scenarios and whose evaluated model share an author can
share blind spots in ways no internal check will reveal.

**What would close it:** a human author, or scenarios from a different vendor's model, writing a
slice from the same templates and brief. Nothing short of that.

**What it does not undermine:** the *deterministic* results. `tool-ceiling` reproducing
undefended overreach (F-11), ASR 0.0% under every compiled scope, the audit chain, the property
tests — none of those depend on who wrote the prose. The authorship risk attacks the
*benchmark's difficulty and realism*, not the monitor's behaviour on it.

## 2. Two frontier vendors only. No open-weight replication (R-09)

The phenomenon is established on `gpt-4.1-mini` and `claude-sonnet-5`. **Three open-weight
attempts failed a pre-registered competency floor** — Qwen3-8B at 31.9%, Qwen3-14B-AWQ at 36.1%,
Llama 3.3 70B at 44.4%, against a 60% floor set in advance (D-019).

Their numbers pointed the same direction, and they are reported as **inconclusive by the
registered gate rather than as evidence**, because a model that cannot do the task cannot be
measured overreaching at it. So: *"agents infer authority from silence"* is a claim about models
competent enough to do the work, and nothing is known about smaller ones.

## 3. This is a research prototype, not a deployable component

**The reference monitor is real.** It intercepts genuine tool calls from a genuine agent loop,
maps arguments to effects, decides ALLOW / ASK / BLOCK against a scope, propagates integrity and
confidentiality labels, enforces four structural gates, and writes a hash-chained audit log you
can replay offline. `agentfw demo` shows it refusing a real payment in three seconds.

**What does not exist:** an MCP proxy, a credential broker, any out-of-process isolation. The
sandbox is in-process and deterministic by design (D-013). There is no integration path for
putting this in front of your own agent, and **nothing in this repository should be read as
offering one.**

The honest description is *"a working reference monitor, evaluated as a research instrument."*

## 4. The replay cannot measure utility under defense

Verdict-level numbers come from replaying committed trajectories through the monitor. That is
sound for **security**: an effect the firewall stops is stopped whatever happens next.

It is **not** sound for utility. A defended agent that was told "no" would have done something
else — asked, retried another tool, given up — and the harness cannot know what. So:

* **Sound:** contested effects prevented, ASR, which gate fired, what the human was shown.
* **Reported as a proxy, not a measurement:** task completion and interruption counts.
* **After the first BLOCK the remaining actions are off-policy** and are counted separately so
  the two populations are never silently mixed.

A live defended run (E-01c) is the only thing that can measure utility under defense. It needs
an API budget and **has never been run.**

## 5. The learned compiler's comparison is not apples-to-apples

**It is supervised on the same blind-authored labels it is scored against. The prompted compiler
is zero-shot and has never seen one.**

So the claim available from Phase 6 is *"a supervised model with 86 training labels matches or
beats a zero-shot frontier model at roughly a thousandth of the cost"* — **not** "learned beats
prompted." A few-shot prompted arm would make it fair; it was costed at ~$2–5 and **deliberately
not bought**.

Two further limits on that phase:

* **293 labelled examples total**, 86 on the primary split, across 19 effect classes. Both rungs
  were still improving when the data ran out (F-41), so the model comparison was made in the
  starved regime.
* **D-038's dataset-extension step was never taken.** The contested-class label is structural and
  extensible by the generator for free. It remains the single most promising untried lever.

## 6. Benchmark construction limits what the splits can test

* **Eight of nine contested classes have a sole template source**, so leave-one-template-out is
  simultaneously a near-zero-shot class-transfer test and cannot cleanly isolate memorisation
  (F-36).
* **22 asking clauses cover 60 underspecified instances** and they cross worlds, which is why
  leave-one-world-out overstates generalisation by 35–41 pp.
* **Utterances are template-generated** from 11 templates; `dev` is hand-written. Surface-form
  variety is therefore bounded by what those templates express.

## 7. Scope-level and verdict-level numbers disagree, in both directions

Not a caveat — a result (F-14, F-38, D-042). But it is a limitation on *quoting*: a
scope-level figure alone has twice been a misleading summary of deployed behaviour, once in each
direction. **Never cite one without the other.** The canonical pairs are in
[`RESULTS.md`](RESULTS.md).

## 8. Smaller things that would each mislead someone

| | |
|---|---|
| **E-00i is superseded** | Its 81.8% was measured on 11 triples and came in at 49.4% on 60. Still referenced throughout the log for the correction's sake; **never quotable** |
| **The apparatus boundary** | Pre-repair (E-00, E-00b, E-00f, E-00h, E-01a, E-01b) and post-repair numbers may not be differenced. The Anthropic dev column was never re-run — a declared budget decision |
| **ASR evidence is weak in absolute terms** | 0.0% under every compiled scope is a strong *pattern*, but held-out ASR rests on **5 injection scenarios**, two defense-aware. It is the half of the thesis this project deliberately did not make the headline (D-001) |
| **Injection scenarios whose oracle reads the agent's final text** are excluded from replay ASR rather than guessed, because replay cannot supply that message |
| **Single-seed arms** | `per-class` on Sonnet is one seed. E-13 established that seeds do not narrow a scenario-clustered interval, so this costs variance information, not precision |
| **No human reviewer was ever in the loop** | Every ASK is answered by a scripted reviewer reading from the gold scope (D-027). Consent-integrity rendering is tested; human behaviour in front of it is not studied |
| **Interruption budget is a placeholder** | A fixed threshold, not a cost model. Phase 4 |
| **One prediction was registered in a currency the project had already disqualified** | D-042 ruled scope-level criteria out; E-15c's criterion was scope-level anyway. Scored as written, not retrofitted |

---

## What this project does establish

Stated so the limitations have something to be limitations *of*:

1. **Undefended competent agents overreach under under-specification, and not against explicit
   boundaries.** 49.4% against 3.5% on 60 held-out triples, replicated on two vendors, with the
   authority gap as a within-scenario paired contrast. This is the finding the project is for.
2. **A deterministic reference monitor with a correct scope removes all measured overreach and
   all measured attack success**, at zero interruptions on benign work.
3. **Restricting the toolset is not the same intervention as compiling a scope.** `tool-ceiling`
   reproduces undefended overreach to the decimal, three times (F-11).
4. **Compiled scopes leave a real residual**, 5.6% at the verdict level on an interval excluding
   zero — confirmed on adequate power after being reopened on inadequate power (D-034, D-037).
5. **ASR is 0.0% under every compiled scope ever measured**, including learned ones.
6. **The evaluation instrument misleads in specific, documented ways** — and each way was found
   by a gate rather than by inspection.
