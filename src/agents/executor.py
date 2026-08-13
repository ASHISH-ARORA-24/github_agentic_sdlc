# Iteration 3 — Single LangChain Agent
#
# We implement the agent loop manually using LangChain message types.
# This makes the comparison to CodeAtlas crystal clear.
#
# CodeAtlas (raw OpenAI types):
#   messages = [{"role": "system", ...}, {"role": "user", ...}]
#   response = client.chat.completions.create(model=..., messages=messages, tools=TOOLS)
#   messages.append({"role": "tool", "tool_call_id": ..., "content": ...})
#
# LangChain (proper message objects — same loop, cleaner types):
#   messages = [SystemMessage(...), HumanMessage(...)]
#   llm_with_tools = llm.bind_tools(tools)
#   response = llm_with_tools.invoke(messages)    ← returns AIMessage
#   messages.append(ToolMessage(content=..., tool_call_id=...))
#
# The structure is identical. LangChain just replaces raw dicts with typed objects.
#
# Usage:
#   PYTHONPATH=. uv run python3 src/agent.py "codeatlas/ecommerce" "what does reserve_stock do?"

import sys
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from src.tools import make_tools
from src.memory_store import get_memories

load_dotenv()


def run_agent(project: str, question: str) -> str:
    """
    Runs the agent loop for one question against one project.

    project  — which codebase to search (e.g. "codeatlas/ecommerce")
    question — the user's natural-language question
    """

    # ── LLM + Tools ───────────────────────────────────────────────────────────
    llm   = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tools = make_tools(project)

    # bind_tools tells the LLM which tools it can call.
    # In CodeAtlas this was done by passing tools= to client.chat.completions.create().
    # Here we bind them once to the model — cleaner and reusable.
    llm_with_tools = llm.bind_tools(tools)

    # Build a lookup so we can call a tool by name
    # In CodeAtlas this was the execute_tool() dispatcher
    tool_by_name = {t.name: t for t in tools}

    # ── Memory ────────────────────────────────────────────────────────────────
    # Load all saved facts about this project and inject into the system prompt.
    # The LLM sees what is already known — no need to rediscover it.
    memories     = get_memories(project)
    memory_text  = "\n".join(f"- {m['key']}: {m['value']}" for m in memories)
    memory_block = (
        f"\n\nKnown facts about this project:\n{memory_text}"
        if memory_text else ""
    )

    # ── Messages ──────────────────────────────────────────────────────────────
    # LangChain typed messages replace raw dicts:
    #   {"role": "system", "content": "..."} → SystemMessage("...")
    #   {"role": "user",   "content": "..."} → HumanMessage("...")
    messages = [
        SystemMessage(
            "You are a software engineering assistant with access to a codebase. "
            "Use the available tools to find accurate, grounded answers. "
            "Do not guess or invent facts about the code. "
            "If you discover a stable, reusable fact about the project — such as where "
            "test files are, what framework is used, or naming conventions — save it "
            "using save_memory so future runs do not need to rediscover it. "
            "Do not save temporary state, errors, or task-specific information."
            + memory_block
        ),
        HumanMessage(question),
    ]

    # ── Agent loop ────────────────────────────────────────────────────────────
    # This is the same while True loop as CodeAtlas — just using LangChain types.
    print("\n--- Agent starting ---\n")

    while True:
        # Call the LLM — returns an AIMessage
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        # No tool calls = LLM has enough information — return the final answer
        if not response.tool_calls:
            print("\n--- Agent done ---")
            return response.content

        # Execute each tool the LLM requested
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            print(f"Tool called : {tool_name}")
            print(f"Arguments   : {tool_args}")

            # Call the actual tool function.
            # Catch errors and return them to the LLM instead of crashing.
            # The LLM can then self-correct — e.g. retry with the right file path.
            tool_fn = tool_by_name[tool_name]
            try:
                result = tool_fn.invoke(tool_args)
            except Exception as e:
                result = {"error": str(e)}

            print(f"Result      : {str(result)[:200]}...\n")

            # ToolMessage replaces {"role": "tool", "tool_call_id": ..., "content": ...}
            # The tool_call_id links this result back to the specific tool call
            messages.append(ToolMessage(
                content=json.dumps(result, default=str),
                tool_call_id=tool_call["id"],
            ))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: PYTHONPATH=. uv run python3 src/agent.py <project> \"<question>\"")
        print("Example: PYTHONPATH=. uv run python3 src/agent.py codeatlas/ecommerce \"what does reserve_stock do?\"")
        sys.exit(1)

    project  = sys.argv[1]
    question = sys.argv[2]

    print(f"Project  : {project}")
    print(f"Question : {question}")

    answer = run_agent(project, question)

    print("\n" + "=" * 60)
    print("FINAL ANSWER")
    print("=" * 60)
    print(answer)
