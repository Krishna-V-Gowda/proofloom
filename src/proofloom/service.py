"""Thread-safe orchestration service for the local Proofloom demonstrator."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from .audit import AuditLedger, simulate_tamper
from .data import HERO_SEED, generate_hero_dataset
from .domain import CloseResult, Decision, DecisionStatus, HeroDataset, to_primitive
from .engine import CloseEngine, normalize_webhooks
from .intelligence import AmbiguityModel
from .policy import PolicyConfig


class ProofloomService:
    def __init__(self, *, seed: int = HERO_SEED) -> None:
        self._lock = RLock()
        self._seed = seed
        self._dataset: HeroDataset
        self._model: AmbiguityModel
        self._ledger: AuditLedger
        self._result: CloseResult | None
        self._model_online: bool
        self._failure_results: dict[str, dict[str, Any]]
        self.reset()

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self._dataset = generate_hero_dataset(self._seed)
            self._model = AmbiguityModel.default()
            self._model_online = True
            self._model.available = True
            self._ledger = AuditLedger()
            self._result = None
            self._failure_results = {}
            self._ledger.append(
                "demo.reset",
                "operator",
                "reset-20260903",
                {"seed": self._seed, "records": self._dataset.source_record_count},
                timestamp=datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc),
            )
            return self.overview()

    @property
    def dataset(self) -> HeroDataset:
        return self._dataset

    @property
    def result(self) -> CloseResult | None:
        return self._result

    def run_close(self) -> dict[str, Any]:
        with self._lock:
            # Every run starts a new proof chain so a deterministic reset + run
            # produces an inspectable, stable decision sequence.
            self._ledger = AuditLedger()
            self._model.available = self._model_online
            engine = CloseEngine(
                model=self._model,
                config=PolicyConfig(
                    auto_match_threshold=max(self._model.threshold, 0.995),
                    review_threshold=0.50,
                    minimum_score_margin=0.02,
                ),
                ledger=self._ledger,
            )
            self._result = engine.run(self._dataset)
            return self.overview()

    def review(self, decision_id: str, *, action: str, reviewer: str, requested_amount_paise: int | None = None) -> dict[str, Any]:
        with self._lock:
            if self._result is None:
                raise ValueError("run the close before reviewing a decision")
            if action not in {"approve", "reject"}:
                raise ValueError("action must be approve or reject")
            updated: list[Decision] = []
            found = False
            for decision in self._result.decisions:
                if decision.decision_id != decision_id:
                    updated.append(decision)
                    continue
                found = True
                if decision.status is not DecisionStatus.REVIEW_REQUIRED:
                    raise ValueError("only review-required decisions may be reviewed")
                if requested_amount_paise is not None and requested_amount_paise != decision.expected_amount_paise:
                    self._ledger.append(
                        "review.rejected_unsafe_adjustment",
                        reviewer,
                        f"review-{decision_id}",
                        {
                            "decision_id": decision_id,
                            "requested_amount_paise": requested_amount_paise,
                            "immutable_amount_paise": decision.expected_amount_paise,
                        },
                    )
                    raise ValueError("financial facts are immutable; requested amount does not equal settlement amount")
                new_status = DecisionStatus.APPROVED if action == "approve" else DecisionStatus.REJECTED
                reviewed = replace(
                    decision,
                    status=new_status,
                    reviewer=reviewer,
                    reviewed_at=datetime.now(timezone.utc),
                    reason_codes=decision.reason_codes + (f"human_{action}",),
                )
                updated.append(reviewed)
                self._ledger.append(
                    f"review.{action}d",
                    reviewer,
                    f"review-{decision_id}",
                    {
                        "decision_id": decision_id,
                        "settlement_id": decision.settlement_id,
                        "amount_paise": decision.expected_amount_paise,
                        "evidence_ids": decision.bank_line_ids,
                    },
                )
            if not found:
                raise KeyError(decision_id)
            reviewed_settlement_id = next(
                decision.settlement_id for decision in updated if decision.decision_id == decision_id
            )
            resolved_exceptions = tuple(
                replace(exception, resolved=True)
                if exception.settlement_id == reviewed_settlement_id
                and exception.code == "ambiguous_reference_requires_human"
                else exception
                for exception in self._result.exceptions
            )
            self._result = replace(
                self._result,
                decisions=tuple(updated),
                exceptions=resolved_exceptions,
                audit_head=self._ledger.head_hash,
                audit_valid=self._ledger.verify().valid,
            )
            return self.overview()

    def failure(self, scenario: str) -> dict[str, Any]:
        with self._lock:
            if scenario == "duplicate-webhook":
                normalized = normalize_webhooks(self._dataset.webhooks)
                result = {
                    "scenario": scenario,
                    "detected": bool(normalized.duplicate_event_ids),
                    "safe": len(normalized.accepted) == len({event.event_id for event in self._dataset.webhooks}),
                    "detail": f"suppressed {len(normalized.duplicate_event_ids)} replayed delivery; no duplicate decision created",
                }
            elif scenario == "model-outage":
                from .audit import AuditLedger
                from .engine import CloseEngine
                from .policy import PolicyConfig

                self._model.available = False
                try:
                    simulated = CloseEngine(
                        model=self._model,
                        config=PolicyConfig(auto_match_threshold=max(self._model.threshold, 0.995), review_threshold=0.50, minimum_score_margin=0.02),
                        ledger=AuditLedger(),
                    ).run(self._dataset, correlation_id="failure-model-outage")
                    unresolved = [d for d in simulated.decisions if d.status is DecisionStatus.UNRESOLVED]
                    deterministic = [d for d in simulated.decisions if d.status is DecisionStatus.AUTO_MATCHED]
                    result = {
                        "scenario": scenario,
                        "detected": True,
                        "safe": bool(unresolved) and len(deterministic) >= 2,
                        "detail": "exact and split paths continued; ambiguous evidence remained open",
                    }
                finally:
                    self._model.available = self._model_online
            elif scenario == "unsafe-adjustment":
                if self._result is None:
                    self.run_close()
                review = next((d for d in self._result.decisions if d.status is DecisionStatus.REVIEW_REQUIRED), None)
                if review is None:
                    raise ValueError("no review decision available")
                try:
                    self.review(
                        review.decision_id,
                        action="approve",
                        reviewer="demo-controller",
                        requested_amount_paise=review.expected_amount_paise + 100,
                    )
                except ValueError as exc:
                    result = {"scenario": scenario, "detected": True, "safe": True, "detail": str(exc)}
                else:
                    result = {"scenario": scenario, "detected": False, "safe": False, "detail": "unsafe change was accepted"}
            elif scenario == "audit-tamper":
                if self._result is None:
                    self.run_close()
                exported = self._ledger.export()
                target_sequence = min(2, len(exported))
                tampered = simulate_tamper(exported, target_sequence, "tampered", True)
                verification = self._ledger.verify(tampered)
                result = {
                    "scenario": scenario,
                    "detected": not verification.valid,
                    "safe": self._ledger.verify().valid,
                    "detail": f"copied chain failed at sequence {verification.first_invalid_sequence}; live chain remained valid",
                }
            elif scenario == "false-tie-out":
                blocked = None
                if self._result is None:
                    self.run_close()
                blocked = next((d for d in self._result.decisions if d.status is DecisionStatus.BLOCKED), None)
                result = {
                    "scenario": scenario,
                    "detected": blocked is not None,
                    "safe": blocked is not None,
                    "detail": "137-paise composition mismatch remained blocked before bank ownership was considered",
                }
            else:
                raise KeyError(f"unknown failure scenario: {scenario}")
            self._failure_results[scenario] = result
            self._ledger.append("failure.simulated", "operator", f"failure-{scenario}", result)
            return deepcopy(result)

    def audit(self) -> dict[str, Any]:
        with self._lock:
            verification = self._ledger.verify()
            return {
                "verification": to_primitive(verification),
                "entries": self._ledger.export(),
            }

    def overview(self) -> dict[str, Any]:
        with self._lock:
            dataset = self._dataset
            result = self._result
            normalization = normalize_webhooks(dataset.webhooks)
            payload: dict[str, Any] = {
                "project": "Proofloom",
                "mode": "synthetic-local",
                "merchant": {"id": dataset.merchant_id, "name": dataset.merchant_name},
                "period": dataset.period.isoformat(),
                "seed": dataset.seed,
                "source_counts": {
                    "payments": len(dataset.payments),
                    "refunds": len(dataset.refunds),
                    "settlements": len(dataset.settlements),
                    "bank_lines": len(dataset.bank_lines),
                    "webhook_deliveries": len(dataset.webhooks),
                    "records": dataset.source_record_count,
                },
                "normalization": {
                    "accepted_webhooks": len(normalization.accepted),
                    "duplicate_events": len(normalization.duplicate_event_ids),
                    "out_of_order_events": len(normalization.out_of_order_event_ids),
                },
                "model": {
                    "version": self._model.model_version,
                    "threshold": self._model.threshold,
                    "online": self._model_online,
                    "authority": "candidate ranking only",
                },
                "failure_results": deepcopy(self._failure_results),
            }
            if result is None:
                payload.update(
                    {
                        "gate": "not_run",
                        "summary": {"closed": 0, "review": 0, "blocked": 0, "unresolved": 0, "matched_value_paise": 0},
                        "decisions": [],
                        "exceptions": [],
                        "audit": {"valid": self._ledger.verify().valid, "head": self._ledger.head_hash[:16], "entries": len(self._ledger.entries)},
                    }
                )
            else:
                payload.update(
                    {
                        "gate": "clear" if result.closed_count == len(result.decisions) else "blocked",
                        "summary": {
                            "closed": result.closed_count,
                            "review": result.review_count,
                            "blocked": result.blocked_count,
                            "unresolved": result.unresolved_count,
                            "matched_value_paise": result.matched_value_paise,
                        },
                        "decisions": to_primitive(result.decisions),
                        "exceptions": to_primitive(result.exceptions),
                        "audit": {"valid": self._ledger.verify().valid, "head": self._ledger.head_hash[:16], "entries": len(self._ledger.entries)},
                    }
                )
            return payload
