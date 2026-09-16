# Source and protocol ledger

Proofloom documents protocol assumptions and external technical concepts separately from its own executable
implementation and evaluation. External references do not manufacture any benchmark or evaluation metric.

| Source area | Design fact used |
|---|---|
| Payment settlement/reconciliation protocols | settlement identifiers, reconciliation entities, and currency subunits |
| Webhook delivery protocols | raw-body signature verification, event-ID deduplication, and possible out-of-order delivery |
| Reliable integration patterns | asynchronous retries and at-least-once delivery behavior |

## Source-handling rules

- External technical references support protocol and API-design statements.
- No external source manufactures a benchmark or evaluation metric.
- The committed generator and executable evaluation own every reported synthetic result.
- Proofloom does not claim production deployment or merchant-data access.
