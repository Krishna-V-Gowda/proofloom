"""Core immutable financial facts and decision records for Proofloom.

Money is represented exclusively in integer paise. Domain facts are frozen;
workflow decisions and audit records are created as new values rather than
mutating the source evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence


class Direction(StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"


class DecisionStatus(StrEnum):
    AUTO_MATCHED = "auto_matched"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    UNRESOLVED = "unresolved"


class MatchMethod(StrEnum):
    EXACT_REFERENCE = "exact_reference"
    SPLIT_SUM = "split_sum"
    MODEL_RANKED = "model_ranked"
    NONE = "none"


class Severity(StrEnum):
    INFO = "info"
    REVIEW = "review"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class Payment:
    payment_id: str
    settlement_id: str
    amount_paise: int
    fee_paise: int
    tax_paise: int
    captured_at: datetime
    status: str = "captured"

    def __post_init__(self) -> None:
        _require_id(self.payment_id, "payment_id")
        _require_id(self.settlement_id, "settlement_id")
        _require_nonnegative(self.amount_paise, "amount_paise")
        _require_nonnegative(self.fee_paise, "fee_paise")
        _require_nonnegative(self.tax_paise, "tax_paise")
        _require_aware(self.captured_at, "captured_at")
        if self.fee_paise + self.tax_paise > self.amount_paise:
            raise ValueError("fees and tax cannot exceed payment amount")


@dataclass(frozen=True, slots=True)
class Refund:
    refund_id: str
    payment_id: str
    settlement_id: str
    amount_paise: int
    created_at: datetime

    def __post_init__(self) -> None:
        _require_id(self.refund_id, "refund_id")
        _require_id(self.payment_id, "payment_id")
        _require_id(self.settlement_id, "settlement_id")
        if self.amount_paise <= 0:
            raise ValueError("refund amount must be positive")
        _require_aware(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class Settlement:
    settlement_id: str
    reported_amount_paise: int
    utr: str
    settled_on: date
    currency: str = "INR"

    def __post_init__(self) -> None:
        _require_id(self.settlement_id, "settlement_id")
        if self.reported_amount_paise <= 0:
            raise ValueError("settlement amount must be positive")
        if not self.utr.strip():
            raise ValueError("utr must not be empty")
        if self.currency != "INR":
            raise ValueError("prototype supports INR only")


@dataclass(frozen=True, slots=True)
class BankLine:
    bank_line_id: str
    amount_paise: int
    direction: Direction
    booked_on: date
    reference: str

    def __post_init__(self) -> None:
        _require_id(self.bank_line_id, "bank_line_id")
        if self.amount_paise <= 0:
            raise ValueError("bank-line amount must be positive")
        if not self.reference.strip():
            raise ValueError("bank reference must not be empty")


@dataclass(frozen=True, slots=True)
class WebhookDelivery:
    event_id: str
    event_type: str
    entity_id: str
    occurred_at: datetime
    delivered_at: datetime
    payload_digest: str

    def __post_init__(self) -> None:
        _require_id(self.event_id, "event_id")
        _require_id(self.entity_id, "entity_id")
        if not self.event_type.strip():
            raise ValueError("event_type must not be empty")
        _require_aware(self.occurred_at, "occurred_at")
        _require_aware(self.delivered_at, "delivered_at")
        if not self.payload_digest.strip():
            raise ValueError("payload_digest must not be empty")


@dataclass(frozen=True, slots=True)
class InvariantResult:
    name: str
    passed: bool
    expected: str
    observed: str
    detail: str


@dataclass(frozen=True, slots=True)
class CandidateScore:
    bank_line_id: str
    score: float
    features: Mapping[str, float]
    model_version: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("candidate score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    source: str
    record_id: str
    summary: str


@dataclass(frozen=True, slots=True)
class Decision:
    decision_id: str
    settlement_id: str
    status: DecisionStatus
    method: MatchMethod
    expected_amount_paise: int
    observed_amount_paise: int | None
    bank_line_ids: tuple[str, ...] = ()
    confidence: float | None = None
    model_version: str | None = None
    reason_codes: tuple[str, ...] = ()
    invariants: tuple[InvariantResult, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    reviewer: str | None = None
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_id(self.decision_id, "decision_id")
        _require_id(self.settlement_id, "settlement_id")
        _require_nonnegative(self.expected_amount_paise, "expected_amount_paise")
        if self.observed_amount_paise is not None:
            _require_nonnegative(self.observed_amount_paise, "observed_amount_paise")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.reviewed_at is not None:
            _require_aware(self.reviewed_at, "reviewed_at")


@dataclass(frozen=True, slots=True)
class ExceptionRecord:
    exception_id: str
    settlement_id: str | None
    severity: Severity
    code: str
    title: str
    detail: str
    resolved: bool = False


@dataclass(frozen=True, slots=True)
class EventNormalization:
    accepted: tuple[WebhookDelivery, ...]
    duplicate_event_ids: tuple[str, ...]
    out_of_order_event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HeroDataset:
    merchant_id: str
    merchant_name: str
    period: date
    payments: tuple[Payment, ...]
    refunds: tuple[Refund, ...]
    settlements: tuple[Settlement, ...]
    bank_lines: tuple[BankLine, ...]
    webhooks: tuple[WebhookDelivery, ...]
    seed: int

    @property
    def source_record_count(self) -> int:
        return (
            len(self.payments)
            + len(self.refunds)
            + len(self.settlements)
            + len(self.bank_lines)
            + len(self.webhooks)
        )


@dataclass(frozen=True, slots=True)
class CloseResult:
    merchant_id: str
    merchant_name: str
    period: date
    source_record_count: int
    decisions: tuple[Decision, ...]
    exceptions: tuple[ExceptionRecord, ...]
    duplicate_events: int
    out_of_order_events: int
    audit_head: str
    audit_valid: bool

    @property
    def closed_count(self) -> int:
        return sum(
            d.status in {DecisionStatus.AUTO_MATCHED, DecisionStatus.APPROVED}
            for d in self.decisions
        )

    @property
    def review_count(self) -> int:
        return sum(d.status is DecisionStatus.REVIEW_REQUIRED for d in self.decisions)

    @property
    def blocked_count(self) -> int:
        return sum(d.status is DecisionStatus.BLOCKED for d in self.decisions)

    @property
    def unresolved_count(self) -> int:
        return sum(d.status is DecisionStatus.UNRESOLVED for d in self.decisions)

    @property
    def matched_value_paise(self) -> int:
        return sum(
            d.expected_amount_paise
            for d in self.decisions
            if d.status in {DecisionStatus.AUTO_MATCHED, DecisionStatus.APPROVED}
        )


@dataclass(frozen=True, slots=True)
class AuditVerification:
    valid: bool
    checked_entries: int
    first_invalid_sequence: int | None = None
    reason: str | None = None
    head_hash: str = ""


def to_primitive(value: Any) -> Any:
    """Convert domain values to stable JSON-compatible primitives."""
    if is_dataclass(value):
        return {key: to_primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): to_primitive(item) for key, item in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [to_primitive(item) for item in value]
    return value


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def money_inr(paise: int | None) -> str:
    if paise is None:
        return "—"
    sign = "-" if paise < 0 else ""
    absolute = abs(paise)
    rupees, remainder = divmod(absolute, 100)
    return f"{sign}₹{rupees:,}.{remainder:02d}"


def _require_id(value: str, name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_nonnegative(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer number of paise")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def sum_paise(values: Iterable[int]) -> int:
    total = 0
    for value in values:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("currency values must be integer paise")
        total += value
    return total


def index_by_id(items: Sequence[Any], attribute: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        key = getattr(item, attribute)
        if key in result:
            raise ValueError(f"duplicate {attribute}: {key}")
        result[key] = item
    return result
