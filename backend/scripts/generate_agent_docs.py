#!/usr/bin/env python3
"""Generate Mermaid flow diagrams for LangGraph agents using LangGraph introspection API.

Usage:
    uv run python scripts/generate_agent_docs.py
    uv run python scripts/generate_agent_docs.py --agent planner
    uv run python scripts/generate_agent_docs.py --output docs
"""

import argparse
import ast
import importlib
import inspect
import re
import sys
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BACKEND_DIR.parent / "docs"
AGENTS_DIR = BACKEND_DIR / "app" / "core" / "agents"

sys.path.insert(0, str(BACKEND_DIR))


def discover_agents() -> list[Path]:
    if not AGENTS_DIR.exists():
        print(f"Error: agents directory not found at {AGENTS_DIR}", file=sys.stderr)
        sys.exit(1)
    return sorted(p for p in AGENTS_DIR.glob("*.py") if p.stem != "__init__")


def find_build_fn(module):
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        if re.match(r"^build_\w+_graph$", name):
            return obj
    return None


def parse_node_mappings(source_file: Path) -> dict[str, str]:
    """Map registered node names back to their function names via AST."""
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    mappings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = getattr(node, "func", None)
            attr = getattr(func, "attr", None)
            if attr == "add_node" and len(node.args) >= 2:
                name_arg, func_arg = node.args[0], node.args[1]
                if isinstance(name_arg, ast.Constant) and isinstance(func_arg, ast.Name):
                    mappings[name_arg.value] = func_arg.id
    return mappings


def get_state_fields(state_class) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    if hasattr(state_class, "__annotations__"):
        for name, tp in state_class.__annotations__.items():
            fields.append((name, _type_name(tp)))
    elif hasattr(state_class, "__fields__"):
        for name, field in state_class.__fields__.items():
            fields.append((name, _type_name(field.annotation)))
    return fields


def _type_name(tp) -> str:
    origin = getattr(tp, "__origin__", None)
    args = getattr(tp, "__args__", None)
    if origin is type(None):
        return "None"
    if origin is not None and hasattr(origin, "__name__"):
        if origin.__name__ == "Union" and args and len(args) == 2 and type(None) in args:
            other = next(a for a in args if a is not type(None))
            return f"Optional[{_type_name(other)}]"
    name = getattr(tp, "__name__", str(tp))
    if "." in name:
        name = name.split(".")[-1]
    return name


def categorize_node(node_name: str) -> str:
    lower = node_name.lower()
    if "validate" in lower or "check" in lower or "verify" in lower:
        return "validation"
    if "generate" in lower or "llm" in lower or "call" in lower:
        return "llm"
    if "parse" in lower or "extract" in lower:
        return "parse"
    if "search" in lower or "scrape" in lower:
        return "tool"
    return "default"


_NODE_STYLE: dict[str, str] = {
    "validation": "fill:#4caf50,stroke:#333,stroke-width:2px,color:#fff",
    "llm": "fill:#2196f3,stroke:#333,stroke-width:2px,color:#fff",
    "parse": "fill:#ff9800,stroke:#333,stroke-width:2px,color:#fff",
    "tool": "fill:#9c27b0,stroke:#333,stroke-width:2px,color:#fff",
    "default": "fill:#607d8b,stroke:#333,stroke-width:2px,color:#fff",
}

_NODE_ICON: dict[str, str] = {
    "validation": "✓",
    "llm": "🤖",
    "parse": "📋",
    "tool": "🔧",
    "default": "⚙",
}


def _render_edge_label(label) -> str:
    if label is None:
        return ""
    text = str(label).replace('"', "")
    return f"|{text}|"


def generate_mermaid(
    agent_name: str,
    node_names: list[str],
    edges: list,
    state_fields: list[tuple[str, str]],
) -> str:
    lines: list[str] = []
    lines.append("%%{init: {'flowchart': {'curve': 'linear'}}}%%")
    lines.append("graph TD;")
    lines.append("")

    has_conditional = any(e[3] for e in edges)

    nodes = set(node_names)
    for n in nodes:
        cat = categorize_node(n)
        icon = _NODE_ICON.get(cat, "")
        label = f"{icon} {n}" if icon else n
        lines.append(f"    {n}(\"{label}\")")

    lines.append("")

    for source, target, label, is_conditional in edges:
        src = source.replace("__start__", "__start__([\"Start\"]):::first") if source == "__start__" else source
        tgt = target.replace("__end__", "__end__([\"End\"]):::last") if target == "__end__" else target

        if is_conditional:
            text = str(label) if label else ""
            lines.append(f"    {src} -. &nbsp;{text}&nbsp; .-> {tgt};")
        else:
            lines.append(f"    {src} --> {tgt};")

    lines.append("")

    style_groups: dict[str, list[str]] = {}
    for n in nodes:
        cat = categorize_node(n)
        style_groups.setdefault(cat, []).append(n)

    for cat, names in style_groups.items():
        cls = f"{cat}Node"
        lines.append(f"    class {' '.join(names)} {cls};")

    lines.append("    classDef first fill-opacity:0;")
    lines.append("    classDef last fill:#bfb6fc;")
    for cat, style in _NODE_STYLE.items():
        if cat in style_groups:
            cls = f"{cat}Node"
            lines.append(f"    classDef {cls} {style};")

    return "\n".join(lines)


def generate_doc(
    agent_name: str,
    compiled,
    source_file: Path,
    module,
) -> str:
    node_mapping = parse_node_mappings(source_file)

    state_class = getattr(compiled, "InputType", None)
    state_fields = get_state_fields(state_class) if state_class else []

    graph = compiled.get_graph()

    node_names: list[str] = []
    node_infos: list[tuple[str, str, str]] = []
    for nid, nobj in graph.nodes.items():
        if nid in ("__start__", "__end__"):
            continue
        node_names.append(nid)
        func_name = node_mapping.get(nid)
        func = getattr(module, func_name, None) if func_name else None
        desc = (func.__doc__ or "").strip() if func else ""
        node_infos.append((nid, func_name or "", desc))

    edges: list = []
    for e in graph.edges:
        edges.append((e.source, e.target, e.data, e.conditional))

    mermaid_code = generate_mermaid(agent_name, node_names, edges, state_fields)

    lines: list[str] = []
    lines.append(f"# {agent_name.title()} Agent")
    lines.append("")
    lines.append(f"**Source**: `app/core/agents/{agent_name}.py`")
    lines.append("")

    if state_fields:
        lines.append("## State")
        lines.append("")
        lines.append("| Field | Type |")
        lines.append("|-------|------|")
        for fname, ftype in state_fields:
            lines.append(f"| `{fname}` | `{ftype}` |")
        lines.append("")

    lines.append("## Flow Diagram")
    lines.append("")
    lines.append("```mermaid")
    lines.append(mermaid_code)
    lines.append("```")
    lines.append("")

    lines.append("## Nodes")
    lines.append("")
    lines.append("| Node | Function | Type | Description |")
    lines.append("|------|----------|------|-------------|")
    for nid, fname, desc in node_infos:
        cat = categorize_node(nid)
        short_desc = desc.split("\n")[0].strip() if desc else "*No description*"
        func_display = f"`{fname}()`" if fname else "*inline*"
        lines.append(f"| `{nid}` | {func_display} | {cat} | {short_desc} |")
    lines.append("")

    lines.append("## Edges")
    lines.append("")
    lines.append("| From | To | Condition | Type |")
    lines.append("|------|----|-----------|------|")
    for src, tgt, label, is_cond in edges:
        src_d = src.replace("__start__", "START").replace("__end__", "END")
        tgt_d = tgt.replace("__start__", "START").replace("__end__", "END")
        lbl = str(label) if label else "—"
        etype = "conditional" if is_cond else "direct"
        lines.append(f"| `{src_d}` | `{tgt_d}` | `{lbl}` | {etype} |")
    lines.append("")

    return "\n".join(lines)


def process_agent(agent_path: Path, output_dir: Path) -> Optional[Path]:
    agent_name = agent_path.stem
    print(f"  Processing `{agent_name}`...", end=" ")

    try:
        module = importlib.import_module(f"app.core.agents.{agent_name}")
    except ImportError as e:
        print(f"ERROR: {e}")
        return None

    build_fn = find_build_fn(module)
    if not build_fn:
        print("SKIPPED (no build_*_graph function)")
        return None

    try:
        compiled = build_fn()
    except Exception as e:
        print(f"ERROR building graph: {e}")
        return None

    doc_content = generate_doc(agent_name, compiled, agent_path, module)

    output_path = output_dir / f"{agent_name}_graph.md"
    output_path.write_text(doc_content, encoding="utf-8")
    print(f"OK -> {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate Mermaid flow diagrams for LangGraph agents"
    )
    parser.add_argument(
        "--agent", "-a",
        help="Specific agent to document (e.g., 'planner')",
    )
    parser.add_argument(
        "--output", "-o",
        default=str(DOCS_DIR),
        help=f"Output directory (default: {DOCS_DIR})",
    )

    args = parser.parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.agent:
        agent_path = AGENTS_DIR / f"{args.agent}.py"
        if not agent_path.exists():
            print(f"Error: agent `{args.agent}` not found at {agent_path}", file=sys.stderr)
            sys.exit(1)
        paths = [agent_path]
    else:
        paths = discover_agents()
        if not paths:
            print(f"No agent files found in {AGENTS_DIR}")
            return

    print(f"Generating agent documentation in {output_dir}/\n")
    results = []
    for path in paths:
        r = process_agent(path, output_dir)
        if r:
            results.append(r)

    print(f"\nDone — {len(results)} document(s) generated in {output_dir}/")


if __name__ == "__main__":
    main()
