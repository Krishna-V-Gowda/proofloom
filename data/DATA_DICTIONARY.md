# Data dictionary

All committed records are deterministic synthetic fixtures. Currency values are integer **paise**.

| Entity | Principal fields | Meaning |
|---|---|---|
| Payment | `payment_id`, `settlement_id`, `amount_paise`, `fee_paise`, `tax_paise`, `captured_at`, `status` | captured payment evidence allocated to a settlement |
| Refund | `refund_id`, `payment_id`, `settlement_id`, `amount_paise`, `created_at` | partial refund linked to a captured payment |
| Settlement | `settlement_id`, `reported_amount_paise`, `utr`, `settled_on`, `currency` | processor-reported settlement fact |
| Bank line | `bank_line_id`, `amount_paise`, `direction`, `booked_on`, `reference` | synthetic statement evidence that may or may not own a settlement |
| Webhook delivery | `event_id`, `event_type`, `entity_id`, `occurred_at`, `delivered_at`, `payload_digest` | at-least-once asynchronous event delivery evidence |
| Evaluation pair | merchant/group IDs, settlement/bank fields, label, difficulty | one generated settlement-candidate pair used for model evaluation |

See [`GENERATION_METHODOLOGY.md`](GENERATION_METHODOLOGY.md) for split, difficulty, and limitation details.
