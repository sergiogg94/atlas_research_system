from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.core.llm.factory import get_llm_provider
from app.core.logging import logger
from app.core.prompts import get_prompt

MAX_ITERATIONS = 3


class SynthesisState(TypedDict):
    objective: str
    task_description: str
    plan: dict | None
    research_findings: list | None
    data_results: list | None
    report: str | None
    error: str | None
    iteration: int
    trace_id: str


async def collect_results(state: SynthesisState) -> SynthesisState:
    """Consolidates inputs from previous agents within a structured context."""
    if state.get("error"):
        logger.debug(
            "collect_results skipped due to prior error: %s", state.get("error")
        )
        return state

    logger.info("Collecting results from plan, research, and data agents")
    return {**state}


async def generate_synthesis(state: SynthesisState) -> SynthesisState:
    """The LLM generates a final report based on all the findings."""
    iteration = state.get("iteration", 0) + 1
    logger.info(
        "Generating synthesis report (attempt %d/%d)", iteration, MAX_ITERATIONS
    )

    if state.get("error"):
        logger.warning("generate_synthesis skipped due to prior error")
        return {**state, "iteration": iteration}

    provider = get_llm_provider()
    system_prompt = get_prompt("synthesis_system")
    user_prompt = get_prompt("synthesis_user")

    context = {
        "objective": state.get("objective"),
        "task_description": state.get("task_description"),
        "plan": state.get("plan"),
        "research_findings": state.get("research_findings"),
        "data_results": state.get("data_results"),
    }

    response = await provider.generate(
        prompt=user_prompt.format(context=context),
        system=system_prompt.template,
    )

    return {**state, "report": response, "iteration": iteration}


async def validate_report(state: SynthesisState) -> SynthesisState:
    """Verify that the generated report has a valid structure."""
    iteration = state.get("iteration", 0)
    logger.info("Validating report (attempt %d/%d)", iteration, MAX_ITERATIONS)

    if state.get("error"):
        logger.warning("validate_report: prior error detected, skipping")
        return state

    if not state.get("report"):
        logger.warning("No report was generated on attempt %d", iteration)
        if iteration >= MAX_ITERATIONS:
            return {**state, "error": "No report was generated"}
        return state

    logger.info("Validation completed successfully")
    return {**state, "error": None}  # Limpia errores previos de reintentos


def synthesis_complete(state: SynthesisState) -> str:
    """Conditional router: decides the next step after validation."""
    iteration = state.get("iteration", 0)

    if state.get("report") and not state.get("error"):
        logger.info("Synthesis complete after %d attempt(s)", iteration)
        return "complete"

    if iteration >= MAX_ITERATIONS:
        logger.error(
            "Max iterations (%d) reached without a valid report. Last error: %s",
            MAX_ITERATIONS,
            state.get("error"),
        )
        return "max_retries_exceeded"

    logger.warning("Retrying synthesis (attempt %d/%d)", iteration, MAX_ITERATIONS)
    return "retry"


def build_synthesis_graph() -> StateGraph:
    logger.info("Building synthesis StateGraph")
    workflow = StateGraph(SynthesisState)

    # Add nodes
    workflow.add_node("collect_results", collect_results)
    workflow.add_node("generate_synthesis", generate_synthesis)
    workflow.add_node("validate_report", validate_report)

    # Set entry point
    workflow.set_entry_point("collect_results")

    # Define edges
    workflow.add_edge("collect_results", "generate_synthesis")
    workflow.add_edge("generate_synthesis", "validate_report")

    workflow.add_conditional_edges(
        "validate_report",
        synthesis_complete,
        {
            "complete": END,
            "retry": "generate_synthesis",
            "max_retries_exceeded": END,
        },
    )

    return workflow.compile()
