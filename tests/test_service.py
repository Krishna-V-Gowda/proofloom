import pytest

from proofloom.service import ProofloomService


def test_review_can_confirm_evidence_but_not_rewrite_money():
    service = ProofloomService()
    overview = service.run_close()
    decision = next(item for item in overview["decisions"] if item["status"] == "review_required")
    with pytest.raises(ValueError, match="immutable"):
        service.review(decision["decision_id"], action="approve", reviewer="controller", requested_amount_paise=decision["expected_amount_paise"] + 1)
    approved = service.review(decision["decision_id"], action="approve", reviewer="controller", requested_amount_paise=decision["expected_amount_paise"])
    updated = next(item for item in approved["decisions"] if item["decision_id"] == decision["decision_id"])
    assert updated["status"] == "approved"
    assert approved["summary"]["closed"] == 3
    assert approved["summary"]["matched_value_paise"] == 9_898_464
    resolved = next(item for item in approved["exceptions"] if item["settlement_id"] == decision["settlement_id"])
    assert resolved["resolved"] is True
    assert approved["audit"]["valid"]


def test_failure_lab_scenarios_are_safe():
    service = ProofloomService()
    service.run_close()
    for scenario in ("duplicate-webhook", "model-outage", "unsafe-adjustment", "audit-tamper", "false-tie-out"):
        result = service.failure(scenario)
        assert result["detected"]
        assert result["safe"]
