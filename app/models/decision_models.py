from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Action(str, Enum):
    EXECUTE_SQL = "execute_sql"
    RETRY = "retry"
    ASK_CLARIFICATION = "ask_clarification"
    REJECT = "reject"
    HUMAN_REVIEW = "human_review"
    SELECT_TOOL = "select_tool"


class JevDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_action: Action
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)
    should_execute: bool = False
    should_retry: bool = False
    needs_clarification: bool = False
    requires_human_review: bool = False

    @model_validator(mode="after")
    def check_flags(self) -> "JevDecision":
        expected = {
            "should_execute": self.selected_action == Action.EXECUTE_SQL,
            "should_retry": self.selected_action == Action.RETRY,
            "needs_clarification": self.selected_action == Action.ASK_CLARIFICATION,
            "requires_human_review": self.selected_action == Action.HUMAN_REVIEW,
        }
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("Decision flags contradict selected_action")
        return self


class TypeSafeChoiceAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["choice"]
    choice: str
    confidence: float = Field(ge=0, le=1)
    probabilities: dict[str, float]


class TypeSafeSystemOneResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str
    answers: dict[str, TypeSafeChoiceAnswer]
    usage: dict[str, int | None] | None = None