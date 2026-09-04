# Source and protocol ledger

The prototype uses official Razorpay sources to define its integration boundary. The repository does not claim conformance beyond the documented, tested adapter behavior.

| Source | URL | Design fact used |
|---|---|---|
| Razorpay AI Buildathon | https://razorpay.com/buildathon/ | AI Finance Controller track; finance-loop, synthetic-record, accuracy/throughput/exception expectations |
| Razorpay API reference | https://razorpay.com/docs/api/ | REST/JSON and Basic Auth boundary |
| API authentication | https://razorpay.com/docs/api/authentication/ | test/live credential distinction and secret protection |
| Settlements API | https://razorpay.com/docs/api/settlements/ | settlement and reconciliation domain boundary |
| Settlement recon details | https://razorpay.com/docs/api/settlements/fetch-recon/ | combined recon entities, identifiers, UTR, and currency subunits |
| Webhook validation | https://razorpay.com/docs/webhooks/validate-test/ | raw-body HMAC-SHA256, event-ID deduplication, possible out-of-order delivery |
| Webhook best practices | https://razorpay.com/docs/webhooks/best-practices/ | asynchronous retries and at-least-once delivery behavior |
| About webhooks | https://razorpay.com/docs/webhooks/ | event-notification boundary |

## Source-handling rules

- Official documentation owns protocol and API statements.
- No external source manufactures a benchmark or evaluation metric.
- The committed generator and executable evaluation own every reported synthetic result.
- No Razorpay trademark, affiliation, production deployment, or merchant-data claim is implied.
