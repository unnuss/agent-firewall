# E-15b — learning curve: is it the data or the model?

**Sizing measurement, not a hypothesis test.** Nothing here selects a configuration,
a rung, a training size or an arm. E-15's published numbers stand unchanged.

Trained on nested subsamples of `dev` (86 examples, subsampled **by scenario**),
scored on the unchanged S1 test set (207 held-out variants).

## R1-tfidf

| train fraction | n examples | draws | contrast (mean) | min | max | retention |
|---|---|---|---|---|---|---|
| 25% | 20 | 5 |  17.0% |  13.6% |  25.8% |  20.0% |
| 50% | 41 | 5 |  24.9% |  15.2% |  33.3% |  29.1% |
| 75% | 65 | 5 |  32.1% |  25.8% |  39.4% |  37.6% |
| 100% | 86 | 1 |  39.4% |  39.4% |  39.4% |  45.5% |

**75% → 100% gain:   7.3%** (still rising)

## R3-finetuned

| train fraction | n examples | draws | contrast (mean) | min | max | retention |
|---|---|---|---|---|---|---|
| 25% | 20 | 3 |   5.6% |   4.5% |   7.6% |  51.5% |
| 50% | 41 | 3 |   7.6% |   6.1% |   9.1% |  62.1% |
| 75% | 65 | 3 |  16.7% |   9.1% |  28.8% |  68.7% |
| 100% | 86 | 1 |  25.8% |  25.8% |  25.8% |  78.8% |

**75% → 100% gain:   9.1%** (still rising)

