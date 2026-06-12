from app.core.prompts.planner import PlannerSystemPrompt, PlannerUserPrompt


_PROMPTS: dict[str, type] = {
    "planner_system": PlannerSystemPrompt,
    "planner_user": PlannerUserPrompt,
}


def get_prompt(name: str) -> object:
    cls = _PROMPTS.get(name)
    if cls is None:
        raise KeyError(f"Prompt '{name}' not found. Available: {list(_PROMPTS.keys())}")
    return cls()