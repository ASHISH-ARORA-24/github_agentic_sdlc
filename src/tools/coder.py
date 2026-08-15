# Coder Tools
#
# Tool factory for the coder agent.
# Combines codebase tools (read, write, test) with git tools (commit, push)
# — all with project/repo/branch baked in so the LLM never sees them.
#
# Lives in src/tools/ because tools always live here, not in agent files.

from langchain_core.tools import tool

from src.tools.codebase import make_tools
from src.tools.git import commit_changes as _git_commit, push_branch as _git_push


def make_coder_tools(project: str, repo: str, branch: str) -> list:
    """
    Creates tools for the coder agent with project/repo/branch baked in.

    Codebase tools (read, write, test) — project baked in via make_tools()
    Git tools (commit, push) — wrapped so LLM only decides the commit message.
    The LLM never sees or chooses project, repo, or branch for git operations.
    """
    # Codebase tools — project already baked in via closure
    all_codebase   = make_tools(project)
    codebase_tools = [t for t in all_codebase if t.name in ("read_file", "write_file", "run_tests")]

    # Git tools — wrap to bake in project/repo/branch
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
