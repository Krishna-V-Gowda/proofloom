# Demo runbook

## Start

```bash
make setup
make run
```

Open `http://127.0.0.1:8000`.

## Ninety-second technical path

1. Select **Run daily close**.
2. Note the fixed 185-record source inventory and the four decisions.
3. Open `set_demo_01`: exact evidence and all deterministic invariants pass.
4. Open `set_demo_03`: two bank credits prove the exact split sum.
5. Open `set_demo_02`: model-ranked evidence remains under human authority; approve it without changing the amount.
6. Open `set_demo_04`: expected ₹37,178.14, reported ₹37,176.77, delta ₹1.37; the close is blocked.
7. Run **Take the model offline**: exact/split paths remain available and ambiguity abstains.
8. Run **Tamper with evidence**: the copied chain fails at the first altered link while the live chain remains valid.

## Deterministic browser capture

The UI supports:

- `/?autorun=1` — run the hero close automatically;
- `/?autorun=1&packet=set_demo_04` — run and open the blocked proof packet.

## Reset

Select **Reset deterministic demo**. The same seed, source records, decisions, and initial proof behavior are restored.
