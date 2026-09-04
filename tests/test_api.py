from fastapi.testclient import TestClient

from proofloom.api import create_app


def test_api_hero_and_review_flow():
    client = TestClient(create_app())
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["real_money_actions"] is False
    response = client.post("/api/run-close")
    assert response.status_code == 200
    body = response.json()
    assert body["source_counts"]["records"] == 185
    review = next(item for item in body["decisions"] if item["status"] == "review_required")
    bad = client.post(f"/api/review/{review['decision_id']}", json={"action":"approve","reviewer":"controller","requested_amount_paise":review["expected_amount_paise"]+100})
    assert bad.status_code == 409
    good = client.post(f"/api/review/{review['decision_id']}", json={"action":"approve","reviewer":"controller","requested_amount_paise":review["expected_amount_paise"]})
    assert good.status_code == 200
    assert good.json()["summary"]["closed"] == 3


def test_api_failure_and_audit_surfaces():
    client = TestClient(create_app())
    client.post("/api/run-close")
    failure = client.post("/api/failures/audit-tamper")
    assert failure.status_code == 200
    assert failure.json()["safe"]
    audit = client.get("/api/audit")
    assert audit.json()["verification"]["valid"]
