# Planner Agent
#
# The planner has NO tools. It only uses the LLM to think.
#
# Job: take a task, produce a structured step-by-step plan.
#
# Why no tools?
#   The planner's job is to DECIDE what needs to be done — not to do it.
#   It does not search code, read files, or call any external system.
#   It just reasons: "given this task, what are the steps?"
#
# The plan it produces is saved into STATE so the orchestrator
# can execute each step in order using the agent.
#
# CodeAtlas comparison:
#   Same concept as agents/planner.py in CodeAtlas.
#   Here we use LangChain's ChatOpenAI + SystemMessage instead of the raw SDK.
#
# Usage:
#   PYTHONPATH=. uv run python3 src/planner_agent.py

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

# The system prompt is the planner's entire intelligence.
# A good system prompt produces a good plan — this is where prompt engineering matters.
# The LLM reads this and understands its role before seeing the task.
PLANNER_SYSTEM_PROMPT = """
You are a senior software engineering planner.

Your job is to take a development task and break it down into clear, ordered steps.

Rules:
- Always investigate before modifying — search and read code before making changes
- Always test after modifying — run tests after any code change
- Keep steps small and specific — one action per step
- Do not invent file names or implementation details — investigation happens first

Return your plan as JSON only, in this exact format:
{
  "goal": "short description of what the task achieves",
  "steps": [
    {"id": 1, "action": "what to do in this step"},
    {"id": 2, "action": "what to do in this step"}
  ]
}
"""


def create_plan(task: str) -> dict:
    """
    Takes a task description and returns a structured plan.
    The plan contains a goal and an ordered list of steps.

    No tools — pure LLM reasoning. The SystemMessage tells the LLM
    how to think about tasks. The HumanMessage is the actual task.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    messages = [
        SystemMessage(PLANNER_SYSTEM_PROMPT),
        HumanMessage(task),
    ]

    response = llm.invoke(messages)

    # Parse the JSON plan the LLM returned
    plan = json.loads(response.content)

    return plan


if __name__ == "__main__":
    task = "Add input validation to reserve_stock to reject negative quantities"

    print(f"Task: {task}\n")

    plan = create_plan(task)

    print(f"Goal: {plan['goal']}\n")
    print("Steps:")
    for step in plan["steps"]:
        print(f"  {step['id']}. {step['action']}")
