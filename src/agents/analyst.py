# Analyst Agent
#
# Investigates the codebase to understand what needs to change for a requirement.
# Read-only — cannot write files or run tests.
#
# Tools: search_code, get_dependencies, read_file
#
# Why read-only?
#   The analyst's job is to UNDERSTAND, not to implement.
#   By giving it only read tools, it physically cannot modify anything —
#   the guardrail is in the tool set, not just the system prompt.
#
# Returns a structured dict:
#   {
#     "feasible":        bool,
#     "repo":            str,   — which service repo needs the change
#     "files_to_change": list,  — file paths to modify
#     "summary":         str    — what needs to change and why
#   }
#
# CodeAtlas comparison:
#   Same concept as multi_agent_demo/analyst_agent.py — read-only investigation.
#   Here: real LangChain tools, structured JSON output, shared observability trace.
#
# Usage:
#   PYTHONPATH=. uv run python3 src/agents/analyst.py codeatlas/ecommerce "Add validation to reserve_stock"

import sys
import json
import re
import time
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from src.tools.codebase import make_read_tools
from src.observability.tracer import new_trace, record_llm_call, record_tool_call, finish_trace

load_dotenv()

ANALYST_SYSTEM_PROMPT = """
You are a senior software engineering analyst.

Your job is to investigate a codebase and understand exactly what needs to change for a given requirement.

Rules:
- Search the codebase thoroughly before drawing any conclusion
- Read the relevant files to understand the current implementation
- Identify exactly which repo and which files need to change
- Determine the status of the requirement given the current code
- Do not suggest implementation details — only investigate and report findings

When you have finished investigating, return your findings as a JSON object ONLY.
No explanation, no markdown, just the JSON:
{
  "status": "feasible" or "already_implemented" or "not_feasible",
  "repo": "name of the service repo that needs to change",
  "files_to_change": ["relative/path/to/file.py"],
  "summary": "what needs to change and why, in plain English"
}

Status values:
  feasible            — requirement is valid and needs to be implemented
  already_implemented — the requirement is already satisfied in the current code
  not_feasible        — the requirement cannot be implemented (out of scope, impossible, etc.)

If status is already_implemented or not_feasible, files_to_change can be an empty list.
"""


def _extract_json(text: str) -> dict:
    """
    Parses the analyst's final response as JSON.
    Handles the case where the LLM wraps the JSON in markdown code blocks.
    """
    # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    return json.loads(text)


def run_analyst(project: str, requirement: str, obs: dict = None) -> dict:
    """
    Runs the analyst agent to investigate the codebase for a given requirement.

    project     — which project to search (e.g. "codeatlas/ecommerce")
    requirement — the user's requirement
    obs         — optional shared observability trace from the orchestrator

    Returns:
        {feasible, repo, files_to_change, summary}
    """
    standalone = obs is None
    if standalone:
        obs = new_trace()

    # Read-only tools — analyst cannot write or run tests
    llm            = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tools          = make_read_tools(project)
    llm_with_tools = llm.bind_tools(tools)
    tool_by_name   = {t.name: t for t in tools}

    messages = [
        SystemMessage(ANALYST_SYSTEM_PROMPT),
        HumanMessage(f"Requirement: {requirement}"),
    ]

    print("\n--- Analyst starting ---\n")

    # Agent loop — same pattern as executor.py, different tools and return type
    while True:
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        record_llm_call(obs, response)

        # No tool calls = LLM has finished investigating — parse the JSON result
        if not response.tool_calls:
            print("\n--- Analyst done ---")
            if standalone:
                finish_trace(obs)
            return _extract_json(response.content)

        # Execute each tool the LLM requested
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            print(f"Tool called : {tool_name}")
            print(f"Arguments   : {tool_args}")

            tool_fn    = tool_by_name[tool_name]
            tool_start = time.perf_counter()
            try:
                result  = tool_fn.invoke(tool_args)
                success = True
            except Exception as e:
                result  = {"error": str(e)}
                success = False

            duration_ms = (time.perf_counter() - tool_start) * 1000
            record_tool_call(obs, tool_name, duration_ms, success)

            print(f"Result      : {str(result)[:200]}...\n")

            messages.append(ToolMessage(
                content=json.dumps(result, default=str),
                tool_call_id=tool_call["id"],
            ))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: PYTHONPATH=. uv run python3 src/agents/analyst.py <project> "<requirement>"')
        sys.exit(1)

    project     = sys.argv[1]
    requirement = sys.argv[2]

    print(f"Project     : {project}")
    print(f"Requirement : {requirement}")

    result = run_analyst(project=project, requirement=requirement)

    print("\n" + "=" * 60)
    print("ANALYST RESULT")
    print("=" * 60)
    print(f"Status         : {result['status']}")
    print(f"Repo           : {result['repo']}")
    print(f"Files to change: {result['files_to_change']}")
    print(f"Summary        : {result['summary']}")
