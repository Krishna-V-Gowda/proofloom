# Proofloom: verification-first settlement close

## Abstract

Proofloom is a synthetic, executable prototype for settlement close under damaged identifiers and asynchronous event delivery. Its central design decision is to separate **evidence ranking** from **financial authority**. A local logistic model may rank ambiguous settlement-bank pairs, but integer-paise invariants, explicit policy gates, and named human review decide whether a close is permitted. The retained demonstration contains 185 source records and deliberately blocks a settlement whose independently computed source net differs from the reported amount by 137 paise. A merchant-group-held-out synthetic benchmark shows the hybrid policy increasing straight-through coverage from 70.24% to 76.79% with zero false auto-matches in the retained test set; the result is explicitly bounded to the generator and does not establish production accuracy.

## 1. Problem

Settlement reconciliation is often described as matching a processor record to a bank credit. That is incomplete. A safe close also requires source composition, event ordering, direction, amount, time, ownership, exception, and authority evidence to agree.

Similarity is useful when identifiers are damaged, but similarity cannot make an inconsistent financial fact true. Proofloom therefore treats the close decision as a proof-carrying workflow rather than a model output.

## 2. Contributions

1. **Authority separation.** Deterministic controls, model ranking, policy, human review, and audit have distinct capabilities.
2. **Integer-paise invariants.** Financial equality never uses floating-point arithmetic or tolerance-based reconciliation.
3. **Inspectable operational demonstration.** Four settlements exercise exact, split, review, and blocked paths across 185 synthetic records.
4. **Failure laboratory.** Duplicate delivery, out-of-order events, model outage, unsafe adjustment, and audit tampering are reproducible.
5. **Merchant-group-held-out evaluation.** Candidate ranking and policy automation are measured separately; thresholds are selected only on validation groups.
6. **Claim discipline.** Synthetic results, illustrative cost assumptions, in-memory architecture, and missing field validation are explicit.

## 3. Hero workflow

The fixed seed creates 84 payments, 6 refunds, 4 settlements, 5 bank lines, and 86 webhook deliveries.

- `set_demo_01` has exact reference and amount evidence and auto-matches.
- `set_demo_02` has a damaged reference. The ranker proposes one bank line; conservative operator policy requires human confirmation.
- `set_demo_03` is represented by two credits whose exact sum and shared evidence prove ownership.
- `set_demo_04` has a reported amount of ₹37,176.77 but a payment/refund/fee/tax composition of ₹37,178.14. The 137-paise contradiction blocks the settlement before bank ownership is considered.

One duplicate webhook is suppressed, one delivery arrives out of occurrence order, and one unrelated bank credit remains unowned.

## 4. Model and policy

The model is a standardized, class-balanced logistic regression. Features encode amount similarity/equality, booking-date distance, token overlap, character similarity, identifier fragments, settlement wording, and credit direction. A simple local model was preferred over an LLM because the task is structured, the evidence must be inspectable, the demo must run without an external provider, and the model has no linguistic generation requirement.

Pair classification and policy automation are separate operating problems:

- the pair threshold is selected on validation merchants under a precision constraint;
- policy searches a predeclared probability/margin grid;
- the chosen policy point maximizes validation coverage subject to zero validation false auto-matches;
- amount, direction, date, source composition, and separation margin remain deterministic constraints.

## 5. Evaluation

The generator produces 24 merchant groups × 42 settlements × 6 candidates. Groups are fixed into 16 train, 4 validation, and 4 test. The held-out test therefore contains 168 settlements and 1,008 pairs.

### 5.1 Candidate-pair result

| Metric | Result |
|---|---:|
| Precision | 0.9918 |
| Recall | 0.7202 |
| F1 | 0.8345 |
| PR-AUC | 0.9738 |
| ROC-AUC | 0.9948 |
| Brier score | 0.0265 |
| 10-bin ECE | 0.0336 |

### 5.2 Policy result

| Policy | Auto precision | Straight-through | Reviews | False auto-matches |
|---|---:|---:|---:|---:|
| Exact-evidence baseline | 1.000 | 0.7024 | 50 | 0 |
| Proofloom hybrid | 1.000 | 0.7679 | 39 | 0 |

The hybrid policy automatically owns 11 additional damaged-reference cases. On the 50-case damaged/ambiguous stress slice, it automates 11 and abstains on 39. Five hundred paired settlement-level bootstrap resamples yield a median straight-through increase of 0.0655, with a retained synthetic interval of [0.0298, 0.1071].

The result is evidence about this controlled generator. It does not establish production merchant accuracy or the prevalence of each difficulty mode.

## 6. Failure analysis

### Duplicate delivery

A repeated event ID is counted and ignored. No duplicate close decision is created.

### Model outage

The model is disabled. Exact and split paths continue; ambiguous evidence stays unresolved. Availability is not allowed to become permissiveness.

### Unsafe human adjustment

A reviewer attempts to approve evidence with an amount changed by 100 paise. The operation is rejected, the original decision remains, and the attempt is audited.

### Audit mutation

An isolated historical payload is changed. Verification returns the first invalid sequence while the live chain remains valid.

### False tie-out

The 137-paise source contradiction is blocked before candidate ownership, demonstrating that similarity cannot repair financial truth.

## 7. Performance boundary

The retained local environment measured approximately 15,120 candidate pairs/s for the 1,008-pair scoring batch, a 1.64 ms median for the in-memory four-settlement close core, and a 1.47 ms median for an in-process overview request. These numbers include local process behavior and exclude production networking, persistence, browser rendering, multi-tenancy, and operational controls.

## 8. Security boundary

The prototype contains synthetic data only. Optional Razorpay adapter credentials are environment-only; non-test-looking key IDs are rejected. Webhook signatures use raw-body HMAC-SHA256 and constant-time comparison. The public tree is scanned for high-confidence credentials and private keys.

Authentication, authorization, durable tenant isolation, encrypted storage, rate limiting, externally anchored audit storage, regulatory certification, and production incident response are not implemented.

## 9. Limitations and next work

Field evaluation requires real, permissioned, independently adjudicated statement/settlement cases. Production architecture also needs durable transactions, policy versioning, dual-control overrides, correction workflows, bank/ledger confirmation, drift monitoring, multi-currency semantics, and external audit-head anchoring.

The next research question is not “can a larger model score higher?” It is whether merchant-specific adaptation can increase difficult-case coverage without eroding calibrated abstention or creating an unacceptable false-auto-match cost.

## 10. Reproduction

```bash
make setup
make validate
make run
```

The complete generator, tests, predictions, raw metrics, figures, benchmark repetitions, hero result, failure outputs, and audit snapshot are committed.
