# Coder Agent
#
# Implements a code change, validates it with tests, commits and pushes.
#
# Tools:
#   read_file      — understand the current implementation before changing it
#   write_file     — write the complete updated file
#   run_tests      — validate the change
#   commit_changes — commit when tests pass (message only — project/repo baked in)
#   push_branch    — push to GitHub (no args — project/repo/branch baked in)
#
# Test retry loop:
#   The LLM sees test failures in its message history and self-corrects.
#   System prompt instructs: retry up to 3 times, then report failed.
#   No external retry counter needed — LLM tracks this through the conversation.
#
# CodeAtlas comparison:
#   CodeAtlas coding_agent.py was read-only (design only, no actual writes).
#   This agent writes real code, runs real tests, commits, and pushes.
#
# Usage:
#   PYTHONPATH=. uv run python3 src/agents/coder.py \
#     codeatlas/ecommerce order_service feat/issue-17-add-empty-cart-validation-agent \
#     "Add validation to reject empty cart" main.py

import sys
import json
import re
import time
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from src.tools.coder import make_coder_tools
from src.observability.tracer import new_trace, record_llm_call, record_tool_call, finish_trace

load_dotenv()


CODER_SYSTEM_PROMPT = """
You are a very senior software engineer. You think before you act, you work in small
logical steps, and you commit your work as you go — just like a professional developer
working on a real codebase.

Your workflow:

STEP 1 — Understand first
  Read every file that needs to change. Understand the existing code completely
  before touching anything. Never guess at what is already there.

STEP 2 — Plan mentally
  Identify the exact change needed. Break it into logical pieces if the change is large.
  One logical piece = one commit.

STEP 3 — Implement one logical piece at a time
  Make the MINIMAL change needed to satisfy the requirement.
  Keep ALL existing code — imports, helper methods, private methods, comments, docstrings.
  You are ADDING to or MODIFYING existing code — you are NOT rewriting the file.

  When calling write_file:
  - The content you provide REPLACES the entire file
  - So the content MUST contain everything that was there before, plus your change
  - Never omit existing methods, classes, imports, or docstrings
  - Never simplify or "clean up" code that wasn't part of the requirement

  Match the existing code style, naming conventions, and patterns exactly.

STEP 4 — Test immediately after each change
  Run the tests right after writing. Do not skip this step.

STEP 5 — Commit if tests pass
  If tests pass, commit with a clear, specific message.
  A good commit message explains WHAT changed and WHY — not just "fix stuff".
  Commit message format: type: short description
  Valid types: feat, fix, hotfix, docs, test, chore, refactor
  Example: "feat: add empty cart validation to OrderManager.create_order"

STEP 6 — Fix and recommit if tests fail
  Read the failure output carefully. Understand the root cause before changing anything.

  IMPORTANT — before fixing, read the test file to understand exactly what is being tested:
  - Which class and method does the failing test call directly?
  - The fix must go in THAT class/method — not in a wrapper or handler above it.
  - A test that calls OrderManager.create_order() tests order_manager.py, not main.py.
  - Do not guess — read the test file with read_file to confirm the target.

  Fix the specific failing case. Write the complete fixed file. Run tests again.
  If tests pass — commit the fix with a clear message explaining what was wrong.
  Retry this up to 3 times. If tests still fail after 3 attempts — stop and report failed.

STEP 7 — Push when everything is done
  Only push when ALL tests pass and ALL logical pieces are committed.
  Push is the final signal that the work is complete and ready for review.

Rules:
  - Read before writing — always
  - Write complete file content — never partial patches
  - Commit at each logical step — not one big commit at the end
  - Match existing code style — do not introduce new patterns without reason
  - Do not create new files unless the requirement explicitly asks for it
  - Do not modify test files unless the requirement asks for new tests

When fully done, return a JSON object ONLY. No explanation, no markdown, just JSON:
{
  "status": "done" or "failed",
  "files_modified": ["relative/path/to/file.py"],
  "commits": [
    {
      "message":      "conventional commit message for this commit",
      "changes":      "plain English description of what changed in this commit and why",
      "test_results": "brief summary of test run outcome e.g. '8 passed in 0.30s' or '1 failed — test_create_order_rejects_empty_items'"
    }
  ]
}

If status is failed, commits should still list everything attempted so far, and the last
entry should explain what failed and why tests could not be fixed after 3 attempts.
"""


def _extract_json(text: str) -> dict:
    """Parses the coder's final response as JSON, handling markdown code fences."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    return json.loads(text)


def run_coder(
    project:        str,
    repo:           str,
    branch:         str,
    requirement:    str,
    files_to_change: list[str],
    feedback:       str = None,
    obs:            dict = None,
) -> dict:
    """
    Runs the coder agent to implement a code change.

    project         — which project (e.g. "codeatlas/ecommerce")
    repo            — which service repo (e.g. "order_service")
    branch          — feature branch already checked out locally
    requirement     — original user requirement
    files_to_change — from analyst: which files need to change
    feedback        — human rejection reason from HITL (None on first run)
    obs             — optional shared observability trace

    Returns:
        {status: "done"|"failed", files_modified: [...], commit_message: "..."}
    """
    standalone = obs is None
    if standalone:
        obs = new_trace()

    llm            = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tools          = make_coder_tools(project=project, repo=repo, branch=branch)
    llm_with_tools = llm.bind_tools(tools)
    tool_by_name   = {t.name: t for t in tools}

    # Build the task — include repo and files explicitly so the LLM never guesses
    task = (
        f"Requirement: {requirement}\n\n"
        f"Repository : {repo}\n"
        f"Files to change: {', '.join(files_to_change)}\n\n"
        f"The feature branch '{branch}' is already checked out locally. "
        f"Use repository name '{repo}' when calling read_file and write_file. "
        f"Read the files, implement the change, run tests, commit, and push."
    )
    if feedback:
        task += (
            f"\n\nThis is a rework. Human feedback on the previous attempt:\n"
            f"{feedback}\n"
            f"Please address this feedback specifically."
        )

    messages = [
        SystemMessage(CODER_SYSTEM_PROMPT),
        HumanMessage(task),
    ]

    print("\n--- Coder starting ---\n")

    MAX_ITERATIONS  = 30   # safety net — prevents runaway loops
    MAX_TEST_FAILS  = 3    # hard limit — stop after 3 consecutive test failures
    iterations      = 0
    test_fail_count = 0
    commits_so_far  = []   # track commits made during this run

    while True:
        iterations += 1
        if iterations > MAX_ITERATIONS:
            if standalone:
                finish_trace(obs)
            return {
                "status":         "failed",
                "files_modified": [],
                "commits":        commits_so_far or [{
                    "message":      "agent loop exceeded max iterations",
                    "changes":      "agent could not complete the task within 30 iterations",
                    "test_results": "n/a",
                }],
            }
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        record_llm_call(obs, response)

        # No tool calls = coder is finished — parse the JSON result
        if not response.tool_calls:
            print("\n--- Coder done ---")
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
                success = "error" not in result if isinstance(result, dict) else True
            except Exception as e:
                result  = {"error": str(e)}
                success = False

            duration_ms = (time.perf_counter() - tool_start) * 1000
            record_tool_call(obs, tool_name, duration_ms, success)

            print(f"Result      : {str(result)[:300]}...\n")

            # Hard test failure counter — enforced in code, not just in prompt
            if tool_name == "run_tests" and isinstance(result, dict):
                if not result.get("passed", True):
                    test_fail_count += 1
                    print(f"Test failures: {test_fail_count}/{MAX_TEST_FAILS}")
                    if test_fail_count >= MAX_TEST_FAILS:
                        print("\n--- Coder stopped: max test failures reached ---")
                        if standalone:
                            finish_trace(obs)
                        return {
                            "status":         "failed",
                            "files_modified": [],
                            "commits":        commits_so_far or [{
                                "message":      "tests failed after 3 attempts",
                                "changes":      "could not fix failing tests in 3 retries",
                                "test_results": result.get("stdout", "")[:300],
                            }],
                        }
                else:
                    test_fail_count = 0  # reset on pass

            # Track commits made by the agent
            if tool_name == "commit_changes" and success:
                commits_so_far.append({
                    "message":      tool_args.get("message", ""),
                    "changes":      "",
                    "test_results": "committed",
                })

            messages.append(ToolMessage(
                content=json.dumps(result, default=str),
                tool_call_id=tool_call["id"],
            ))


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(
            "Usage: PYTHONPATH=. uv run python3 src/agents/coder.py "
            '<project> <repo> <branch> "<requirement>" [file1 file2 ...]'
        )
        sys.exit(1)

    project     = sys.argv[1]
    repo        = sys.argv[2]
    branch      = sys.argv[3]
    requirement = sys.argv[4]
    files       = sys.argv[5:] if len(sys.argv) > 5 else []

    print(f"Project     : {project}")
    print(f"Repo        : {repo}")
    print(f"Branch      : {branch}")
    print(f"Requirement : {requirement}")
    print(f"Files       : {files}")

    result = run_coder(
        project=project,
        repo=repo,
        branch=branch,
        requirement=requirement,
        files_to_change=files,
    )

    print("\n" + "=" * 60)
    print("CODER RESULT")
    print("=" * 60)
    print(f"Status         : {result['status']}")
    print(f"Files modified : {result['files_modified']}")
    for i, commit in enumerate(result.get("commits", []), 1):
        print(f"  Commit {i}     : {commit.get('message', '')}")
        print(f"  Changes      : {commit.get('changes', '')}")
        print(f"  Tests        : {commit.get('test_results', '')}")
