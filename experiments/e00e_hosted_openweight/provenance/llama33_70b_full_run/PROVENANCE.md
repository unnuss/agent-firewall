# E-00e provenance — no canonical result

**E-00e has no `results/` directory, and that is correct: it never produced an
interpretable run.** Both attempts failed the pre-registered 60% competency floor (D-019).
They are preserved because a replication programme that keeps only its successes is not
auditable.

| Artifact | Model | Episodes | Compliance | Verdict |
|---|---|---|---|---|
| `maverick_pilot/` | Llama 4 Maverick | 3 | 0/1 | pilot; correctly predicted the failure below |
| `maverick_attempt1/` | Llama 4 Maverick | 186 | **44.4% [29.2, 61.1]** | **INCONCLUSIVE** — floor is 60% |
| attempt 2 | Llama 3.3 70B | — | — | configured but never run |

The config names `meta-llama/llama-3.3-70b-instruct`; attempt 2 was prepared and then
overtaken by the decision to close Phase 1 on the cross-vendor result (D-022). Running it
later would write to a fresh `results/` without disturbing anything here.

## Why 44.4% is not a near-pass

The upper CI bound reaches 61.1%, which is the closest any non-OpenAI model came. It is
still not a pass. D-019 fixes the rule against the point estimate precisely so that a near
miss cannot be talked into one. Roughly 56% of high-authority episodes failed to produce the
contested effect when the user explicitly asked for it.

The directional signal was consistent with the Phase 1 finding — 24.4% underspecified versus
0.0% explicit-low — and does **not** count as replication. An agent that often fails to act
produces low rates everywhere, and the explicit-low denominator is exactly where
incapability and correct restraint are indistinguishable.

## What it contributed

The third point in the trend that made R-13 a live hypothesis: compliance 31.9% (Qwen3-8B) →
36.1% (Qwen3-14B-AWQ) → 44.4% (Maverick), rising with capability but still far short of the
81.2% and 91.7% reached by OpenAI and Anthropic frontier models on identical scenarios.
Whether that cliff is about the models or about our harness is unresolved.

Unlike E-00c and E-00d, this run's raw `episodes.jsonl` is preserved, so it recomputes.
