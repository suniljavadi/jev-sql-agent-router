import asyncio

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import ProviderError
from app.services.jev_service import ACTION_CRITERIA, ACTIONS, MockJevProvider, TypeSafeJevProvider


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
        return httpx.Response(200, json={"model": "jev-1.13.0", "answers": {
            "selected_action": {"type": "choice", "choice": "execute_sql", "confidence": "bad",
                                "probabilities": {"execute_sql": 1.0}}}, "usage": {}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = TypeSafeJevProvider(Settings(jev_base_url="https://example.test/decide",
                jev_model="configured-model", typesafe_api_key="test-key"), client)
            with pytest.raises(ProviderError):
                await provider.decide("customers", {"generated_sql": "SELECT 1"})

    asyncio.run(run())


def test_typesafe_official_payload_and_decision():
    def handler(request):
        import json
        payload = json.loads(request.content)
        assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert payload["state"]["application_state"]["generated_sql"] == "SELECT 1"
        assert payload["state"]["user_request"] == "count"
        assert payload["state"]["available_actions"] == ACTIONS
        assert payload["model"] == "jev-latest"
        assert payload["questions"]["selected_action"]["type"] == "choice"
        assert payload["questions"]["selected_action"]["criteria"] == ACTION_CRITERIA
        return httpx.Response(200, json={"model": "jev-1.13.0", "answers": {
            "selected_action": {"type": "choice", "choice": "execute_sql", "confidence": 0.96,
                                "probabilities": {action: float(action == "execute_sql") for action in ACTIONS}}},
            "usage": {"input_tokens": 42, "output_tokens": 5}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = TypeSafeJevProvider(Settings(typesafe_api_key="test-key"), client)
            result = await provider.decide("count", {"generated_sql": "SELECT 1"})
            assert result.selected_action.value == "execute_sql"
            assert result.confidence == 0.96
            assert result.should_execute is True

    asyncio.run(run())


def test_typesafe_maps_human_review_answer():
    def handler(request):
        import json
        payload = json.loads(request.content)
        return httpx.Response(200, json={"model": "jev-1.13.0", "answers": {
            "selected_action": {"type": "choice", "choice": "human_review", "confidence": 0.91,
                                "probabilities": {action: float(action == "human_review") for action in ACTIONS}}},
            "usage": {"input_tokens": 42, "output_tokens": 5}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = TypeSafeJevProvider(Settings(typesafe_api_key="test-key"), client)
            result = await provider.decide("uncertain request", {})
            assert result.selected_action.value == "human_review"
            assert result.requires_human_review is True

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