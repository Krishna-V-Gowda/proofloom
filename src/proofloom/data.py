"""Deterministic synthetic evidence for the Proofloom demonstrator."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import random
from typing import Iterable, Sequence

from .domain import BankLine, Direction, HeroDataset, Payment, Refund, Settlement, WebhookDelivery, to_primitive

HERO_SEED = 20260903
HERO_PERIOD = date(2026, 8, 29)


@dataclass(frozen=True, slots=True)
class EvaluationPair:
    merchant_id: str
    settlement_id: str
    bank_line_id: str
    label: int
    settlement_amount_paise: int
    bank_amount_paise: int
    settlement_date: date
    bank_date: date
    settlement_reference: str
    bank_reference: str
    direction: Direction
    difficulty: str


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    pairs: tuple[EvaluationPair, ...]
    merchant_groups: tuple[str, ...]
    seed: int


def generate_hero_dataset(seed: int = HERO_SEED) -> HeroDataset:
    rng = random.Random(seed)
    settlement_specs = [
        # id, reported, expected, UTR, refund total, total fees, total tax
        ("set_demo_01", 2_850_990, 2_850_990, "UTR-AX91-0001", 22_500, 72_000, 12_960),
        ("set_demo_02", 3_898_875, 3_898_875, "UTR-BK84-X3Z2", 31_250, 91_000, 16_380),
        ("set_demo_03", 3_148_599, 3_148_599, "UTR-CP55-7733", 18_750, 68_000, 12_240),
        # Deliberate source-composition contradiction: reported is 137 paise lower.
        ("set_demo_04", 3_717_677, 3_717_814, "UTR-DQ77-9914", 27_500, 82_000, 14_760),
    ]

    payments: list[Payment] = []
    refunds: list[Refund] = []
    settlements: list[Settlement] = []
    payment_counter = 1
    refund_counter = 1
    base_dt = datetime(2026, 8, 27, 9, 0, tzinfo=timezone.utc)

    # Six refunds across the four packets: 2, 2, 1, 1.
    refund_parts_by_settlement = {
        "set_demo_01": (12_500, 10_000),
        "set_demo_02": (20_000, 11_250),
        "set_demo_03": (18_750,),
        "set_demo_04": (27_500,),
    }

    for index, (sid, reported, expected, utr, refund_total, fee_total, tax_total) in enumerate(settlement_specs):
        settlements.append(Settlement(sid, reported, utr, HERO_PERIOD + timedelta(days=index % 2)))
        gross = expected + refund_total + fee_total + tax_total
        amounts = _partition_positive(gross, 21, rng)
        fees = _partition_nonnegative(fee_total, 21, rng)
        taxes = _partition_nonnegative(tax_total, 21, rng)
        settlement_payments: list[Payment] = []
        for item_index, (amount, fee, tax) in enumerate(zip(amounts, fees, taxes, strict=True)):
            payment = Payment(
                payment_id=f"pay_demo_{payment_counter:03d}",
                settlement_id=sid,
                amount_paise=amount,
                fee_paise=fee,
                tax_paise=tax,
                captured_at=base_dt + timedelta(minutes=payment_counter * 17 + index),
            )
            payments.append(payment)
            settlement_payments.append(payment)
            payment_counter += 1

        for ref_index, refund_amount in enumerate(refund_parts_by_settlement[sid]):
            payment = settlement_payments[(ref_index * 7 + 3) % len(settlement_payments)]
            if refund_amount >= payment.amount_paise:
                raise AssertionError("generated refund must be partial")
            refunds.append(
                Refund(
                    refund_id=f"rfnd_demo_{refund_counter:03d}",
                    payment_id=payment.payment_id,
                    settlement_id=sid,
                    amount_paise=refund_amount,
                    created_at=payment.captured_at + timedelta(hours=2 + ref_index),
                )
            )
            refund_counter += 1

    bank_lines = (
        BankLine("bank_demo_001", 2_850_990, Direction.CREDIT, date(2026, 8, 29), "RZP SET_DEMO_01 UTR AX910001"),
        BankLine("bank_demo_002", 3_898_875, Direction.CREDIT, date(2026, 8, 30), "RZP SETTLEMENT SET_DEM_02 BK84X3"),
        BankLine("bank_demo_003A", 2_000_000, Direction.CREDIT, date(2026, 8, 30), "RZP SET_DEMO_03 PART A CP557733"),
        BankLine("bank_demo_003B", 1_148_599, Direction.CREDIT, date(2026, 8, 30), "RZP SET_DEMO_03 PART B CP557733"),
        BankLine("bank_demo_099", 3_039_375, Direction.CREDIT, date(2026, 8, 31), "NEFT CREDIT UNOWNED 9039"),
    )

    webhooks: list[WebhookDelivery] = []
    for idx, payment in enumerate(payments, start=1):
        occurred = payment.captured_at
        delivered = occurred + timedelta(seconds=5 + (idx % 9))
        # One event occurred earlier but was delivered after a later event.
        if idx == 18:
            occurred = payments[15].captured_at - timedelta(minutes=4)
            delivered = payments[21].captured_at + timedelta(minutes=2)
        payload = {"payment_id": payment.payment_id, "status": "captured", "amount": payment.amount_paise}
        webhooks.append(
            WebhookDelivery(
                event_id=f"evt_demo_{idx:03d}",
                event_type="payment.captured",
                entity_id=payment.payment_id,
                occurred_at=occurred,
                delivered_at=delivered,
                payload_digest=_payload_digest(payload),
            )
        )

    settlement_payload = {"settlement_id": "set_demo_01", "status": "processed"}
    webhooks.append(
        WebhookDelivery(
            event_id="evt_demo_085",
            event_type="settlement.processed",
            entity_id="set_demo_01",
            occurred_at=datetime(2026, 8, 29, 7, 0, tzinfo=timezone.utc),
            delivered_at=datetime(2026, 8, 29, 7, 0, 8, tzinfo=timezone.utc),
            payload_digest=_payload_digest(settlement_payload),
        )
    )
    # Duplicate delivery of one event ID with identical semantics.
    duplicate_source = webhooks[10]
    webhooks.append(
        WebhookDelivery(
            event_id=duplicate_source.event_id,
            event_type=duplicate_source.event_type,
            entity_id=duplicate_source.entity_id,
            occurred_at=duplicate_source.occurred_at,
            delivered_at=duplicate_source.delivered_at + timedelta(minutes=11),
            payload_digest=duplicate_source.payload_digest,
        )
    )

    dataset = HeroDataset(
        merchant_id="merchant_aster_house",
        merchant_name="Aster House Goods",
        period=HERO_PERIOD,
        payments=tuple(payments),
        refunds=tuple(refunds),
        settlements=tuple(settlements),
        bank_lines=bank_lines,
        webhooks=tuple(webhooks),
        seed=seed,
    )
    if dataset.source_record_count != 185:
        raise AssertionError(f"hero dataset must contain 185 records, got {dataset.source_record_count}")
    return dataset


def generate_evaluation_dataset(seed: int = HERO_SEED + 17) -> EvaluationDataset:
    """Generate 24 merchant groups × 42 settlements × 6 candidates.

    Identifier vocabularies are group-specific. True candidates vary across
    exact, damaged and difficult cases. Negatives include random distractors
    plus near-collision hard negatives.
    """
    rng = random.Random(seed)
    pairs: list[EvaluationPair] = []
    groups = tuple(f"merchant_{idx:02d}" for idx in range(24))
    base = date(2025, 1, 1)
    for merchant_index, merchant in enumerate(groups):
        merchant_token = f"M{merchant_index:02d}{rng.randrange(1000,9999)}"
        for settlement_index in range(42):
            settlement_id = f"{merchant}_set_{settlement_index:03d}"
            amount = rng.randint(45_000, 9_500_000)
            settled_on = base + timedelta(days=merchant_index * 47 + settlement_index * 3)
            utr_core = f"{merchant_token}{settlement_index:04d}{rng.randrange(100,999)}"
            difficulty_roll = rng.random()
            if difficulty_roll < 0.70:
                difficulty = "exact"
                true_reference = f"RZP SETTLEMENT {settlement_id} UTR {utr_core}"
                true_amount = amount
                date_shift = rng.choice([0, 0, 0, 1])
            elif difficulty_roll < 0.91:
                difficulty = "damaged"
                cut = rng.randrange(2, max(3, len(utr_core) - 2))
                damaged = utr_core[:cut] + utr_core[cut + 1 :]
                true_reference = f"RAZOR STLMNT {merchant_token} {damaged}"
                true_amount = amount + rng.choice([0, 0, 1, -1])
                date_shift = rng.choice([0, 1, 1, 2])
            else:
                difficulty = "ambiguous"
                true_reference = f"MERCHANT CREDIT {merchant_token[-4:]} SET {settlement_index:03d}"
                true_amount = amount + rng.randint(-40, 40)
                date_shift = rng.choice([1, 2, 3])

            positive_position = rng.randrange(6)
            for candidate_index in range(6):
                if candidate_index == positive_position:
                    pair = EvaluationPair(
                        merchant,
                        settlement_id,
                        f"{settlement_id}_bank_true",
                        1,
                        amount,
                        true_amount,
                        settled_on,
                        settled_on + timedelta(days=date_shift),
                        f"SETTLEMENT {settlement_id} UTR {utr_core}",
                        true_reference,
                        Direction.CREDIT,
                        difficulty,
                    )
                else:
                    near_twin = (
                        difficulty != "exact"
                        and candidate_index == (positive_position + 1) % 6
                        and rng.random() < 0.62
                    )
                    hard = candidate_index in {(positive_position + 1) % 6, (positive_position + 2) % 6} and rng.random() < 0.68
                    if near_twin:
                        # Deliberately underidentified case: a wrong candidate has almost the
                        # same observable evidence. A well-behaved policy should abstain when
                        # the top-vs-second margin collapses rather than manufacture certainty.
                        bank_amount = true_amount
                        bank_date = settled_on + timedelta(days=date_shift)
                        reference = true_reference.replace(merchant_token, merchant_token[:-1] + str((int(merchant_token[-1]) + 1) % 10), 1)
                        direction = Direction.CREDIT
                        negative_difficulty = "near_twin_negative"
                    elif hard:
                        # Hard negative: amount/date resemble the target and one identifier fragment collides.
                        bank_amount = amount + rng.randint(-90, 90)
                        bank_date = settled_on + timedelta(days=rng.choice([0, 1, 2, 3]))
                        collision = utr_core[: rng.choice([4, 5, 6])]
                        reference = f"RZP CREDIT {collision} {merchant_token} ALT{rng.randrange(100,999)}"
                        direction = Direction.CREDIT
                        negative_difficulty = "hard_negative"
                    else:
                        bank_amount = max(1, amount + rng.randint(-900_000, 900_000))
                        bank_date = settled_on + timedelta(days=rng.randint(-5, 8))
                        other_group = groups[(merchant_index + rng.randint(1, 23)) % 24]
                        reference = f"NEFT {other_group.upper()} REF {rng.randrange(100000,999999)}"
                        direction = Direction.DEBIT if rng.random() < 0.08 else Direction.CREDIT
                        negative_difficulty = "negative"
                    pair = EvaluationPair(
                        merchant,
                        settlement_id,
                        f"{settlement_id}_bank_{candidate_index}",
                        0,
                        amount,
                        bank_amount,
                        settled_on,
                        bank_date,
                        f"SETTLEMENT {settlement_id} UTR {utr_core}",
                        reference,
                        direction,
                        negative_difficulty,
                    )
                pairs.append(pair)
    return EvaluationDataset(tuple(pairs), groups, seed)


def export_hero_dataset(dataset: HeroDataset, destination: str) -> None:
    from pathlib import Path

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "payments.json": dataset.payments,
        "refunds.json": dataset.refunds,
        "settlements.json": dataset.settlements,
        "bank_lines.json": dataset.bank_lines,
        "webhooks.json": dataset.webhooks,
        "manifest.json": {
            "merchant_id": dataset.merchant_id,
            "merchant_name": dataset.merchant_name,
            "period": dataset.period,
            "seed": dataset.seed,
            "records": dataset.source_record_count,
        },
    }
    for name, value in payloads.items():
        (root / name).write_text(json.dumps(to_primitive(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _partition_positive(total: int, count: int, rng: random.Random) -> list[int]:
    if total < count:
        raise ValueError("total too small for positive partition")
    weights = [rng.uniform(0.3, 1.8) for _ in range(count)]
    remaining = total - count
    raw = [remaining * w / sum(weights) for w in weights]
    values = [1 + int(v) for v in raw]
    delta = total - sum(values)
    for idx in range(abs(delta)):
        values[idx % count] += 1 if delta > 0 else -1
    if sum(values) != total or min(values) <= 0:
        raise AssertionError("invalid positive partition")
    return values


def _partition_nonnegative(total: int, count: int, rng: random.Random) -> list[int]:
    if total == 0:
        return [0] * count
    weights = [rng.uniform(0.2, 1.6) for _ in range(count)]
    raw = [total * w / sum(weights) for w in weights]
    values = [int(v) for v in raw]
    delta = total - sum(values)
    for idx in range(delta):
        values[idx % count] += 1
    if sum(values) != total or min(values) < 0:
        raise AssertionError("invalid nonnegative partition")
    return values


def _payload_digest(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
