from app.core.prompts.data import (
    AnalysisSystemPrompt,
    AnalysisUserPrompt,
    CodeGenSystemPrompt,
    CodeGenUserPrompt,
)
from app.core.prompts.planner import PlannerSystemPrompt, PlannerUserPrompt
from app.core.prompts.research import ResearchSystemPrompt, ResearchUserPrompt
from app.core.prompts.synthesis import SynthesisSystemPrompt, SynthesisUserPrompt

_PROMPTS: dict[str, type] = {
    "planner_system": PlannerSystemPrompt,
    "planner_user": PlannerUserPrompt,
    "research_system": ResearchSystemPrompt,
    "research_user": ResearchUserPrompt,
    "data_analysis_system": AnalysisSystemPrompt,
    "data_analysis_user": AnalysisUserPrompt,
    "data_code_gen_system": CodeGenSystemPrompt,
    "data_code_gen_user": CodeGenUserPrompt,
    "synthesis_system": SynthesisSystemPrompt,
    "synthesis_user": SynthesisUserPrompt,
}


def get_prompt(name: str) -> object:
    cls = _PROMPTS.get(name)
    if cls is None:
        raise KeyError(f"Prompt '{name}' not found. Available: {list(_PROMPTS.keys())}")
    return cls()
