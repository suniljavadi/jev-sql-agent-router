import asyncio
import json

import httpx

from app.core.config import Settings
from app.services.llm_service import OpenAICompatibleLLM


def test_openai_compatible_request_uses_bearer_auth():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-key"
        assert str(request.url) == "https://llm.example.test/v1/chat/completions"
        assert json.loads(request.content)["model"] == "test-model"
        return httpx.Response(200, json={"choices": [{
            "message": {"content": "SELECT 1"}
        }]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAICompatibleLLM(Settings(
                llm_base_url="https://llm.example.test/v1/chat/completions",
                llm_model="test-model",
                llm_api_key="test-key",
            ), client)
            result = await provider.generate("count customers")
            assert result.sql == "SELECT 1"
            assert result.intent == "sql"

    asyncio.run(run())
