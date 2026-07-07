from typing import Optional, TypedDict

from app.core.llm.factory import get_llm_provider
from app.core.logging import logger
from app.core.prompts import get_prompt
from app.core.tools import get_tool
from langgraph.graph import END, StateGraph


class DataState(TypedDict):
    task: str  # Description of the data tak
    context: str  # Context for the previous research
    code: Optional[str]  # Generated python code
    query: Optional[str]  # SQL query
    execution_result: Optional[dict]
    error: Optional[str]
    iteration: int  # Iteration counter (max 3)
    analysis: Optional[str]  # Result of the analysis
    trace_id: str


async def analyze_task(state: DataState) -> DataState:
    """Decides which tool to use for the task."""
    if state.get("error"):
        logger.debug("analyze_task skipped due to prior error: %s", state.get("error"))
        return state

    logger.info("Analyzing the task to decide which tool to use")
    provider = get_llm_provider()
    system_prompt = get_prompt("data_analysis_system")
    user_prompt = get_prompt("data_analysis_user")

    response = await provider.generate(
        prompt=user_prompt.format(task=state["task"], context=state.get("context", "")),
        system=system_prompt.template,
    )

    return {**state, "analysis": response}


async def generate_code(state: DataState) -> DataState:
    """Generates Python or SQL code based on the analysis."""
    logger.info("Generating code for the task")
    provider = get_llm_provider()
    user_prompt = get_prompt("data_code_gen_user")
    system_prompt = get_prompt("data_code_gen_system")

    response = await provider.generate(
        prompt=user_prompt.format(
            task=state["task"],
            analysis=state.get("analysis", ""),
            error=state.get("error", "None"),
        ),
        system=system_prompt.template,
    )

    return {**state, "code": response}


async def execute_python(state: DataState) -> DataState:
    """Execute the generated Python code."""
    if not state.get("code"):
        logger.debug("No code provided for python execution node")
        return state

    logger.info("Executing python code")
    tool = get_tool("python_executor")
    result = await tool.execute(code=state["code"])

    return {
        **state,
        "execution_result": result.data if result.success else None,
        "error": result.error if not result.success else None,
        "iteration": state.get("iteration", 0) + 1,
    }


async def execute_sql(state: DataState) -> DataState:
    """Execute the generated SQL query."""
    if not state.get("code"):
        logger.debug("No code provided for SQL execution node")
        return state

    logger.info("Executing SQL query")
    tool = get_tool("sql_query")
    result = await tool.execute(query=state["code"])

    return {
        **state,
        "execution_result": result.data if result.success else None,
        "error": result.error if not result.success else None,
        "iteration": state.get("iteration", 0) + 1,
    }


def has_error(state: DataState) -> str:
    if state.get("error") and state.get("iteration", 0) < 3:
        return "retry"
    if state.get("error"):
        return "failed"
    return "success"


def needs_sql(state: DataState) -> str:
    """Determines whether SQL is also needed, based on the analysis."""
    analysis = state.get("analysis", "").lower()
    if "sql" in analysis or "database" in analysis or "query" in analysis:
        return "sql"
    return "python_only"


def build_data_graph() -> StateGraph:
    logger.info("Building data StateGraph")
    workflow = StateGraph(DataState)

    # Add nodes
    workflow.add_node("analyze_task", analyze_task)
    workflow.add_node("generate_code", generate_code)
    workflow.add_node("execute_python", execute_python)
    workflow.add_node("execute_sql", execute_sql)

    # Set entry point
    workflow.set_entry_point("analyze_task")

    # Define edges
    workflow.add_edge("analyze_task", "generate_code")
    workflow.add_conditional_edges(
        "generate_code",
        needs_sql,
        {
            "python_only": "execute_python",
            "sql": "execute_sql",
        },
    )
    workflow.add_conditional_edges(
        "execute_python",
        has_error,
        {
            "retry": "generate_code",  # Re-intentar con código corregido
            "success": END,
            "failed": END,
        },
    )
    workflow.add_edge("execute_sql", END)

    try:
        compiled = workflow.compile()
        logger.info("Data StateGraph compiled successfully")
        return compiled
    except Exception as e:
        logger.exception("Failed to compile data StateGraph: %s", e)
        raise
