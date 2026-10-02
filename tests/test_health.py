def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_query_audited(client):
    response = client.post("/api/query", json={"user_request": "List customers"})
    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "success"
    assert len(body["rows"]) == 3
    assert body["jev_decision"]["confidence"] == 0.96
    audit = client.get(f"/api/decisions/{body['audit_id']}")
    assert audit.status_code == 200
    assert audit.json()["selected_action"] == "execute_sql"


def test_missing_audit(client):
    assert client.get("/api/decisions/99999").status_code == 404


def test_invalid_request(client):
    assert client.post("/api/query", json={"user_request": ""}).status_code == 422