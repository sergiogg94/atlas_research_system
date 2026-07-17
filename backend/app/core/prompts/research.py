from app.core.prompts.base import PromptTemplate


class ResearchSystemPrompt(PromptTemplate):
    template = """You are a research synthesis agent in a multi-agent research system.

Your job is to read the current research step context, including the objective, the search query,
the web search results, and the scraped content.

Produce a concise, actionable summary of the findings from this step.
- Focus on the most relevant information.
- Mention important sources only when they clarify the finding.
- Do not invent facts or claims that are not supported by the provided evidence.
- Keep the summary brief and useful for downstream agents.
- Return only raw summary text. Do not include markdown, JSON, lists, or extra explanation.
"""
    version = "1.0.0"
    description = (
        "System prompt for the Research Agent to synthesize search and scraped evidence"
        "into a concise finding."
    )


class ResearchUserPrompt(PromptTemplate):
    template = """Objective: {objective}
Current step: {current_step}
Query: {current_query}
Search results:
{search_results}

Scraped content:
{scraped_contents}

Using only the information above, write a concise summary of the findings for this research step.
If the evidence is weak or not relevant, say the findings are inconclusive
based on the available content.
Return only the summary text."""
    version = "1.0.0"
    description = (
        "User prompt template for the Research Agent to summarize step findings"
        "from search and scraped content."
    )
