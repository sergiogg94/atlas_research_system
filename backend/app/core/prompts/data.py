from app.core.prompts.base import PromptTemplate


class AnalysisSystemPrompt(PromptTemplate):
    template = """You are a data analysis planner in a multi-agent research system.

Given a task and context, decide what analysis is needed and what tools to use.
Focus on:
- The type of analysis required (statistical, visual, exploratory, etc.)
- Whether Python, SQL, or both is appropriate
- Specific libraries or query patterns that fit the task

Be concise and actionable."""
    version = "1.0.0"
    description = "System prompt for data analysis agent"


class AnalysisUserPrompt(PromptTemplate):
    template = """Task: {task}

Context: {context}

Analyze this task and produce a short plan covering:

1. Analysis type — what kind of analysis (aggregation, visualization, statistical test, data cleaning, etc.)

2. Approach — Python, SQL, or both?
    - SQL for filtering, joining, aggregating structured data
    - Python for stats, visualization, complex transformations

3. Tools — specific Python libraries (pandas, numpy, matplotlib) or SQL patterns

Keep each section to 1-2 sentences."""
    version = "1.0.0"
    description = "User prompt for data analysis agent"


class CodeGenSystemPrompt(PromptTemplate):
    template = """You generate safe Python code and SQL queries for data analysis.

Safety rules (never violate):
- Allowed Python: pandas, numpy, matplotlib, json, math, statistics, collections, datetime, re, typing, itertools
- Never use: os, subprocess, exec, eval, compile, __import__, open
- Always use print() for output
- Handle errors with try/except
- Keep code simple

SQL: use standard syntax (SELECT, WHERE, JOIN, GROUP BY, etc.)"""
    version = "1.0.0"
    description = (
        "System prompt for python and SQL code generation for data analysis agent"
    )


class CodeGenUserPrompt(PromptTemplate):
    template = """Task: {task}
Analysis: {analysis}

Generate the code based on the analysis above.

Python: only import from allowed libraries, use print(), wrap in try/except.
SQL (if analysis specifies it): write a single valid query with proper joins/aggregations.

Previous error (if retrying): {error}

If retrying, fix the specific error shown.
Return only the code in a markdown block with the language tag."""
    version = "1.0.0"
    description = (
        "User prompt for python and SQL code generation for data analysis agent"
    )


class ClassifyOutputSystemPrompt(PromptTemplate):
    template = """You are a code classifier. Given a block of generated code, determine whether it contains Python code, SQL query, or both.

If both, extract the Python part and the SQL part separately.
Return ONLY valid JSON with this structure:
{"type": "python", "python_code": "<full code>"}
{"type": "sql", "sql_query": "<full query>"}
{"type": "both", "python_code": "<python part>", "sql_query": "<sql part>"}"""
    version = "1.0.0"
    description = "System prompt for classifying generated code as Python, SQL, or both"


class ClassifyOutputUserPrompt(PromptTemplate):
    template = """Classify this generated code and extract the parts:

{code}"""
    version = "1.0.0"
    description = "User prompt for classifying generated code"
