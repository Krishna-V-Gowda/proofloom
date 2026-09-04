# Evaluation protocol

## Question

Can a locally inspectable ranker increase safe straight-through settlement ownership beyond a reasonable exact-evidence baseline while deterministic financial constraints and abstention retain authority?

## Split discipline

The synthetic generator creates 24 merchant groups. The first 16 train the ranker, the next 4 choose thresholds, and the final 4 are touched once for reported evaluation. Identifier vocabularies are group-specific, preventing the same merchant narration patterns from crossing splits.

## Candidate-pair model

A standardized, class-balanced logistic regression uses amount, date, token, character, identifier-fragment, settlement-wording, and credit-direction features. Its candidate-classification threshold is selected on validation merchants under a precision constraint.

Pair metrics report precision, recall, F1, PR-AUC, ROC-AUC, Brier score, and 10-bin expected calibration error.

## Policy evaluation

Pair ranking and automated close policy are evaluated separately.

The deterministic baseline requires:

- incoming credit direction;
- exact settlement amount;
- booking within three days;
- exact significant settlement/UTR evidence.

The hybrid policy retains those deterministic amount/date/direction constraints, then adds the ranker for unresolved one-to-one candidates. Its probability threshold and top-vs-runner-up margin are selected on validation merchant groups from a predeclared grid, maximizing validation coverage subject to **zero validation false auto-matches**. Ties are resolved conservatively toward greater margin and probability.

The selected operating point is frozen before test evaluation.

## Stress slice

A separate slice includes only settlements whose generated true owner is labelled `damaged` or `ambiguous`. It demonstrates whether the system automates some difficult cases while preserving abstention—not whether those difficulty proportions reflect production.

## Uncertainty

Five hundred paired settlement-level bootstrap resamples estimate the distribution of the hybrid-minus-baseline straight-through-rate difference within the retained synthetic test population. This is not a confidence interval for live merchants.

## Economic sensitivity

Illustrative costs of INR 2,500 per false auto-match and INR 35 per review make the asymmetry explicit. These are assumptions for sensitivity analysis, not observed costs, savings, or ROI.

## Reproduce

```bash
make setup
make evaluate
```

The run writes `results.json`, `results.md`, `predictions.csv`, and the evaluation figure. The release validator regenerates the result in a temporary directory and compares semantic fields against the retained evidence.
