# E-15c — calibrating R3 inside the training split

Selection used **out-of-fold probabilities on the 86 training examples only**,
grouped 5-fold by scenario. Held-out was read **once**, after the
configuration below was frozen and written to disk.

## The frozen configuration

- **positive-weight cap: 50.0** (searched (1.0, 5.0, 10.0, 50.0), E-15's blind value was 50.0)
- out-of-fold contrast fidelity:  45.8%
- out-of-fold leakage  20.0%, retention  70.8%

| cap | OOF contrast |
|---|---|
| 1.0 |  16.7% |
| 5.0 |  29.2% |
| 10.0 |  20.8% |
| 50.0 |  45.8% |

### Per-class thresholds

| effect class | cut |
|---|---|
| `GRANT:CLOUD_STORAGE` | 0.95 |
| `SEND:PUBLIC_WEB` | 0.95 |
| `PURCHASE:FINANCIAL` | 0.70 |
| `CREATE:CLOUD_STORAGE` | 0.65 |
| `DELETE:USER_FILES` | 0.65 |
| `WRITE:USER_FILES` | 0.65 |
| `READ:CLOUD_STORAGE` | 0.60 |
| `READ:PUBLIC_WEB` | 0.60 |
| `CREATE:CALENDAR` | 0.55 |
| `CREATE:USER_FILES` | 0.55 |
| `READ:FINANCIAL` | 0.55 |
| `SEND:EMAIL` | 0.55 |
| `READ:CALENDAR` | 0.50 |
| `READ:CONTACTS` | 0.50 |
| `DELETE:CALENDAR` | 0.45 |
| `GRANT:USER_FILES` | 0.45 |
| `CREATE:EMAIL` | 0.40 |
| `READ:USER_FILES` | 0.40 |
| `READ:EMAIL` | 0.35 |

## Held-out, read once

| | E-15 R3 (blind) | E-15c R3 (calibrated) |
|---|---|---|
| leakage | 51.7% | ** 31.7%** |
| retention | 78.8% | ** 48.5%** |
| contrast fidelity | 25.8% | ** 13.6%** |
| exact-set match | 10.1% |  11.6% |

Reference: `per-class` sonnet 15.0% / 100% / 86.4%; R1 TF-IDF 1.7% / 45.5% / 39.4%.

