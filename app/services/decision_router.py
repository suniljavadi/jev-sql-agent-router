from dataclasses import dataclass

from app.core.config import Settings
from app.models.decision_models import Action, JevDecision


@dataclass(frozen=True)
class Route:
    action: Action
    reason: str
    extra_validation: bool = False


class DecisionRouter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def route(self, decision: JevDecision) -> Route:
        if decision.selected_action != Action.EXECUTE_SQL:
            return Route(decision.selected_action, decision.reason)
        if decision.confidence < self.settings.review_threshold:
            return Route(Action.HUMAN_REVIEW, "Confidence below review threshold")
        if decision.confidence < self.settings.auto_execute_threshold:
            return Route(Action.EXECUTE_SQL, "Medium confidence: strict read-only validation", True)
        return Route(Action.EXECUTE_SQL, decision.reason)