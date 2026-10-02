from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    user_request: str = Field(min_length=1, max_length=2000)