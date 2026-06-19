from typing import Optional, TypedDict

from app.core.logging import logger
from app.core.tools import get_tool
from app.schemas.plan import Plan
from langgraph.graph import END, StateGraph


class ResearchState(TypedDict):
    objective: str  # Original plan objective
    steps: list  # Stepts taken/completed
    current_step: int  # Current step
    findings: list  # Findings from research
    error: Optional[str]  # Error message if any step fails
    current_query: Optional[str]  # Current query being researched
    search_results: Optional[list]  # Results from web search
    scraped_contents: Optional[list]  # Scraped content from search results


async def parse_step(state: ResearchState) -> ResearchState:
    """Defines the current query based on the current step and objective."""
    if state.get("error"):
        logger.debug("parse_step skipped due to prior error: %s", state.get("error"))
        return state

    step = state["steps"][state["current_step"]]
    query = f"{step['action']} {state['objective']}"

    logger.info("Parsing step %s: %s", state["current_step"], step)
    logger.debug("Generated query: %s", query[:500])

    return {
        **state,
        "current_query": query,
    }


async def search_web(state: ResearchState) -> ResearchState:
    """Executes a web search."""
    if state.get("error"):
        logger.debug("search_web skipped due to prior error: %s", state.get("error"))
        return state

    logger.info("Executing web search for query: %s", state.get("current_query"))
    tool = get_tool("web_search")
    result = await tool.execute(query=state["current_query"])

    if not result.success:
        logger.warning("Web search failed: %s", result.error)
        return {**state, "error": f"Search failed: {result.error}"}

    logger.info(
        "Web search completed with %s results", len(result.data) if result.data else 0
    )
    return {**state, "search_results": result.data}


async def scrape_content(state: ResearchState) -> ResearchState:
    """Scrapes content from the search results."""
    if state.get("error") or not state.get("search_results"):
        logger.debug(
            "scrape_content skipped due to prior error or no search results: %s",
            state.get("error") or "No search results",
        )
        return state

    logger.info("Scraping content from search results")
    logger.debug("Step %s", state["current_step"])
    tool = get_tool("web_scraper")
    contents = []

    for item in state["search_results"][:3]:
        url = item.get("href") or item.get("link")
        if url:
            logger.info("Scraping URL: %s", url)
            scraped = await tool.execute(url=url, max_chars=3000)
            if scraped.success:
                logger.info("Scraping successful")
                contents.append(
                    {
                        "url": url,
                        "title": item.get("title", ""),
                        "content": scraped.data["content"],
                    }
                )
            else:
                logger.warning("Scraping failed for %s: %s", url, scraped.error)

    return {**state, "scraped_contents": contents}


async def synthesize_finding(state: ResearchState) -> ResearchState:
    """Sinthesizes the findings into a summary for the current step."""
    if state.get("error"):
        logger.debug(
            "synthesize_finding skipped due to prior error: %s", state.get("error")
        )
        return state

    logger.info("Synthesizing findings for step %s", state["current_step"])
    finding = {
        "step": state["current_step"],
        "query": state["current_query"],
        "summary": f"Found {len(state.get('search_results', []))} results, "
        f"scraped {len(state.get('scraped_contents', []))} pages",
    }

    findings = state.get("findings", []) + [finding]

    return {
        **state,
        "findings": findings,
        "current_step": state["current_step"] + 1,
    }


def has_more_steps(state: ResearchState) -> str:
    if state.get("error"):
        return "error"
    if state["current_step"] < len(state["steps"]):
        return "continue"
    return "complete"


def research_complete(state: ResearchState) -> str:
    if state.get("error"):
        return "error"
    if state.get("findings"):
        return "complete"
    return "incomplete"


def build_research_graph() -> StateGraph:
    logger.info("Building research StateGraph")
    workflow = StateGraph(ResearchState)

    # Add nodes
    workflow.add_node("parse_step", parse_step)
    workflow.add_node("search_web", search_web)
    workflow.add_node("scrape_content", scrape_content)
    workflow.add_node("synthesize_finding", synthesize_finding)

    # Set entry point
    workflow.set_entry_point("parse_step")

    # Define edges
    workflow.add_edge("parse_step", "search_web")
    workflow.add_edge("search_web", "scrape_content")
    workflow.add_edge("scrape_content", "synthesize_finding")
    workflow.add_conditional_edges(
        "synthesize_finding",
        has_more_steps,
        {
            "continue": "parse_step",
            "complete": END,
            "error": END,
        },
    )

    try:
        compiled = workflow.compile()
        logger.info("Research StateGraph compiled successfully")
        return compiled
    except Exception as e:
        logger.exception("Failed to compile research StateGraph: %s", e)
        raise
