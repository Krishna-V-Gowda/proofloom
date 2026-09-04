"""Settlement close engine: exact evidence first, AI only for ambiguity."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from itertools import combinations
from typing import Iterable, Sequence
import re

from .audit import AuditLedger
from .domain import (
    BankLine,
    CloseResult,
    Decision,
    DecisionStatus,
    EventNormalization,
    EvidenceItem,
    ExceptionRecord,
    HeroDataset,
    MatchMethod,
    Severity,
    Settlement,
    WebhookDelivery,
)
from .features import normalize_reference
from .intelligence import AmbiguityModel, ModelUnavailable
from .policy import PolicyConfig, composition_invariant, decide_exact_or_split, decide_model_candidate

NON_ALNUM = re.compile(r"[^A-Z0-9]+")


class CloseEngine:
    def __init__(
        self,
        *,
        model: AmbiguityModel | None = None,
        config: PolicyConfig | None = None,
        ledger: AuditLedger | None = None,
    ) -> None:
        self.model = model or AmbiguityModel.default()
        self.config = config or PolicyConfig(auto_match_threshold=max(0.985, (model.threshold if model else 0.985)))
        self.ledger = ledger or AuditLedger()

    def run(self, dataset: HeroDataset, *, correlation_id: str = "close-20260903") -> CloseResult:
        self.ledger.append(
            "close.started",
            "system",
            correlation_id,
            {"merchant_id": dataset.merchant_id, "records": dataset.source_record_count, "seed": dataset.seed},
        )
        normalized = normalize_webhooks(dataset.webhooks)
        self.ledger.append(
            "events.normalized",
            "system",
            correlation_id,
            {
                "accepted": len(normalized.accepted),
                "duplicates": len(normalized.duplicate_event_ids),
                "out_of_order": len(normalized.out_of_order_event_ids),
            },
        )

        decisions: list[Decision] = []
        exceptions: list[ExceptionRecord] = []
        used_bank_ids: set[str] = set()

        for settlement in dataset.settlements:
            decision, settlement_exceptions = self._close_one(
                dataset,
                settlement,
                used_bank_ids,
                correlation_id=correlation_id,
            )
            decisions.append(decision)
            exceptions.extend(settlement_exceptions)
            if decision.status in {DecisionStatus.AUTO_MATCHED, DecisionStatus.APPROVED, DecisionStatus.REVIEW_REQUIRED}:
                used_bank_ids.update(decision.bank_line_ids)
            self.ledger.append(
                "decision.created",
                "close-engine",
                correlation_id,
                {
                    "decision_id": decision.decision_id,
                    "settlement_id": decision.settlement_id,
                    "status": decision.status.value,
                    "method": decision.method.value,
                    "bank_line_ids": decision.bank_line_ids,
                    "reason_codes": decision.reason_codes,
                },
            )

        for bank_line in dataset.bank_lines:
            if bank_line.bank_line_id not in used_bank_ids:
                exceptions.append(
                    ExceptionRecord(
                        exception_id=f"exc_unowned_{bank_line.bank_line_id}",
                        settlement_id=None,
                        severity=Severity.REVIEW,
                        code="unowned_bank_credit",
                        title="Bank credit has no proven settlement owner",
                        detail=f"{bank_line.bank_line_id} remains outside every accepted proof path.",
                    )
                )

        verification = self.ledger.verify()
        result = CloseResult(
            merchant_id=dataset.merchant_id,
            merchant_name=dataset.merchant_name,
            period=dataset.period,
            source_record_count=dataset.source_record_count,
            decisions=tuple(decisions),
            exceptions=tuple(exceptions),
            duplicate_events=len(normalized.duplicate_event_ids),
            out_of_order_events=len(normalized.out_of_order_event_ids),
            audit_head=self.ledger.head_hash,
            audit_valid=verification.valid,
        )
        self.ledger.append(
            "close.completed",
            "system",
            correlation_id,
            {
                "closed": result.closed_count,
                "review": result.review_count,
                "blocked": result.blocked_count,
                "unresolved": result.unresolved_count,
                "exceptions": len(result.exceptions),
            },
        )
        # Return the final head including the completion event.
        return replace(result, audit_head=self.ledger.head_hash, audit_valid=self.ledger.verify().valid)

    def _close_one(
        self,
        dataset: HeroDataset,
        settlement: Settlement,
        used_bank_ids: set[str],
        *,
        correlation_id: str,
    ) -> tuple[Decision, list[ExceptionRecord]]:
        composition = composition_invariant(settlement, dataset.payments, dataset.refunds)
        expected = int(composition.expected)
        if not composition.passed:
            delta = expected - settlement.reported_amount_paise
            decision = Decision(
                decision_id=f"dec_{settlement.settlement_id}",
                settlement_id=settlement.settlement_id,
                status=DecisionStatus.BLOCKED,
                method=MatchMethod.NONE,
                expected_amount_paise=expected,
                observed_amount_paise=settlement.reported_amount_paise,
                reason_codes=("settlement_composition_mismatch",),
                invariants=(composition,),
                evidence=(
                    EvidenceItem(
                        "payments_and_refunds",
                        settlement.settlement_id,
                        "Computed from captured payments minus refunds, fees and tax.",
                    ),
                    EvidenceItem(
                        "settlement",
                        settlement.settlement_id,
                        f"Reported amount differs from expected source net by {abs(delta)} paise.",
                    ),
                ),
            )
            exception = ExceptionRecord(
                exception_id=f"exc_comp_{settlement.settlement_id}",
                settlement_id=settlement.settlement_id,
                severity=Severity.CRITICAL,
                code="settlement_composition_mismatch",
                title="Settlement composition does not conserve money",
                detail=f"Expected {expected} paise from source events, but the settlement reports {settlement.reported_amount_paise} paise; delta {abs(delta)} paise.",
            )
            return decision, [exception]

        available = [line for line in dataset.bank_lines if line.bank_line_id not in used_bank_ids]
        exact = [line for line in available if self._is_exact_reference(settlement, line)]
        if len(exact) == 1:
            outcome = decide_exact_or_split(settlement, exact, composition=composition, config=self.config)
            if outcome.permitted:
                line = exact[0]
                return (
                    Decision(
                        decision_id=f"dec_{settlement.settlement_id}",
                        settlement_id=settlement.settlement_id,
                        status=DecisionStatus.AUTO_MATCHED,
                        method=MatchMethod.EXACT_REFERENCE,
                        expected_amount_paise=expected,
                        observed_amount_paise=line.amount_paise,
                        bank_line_ids=(line.bank_line_id,),
                        confidence=1.0,
                        reason_codes=outcome.reason_codes,
                        invariants=outcome.invariants,
                        evidence=(EvidenceItem("bank_statement", line.bank_line_id, line.reference),),
                    ),
                    [],
                )

        split = self._find_split(settlement, available)
        if split is not None:
            outcome = decide_exact_or_split(settlement, list(split), composition=composition, config=self.config)
            if outcome.permitted:
                return (
                    Decision(
                        decision_id=f"dec_{settlement.settlement_id}",
                        settlement_id=settlement.settlement_id,
                        status=DecisionStatus.AUTO_MATCHED,
                        method=MatchMethod.SPLIT_SUM,
                        expected_amount_paise=expected,
                        observed_amount_paise=sum(line.amount_paise for line in split),
                        bank_line_ids=tuple(line.bank_line_id for line in split),
                        confidence=1.0,
                        reason_codes=outcome.reason_codes,
                        invariants=outcome.invariants,
                        evidence=tuple(EvidenceItem("bank_statement", line.bank_line_id, line.reference) for line in split),
                    ),
                    [],
                )

        credit_candidates = [line for line in available if line.direction.value == "credit"]
        try:
            scores = sorted(
                (self.model.score(settlement, line) for line in credit_candidates),
                key=lambda score: (-score.score, score.bank_line_id),
            )
        except ModelUnavailable:
            decision = Decision(
                decision_id=f"dec_{settlement.settlement_id}",
                settlement_id=settlement.settlement_id,
                status=DecisionStatus.UNRESOLVED,
                method=MatchMethod.NONE,
                expected_amount_paise=expected,
                observed_amount_paise=None,
                reason_codes=("model_unavailable_safe_abstention",),
                invariants=(composition,),
            )
            return decision, [
                ExceptionRecord(
                    f"exc_model_{settlement.settlement_id}",
                    settlement.settlement_id,
                    Severity.REVIEW,
                    "model_unavailable",
                    "Ambiguous evidence retained for review",
                    "Deterministic paths continued; no heuristic fallback was allowed to auto-close this settlement.",
                )
            ]

        if not scores:
            return self._unresolved(settlement, expected, composition, "no_candidate_bank_credit")
        top = scores[0]
        second = scores[1].score if len(scores) > 1 else 0.0
        line_by_id = {line.bank_line_id: line for line in credit_candidates}
        top_line = line_by_id[top.bank_line_id]
        outcome = decide_model_candidate(
            settlement,
            top_line,
            top,
            second,
            composition=composition,
            config=self.config,
        )
        if outcome.permitted:
            status = DecisionStatus.AUTO_MATCHED
            exceptions: list[ExceptionRecord] = []
        elif outcome.review_required:
            status = DecisionStatus.REVIEW_REQUIRED
            exceptions = [
                ExceptionRecord(
                    f"exc_review_{settlement.settlement_id}",
                    settlement.settlement_id,
                    Severity.REVIEW,
                    "ambiguous_reference_requires_human",
                    "Damaged bank reference needs review confirmation",
                    f"Candidate {top_line.bank_line_id} ranked first at {top.score:.1%}; financial facts remain immutable.",
                )
            ]
        else:
            return self._unresolved(settlement, expected, composition, "no_candidate_cleared_policy")
        decision = Decision(
            decision_id=f"dec_{settlement.settlement_id}",
            settlement_id=settlement.settlement_id,
            status=status,
            method=MatchMethod.MODEL_RANKED,
            expected_amount_paise=expected,
            observed_amount_paise=top_line.amount_paise,
            bank_line_ids=(top_line.bank_line_id,),
            confidence=top.score,
            model_version=top.model_version,
            reason_codes=outcome.reason_codes,
            invariants=outcome.invariants,
            evidence=(
                EvidenceItem("model_candidate", top_line.bank_line_id, f"Ranked from amount, date and reference evidence; runner-up {second:.1%}."),
                EvidenceItem("bank_statement", top_line.bank_line_id, top_line.reference),
            ),
        )
        return decision, exceptions

    def _unresolved(self, settlement: Settlement, expected: int, composition, reason: str):
        decision = Decision(
            decision_id=f"dec_{settlement.settlement_id}",
            settlement_id=settlement.settlement_id,
            status=DecisionStatus.UNRESOLVED,
            method=MatchMethod.NONE,
            expected_amount_paise=expected,
            observed_amount_paise=None,
            reason_codes=(reason,),
            invariants=(composition,),
        )
        exception = ExceptionRecord(
            f"exc_unresolved_{settlement.settlement_id}",
            settlement.settlement_id,
            Severity.REVIEW,
            reason,
            "No bank evidence cleared the close policy",
            "The settlement remains open; no candidate received ownership.",
        )
        return decision, [exception]

    @staticmethod
    def _is_exact_reference(settlement: Settlement, bank_line: BankLine) -> bool:
        if bank_line.amount_paise != settlement.reported_amount_paise:
            return False
        bank = NON_ALNUM.sub("", bank_line.reference.upper())
        utr = NON_ALNUM.sub("", settlement.utr.upper())
        sid = NON_ALNUM.sub("", settlement.settlement_id.upper())
        return utr in bank or sid in bank

    @staticmethod
    def _find_split(settlement: Settlement, bank_lines: Sequence[BankLine]) -> tuple[BankLine, BankLine] | None:
        sid_tokens = set(normalize_reference(settlement.settlement_id).split())
        utr_compact = NON_ALNUM.sub("", settlement.utr.upper())
        for left, right in combinations(bank_lines, 2):
            if left.amount_paise + right.amount_paise != settlement.reported_amount_paise:
                continue
            combined = f"{left.reference} {right.reference}".upper()
            combined_compact = NON_ALNUM.sub("", combined)
            combined_tokens = set(normalize_reference(combined).split())
            reference_support = bool(sid_tokens & combined_tokens) or utr_compact in combined_compact
            if reference_support and left.direction.value == right.direction.value == "credit":
                return left, right
        return None


def normalize_webhooks(deliveries: Iterable[WebhookDelivery]) -> EventNormalization:
    delivered = sorted(deliveries, key=lambda item: (item.delivered_at, item.event_id))
    accepted_by_id: dict[str, WebhookDelivery] = {}
    duplicates: list[str] = []
    out_of_order: list[str] = []
    max_occurred: datetime | None = None
    for delivery in delivered:
        existing = accepted_by_id.get(delivery.event_id)
        if existing is not None:
            if (
                existing.event_type != delivery.event_type
                or existing.entity_id != delivery.entity_id
                or existing.payload_digest != delivery.payload_digest
            ):
                raise ValueError(f"event ID collision with different semantics: {delivery.event_id}")
            duplicates.append(delivery.event_id)
            continue
        if max_occurred is not None and delivery.occurred_at < max_occurred:
            out_of_order.append(delivery.event_id)
        max_occurred = max(max_occurred, delivery.occurred_at) if max_occurred else delivery.occurred_at
        accepted_by_id[delivery.event_id] = delivery
    accepted = tuple(sorted(accepted_by_id.values(), key=lambda item: (item.occurred_at, item.event_id)))
    return EventNormalization(accepted, tuple(duplicates), tuple(out_of_order))
