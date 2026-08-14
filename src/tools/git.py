# Local Git Operations
#
# Runs git commands inside the local service repo directories.
# All operations are @tool — the agent owns the full git workflow:
#
#   checkout_main + pull_main   → start from clean base
#   checkout_branch             → switch to feature branch
#   write_file (codebase tool)  → agent writes code
#   commit_changes              → agent commits when done
#   push_branch                 → agent pushes to GitHub
#   sync_with_main              → agent syncs if PR is outdated
#
# All functions run subprocess commands inside source/{project}/{repo}/
# and raise RuntimeError with clear messages on failure.

import subprocess
from pathlib import Path
from langchain_core.tools import tool


def _repo_path(project: str, repo: str) -> Path:
    """Returns the absolute path to the local repo directory."""
    path = Path(f"source/{project}/{repo}").resolve()
    if not path.exists():
        raise FileNotFoundError(f"Repo not found locally: {path}")
    return path


def _run(cmd: list[str], cwd: Path) -> str:
    """
    Runs a git command in the given directory.
    Returns stdout on success. Raises RuntimeError with stderr on failure.
    """
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git command failed: {' '.join(cmd)}\n"
            f"Error: {result.stderr.strip()}"
        )
    return result.stdout.strip()


# ── Operations ────────────────────────────────────────────────────────────────

@tool
def checkout_main(project: str, repo: str) -> dict:
    """
    Switches the local repo to the main branch.
    Called at the start of every task to ensure we begin from a clean base.
    """
    cwd = _repo_path(project, repo)
    _run(["git", "checkout", "main"], cwd)
    return {"repo": repo, "branch": "main", "status": "checked out"}


@tool
def pull_main(project: str, repo: str) -> dict:
    """
    Pulls the latest commits from origin/main into the local main branch.
    Called after checkout_main to ensure we have the most recent code.
    """
    cwd    = _repo_path(project, repo)
    output = _run(["git", "pull", "origin", "main"], cwd)
    return {"repo": repo, "branch": "main", "output": output}


@tool
def checkout_branch(project: str, repo: str, branch_name: str) -> dict:
    """
    Creates and switches to a new local feature branch.
    Called after create_branch (GitHub API) so local and remote are in sync.
    The branch already exists on GitHub — we create it locally from the same SHA.
    """
    cwd = _repo_path(project, repo)
    _run(["git", "checkout", "-b", branch_name], cwd)
    return {"repo": repo, "branch": branch_name, "status": "checked out"}


@tool
def commit_changes(project: str, repo: str, message: str) -> dict:
    """
    Stages all changes and commits them locally.
    Called after the agent has written code using write_file.
    The commit message should describe what was changed and reference the issue.
    """
    # Guardrail — commit message cannot be empty
    if not message or not message.strip():
        raise ValueError("Commit message cannot be empty.")

    cwd = _repo_path(project, repo)

    # Stage all changes — picks up everything write_file modified
    _run(["git", "add", "."], cwd)

    # Check if there is anything to commit
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cwd, capture_output=True, text=True,
    )
    if not status.stdout.strip():
        raise RuntimeError("Nothing to commit — no changes were made by the agent.")

    output = _run(["git", "commit", "-m", message], cwd)
    return {"repo": repo, "message": message, "output": output}


@tool
def push_branch(project: str, repo: str, branch_name: str) -> dict:
    """
    Pushes the local feature branch to GitHub (origin).
    Called after commit_changes — makes the commits visible on GitHub
    so create_pr can open a PR against them.
    """
    # Guardrail — cannot push main directly
    if branch_name == "main":
        raise ValueError("Cannot push directly to main. Use a feature branch.")

    cwd    = _repo_path(project, repo)
    output = _run(["git", "push", "origin", branch_name], cwd)
    return {"repo": repo, "branch": branch_name, "output": output}


@tool
def sync_with_main(project: str, repo: str, branch_name: str) -> dict:
    """
    Updates the feature branch with the latest commits from main.
    Called when GitHub reports the branch is out of date with main.

    Steps:
      1. Fetch latest main from origin
      2. Merge origin/main into the current branch

    If merge conflicts are detected — raises immediately.
    The pipeline stops and the human must resolve conflicts manually.
    Conflicts cannot be auto-resolved — letting the agent guess would risk broken code.
    """
    cwd = _repo_path(project, repo)

    # Ensure we are on the feature branch before merging
    _run(["git", "checkout", branch_name], cwd)

    # Step 1 — fetch latest main from GitHub
    _run(["git", "fetch", "origin", "main"], cwd)

    # Step 2 — merge origin/main into the feature branch
    result = subprocess.run(
        ["git", "merge", "origin/main"],
        cwd=cwd, capture_output=True, text=True,
    )

    # Conflict detected — git exits with code 1 and leaves conflict markers
    if result.returncode != 0:
        # Abort the merge to leave the repo in a clean state
        subprocess.run(["git", "merge", "--abort"], cwd=cwd, capture_output=True)
        raise RuntimeError(
            f"Merge conflict detected when syncing '{branch_name}' with main.\n"
            f"Details: {result.stderr.strip() or result.stdout.strip()}\n"
            f"Human intervention required — resolve conflicts manually."
        )

    return {
        "repo":    repo,
        "branch":  branch_name,
        "status":  "synced with main",
        "output":  result.stdout.strip(),
    }
