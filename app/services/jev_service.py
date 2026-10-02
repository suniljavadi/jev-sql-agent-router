from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import ProviderError
from app.models.decision_models import Action, JevDecision


ACTIONS = [action.value for action in Action]
QUESTIONS = ["Is the SQL safe to execute?", "Is the request unambiguous?", "Should this action require a human?", "Should execution be retried or another tool selected?"]


class JevProvider(Protocol):
    async def decide(self, user_request: str, state: dict[str, Any]) -> JevDecision: ...


def decision(action: Action, confidence: float, reason: str) -> JevDecision:
    return JevDecision(selected_action=action, confidence=confidence, reason=reason,
                       should_execute=action == Action.EXECUTE_SQL, should_retry=action == Action.RETRY,
                       needs_clarification=action == Action.ASK_CLARIFICATION,
                       requires_human_review=action == Action.HUMAN_REVIEW)


class MockJevProvider:
    async def decide(self, user_request: str, state: dict[str, Any]) -> JevDecision:
        lower = user_request.lower()
        if "reject" in lower or state.get("security") == "blocked":
            return decision(Action.REJECT, 0.99, "Request is rejected by policy")
        if "review" in lower:
            return decision(Action.HUMAN_REVIEW, 0.95, "Explicit review requested")
        if "clarif" in lower or state.get("intent") == "clarification":
            return decision(Action.ASK_CLARIFICATION, 0.95, "Request needs more detail")
        if "retry" in lower:
            return decision(Action.RETRY, 0.95, "Transient execution may be retried")
        if "tool" in lower or state.get("intent") == "unsupported":
            return decision(Action.SELECT_TOOL, 0.95, "A different tool is required")
        if "low confidence" in lower:
            return decision(Action.EXECUTE_SQL, 0.55, "Insufficient confidence for execution")
        if "medium confidence" in lower:
            return decision(Action.EXECUTE_SQL, 0.80, "Additional validation required")
        return decision(Action.EXECUTE_SQL, 0.96, "Safe, unambiguous read-only query")


class TypeSafeJevProvider:
    """Versioned local adapter contract; map the documented Jev API here for deployment."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client

    async def decide(self, user_request: str, state: dict[str, Any]) -> JevDecision:
        if not all((self.settings.jev_base_url, self.settings.jev_model, self.settings.typesafe_api_key)):
            raise ProviderError("Jev endpoint, model and key must be configured")
        client = self.client or httpx.AsyncClient(timeout=self.settings.external_timeout_seconds)
        try:
            response = await client.post(self.settings.jev_base_url,
                headers={"Authorization": f"Bearer {self.settings.typesafe_api_key}"},
                json={"model": self.settings.jev_model, "application_state": state,
                      "user_request": user_request, "available_actions": ACTIONS,
                      "decision_questions": QUESTIONS})
            response.raise_for_status()
            return JevDecision.model_validate(response.json())
        except (httpx.TimeoutException, httpx.HTTPError, ValidationError, ValueError) as exc:
            raise ProviderError("Jev decision unavailable or malformed") from exc
        finally:
            if self.client is None:
                await client.aclose()


class JevService:
    def __init__(self, provider: JevProvider):
        self.provider = provider

    async def decide(self, user_request: str, state: dict[str, Any]) -> JevDecision:
        return await self.provider.decide(user_request, state)


def make_jev(settings: Settings) -> JevService:
    if settings.jev_provider == "mock":
        return JevService(MockJevProvider())
    if settings.jev_provider == "typesafe":
        return JevService(TypeSafeJevProvider(settings))
    raise ValueError("Unknown JEV_PROVIDER")