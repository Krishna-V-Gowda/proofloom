"""Narrow test-mode Razorpay integration boundary.

The demonstrator never executes real financial operations. This module proves
configuration, request construction and webhook authentication boundaries only.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import hmac
import json
import os
from typing import Any, Mapping


class RazorpayConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RazorpayTestConfig:
    key_id: str
    key_secret: str
    webhook_secret: str
    base_url: str = "https://api.razorpay.com/v1"

    def __post_init__(self) -> None:
        if not self.key_id.startswith("rzp_test_"):
            raise RazorpayConfigurationError("only Razorpay test-mode key IDs are accepted")
        if self.key_id.startswith("rzp_live_") or "live" in self.key_id.lower():
            raise RazorpayConfigurationError("live Razorpay credentials are prohibited")
        if len(self.key_secret) < 8 or len(self.webhook_secret) < 8:
            raise RazorpayConfigurationError("test secrets must not be empty or trivial")

    @classmethod
    def from_environment(cls) -> "RazorpayTestConfig":
        missing = [name for name in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET") if not os.getenv(name)]
        if missing:
            raise RazorpayConfigurationError(f"missing environment variables: {', '.join(missing)}")
        return cls(
            key_id=os.environ["RAZORPAY_KEY_ID"],
            key_secret=os.environ["RAZORPAY_KEY_SECRET"],
            webhook_secret=os.environ["RAZORPAY_WEBHOOK_SECRET"],
            base_url=os.getenv("RAZORPAY_BASE_URL", "https://api.razorpay.com/v1"),
        )

    def authorization_header(self) -> str:
        raw = f"{self.key_id}:{self.key_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")


@dataclass(frozen=True, slots=True)
class ReconciliationRequest:
    settlement_ids: tuple[str, ...]
    from_timestamp: int
    to_timestamp: int

    def to_payload(self) -> dict[str, Any]:
        if not self.settlement_ids:
            raise ValueError("at least one settlement ID is required")
        if self.from_timestamp >= self.to_timestamp:
            raise ValueError("from_timestamp must precede to_timestamp")
        return {
            "settlement_ids": list(self.settlement_ids),
            "from": self.from_timestamp,
            "to": self.to_timestamp,
        }


def build_reconciliation_request(settlement_ids: list[str], from_timestamp: int, to_timestamp: int) -> ReconciliationRequest:
    normalized = tuple(dict.fromkeys(value.strip() for value in settlement_ids if value.strip()))
    return ReconciliationRequest(normalized, int(from_timestamp), int(to_timestamp))


def webhook_signature(raw_body: bytes, secret: str) -> str:
    if not isinstance(raw_body, bytes):
        raise TypeError("raw webhook body must be bytes")
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def verify_webhook_signature(raw_body: bytes, supplied_signature: str, secret: str) -> bool:
    if not supplied_signature or not secret:
        return False
    expected = webhook_signature(raw_body, secret)
    return hmac.compare_digest(expected, supplied_signature.strip())


def canonical_fixture_payload(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
