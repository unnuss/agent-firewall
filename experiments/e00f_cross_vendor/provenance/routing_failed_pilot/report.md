# E-00f — undefended

0 usable episodes of 3 run · 1 scenarios · models: claude-sonnet-5 · seeds: 1

Intervals are percentile bootstrap 95% CIs, resampled over **scenarios** (not episodes), because repeats of the same scenario are correlated.

## Headline

| Metric | All models | claude-sonnet-5 |
|---|---|---|
| **OR** — overreach rate, episode level (AF-Auth, low authority) | n/a (0/0) | n/a (0/0) |
| **Incidence** — scenarios with >=1 overreach | n/a (0/0) | n/a (0/0) |
| Compliance (AF-Auth, high authority) | n/a (0/0) | n/a (0/0) |
| **ASR** — attack success rate (AF-Inject) | n/a (0/0) | n/a (0/0) |
| **BTC** — benign task completion | n/a (0/0) | n/a (0/0) |
| BTC under attack (AF-Inject side task) | n/a (0/0) | n/a (0/0) |
| BTC (AF-Auth, low-authority half) | n/a (0/0) | n/a (0/0) |
| BTC (AF-Auth, high-authority half) | n/a (0/0) | n/a (0/0) |
| CuP (AF-Auth, both halves) | n/a (0/0) | n/a (0/0) |

## Uncertainty accounting (D-018 point 6)

- Reported interval, **clustered by scenario**: [nan, nan]
- Naive episode-level iid interval: [nan, nan]
- Width ratio (design effect): **nanx**

The naive figure is shown only for contrast and is never quoted as a result.
Seeds and models within one scenario are not independent observations, so an
episode-level bootstrap understates uncertainty by roughly that factor.

## Overreach by sub-family (AF-Auth, low-authority half)

| Family | OR | n |
|---|---|---|

## Per scenario (AF-Auth)

| Scenario | Fam | Overreach (low) | Compliance (high) | Task done low/high |
|---|---|---|---|---|

## Cost and latency

| Model | Episodes | Prompt tok | Completion tok | Tok/episode | Median latency | Median steps |
|---|---|---|---|---|---|---|

## Episode errors

| Error | Count |
|---|---|
| `ProviderError` | 3 |
