import pytest

from proofloom.razorpay_adapter import (
    RazorpayConfigurationError,
    RazorpayTestConfig,
    build_reconciliation_request,
    verify_webhook_signature,
    webhook_signature,
)


def test_test_mode_guard_and_basic_auth():
    config = RazorpayTestConfig("rzp_test_example", "testsecret123", "webhooksecret123")
    assert config.authorization_header().startswith("Basic ")
    with pytest.raises(RazorpayConfigurationError):
        RazorpayTestConfig("rzp_" + "live_example", "livesecret123", "webhooksecret123")


def test_webhook_signature_uses_raw_body_and_constant_time_comparison():
    raw = b'{"event":"payment.captured"}'
    signature = webhook_signature(raw, "secret-123")
    assert verify_webhook_signature(raw, signature, "secret-123")
    assert not verify_webhook_signature(raw + b" ", signature, "secret-123")


def test_reconciliation_request_is_typed_and_deduplicated():
    request = build_reconciliation_request(["set_1", "set_1", " set_2 "], 100, 200)
    assert request.to_payload()["settlement_ids"] == ["set_1", "set_2"]
