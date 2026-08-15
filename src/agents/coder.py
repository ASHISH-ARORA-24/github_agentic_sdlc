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
from langchain_core.tools import tool

from src.tools.codebase import make_tools
from src.tools.git import commit_changes as _git_commit, push_branch as _git_push
from src.observability.tracer import new_trace, record_llm_call, record_tool_call, finish_trace

load_dotenv()


CODER_SYSTEM_PROMPT = """
You are a senior software engineer implementing a code change.

Your job in order:
1. Read the file(s) that need to change — understand what is already there
2. Write the code change — provide the COMPLETE new file content, not just the changed section
3. Run the tests to validate your change
4. If tests fail, read the failure output carefully, fix the code, run tests again
5. Retry up to 3 times — if tests still fail after 3 attempts, stop and report failed
6. When all tests pass, commit the changes with a conventional commit message
7. Push the branch to GitHub

Rules:
- Always read before writing — never guess at the existing code
- Write the complete file — not just the diff or the changed function
- Commit message must follow conventional commits: type: description
  Valid types: feat, fix, hotfix, docs, test, chore, refactor, style, perf
  Example: "feat: add empty cart validation to OrderManager.create_order"
- Do not create new files unless the requirement explicitly asks for it

When finished, return a JSON object ONLY. No explanation, no markdown, just JSON:
{
  "status": "done" or "failed",
  "files_modified": ["relative/path/to/file.py"],
  "commit_message": "the commit message used, or reason for failure if status is failed"
}
"""


def make_coder_tools(project: str, repo: str, branch: str) -> list:
    """
    Creates tools for the coder agent with project/repo/branch baked in.

    Codebase tools (read, write, test) — project baked in via make_tools()
    Git tools (commit, push) — wrapped so LLM only decides the commit message.
    The LLM never sees or chooses project, repo, or branch for git operations.
    """
    # Codebase tools — project already baked in via make_tools closure
    all_codebase  = make_tools(project)
    codebase_tools = [t for t in all_codebase if t.name in ("read_file", "write_file", "run_tests")]

    # Git tools — wrap to bake in project/repo/branch
    # LLM only decides: the commit message

    @tool
    def commit_changes(message: str) -> dict:
        """
        Stages all changed files and commits them locally.
        Call this after tests pass.
        Message must follow conventional commits: type: description
        Valid types: feat, fix, hotfix, docs, test, chore, refactor
        Example: "feat: add empty cart validation to OrderManager"
        """
        return _git_commit.invoke({"project": project, "repo": repo, "message": message})

    @tool
    def push_branch() -> dict:
        """
        Pushes the feature branch to GitHub (origin).
        Call this after commit_changes succeeds.
        No arguments needed.
        """
        return _git_push.invoke({"project": project, "repo": repo, "branch_name": branch})

    return codebase_tools + [commit_changes, push_branch]


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

    # Build the task — include human feedback if this is a rework after HITL rejection
    task = (
        f"Requirement: {requirement}\n\n"
        f"Files to change: {', '.join(files_to_change)}\n\n"
        f"The feature branch is already checked out locally. "
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

    while True:
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
    print(f"Commit message : {result['commit_message']}")
