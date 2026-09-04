# Proofloom evaluation results

## Executive result

On a merchant-group-held-out synthetic benchmark containing **168 settlements / 1,008 candidate pairs**, the local ranker achieved **99.2% precision**, **72.0% recall**, and **0.974 PR-AUC** at a threshold selected only on validation merchant groups.

At the policy level, the deterministic exact-evidence baseline auto-matched **70.2%** of settlements at **100.0% precision**. The hybrid policy auto-matched **76.8%** at **100.0% precision**, leaving **39** cases for review and producing **0** false auto-matches in this synthetic test set. Its automation threshold (**0.60**) and minimum score margin (**0.12**) were selected on validation merchants only, subject to zero validation false auto-matches.

## Held-out candidate-pair model

| Metric | Result |
|---|---:|
| Precision | 0.9918 |
| Recall | 0.7202 |
| F1 | 0.8345 |
| PR-AUC | 0.9738 |
| ROC-AUC | 0.9948 |
| Brier score | 0.0265 |
| 10-bin ECE | 0.0336 |
| Threshold | 0.9847 |

## Policy comparison

| Policy | Auto precision | Straight-through | Review queue | False auto-matches | Illustrative operating cost |
|---|---:|---:|---:|---:|---:|
| Deterministic exact-evidence baseline | 100.0% | 70.2% | 50 | 0 | INR 1,750 |
| Proofloom hybrid | 100.0% | 76.8% | 39 | 0 | INR 1,365 |

The bootstrap median straight-through-rate delta is **+6.5%** with a synthetic resampling interval of **[+3.0%, +10.7%]**. This interval describes the retained synthetic test population; it is not a confidence interval for live merchants.

## Stress slice

The damaged/ambiguous-only slice contains **50** settlements. The hybrid policy auto-matched **22.0%** at **100.0% precision**, with **0** false auto-matches and **39** reviews.

## What is and is not claimed

- Merchant identifiers and narration vocabularies do not cross the train, validation and test groups.
- The deterministic baseline is a reasonable exact-evidence join, not an intentionally weak straw man.
- The model ranks candidates; exact money conservation, credit direction, booking windows, thresholds and human review remain deterministic controls.
- All records and labels are synthetic. The result is reproducible engineering evidence—not production merchant accuracy, recovered money, savings, ROI, or regulatory assurance.
- The illustrative cost model uses INR 2,500 per false auto-match and INR 35 per review.

## Reproduce

```bash
make setup
make evaluate
```

Raw predictions are retained in `predictions.csv`; the complete machine-readable result is in `results.json`.
