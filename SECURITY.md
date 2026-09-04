# Security policy

Proofloom is a synthetic local prototype, not a production settlement or accounting system. Do not use it with real credentials, merchant data, bank statements, or payment instructions.

Report suspected vulnerabilities privately to the repository owner. Do not include secrets or personal data in a public issue.

## Implemented boundaries

- all financial equality uses integer paise;
- optional Razorpay credentials are environment-only and test keys are enforced;
- raw-body HMAC-SHA256 webhook verification is implemented;
- duplicate event IDs are suppressed and event occurrence time is normalized;
- model output cannot alter financial facts or bypass deterministic invariants;
- uncertain cases abstain or require named human review;
- audit entries form a verifiable SHA-256 hash chain;
- committed source and release artifacts are scanned for high-confidence secret patterns.

## Deliberately not claimed

Production authentication, authorization, durable tenant isolation, encrypted persistence, rate limiting, externally anchored append-only storage, accounting certification, regulatory compliance, and incident-response operations are outside this prototype.
