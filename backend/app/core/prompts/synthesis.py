from app.core.prompts.base import PromptTemplate


class SynthesisSystemPrompt(PromptTemplate):
    template = """You are a senior research analyst specializing in synthesizing
information from multiple sources into clear, structured reports.

You will receive:
1. The original task and plan
2. Web research findings
3. Data analysis results

Produce a comprehensive report with:
- Executive summary
- Key findings organized by theme
- Data-backed insights
- Conclusions and recommendations
- References"""
    version = "1.0.0"
    description = "System prompt for data analysis agent"


class SynthesisUserPrompt(PromptTemplate):
    template = """Synthesize the following research into a structured report.

{context}

Return the report in markdown format with clear sections."""
    version = "1.0.0"
    description = "User prompt for data analysis agent"
