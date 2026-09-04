"""Tamper-evident audit ledger.

The ledger is intentionally small and in-memory for the demonstrator. It proves
linkage and canonical payload integrity inside one exported chain; it does not
provide durable immutability, access control, replication, or external anchoring.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping

from .domain import AuditVerification, to_primitive

GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class AuditEntry:
    sequence: int
    timestamp: str
    event_type: str
    actor: str
    correlation_id: str
    payload: Mapping[str, Any]
    previous_hash: str
    entry_hash: str

    def canonical_body(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor": self.actor,
            "correlation_id": self.correlation_id,
            "payload": to_primitive(self.payload),
            "previous_hash": self.previous_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.canonical_body(), "entry_hash": self.entry_hash}


class AuditLedger:
    """Append-only in-memory hash chain with defensive payload ownership."""

    def __init__(self, clock=None) -> None:
        self._entries: list[AuditEntry] = []
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def entries(self) -> tuple[AuditEntry, ...]:
        return tuple(self._entries)

    @property
    def head_hash(self) -> str:
        return self._entries[-1].entry_hash if self._entries else GENESIS_HASH

    def append(
        self,
        event_type: str,
        actor: str,
        correlation_id: str,
        payload: Mapping[str, Any],
        *,
        timestamp: datetime | None = None,
    ) -> AuditEntry:
        if not event_type.strip() or not actor.strip() or not correlation_id.strip():
            raise ValueError("event_type, actor and correlation_id are required")
        at = timestamp or self._clock()
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("audit timestamps must be timezone-aware")
        sequence = len(self._entries) + 1
        previous_hash = self.head_hash
        owned_payload = deepcopy(to_primitive(payload))
        body = {
            "sequence": sequence,
            "timestamp": at.isoformat(),
            "event_type": event_type,
            "actor": actor,
            "correlation_id": correlation_id,
            "payload": owned_payload,
            "previous_hash": previous_hash,
        }
        entry_hash = hash_body(body)
        entry = AuditEntry(entry_hash=entry_hash, **body)
        self._entries.append(entry)
        return entry

    def verify(self, entries: Iterable[AuditEntry | Mapping[str, Any]] | None = None) -> AuditVerification:
        candidate = list(entries if entries is not None else self._entries)
        previous_hash = GENESIS_HASH
        for expected_sequence, item in enumerate(candidate, start=1):
            data = item.to_dict() if isinstance(item, AuditEntry) else deepcopy(dict(item))
            actual_sequence = data.get("sequence")
            if actual_sequence != expected_sequence:
                return AuditVerification(
                    valid=False,
                    checked_entries=expected_sequence - 1,
                    first_invalid_sequence=expected_sequence,
                    reason=f"sequence expected {expected_sequence}, observed {actual_sequence}",
                    head_hash=previous_hash,
                )
            if data.get("previous_hash") != previous_hash:
                return AuditVerification(
                    valid=False,
                    checked_entries=expected_sequence - 1,
                    first_invalid_sequence=expected_sequence,
                    reason="previous-hash linkage mismatch",
                    head_hash=previous_hash,
                )
            claimed_hash = str(data.pop("entry_hash", ""))
            observed_hash = hash_body(data)
            if claimed_hash != observed_hash:
                return AuditVerification(
                    valid=False,
                    checked_entries=expected_sequence - 1,
                    first_invalid_sequence=expected_sequence,
                    reason="entry payload/hash mismatch",
                    head_hash=previous_hash,
                )
            previous_hash = claimed_hash
        return AuditVerification(
            valid=True,
            checked_entries=len(candidate),
            first_invalid_sequence=None,
            reason=None,
            head_hash=previous_hash,
        )

    def export(self) -> list[dict[str, Any]]:
        return [deepcopy(entry.to_dict()) for entry in self._entries]


def canonical_json(value: Any) -> str:
    return json.dumps(
        to_primitive(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def hash_body(body: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def simulate_tamper(entries: Iterable[AuditEntry | Mapping[str, Any]], sequence: int, key: str, value: Any) -> list[dict[str, Any]]:
    copy = [entry.to_dict() if isinstance(entry, AuditEntry) else deepcopy(dict(entry)) for entry in entries]
    if sequence < 1 or sequence > len(copy):
        raise IndexError("sequence outside audit chain")
    payload = dict(copy[sequence - 1].get("payload", {}))
    payload[key] = value
    copy[sequence - 1]["payload"] = payload
    return copy
