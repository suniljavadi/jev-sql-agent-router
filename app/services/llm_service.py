from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings
from app.core.exceptions import ProviderError


@dataclass(frozen=True)
class LLMResult:
    sql: str | None
    intent: str


class LLMProvider(Protocol):
    async def generate(self, request: str) -> LLMResult: ...


class MockLLM:
    async def generate(self, request: str) -> LLMResult:
        lower = request.lower()
        if "clarif" in lower or "ambiguous" in lower:
            return LLMResult(None, "clarification")
        if "delete" in lower or "drop" in lower:
            return LLMResult("DELETE FROM customers", "sql")
        if "invalid" in lower:
            return LLMResult("SELECT missing FROM customers", "sql")
        if "total" in lower or "sum" in lower:
            return LLMResult("SELECT region, SUM(revenue) AS total_revenue FROM customers GROUP BY region", "sql")
        if "count" in lower:
            return LLMResult("SELECT COUNT(*) AS customer_count FROM customers", "sql")
        if "customer" in lower or "revenue" in lower:
            return LLMResult("SELECT id, name, region, revenue FROM customers ORDER BY id", "sql")
        return LLMResult(None, "unsupported")


class OpenAICompatibleLLM:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client

    async def generate(self, request: str) -> LLMResult:
        if not all((self.settings.llm_base_url, self.settings.llm_model, self.settings.llm_api_key)):
            raise ProviderError("LLM endpoint, model and key must be configured")
        client = self.client or httpx.AsyncClient(timeout=self.settings.external_timeout_seconds)
        try:
            response = await client.post(
                self.settings.llm_base_url,
                headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                json={"model": self.settings.llm_model, "messages": [
                    {"role": "system", "content": "Return one read-only SQL SELECT for the customers table (id, name, region, revenue). Return only SQL; if unclear or unrelated, return CLARIFY."},
                    {"role": "user", "content": request},
                ]},
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()
            if content == "CLARIFY":
                return LLMResult(None, "clarification")
            return LLMResult(content, "sql")
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise ProviderError("LLM provider failed") from exc
        finally:
            if self.client is None:
                await client.aclose()


def make_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockLLM()
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleLLM(settings)
    raise ValueError("Unknown LLM_PROVIDER")