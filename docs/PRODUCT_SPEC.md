# Product Specification - Proofloom

## 1. Product thesis

Proofloom is a verification-first settlement-close workspace for merchant finance operators. It combines exact reconciliation, limited ambiguity ranking, deterministic financial controls, explicit human authority and tamper-evident evidence so a settlement closes only when the system can show why the match is safe.

## 2. Target user and stakeholder

- **Primary user:** Finance controller or reconciliation analyst responsible for daily merchant cash close.
- **Secondary user:** Payments operations engineer investigating event or integration failures.
- **Buyer/stakeholder:** Finance leader, payments product owner, internal audit/control owner.
- **Reviewer in this submission:** Razorpay engineer/product leader assessing AI judgment and execution.

## 3. Current workflow

A finance operator typically needs to connect:

1. captured payments;
2. refunds and adjustments;
3. fees and tax;
4. processor settlement records;
5. bank credits;
6. payment and settlement events;
7. exceptions and reviewer decisions.

Exact identifiers often resolve the easy majority. The remaining tail contains damaged references, split credits, duplicate/out-of-order events and records that should never be forced to match.

## 4. Pain and economic consequence

The difficult question is not “which row looks similar?” It is “is the evidence sufficient to permit the close?” A false auto-match can hide missing cash or create an incorrect accounting state. Excessive abstention creates manual workload and delays close. The product must therefore optimize precision and review workload together, not maximize match count.

## 5. Existing alternatives and remaining gap

Alternatives include manual spreadsheets, exact joins, fuzzy matching, reconciliation reports and conversational statement matching. These can surface a candidate but often leave five controls implicit:

- source composition;
- paise-level money conservation;
- direction and booking-window validity;
- calibrated abstention;
- replayable decision provenance.

Proofloom treats these controls as the product boundary.

## 6. Hero workflow

A deterministic synthetic merchant contains four settlements:

| Case | Evidence condition | Expected behavior |
|---|---|---|
| Exact | UTR, amount and date align | Auto-match after all invariants pass. |
| Damaged reference | One UTR character is missing and settlement text is distorted | Local model ranks a candidate; medium confidence forces human review. |
| Split credit | Two bank credits share evidence and sum exactly | Deterministic split-sum auto-match. |
| Composition break | Reported settlement differs from computed source net by 137 paise | Block before bank matching; expose critical exception. |

The event stream also contains one duplicate webhook and one out-of-order authorization event.

## 7. User stories

- As a controller, I can run the close and see matched, review and unresolved counts.
- As a controller, I can inspect the evidence and invariant checks behind every decision.
- As a controller, I can approve or reject an ambiguous candidate but cannot alter the amount to manufacture agreement.
- As an operator, I can see exactly which records remain unowned or contradictory.
- As an engineer, I can replay duplicate, model-outage, unsafe-adjustment and audit-tamper failures.
- As an auditor, I can verify that historical entries form a valid hash chain.
- As a reviewer, I can reproduce the benchmark and understand what AI does and does not control.

## 8. Non-goals

- Moving real money or writing accounting entries.
- Claiming production merchant accuracy or regulatory certification.
- Replacing a general ledger, bank feed, data warehouse or Razorpay Dashboard.
- Using an LLM as a universal reconciliation engine.
- Hiding unresolved cases to maximize a vanity match rate.
- Supporting every bank format, currency or settlement product in the first wedge.

## 9. Functional requirements

### Evidence intake

- Represent payments, refunds, settlements, bank lines and webhooks with typed domain objects.
- Preserve currency subunits as integers.
- Export deterministic CSV/JSON fixtures from fixed seeds.

### Event truth

- Deduplicate by event ID and identical payload semantics.
- Normalize event order by occurrence time rather than delivery order.
- Record duplicate and out-of-order counts.

### Matching

- Resolve exact UTR or settlement-reference matches first.
- Resolve safe two-line split matches when references and sum prove ownership.
- Score one-to-one ambiguous candidates with a local model.
- Compute confidence band and top-vs-second score margin.

### Policy and close

- Prove payment/refund/fee/tax composition.
- Prove exact money conservation in paise.
- Require incoming-credit direction.
- Enforce a configurable booking window.
- Auto-match only above precision-oriented confidence and margin gates.
- Route uncertainty to review; block contradiction.
- Prevent a reviewer from modifying expected or observed financial facts.

### Audit and failure recovery

- Append an event for every consequential state change.
- Hash each entry with the previous hash.
- Verify the entire chain and report the first failed sequence.
- Demonstrate model outage, duplicate replay, unsafe adjustment and isolated tamper detection.

### Evaluation

- Split synthetic data by merchant group.
- Select threshold on validation merchants only.
- Report pair metrics and end-policy metrics.
- Compare with a deterministic baseline.
- Run sensitivity and local throughput measurements.

## 10. Reliability requirements

- Same seed produces the same entities, labels and evaluation metrics.
- A model outage must never convert ambiguity into auto-approval.
- Duplicate delivery must not create a duplicate decision.
- A contradiction in source composition must block the close before fuzzy matching.
- The app must run without network access or model-provider credentials.
- Material failures must be visible and auditable rather than silently dropped.

## 11. Security and privacy requirements

- Synthetic demo data only; no customer identifiers or bank statements.
- No real or live API key accepted by the adapter.
- Webhook verification uses raw-body HMAC-SHA256 and constant-time comparison.
- Secrets loaded from environment variables and excluded from source.
- Inputs bounded through typed API models.
- Logs and exported evidence avoid credentials.
- This prototype makes no compliance or certification claim.

## 12. Evaluation criteria and success metrics

| Dimension | Metric / acceptance |
|---|---|
| Correctness | All behavior tests pass; invariants block the 137-paise contradiction. |
| Batch bar | At least 50 synthetic records; hero has 185. |
| Pair ranking | Precision, recall, F1, PR-AUC, Brier and ECE on held-out merchants. |
| Close policy | Auto precision, straight-through rate, false auto-matches and review queue. |
| Baseline | Deterministic exact-rule policy using the same held-out settlement groups. |
| Reliability | Failure scenarios detected with safe degradation and audit evidence. |
| Performance | Reproducible model-scoring, close-core and API latency measurements. |
| Audit | Chain verifies after run and review; isolated tampering is detected. |

## 13. System boundary

Proofloom consumes official-shaped/synthetic evidence and produces close decisions and proof packets. It does not post a settlement, journal, payout, refund or bank instruction. The optional Razorpay adapter defines how authenticated test-mode reads and webhook verification fit the architecture, while the shipped demo remains credentials-free.

## 14. Assumptions

- INR amounts are represented in paise.
- One settlement currency and one merchant are used in the hero flow.
- Bank credits occur within a three-day window for safe matching.
- A human reviewer has legitimate authority and authenticated identity in a production implementation.
- Synthetic label-generation rules are documented and separated by merchant group.

## 15. Limitations

- Generated statement text is less diverse than live bank narration.
- The one-to-one model benchmark does not measure split-settlement search; split behavior is tested in integration tests.
- Audit persistence is in memory for the demo.
- Authentication and role-based access are deployment concerns not implemented in local mode.
- Economics are illustrative assumptions, not observed merchant costs.
