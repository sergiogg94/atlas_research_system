# Research Agent

**Source**: `app/core/agents/research.py`

## State

| Field | Type |
|-------|------|
| `objective` | `str` |
| `steps` | `list` |
| `current_step` | `int` |
| `findings` | `list` |
| `error` | `Optional[str]` |
| `current_query` | `Optional[str]` |
| `search_results` | `Optional[list]` |
| `scraped_contents` | `Optional[list]` |

## Flow Diagram

```mermaid
%%{init: {'flowchart': {'curve': 'linear'}}}%%
graph TD;

    parse_step("📋 parse_step")
    search_web("🔧 search_web")
    scrape_content("🔧 scrape_content")
    synthesize_finding("⚙ synthesize_finding")

    __start__(["Start"]):::first --> parse_step;
    parse_step --> search_web;
    search_web --> scrape_content;
    scrape_content --> synthesize_finding;
    synthesize_finding -. &nbsp;complete&nbsp; .-> __end__(["End"]):::last;
    synthesize_finding -. &nbsp;continue&nbsp; .-> parse_step;

    class parse_step parseNode;
    class search_web,scrape_content toolNode;
    class synthesize_finding defaultNode;
    classDef first fill-opacity:0;
    classDef last fill:#bfb6fc;
    classDef parseNode fill:#ff9800,stroke:#333,stroke-width:2px,color:#fff;
    classDef toolNode fill:#9c27b0,stroke:#333,stroke-width:2px,color:#fff;
    classDef defaultNode fill:#607d8b,stroke:#333,stroke-width:2px,color:#fff;
```

## Nodes

| Node | Function | Type | Description |
|------|----------|------|-------------|
| `parse_step` | `parse_step()` | parse | Defines the current query based on the current step and objective. |
| `search_web` | `search_web()` | tool | Executes a web search. |
| `scrape_content` | `scrape_content()` | tool | Scrapes content from the search results. |
| `synthesize_finding` | `synthesize_finding()` | default | Sinthesizes the findings into a summary for the current step. |

## Edges

| From | To | Condition | Type |
|------|----|-----------|------|
| `START` | `parse_step` | `—` | direct |
| `parse_step` | `search_web` | `—` | direct |
| `scrape_content` | `synthesize_finding` | `—` | direct |
| `search_web` | `scrape_content` | `—` | direct |
| `synthesize_finding` | `END` | `complete` | conditional |
| `synthesize_finding` | `parse_step` | `continue` | conditional |
