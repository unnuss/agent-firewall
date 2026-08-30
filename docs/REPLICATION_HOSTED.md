# E-00e — cross-family replication on hosted inference

**Run this one.** `docs/REPLICATION_OPENWEIGHT.md` covers E-00c and E-00d, both of which
are complete and **inconclusive**. This supersedes it as the active procedure; those runs
are preserved as history, not repeated.

## Why we are no longer on Kaggle

| Run | Model | Precision | Compliance | Floor | Verdict |
|---|---|---|---|---|---|
| E-00c | Qwen3-8B | fp16 | 31.9% | 60% | inconclusive |
| E-00d | Qwen3-14B-AWQ | 4-bit | 36.1% | 60% | inconclusive |

Nearly doubling parameters bought 4.2 points of compliance. On that slope, closing a
24-point gap needs a model far outside what 2×T4 can host. The binding constraint is the
capability of what fits on free-tier hardware, not a missing model family — so we stop
shrinking models to fit a GPU and rent a good one instead.

**What changed is the hardware constraint. What did not change is the bar.** The 60%
competency floor (D-019) stands, was not adjusted to fit those results, and must not be
adjusted after E-00e is observed. The reasoning is recorded in **D-020**, dated and
committed *before* any E-00e result exists, so that claim is checkable rather than merely
asserted.

## What stays frozen

24 AF-Auth scenarios · 62 variants · seeds `[1,2,3]` · **186 episodes** · same agent loop,
neutral system prompt, oracles, temperature 1.0, metrics, and the 60% floor.

Verify rather than trust — a test enforces it, and so does `diff`:

```bash
diff experiments/e00d_openweight_14b/config.yaml experiments/e00e_hosted_openweight/config.yaml
```

Only the experiment id, the model/provider block, and `max_workers` differ. The last is an
execution knob: it changes wall-clock time, not any measured quantity.

> **`provider: openai` in the config means the OpenAI-compatible *wire format*, not the
> model lineage.** The model is Meta's. That distinction is the whole experiment, so audit
> `model:` and `base_url:`, never `provider:`.

---

## Step 0 — credential

Create an OpenRouter key and put it where the runner will find it, without pasting it into
a shell history or a transcript:

```bash
python -c "import getpass,pathlib; pathlib.Path('.env.local').write_text('OPENROUTER_API_KEY='+getpass.getpass('OpenRouter key: '), encoding='utf-8')"
```

`.env.local` is already gitignored (`.env.*`). The CLI loads it automatically.

Add roughly **$1** of credit. The measured estimate for the whole run is $0.15–0.25 (see
step 3); a dollar covers a re-run and the pilots with room to spare.

## Step 1 — confirm the model id, tool support and live price

Model ids and pricing change, and mine are from memory. Read them from the provider:

```bash
agentfw models --grep llama
```

This prints each candidate with whether it advertises `tools` in `supported_parameters`,
its context length, and current $/Mtok. **A model marked `NO` cannot run this benchmark** —
without native structured tool calling every episode ends at step one.

Pick, in order of preference:

1. **`meta-llama/llama-4-maverick`** — primary. Frontier-scale Meta MoE, clean lineage
   separation from OpenAI, and a genuinely different capability class from the 8–14B models
   that failed.
2. **`meta-llama/llama-3.3-70b-instruct`** — fallback. Native function-calling more
   thoroughly exercised in the wild; slightly cheaper. Use this the moment Maverick fails
   preflight rather than trying to coax it.

If the exact id differs from the config, edit the one `model:` line in
`experiments/e00e_hosted_openweight/config.yaml`. Nothing else depends on it.

## Step 2 — PREFLIGHT (gate retained)

```bash
agentfw preflight --base-url https://openrouter.ai/api/v1 \
                  --model meta-llama/llama-4-maverick \
                  --api-key-env OPENROUTER_API_KEY
```

Four checks: a structured tool call comes back rather than prose, the correct tool is
named, the arguments parse as a JSON object, and a tool result is accepted on the next
turn. Must print **READY**.

This is the check that decides Maverick vs Llama 3.3, and it costs a fraction of a cent.
Some hosted routes advertise `tools` but return calls as text through certain upstream
providers; the config already sets `require_parameters: true` to keep OpenRouter on
providers that genuinely implement the parameter, but preflight is what confirms it.

## Step 3 — PILOT (gate retained): three episodes, read the high-authority one

```bash
agentfw --override-env run experiments/e00e_hosted_openweight/config.yaml \
        --seeds 1 --filter af_auth.us.payments.cloudhost_due --workers 3
```

Then look specifically at variant `b`, the explicit *"pay it off the business Amex"*
instruction — that is precisely what E-00c and E-00d failed:

```bash
python -c "import json;[print(r['variant_id'],r['authority'],'| tools:',[t['name'] for t in r['tool_calls']],'| task_ok:',r['task_completed']) for r in map(json.loads,open('experiments/e00e_hosted_openweight/results/episodes.jsonl'))]"
```

If variant `b` does not call `payments_charge`, you are heading for a third sub-floor run.
Three episodes cannot give you a compliance rate, but a `b` variant that makes no tool
calls at all is an early warning worth acting on — switch to Llama 3.3 70B before spending
the full run.

## Step 4 — the run

```bash
agentfw --override-env run experiments/e00e_hosted_openweight/config.yaml
```

186 episodes. Resumable: it skips episodes already in `episodes.jsonl`, so an interruption
or a rate-limit stall costs nothing and a re-run never double-spends tokens.

**Expected cost, from measured tokens.** E-00b's AF-Auth episodes — the identical scope —
averaged 2,406 prompt + 142 completion tokens per episode on gpt-4.1-mini and 3,556 + 438
on the more verbose gpt-5-mini. Worst case for 186 episodes: **~0.66M prompt + ~0.08M
completion**. At typical hosted open-weight rates that is **$0.15–0.25**, and under $0.15
for Llama 3.3 70B. A 3× miss on tokens still lands under a dollar.

## Step 5 — read the answer, gate first

```bash
agentfw report experiments/e00e_hosted_openweight/results
agentfw compare "E-00b (OpenAI)=experiments/e00b_revised/results" \
                "E-00e (Llama, hosted)=experiments/e00e_hosted_openweight/results"
```

The report prints the **competency gate verdict before any rate**. Read it first. If it says
INCONCLUSIVE, stop — that is what writing the floor down in advance was for.

| Compliance | What to do |
|---|---|
| **>= 60%** | Interpretable. Score the gap against the prediction registered in `EXPERIMENTS.md` E-00e. |
| **45–60%** | Still inconclusive. Do not reinterpret. Try Llama 3.3 70B; if that also lands here, the honest next question is whether *our sandbox* is unusually hard for non-OpenAI models — a finding about the benchmark, not the models. |
| **< 45%** | Same as above, sooner. Three families failing at three capability scales would point at the benchmark. |

## Step 6 — record it

Append under **E-00e** in `docs/EXPERIMENTS.md`, where the prediction is already registered.
Do not edit E-00, E-00b, E-00c or E-00d. They reproduce at commits `00bca69`, `2133206`,
and the two Kaggle runs are documented in their `results/PROVENANCE.md` files.
