from app.models.decision_models import Action
from app.services.decision_router import DecisionRouter
from app.services.jev_service import decision


def test_confidence_thresholds(settings):
    router = DecisionRouter(settings)
    assert router.route(decision(Action.EXECUTE_SQL, 0.96, "ok")).action == Action.EXECUTE_SQL
    medium = router.route(decision(Action.EXECUTE_SQL, 0.8, "check"))
    assert medium.extra_validation is True
    assert router.route(decision(Action.EXECUTE_SQL, 0.55, "uncertain")).action == Action.HUMAN_REVIEW


def test_workflow_actions(client):
    for text, status in [("low confidence customers", "review_required"),
                         ("retry customers", "success"),
                         ("clarify customers", "clarification_required"),
                         ("review customers", "review_required"),
                         ("reject customers", "rejected"),
                         ("another tool please", "success"),
                         ("medium confidence customers", "success")]:
        assert client.post("/api/query", json={"user_request": text}).json()["execution_status"] == status


def test_selected_schema_tool_excludes_audit(client):
    result = client.post("/api/query", json={"user_request": "another tool please"}).json()
    assert result["selected_action"] == "select_tool"
    assert [row["table"] for row in result["rows"]] == ["customers"]