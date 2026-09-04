# Synthetic data generation methodology

## Hero fixture

`generate_hero_dataset(seed=20260903)` creates a fixed operational demonstration:

- 84 captured payments;
- 6 partial refunds;
- 4 settlements;
- 5 bank lines;
- 86 webhook deliveries;
- 185 records total.

The generator solves payment gross values so each settlement has a known expected net after refunds, fees, and tax. The fourth reported settlement is deliberately 137 paise below its independently calculated source composition.

The fixture also includes:

- one duplicate webhook event ID;
- one event whose occurrence order differs from delivery order;
- one damaged bank reference;
- one exact two-credit split;
- one unrelated bank credit.

## Evaluation fixture

`generate_evaluation_dataset(seed=20260920)` creates:

- 24 merchant groups;
- 42 settlements per group;
- 6 candidates per settlement;
- 6,048 pair rows total;
- exactly one generated true owner per settlement.

The split is fixed at 16 train / 4 validation / 4 test merchant groups. Merchant-specific identifier vocabularies do not cross the split.

Difficulty types include exact references, damaged references, ambiguous narrations, amount/date hard negatives, and near-twin negatives. Near twins deliberately create cases where observable evidence is almost indistinguishable; the intended behavior is abstention when the top-vs-runner-up margin collapses.

## What the data cannot establish

The generator is a controlled test instrument—not a sample of live merchant statements. It cannot establish field prevalence, bank narration coverage, merchant accuracy, financial savings, or production return on investment. Generated labels are not independently adjudicated by finance operators.
