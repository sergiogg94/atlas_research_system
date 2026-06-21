from app.core.prompts.planner import PlannerSystemPrompt, PlannerUserPrompt
from app.core.prompts.research import ResearchSystemPrompt, ResearchUserPrompt


_PROMPTS: dict[str, type] = {
    "planner_system": PlannerSystemPrompt,
    "planner_user": PlannerUserPrompt,
    "research_system": ResearchSystemPrompt,
    "research_user": ResearchUserPrompt,
}


def get_prompt(name: str) -> object:
    cls = _PROMPTS.get(name)
    if cls is None:
        raise KeyError(f"Prompt '{name}' not found. Available: {list(_PROMPTS.keys())}")
    return cls()