from hmac import compare_digest

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_access(
    key: str | None = Depends(api_key_header), settings: Settings = Depends(get_settings)
) -> None:
    if not settings.api_key and settings.jev_provider == "mock" and settings.llm_provider == "mock":
        return
    if key and ((settings.api_key and compare_digest(key, settings.api_key)) or
                (settings.reviewer_api_key and compare_digest(key, settings.reviewer_api_key))):
        return
    raise HTTPException(status_code=401, detail="Invalid API key")


def require_reviewer(
    key: str | None = Depends(api_key_header), settings: Settings = Depends(get_settings)
) -> None:
    if key and settings.reviewer_api_key and compare_digest(key, settings.reviewer_api_key):
        return
    raise HTTPException(status_code=401, detail="Invalid reviewer key")