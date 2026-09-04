# Threat model

## Assets

- correctness of financial facts and invariant outcomes;
- integrity of close decisions and human approvals;
- idempotency of event handling;
- confidentiality of optional credentials and merchant evidence;
- reproducibility and provenance of published evaluation results.

## Trust boundaries

1. external processor/webhook payload → adapter;
2. imported settlement/bank evidence → immutable domain model;
3. model score → deterministic policy;
4. reviewer request → human-authority boundary;
5. runtime state → audit chain;
6. committed synthetic evidence → public reviewer.

## Principal threats and controls

| Threat | Prototype control | Residual risk |
|---|---|---|
| duplicate webhook creates duplicate decision | event-ID deduplication and test | durable idempotency store is absent |
| delivery order interpreted as event truth | normalization by occurrence time | clock/source semantics require production contracts |
| model assigns wrong owner | exact amount/date/direction gates, score margin, abstention, review | synthetic calibration may not transfer |
| model repairs a broken settlement | composition is evaluated before ranking; failed invariant blocks | upstream facts can still be incomplete or wrong |
| reviewer edits financial amount | facts are immutable; mismatched requested amount is rejected and audited | production identity/RBAC absent |
| live credential committed | `.env` excluded, test-key guard, source scanner | scanner is not exhaustive |
| forged webhook | raw-body HMAC-SHA256 verification | secret rotation/replay-window controls absent |
| audit history mutated | hash-chain verification identifies first changed link | truncation needs trusted external head; storage is in memory |
| cross-tenant access | no real tenants or merchant data in prototype | production tenant isolation not implemented |
| benchmark overclaim | raw repetitions, environment and scope retained | local workload does not predict production capacity |

## Out of scope

Real-money execution, production accounting, authorization infrastructure, regulatory compliance, penetration testing, service availability, disaster recovery, and formal verification.
