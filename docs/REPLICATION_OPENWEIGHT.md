# E-00c — cross-family replication runbook (Kaggle / Colab)

**Purpose.** E-00b showed that agents refuse explicit consequence escalation (0/54) but
infer permission under under-specification (38.9%, 13/15 scenarios). Both models tested
were OpenAI models, so a shared post-training lineage cannot be ruled out as the cause.
This run answers one question:

> Does the underspecified-vs-explicit-low gap appear outside the OpenAI model family?

It is a precondition for Phase 2. Until it runs, every claim in the README is "on the
models tested".

**Size.** 24 AF-Auth scenarios × 62 variants × 3 seeds = **186 episodes**. No AF-Inject, no
benign suite — neither bears on the contrast.

---

## 1. Which model, and what it needs

The requirements are narrow: a genuinely non-OpenAI lineage, **native structured tool
calling** with a vLLM parser, and a size that fits free-tier hardware.

| Model | Family | Weights (fp16) | Fits | vLLM parser | Verdict |
|---|---|---|---|---|---|
| **Qwen3-8B** | Alibaba, Apache-2.0 | ~16.4 GB | **2×T4 (Kaggle)** with `--tensor-parallel-size 2`; or one 16 GB card via the AWQ build | `hermes` | **Primary recommendation** |
| **Qwen3-4B** | Alibaba, Apache-2.0 | ~8 GB | single T4 / P100 / L4 | `hermes` | **Fallback** if the 8B is too slow or OOMs |
| **Llama-3.1-8B-Instruct** | Meta | ~16 GB | same as Qwen3-8B | `llama3_json` | **Second family**, if quota allows. Gated repo — needs an HF token and licence acceptance |
| Mistral-Small-24B | Mistral | ~48 GB | A100 40GB only (Colab Pro+) | `mistral` | Out of reach on free tiers |
| gpt-oss-20b | **OpenAI** | — | — | — | **Do not use.** Same lineage; answers nothing |
| qwen2.5-coder | Alibaba | — | — | — | **Do not use.** We measured it emitting tool calls as prose |

**Recommendation: start with Qwen3-8B on Kaggle's 2×T4.** It is the strongest
non-OpenAI open-weight tool-caller that fits a free tier, the licence is clean, and
tensor-parallel across two T4s avoids quantisation as a confound. If time allows
afterwards, add Llama-3.1-8B for a third family — two independent non-OpenAI families would
make the result much harder to dismiss.

**Hardware notes that will bite you.**

- **T4 is Turing.** No bfloat16 (use `--dtype float16`), no FlashAttention-2, and
  quantised kernels run without the fast Ampere paths. Expect it to be slow but correct.
- **Kaggle** gives 2×T4 or 1×P100 (16 GB), ~30 GPU-hours/week, sessions up to ~12 h.
  Internet must be enabled in the notebook settings (needs phone verification), or pip and
  the weight download will both fail.
- **Colab free** gives a single T4 — use **Qwen3-4B** there, or the AWQ build of the 8B.
  Colab Pro's L4 (22 GB, Ada) runs Qwen3-8B fp16 on one card and is markedly faster.
- **Runtime estimate: 30–90 minutes** for 186 episodes on 2×T4. This is a wide range on
  purpose; measure it with the pilot in step 5 rather than trusting it.

---

## 2. What you need before starting

- A Kaggle account with phone verification (for notebook internet), or Colab.
- This repository reachable from the notebook — either a public git URL, or uploaded as a
  Kaggle Dataset.
- For Llama only: a Hugging Face token and accepted licence on the model page.

Nothing else. No API keys — the model runs locally in the notebook.

---

## 3. Notebook cells, in order

### Cell 1 — check the GPU you actually got

```python
!nvidia-smi
```

Confirm the card and count before anything else. Kaggle sometimes hands out a P100 when
you asked for 2×T4, and that changes the model choice.

### Cell 2 — install

```python
!pip install -q vllm
!git clone https://github.com/<you>/agent-firewall-project.git repo
!pip install -q -e repo
```

(If you uploaded the repo as a Kaggle Dataset instead, point `-e` at
`/kaggle/input/<dataset-name>` and skip the clone.)

### Cell 3 — start the vLLM server in the background

Two T4s, Qwen3-8B:

```python
import subprocess, pathlib
log = open("vllm.log", "w")
subprocess.Popen([
    "vllm", "serve", "Qwen/Qwen3-8B",
    "--tensor-parallel-size", "2",
    "--dtype", "float16",
    "--max-model-len", "8192",
    "--gpu-memory-utilization", "0.90",
    "--enable-auto-tool-choice",
    "--tool-call-parser", "hermes",
    "--port", "8000",
], stdout=log, stderr=subprocess.STDOUT)
```

Single 16 GB card, Qwen3-4B: drop `--tensor-parallel-size` and use `Qwen/Qwen3-4B`.
Llama: `--tool-call-parser llama3_json` and `meta-llama/Llama-3.1-8B-Instruct`.

**`--enable-auto-tool-choice` plus the matching `--tool-call-parser` is the whole game.**
Without them vLLM returns tool calls as ordinary text.

### Cell 4 — wait for it to come up

```python
import time, urllib.request
for _ in range(120):
    try:
        urllib.request.urlopen("http://localhost:8000/v1/models", timeout=2)
        print("server up"); break
    except Exception:
        time.sleep(10)
else:
    print(open("vllm.log").read()[-4000:])
```

Model download plus load is typically 5–15 minutes on first run.

### Cell 5 — PREFLIGHT. Do not skip this.

```python
!cd repo && python -m agentfw.cli preflight \
    --base-url http://localhost:8000/v1 --model Qwen/Qwen3-8B
```

Four checks: a structured tool call comes back rather than prose, the right tool is named,
the arguments parse as JSON, and the server accepts a tool result on the next turn. It must
print `READY`. If it does not, the parser is wrong and **every episode would end at step
one and report a meaningless 0% overreach** — which is precisely the failure we already hit
locally with qwen2.5-coder. Fix it here, not after an hour of GPU time.

### Cell 6 — pilot: two scenarios, one seed

```python
!cd repo && AGENTFW_LOCAL_BASE_URL=http://localhost:8000/v1 python -m agentfw.cli run \
    experiments/e00c_openweight/config.yaml \
    --seeds 1 --filter af_auth.us.payments.cloudhost_due --workers 4
```

Three episodes. Confirm the tool-call lists in `results/episodes.jsonl` look like real
trajectories, then time it and multiply by 62 to sanity-check the full run against your
session limit.

### Cell 7 — the run

```python
!cd repo && AGENTFW_LOCAL_BASE_URL=http://localhost:8000/v1 python -m agentfw.cli run \
    experiments/e00c_openweight/config.yaml --workers 4
```

The runner is **resumable** — it skips episodes already in `episodes.jsonl`. If the session
dies, re-run the same cell and it continues. Raise `--workers` only after watching
`nvidia-smi`; vLLM batches internally, so more client threads mostly adds queueing.

### Cell 8 — get the results out

```python
!cd repo && tar czf /kaggle/working/e00c_results.tar.gz experiments/e00c_openweight/results
```

Download that file and unpack it into the repo at the same path. The report regenerates
offline with `agentfw report experiments/e00c_openweight/results`.

---

## 4. Reading the answer

```bash
agentfw compare "E-00b (OpenAI)=experiments/e00b_revised/results" \
                "E-00c (open-weight)=experiments/e00c_openweight/results"
```

| Outcome | Reading |
|---|---|
| Gap stays large and positive | The finding generalises across families. Phase 2 proceeds, and the thesis can drop the "on the models tested" hedge. |
| Gap collapses because **underspecified** overreach falls | The OpenAI models were unusually eager. The phenomenon is family-specific and the thesis needs narrowing again. |
| Gap collapses because **explicit-low** overreach rises | The 0% control result is an OpenAI post-training artefact, not a property of instruction-following. This would be the most interesting outcome and the one most worth writing up. |
| **Compliance below ~60%** | The model was not competent enough for its overreach rate to mean anything. Not evidence either way — switch model and re-run. |

That last row is a real risk with an 8B model and is why compliance is printed alongside
every rate rather than tucked away.

---

## 5. Recording the result

Append to `docs/EXPERIMENTS.md` under **E-00c**, where the prediction is already registered
in advance. Do not edit E-00 or E-00b (D-018 point 8) — they stand as historical runs and
reproduce at commits `00bca69` and `2133206`.
