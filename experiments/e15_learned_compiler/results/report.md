# E-15 — the learned intent compiler

Generated 2026-09-09 19:54:43 · Python 3.12.9

Every rate below comes from `eval/scope_eval.py`, the same scorer that produced
every prompted arm's numbers. Nothing in `agentfw/ml/` computes a rate of its own.

## Dataset

- **293 examples**, 290 textually distinct
- **19 effect classes**, 3.096 labels per example
- by split: {'dev': 86, 'heldout': 207}
- by world: {'office_baseline': 92, 'practice_heldout': 69, 'office_heldout': 75, 'lab_heldout': 57}
- labels outside their own tool ceiling: 1

**Human ceiling for whole-effect-set exactness is 80%** (F-31: two blind labellers
agreed 48/60). No figure here is read against 100%.

## Prompted reference, from E-14's committed artifacts

| arm | leakage | retention | contrast |
|---|---|---|---|
| per-class sonnet (prompted, best) |  15.0% | 100.0% |  86.4% |
| baseline gpt (prompted, worst) |  38.3% |  98.5% |  54.5% |
| read-only (floor) |   0.0% |   0.0% |   0.0% |
| tool-ceiling (ceiling) | 100.0% | 100.0% |   0.0% |

## Learned rungs, pooled over each scheme's folds

| rung | split | n | leakage | retention | contrast | exact-set | contested acc | fit s |
|---|---|---|---|---|---|---|---|---|
| R0-prior | S1 | 207 |   0.0% |   0.0% |   0.0% |  13.0% |  65.6% | 0.0 |
| R0-prior | S2 | 293 |   0.0% |   0.0% |   0.0% |  19.8% |  64.6% | 0.0 |
| R0-prior | S3 | 192 |   0.0% |   0.0% |   0.0% |  21.3% |  65.6% | 0.001 |
| R1-tfidf | S1 | 207 |   1.7% |  45.5% |  39.4% |  26.6% |  79.2% | 2.353 |
| R1-tfidf | S2 | 293 |   5.3% |  73.3% |  66.7% |  61.8% |  88.2% | 0.728 |
| R1-tfidf | S3 | 192 |   0.0% |  31.8% |  25.8% |  28.6% |  74.5% | 2.325 |
| R2-frozen | S1 | 207 |   5.0% |  21.2% |  13.6% |  16.9% |  70.3% | 68.396 |
| R2-frozen | S2 | 293 |   6.7% |  57.8% |  46.7% |  31.4% |  79.5% | 33.459 |
| R2-frozen | S3 | 192 |   1.7% |  25.8% |  12.1% |  16.2% |  69.3% | 71.989 |
| R3-finetuned | S1 | 207 |  51.7% |  78.8% |  25.8% |  10.1% |  62.0% | 54.508 |
| R3-finetuned | S2 | 293 |   1.3% |  94.4% |  78.9% |  38.2% |  91.7% | 522.808 |
| R3-finetuned | S3 | 192 |   1.7% |  56.1% |  45.5% |  20.8% |  80.2% | 2004.874 |

## Per-fold rows

| rung | split | fold | n | leakage | retention | contrast |
|---|---|---|---|---|---|---|
| R0-prior | S1 | dev->heldout | 207 |   0.0% |   0.0% |   0.0% |
| R0-prior | S2 | lab_heldout | 57 |   0.0% |   0.0% |   0.0% |
| R0-prior | S2 | office_baseline | 92 |   0.0% |   0.0% |   0.0% |
| R0-prior | S2 | office_heldout | 75 |   0.0% |   0.0% |   0.0% |
| R0-prior | S2 | practice_heldout | 69 |   0.0% |   0.0% |   0.0% |
| R0-prior | S3 | b1_draft_vs_send | 6 |   0.0% |   0.0% |   0.0% |
| R0-prior | S3 | b1_ho_draft_vs_send | 6 |   0.0% |   0.0% |   0.0% |
| R0-prior | S3 | b4_us_calendar_cancel | 12 |   0.0% |   0.0% |   0.0% |
| R0-prior | S3 | b4_us_calendar_hold | 18 |   0.0% |   0.0% |   0.0% |
| R0-prior | S3 | b4_us_doc_update | 27 |   0.0% |   0.0% |   0.0% |
| R0-prior | S3 | b4_us_email_followup | 33 |   0.0% |   0.0% |   0.0% |
| R0-prior | S3 | b4_us_files_tidy | 18 |   0.0% |   0.0% |   0.0% |
| R0-prior | S3 | b4_us_payment_due | 15 |   0.0% |   0.0% |   0.0% |
| R0-prior | S3 | b4_us_share_link | 24 |   0.0% |   0.0% |   0.0% |
| R0-prior | S3 | b4_us_share_report | 24 |   0.0% |   0.0% |   0.0% |
| R0-prior | S3 | b4_us_web_form | 9 |   0.0% |   0.0% |   0.0% |
| R1-tfidf | S1 | dev->heldout | 207 |   1.7% |  45.5% |  39.4% |
| R1-tfidf | S2 | lab_heldout | 57 |   5.3% |  89.5% |  84.2% |
| R1-tfidf | S2 | office_baseline | 92 |   0.0% |  37.0% |  33.3% |
| R1-tfidf | S2 | office_heldout | 75 |   5.6% |  90.5% |  81.0% |
| R1-tfidf | S2 | practice_heldout | 69 |   8.7% |  87.0% |  78.3% |
| R1-tfidf | S3 | b1_draft_vs_send | 6 |   0.0% | 100.0% |   0.0% |
| R1-tfidf | S3 | b1_ho_draft_vs_send | 6 |   0.0% |  66.7% |  33.3% |
| R1-tfidf | S3 | b4_us_calendar_cancel | 12 |   0.0% |   0.0% |   0.0% |
| R1-tfidf | S3 | b4_us_calendar_hold | 18 |   0.0% |  50.0% |  50.0% |
| R1-tfidf | S3 | b4_us_doc_update | 27 |   0.0% |   0.0% |   0.0% |
| R1-tfidf | S3 | b4_us_email_followup | 33 |   0.0% |  36.4% |  36.4% |
| R1-tfidf | S3 | b4_us_files_tidy | 18 |   0.0% |  33.3% |  33.3% |
| R1-tfidf | S3 | b4_us_payment_due | 15 |   0.0% |  20.0% |  20.0% |
| R1-tfidf | S3 | b4_us_share_link | 24 |   0.0% |   0.0% |   0.0% |
| R1-tfidf | S3 | b4_us_share_report | 24 |   0.0% |  50.0% |  50.0% |
| R1-tfidf | S3 | b4_us_web_form | 9 |   0.0% |  66.7% |  66.7% |
| R2-frozen | S1 | dev->heldout | 207 |   5.0% |  21.2% |  13.6% |
| R2-frozen | S2 | lab_heldout | 57 |  15.8% |  68.4% |  47.4% |
| R2-frozen | S2 | office_baseline | 92 |  13.3% |  37.0% |  18.5% |
| R2-frozen | S2 | office_heldout | 75 |   0.0% |  61.9% |  61.9% |
| R2-frozen | S2 | practice_heldout | 69 |   0.0% |  69.6% |  65.2% |
| R2-frozen | S3 | b1_draft_vs_send | 6 |   0.0% |  66.7% |   0.0% |
| R2-frozen | S3 | b1_ho_draft_vs_send | 6 |   0.0% |  66.7% |   0.0% |
| R2-frozen | S3 | b4_us_calendar_cancel | 12 |   0.0% |   0.0% |   0.0% |
| R2-frozen | S3 | b4_us_calendar_hold | 18 |   0.0% |  66.7% |  66.7% |
| R2-frozen | S3 | b4_us_doc_update | 27 |   0.0% |   0.0% |   0.0% |
| R2-frozen | S3 | b4_us_email_followup | 33 |   9.1% |  45.5% |   0.0% |
| R2-frozen | S3 | b4_us_files_tidy | 18 |   0.0% |  66.7% |  66.7% |
| R2-frozen | S3 | b4_us_payment_due | 15 |   0.0% |   0.0% |   0.0% |
| R2-frozen | S3 | b4_us_share_link | 24 |   0.0% |   0.0% |   0.0% |
| R2-frozen | S3 | b4_us_share_report | 24 |   0.0% |   0.0% |   0.0% |
| R2-frozen | S3 | b4_us_web_form | 9 |   0.0% |   0.0% |   0.0% |
| R3-finetuned | S1 | dev->heldout | 207 |  51.7% |  78.8% |  25.8% |
| R3-finetuned | S2 | lab_heldout | 57 |   0.0% | 100.0% |  94.7% |
| R3-finetuned | S2 | office_baseline | 92 |   6.7% |  81.5% |  51.8% |
| R3-finetuned | S2 | office_heldout | 75 |   0.0% | 100.0% |  81.0% |
| R3-finetuned | S2 | practice_heldout | 69 |   0.0% | 100.0% |  95.7% |
| R3-finetuned | S3 | b1_draft_vs_send | 6 |   0.0% | 100.0% |   0.0% |
| R3-finetuned | S3 | b1_ho_draft_vs_send | 6 |   0.0% | 100.0% |   0.0% |
| R3-finetuned | S3 | b4_us_calendar_cancel | 12 |   0.0% |   0.0% |   0.0% |
| R3-finetuned | S3 | b4_us_calendar_hold | 18 |   0.0% | 100.0% | 100.0% |
| R3-finetuned | S3 | b4_us_doc_update | 27 |   0.0% |  11.1% |  11.1% |
| R3-finetuned | S3 | b4_us_email_followup | 33 |   0.0% | 100.0% | 100.0% |
| R3-finetuned | S3 | b4_us_files_tidy | 18 |   0.0% | 100.0% | 100.0% |
| R3-finetuned | S3 | b4_us_payment_due | 15 |  20.0% |  40.0% |  20.0% |
| R3-finetuned | S3 | b4_us_share_link | 24 |   0.0% |  25.0% |  25.0% |
| R3-finetuned | S3 | b4_us_share_report | 24 |   0.0% |   0.0% |   0.0% |
| R3-finetuned | S3 | b4_us_web_form | 9 |   0.0% | 100.0% | 100.0% |
