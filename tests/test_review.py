import pytest
from sqlalchemy import inspect
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.exceptions import QueryTimeout
from app.db.models import Review
from app.services.sql_service import SQLService


REVIEW_HEADERS = {"X-API-Key": "test-reviewer-key"}


@pytest.fixture
def authorized_client(client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="sqlite://", api_key="test-query-key", reviewer_api_key="test-reviewer-key")
    return client


def test_review_table_initialized(session):
    assert "human_reviews" in inspect(session.get_bind()).get_table_names()


def test_pending_review_created_with_audit(client, session):
    result = client.post("/api/query", json={"user_request": "low confidence customers"}).json()
    review = session.scalar(select(Review).where(Review.audit_id == result["audit_id"]))
    assert review is not None
    assert review.status == "pending"


def test_api_keys_are_separate(authorized_client):
    assert authorized_client.post("/api/query", json={"user_request": "customers"}).status_code == 401
    query = authorized_client.post("/api/query", headers={"X-API-Key": "test-query-key"},
                                   json={"user_request": "customers"})
    assert query.status_code == 200
    audit_id = query.json()["audit_id"]
    assert authorized_client.get(f"/api/decisions/{audit_id}").status_code == 401
    assert authorized_client.get(f"/api/decisions/{audit_id}",
                                 headers={"X-API-Key": "test-query-key"}).status_code == 200
    assert authorized_client.get("/api/reviews", headers={"X-API-Key": "test-query-key"}).status_code == 401
    assert authorized_client.get("/api/reviews", headers=REVIEW_HEADERS).status_code == 200
    assert authorized_client.get("/health").status_code == 200


def test_approval_is_strict_and_audited(authorized_client):
    original = authorized_client.post("/api/query", headers=REVIEW_HEADERS,
        json={"user_request": "low confidence customers"}).json()
    audit_id = original["audit_id"]
    queued = authorized_client.get("/api/reviews", headers=REVIEW_HEADERS).json()
    assert [item["audit_id"] for item in queued] == [audit_id]
    approved = authorized_client.post(f"/api/reviews/{audit_id}/approve", headers=REVIEW_HEADERS,
        json={"reviewer": "Analyst"})
    assert approved.status_code == 200
    review = approved.json()
    assert review["status"] == "approved"
    assert review["resolution_audit_id"] != audit_id
    resolution = authorized_client.get(f"/api/decisions/{review['resolution_audit_id']}",
                                       headers=REVIEW_HEADERS).json()
    assert resolution["execution_status"] == "success"
    assert resolution["security_validation"] == "passed_strict"
    assert len(resolution["rows"]) == 3
    assert authorized_client.get(f"/api/decisions/{audit_id}",
        headers=REVIEW_HEADERS).json()["execution_status"] == "review_required"
    assert authorized_client.get("/api/reviews", headers=REVIEW_HEADERS).json() == []
    assert authorized_client.post(f"/api/reviews/{audit_id}/approve", headers=REVIEW_HEADERS,
        json={"reviewer": "Another analyst"}).status_code == 409


def test_rejection_never_executes(authorized_client):
    original = authorized_client.post("/api/query", headers=REVIEW_HEADERS,
        json={"user_request": "review customers"}).json()
    audit_id = original["audit_id"]
    review = authorized_client.post(f"/api/reviews/{audit_id}/reject", headers=REVIEW_HEADERS,
        json={"reviewer": "Analyst"}).json()
    assert review["status"] == "rejected"
    resolution = authorized_client.get(f"/api/decisions/{review['resolution_audit_id']}",
                                       headers=REVIEW_HEADERS).json()
    assert resolution["execution_status"] == "review_rejected"
    assert resolution["rows"] == []
    assert authorized_client.post(f"/api/reviews/{audit_id}/approve", headers=REVIEW_HEADERS,
        json={"reviewer": "Analyst"}).status_code == 409


def test_unsafe_approval_remains_pending(authorized_client, session):
    from app.db.models import Audit

    authorized_client.app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="sqlite://", api_key="test-query-key", reviewer_api_key="test-reviewer-key",
        allow_destructive_sql=True)
    original = authorized_client.post("/api/query", headers=REVIEW_HEADERS,
        json={"user_request": "review customers"}).json()
    audit_id = original["audit_id"]
    event = session.get(Audit, audit_id)
    event.generated_sql = "DELETE FROM customers"
    session.commit()
    rejected = authorized_client.post(f"/api/reviews/{audit_id}/approve", headers=REVIEW_HEADERS,
        json={"reviewer": "Analyst"})
    assert rejected.status_code == 409
    assert authorized_client.get(f"/api/reviews/{audit_id}", headers=REVIEW_HEADERS).json()["status"] == "pending"


def test_failed_execution_gets_resolution_audit(authorized_client, monkeypatch):
    original = authorized_client.post("/api/query", headers=REVIEW_HEADERS,
        json={"user_request": "review customers"}).json()

    def timeout(self, session, sql, retry=False):
        raise QueryTimeout("Database query timed out")

    monkeypatch.setattr(SQLService, "execute", timeout)
    review = authorized_client.post(f"/api/reviews/{original['audit_id']}/approve", headers=REVIEW_HEADERS,
        json={"reviewer": "Analyst"}).json()
    assert review["status"] == "failed"
    resolution = authorized_client.get(f"/api/decisions/{review['resolution_audit_id']}",
                                       headers=REVIEW_HEADERS).json()
    assert resolution["execution_status"] == "failed"
    assert resolution["error_message"] == "Database query timed out"


def test_unknown_review_and_invalid_reviewer(authorized_client):
    assert authorized_client.get("/api/reviews/9999", headers=REVIEW_HEADERS).status_code == 404
    assert authorized_client.post("/api/reviews/9999/reject", headers=REVIEW_HEADERS,
                                  json={"reviewer": ""}).status_code == 422


def test_live_provider_requires_distinct_keys():
    with pytest.raises(ValueError):
        Settings(jev_provider="typesafe")
    with pytest.raises(ValueError):
        Settings(api_key="same", reviewer_api_key="same")
    with pytest.raises(ValueError):
        Settings(api_key="replace-with-sample", reviewer_api_key="real-reviewer-key")