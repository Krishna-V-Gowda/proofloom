"""Deterministic close policy and financial invariants."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable, Sequence

from .domain import (
    BankLine,
    CandidateScore,
    Direction,
    InvariantResult,
    Payment,
    Refund,
    Settlement,
    sum_paise,
)


@dataclass(frozen=True, slots=True)
class PolicyConfig:
    booking_window_days: int = 3
    auto_match_threshold: float = 0.995
    review_threshold: float = 0.70
    minimum_score_margin: float = 0.08


@dataclass(frozen=True, slots=True)
class PolicyOutcome:
    permitted: bool
    review_required: bool
    blocked: bool
    reason_codes: tuple[str, ...]
    invariants: tuple[InvariantResult, ...]


def expected_net_paise(
    settlement: Settlement,
    payments: Iterable[Payment],
    refunds: Iterable[Refund],
) -> int:
    related_payments = [p for p in payments if p.settlement_id == settlement.settlement_id and p.status == "captured"]
    related_refunds = [r for r in refunds if r.settlement_id == settlement.settlement_id]
    gross = sum_paise(p.amount_paise for p in related_payments)
    fee = sum_paise(p.fee_paise for p in related_payments)
    tax = sum_paise(p.tax_paise for p in related_payments)
    refunded = sum_paise(r.amount_paise for r in related_refunds)
    return gross - fee - tax - refunded


def composition_invariant(
    settlement: Settlement,
    payments: Iterable[Payment],
    refunds: Iterable[Refund],
) -> InvariantResult:
    expected = expected_net_paise(settlement, payments, refunds)
    observed = settlement.reported_amount_paise
    return InvariantResult(
        name="settlement_composition",
        passed=expected == observed,
        expected=str(expected),
        observed=str(observed),
        detail=(
            "captured payment gross minus refunds, processing fees and tax must equal the reported settlement amount"
        ),
    )


def bank_invariants(
    settlement: Settlement,
    bank_lines: Sequence[BankLine],
    *,
    booking_window_days: int,
) -> tuple[InvariantResult, ...]:
    observed = sum_paise(line.amount_paise for line in bank_lines)
    money = InvariantResult(
        name="bank_money_conservation",
        passed=observed == settlement.reported_amount_paise,
        expected=str(settlement.reported_amount_paise),
        observed=str(observed),
        detail="selected incoming bank credits must sum exactly to the reported settlement amount",
    )
    direction = InvariantResult(
        name="incoming_credit_direction",
        passed=bool(bank_lines) and all(line.direction is Direction.CREDIT for line in bank_lines),
        expected="credit",
        observed=",".join(line.direction.value for line in bank_lines) if bank_lines else "none",
        detail="a debit or empty candidate set cannot own an incoming settlement",
    )
    allowed = timedelta(days=booking_window_days)
    valid_dates = bool(bank_lines) and all(abs(line.booked_on - settlement.settled_on) <= allowed for line in bank_lines)
    dates = InvariantResult(
        name="booking_window",
        passed=valid_dates,
        expected=f"within {booking_window_days} days",
        observed=",".join(line.booked_on.isoformat() for line in bank_lines) if bank_lines else "none",
        detail="selected credits must be booked within the configured settlement window",
    )
    return money, direction, dates


def decide_exact_or_split(
    settlement: Settlement,
    bank_lines: Sequence[BankLine],
    *,
    composition: InvariantResult,
    config: PolicyConfig,
) -> PolicyOutcome:
    invariants = (composition,) + bank_invariants(settlement, bank_lines, booking_window_days=config.booking_window_days)
    permitted = all(item.passed for item in invariants)
    reasons = tuple(item.name for item in invariants if not item.passed)
    return PolicyOutcome(
        permitted=permitted,
        review_required=False,
        blocked=not composition.passed,
        reason_codes=reasons or ("all_deterministic_invariants_pass",),
        invariants=invariants,
    )


def decide_model_candidate(
    settlement: Settlement,
    bank_line: BankLine,
    top: CandidateScore,
    second_score: float,
    *,
    composition: InvariantResult,
    config: PolicyConfig,
) -> PolicyOutcome:
    confidence = InvariantResult(
        name="model_confidence",
        passed=top.score >= config.auto_match_threshold,
        expected=f">={config.auto_match_threshold:.4f}",
        observed=f"{top.score:.4f}",
        detail="candidate probability must clear the precision-oriented automation threshold",
    )
    margin_value = max(0.0, top.score - second_score)
    margin = InvariantResult(
        name="score_margin",
        passed=margin_value >= config.minimum_score_margin,
        expected=f">={config.minimum_score_margin:.4f}",
        observed=f"{margin_value:.4f}",
        detail="the leading candidate must be decisively separated from the runner-up",
    )
    deterministic = bank_invariants(settlement, [bank_line], booking_window_days=config.booking_window_days)
    invariants = (composition,) + deterministic + (confidence, margin)
    deterministic_pass = composition.passed and all(item.passed for item in deterministic)
    if not composition.passed:
        return PolicyOutcome(False, False, True, ("settlement_composition",), invariants)
    if deterministic_pass and confidence.passed and margin.passed:
        return PolicyOutcome(True, False, False, ("model_ranked_and_policy_gated",), invariants)
    if deterministic_pass and top.score >= config.review_threshold:
        reasons = ["human_confirmation_required"]
        if not confidence.passed:
            reasons.append("below_auto_threshold")
        if not margin.passed:
            reasons.append("insufficient_score_margin")
        return PolicyOutcome(False, True, False, tuple(reasons), invariants)
    reasons = tuple(item.name for item in invariants if not item.passed)
    return PolicyOutcome(False, False, False, reasons or ("no_safe_candidate",), invariants)
