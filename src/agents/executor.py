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
import time
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from src.tools import make_tools
from src.memory_store import get_memories
from src.observability.tracer import new_trace, record_llm_call, record_tool_call, finish_trace

load_dotenv()


def run_agent(project: str, question: str, return_trace: bool = False, obs: dict = None) -> str | dict:
    """
    Runs the agent loop for one question against one project.

    project      — which codebase to search (e.g. "codeatlas/ecommerce")
    question     — the user's natural-language question
    return_trace — if True, returns a dict with answer + trace instead of just the answer
                   Used by the evaluator to check what tools were called
    """
    # Trace captures what happened during this agent run
    # — tool calls, files, test results (for evaluation)
    # — LLM calls, timing, tokens, cost (for observability)
    trace = {
        "tools_called":  [],
        "files_read":    [],
        "files_written": [],
        "test_results":  [],
    }
    # If obs is passed from orchestrator, use it. Otherwise create standalone.
    standalone_obs = obs is None
    if standalone_obs:
        obs = new_trace()

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
        # Call the LLM — record timing and token usage
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        record_llm_call(obs, response)   # ← observability: tokens + cost

        # No tool calls = LLM has enough information — return the final answer
        if not response.tool_calls:
            print("\n--- Agent done ---")
            if standalone_obs:
                finish_trace(obs)
            if return_trace:
                return {"answer": response.content, "trace": trace, "obs": obs}
            return response.content

        # Execute each tool the LLM requested
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            print(f"Tool called : {tool_name}")
            print(f"Arguments   : {tool_args}")

            # Call the actual tool function — record timing
            tool_fn    = tool_by_name[tool_name]
            tool_start = time.perf_counter()
            try:
                result  = tool_fn.invoke(tool_args)
                success = "error" not in result if isinstance(result, dict) else True
            except Exception as e:
                result  = {"error": str(e)}
                success = False

            duration_ms = (time.perf_counter() - tool_start) * 1000
            record_tool_call(obs, tool_name, duration_ms, success)  # ← observability

            print(f"Result      : {str(result)[:200]}...\n")

            # Capture trace — record what each tool did
            trace["tools_called"].append(tool_name)
            if tool_name == "read_file":
                trace["files_read"].append(tool_args.get("file_path"))
            if tool_name == "write_file" and "error" not in result:
                trace["files_written"].append(tool_args.get("file_path"))
            if tool_name == "run_tests":
                trace["test_results"].append({
                    "passed":      result.get("passed"),
                    "return_code": result.get("return_code"),
                })

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
