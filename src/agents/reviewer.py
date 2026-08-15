# Reviewer Agent
#
# Reviews a pull request independently — decides APPROVED or REJECTED with a reason.
#
# Tools:
#   get_pr_diff — read the actual PR diff from GitHub
#
# Read-only. Cannot merge, cannot commit, cannot write files.
#
# Why "independent"?
#   The reviewer sees only the PR diff and the requirement — it does NOT see
#   the coder's reasoning. This gives a true second opinion. If the reviewer
#   had the coder's justification, it would be biased toward approving.
#
# CodeAtlas comparison:
#   Same concept as multi_agent_demo/reviewer_agent.py — but this reads a real
#   GitHub PR diff instead of reasoning about a plan.
#
# Usage:
#   PYTHONPATH=. uv run python3 src/agents/reviewer.py \
#     codeatlas/ecommerce order_service 42 "Add validation to reject empty cart"

import sys
import json
import re
import time
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from src.tools.github import get_pr_diff
from src.observability.tracer import new_trace, record_llm_call, record_tool_call, finish_trace

load_dotenv()


REVIEWER_SYSTEM_PROMPT = """
You are a senior code reviewer. You review a pull request the same way a
principal engineer would — carefully, honestly, and constructively.

Your job:
1. Read the PR diff using get_pr_diff
2. Judge whether the changes correctly satisfy the requirement
3. Return APPROVED or REJECTED with a clear, specific reason

What to check:
  Correctness    — does the change actually do what the requirement asks?
  Scope          — are the changes limited to what was needed, or did the coder
                   change unrelated things?
  Style          — does the new code match the existing project style?
  Safety         — any obvious bugs, edge cases missed, or broken tests?
  Tests          — if new behaviour was added, is it tested?

Rules:
- Be strict but fair. Approve when the work is genuinely good.
- Reject when there is a real problem — never reject on style preferences alone.
- Read the ENTIRE diff before deciding — don't judge based on the first file only.
- Your reason must be specific — cite the file and what is wrong.
- Do not run tests, do not fix code — you only judge.

When done, return a JSON object ONLY. No explanation, no markdown, just JSON:
{
  "status": "approved" or "rejected",
  "reason": "specific explanation of the decision, citing files and lines where relevant"
}
"""


def _extract_json(text: str) -> dict:
    """Parses the reviewer's final response as JSON, handling markdown fences."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    return json.loads(text)


def run_reviewer(
    project:     str,
    repo:        str,
    pr_number:   int,
    requirement: str,
    obs:         dict = None,
) -> dict:
    """
    Runs the reviewer agent to independently review a PR.

    project     — which project (e.g. "codeatlas/ecommerce")
    repo        — which service repo (e.g. "order_service")
    pr_number   — the PR to review
    requirement — the original requirement the PR should satisfy
    obs         — optional shared observability trace

    Returns:
        {status: "approved"|"rejected", reason: "..."}
    """
    standalone = obs is None
    if standalone:
        obs = new_trace()

    llm            = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tools          = [get_pr_diff]
    llm_with_tools = llm.bind_tools(tools)
    tool_by_name   = {t.name: t for t in tools}

    task = (
        f"Requirement: {requirement}\n\n"
        f"Project    : {project}\n"
        f"Repository : {repo}\n"
        f"PR number  : {pr_number}\n\n"
        f"Call get_pr_diff with project='{project}', repo='{repo}', pr_number={pr_number} "
        f"to read the diff. Then decide APPROVED or REJECTED and return the JSON result."
    )

    messages = [
        SystemMessage(REVIEWER_SYSTEM_PROMPT),
        HumanMessage(task),
    ]

    print("\n--- Reviewer starting ---\n")

    MAX_ITERATIONS = 10   # reviewer only reads diff — should be quick
    iterations     = 0

    while True:
        iterations += 1
        if iterations > MAX_ITERATIONS:
            if standalone:
                finish_trace(obs)
            return {
                "status": "rejected",
                "reason": "reviewer exceeded max iterations — could not complete review",
            }

        response = llm_with_tools.invoke(messages)
        messages.append(response)
        record_llm_call(obs, response)

        if not response.tool_calls:
            print("\n--- Reviewer done ---")
            if standalone:
                finish_trace(obs)
            return _extract_json(response.content)

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

            print(f"Result      : {str(result)[:300]}...\n")

            messages.append(ToolMessage(
                content=json.dumps(result, default=str),
                tool_call_id=tool_call["id"],
            ))


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(
            "Usage: PYTHONPATH=. uv run python3 src/agents/reviewer.py "
            '<project> <repo> <pr_number> "<requirement>"'
        )
        sys.exit(1)

    project     = sys.argv[1]
    repo        = sys.argv[2]
    pr_number   = int(sys.argv[3])
    requirement = sys.argv[4]

    print(f"Project     : {project}")
    print(f"Repo        : {repo}")
    print(f"PR          : #{pr_number}")
    print(f"Requirement : {requirement}")

    result = run_reviewer(
        project=project,
        repo=repo,
        pr_number=pr_number,
        requirement=requirement,
    )

    print("\n" + "=" * 60)
    print("REVIEWER RESULT")
    print("=" * 60)
    print(f"Status : {result['status']}")
    print(f"Reason : {result['reason']}")
