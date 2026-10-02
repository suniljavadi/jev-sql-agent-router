import asyncio

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import ProviderError
from app.services.jev_service import ACTIONS, QUESTIONS, MockJevProvider, TypeSafeJevProvider


@pytest.mark.parametrize("user_text,action", [
    ("customers", "execute_sql"), ("low confidence customers", "execute_sql"),
    ("retry customers", "retry"), ("clarify", "ask_clarification"),
    ("review", "human_review"), ("reject", "reject")])
def test_mock_scenarios(user_text, action):
    result = asyncio.run(MockJevProvider().decide(user_text, {}))
    assert result.selected_action.value == action


@pytest.mark.parametrize("failure", ["timeout", "http", "malformed"])
def test_typesafe_fail_closed(failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("timed out")
        if failure == "http":
            return httpx.Response(503)
        return httpx.Response(200, json={"selected_action": "execute_sql", "confidence": "bad"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = TypeSafeJevProvider(Settings(jev_base_url="https://example.test/decide",
                jev_model="configured-model", typesafe_api_key="test-key"), client)
            with pytest.raises(ProviderError):
                await provider.decide("customers", {"generated_sql": "SELECT 1"})

    asyncio.run(run())


def test_typesafe_payload_and_decision():
    def handler(request):
        import json
        payload = json.loads(request.content)
        assert payload["application_state"]["generated_sql"] == "SELECT 1"
        assert payload["user_request"] == "count"
        assert payload["available_actions"] == ACTIONS
        assert payload["decision_questions"] == QUESTIONS
        return httpx.Response(200, json={"selected_action": "execute_sql", "confidence": 0.96,
            "reason": "safe", "should_execute": True})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = TypeSafeJevProvider(Settings(jev_base_url="https://example.test/decide",
                jev_model="configured-model", typesafe_api_key="test-key"), client)
            assert (await provider.decide("count", {"generated_sql": "SELECT 1"})).confidence == 0.96

    asyncio.run(run())


def test_provider_failure_is_audited(client):
    from app.api.routes import get_agent
    from app.services.agent_service import AgentService
    from app.services.llm_service import MockLLM

    class FailingJev:
        async def decide(self, user_request, state):
            raise ProviderError("Jev decision unavailable or malformed")

    client.app.dependency_overrides[get_agent] = lambda: AgentService(
        Settings(database_url="sqlite://"), MockLLM(), FailingJev())
    result = client.post("/api/query", json={"user_request": "count customers"}).json()
    assert result["execution_status"] == "failed"
    assert result["selected_action"] is None
    assert client.get(f"/api/decisions/{result['audit_id']}").json()["execution_status"] == "failed"