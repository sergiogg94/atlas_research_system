import json

from typing import TypedDict, Optional
from pydantic import ValidationError
from langgraph.graph import StateGraph, END

from app.core.llm.factory import get_llm_provider
from app.core.prompts import get_prompt
from app.schemas.plan import Plan


class PlannerState(TypedDict):
    task_description: str
    plan: Optional[Plan]
    error: Optional[str]
    llm_response: Optional[str]


def validate_task(state: PlannerState) -> PlannerState:
    """Validate that the task description is not empty."""
    if not state["task_description"] or len(state["task_description"]) < 10:
        return {**state, "error": "Task description must be at least 10 characters"}
    return state


async def generate_plan(state: PlannerState) -> PlannerState:
    """Call the LLM to generate a plan."""
    if state.get("error"):
        return state

    provider = get_llm_provider()
    sys_prompt = get_prompt("planner_system")
    user_prompt = get_prompt("planner_user")

    response = await provider.generate(
        prompt=user_prompt.format(task_description=state["task_description"]),
        system=sys_prompt.template,
    )

    return {**state, "llm_response": response}


def parse_plan(state: PlannerState) -> PlannerState:
    """Parse and validate the LLM response into a Plan."""
    if state.get("error"):
        return state

    try:
        data = json.loads(state["llm_response"])
        plan = Plan(**data)
        return {**state, "plan": plan}
    except (json.JSONDecodeError, ValidationError) as e:
        return {**state, "error": f"Failed to parse plan: {e}"}


def has_error(state: PlannerState) -> str:
    if state.get("error"):
        return "error"
    return "continue"


def plan_complete(state: PlannerState) -> str:
    if state.get("plan"):
        return "complete"
    if state.get("error"):
        return "error"
    return "continue"


def build_planner_graph() -> StateGraph:
    workflow = StateGraph(PlannerState)

    # Add nodes
    workflow.add_node("validate", validate_task)
    workflow.add_node("generate", generate_plan)
    workflow.add_node("parse", parse_plan)

    # Set entry point
    workflow.set_entry_point("validate")

    # Add edges
    workflow.add_conditional_edges(
        "validate",
        has_error,
        {"error": END, "continue": "generate"},
    )
    workflow.add_edge("generate", "parse")
    workflow.add_conditional_edges(
        "parse",
        plan_complete,
        {"complete": END, "error": END},
    )

    return workflow.compile()
