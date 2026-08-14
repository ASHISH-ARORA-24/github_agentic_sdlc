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
# Guardrail principle: the agent must NEVER work on or commit to main.
# Every operation that could touch main is blocked with an explicit check.

import subprocess
from pathlib import Path
from langchain_core.tools import tool

# These branch names are always protected — no commits, writes, or pushes allowed.
PROTECTED_BRANCHES = {"main", "master"}


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


def _get_current_branch(cwd: Path) -> str:
    """Returns the name of the currently checked-out branch."""
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)


def _guard_not_on_main(cwd: Path, operation: str) -> None:
    """
    Raises if the current branch is main or any protected branch.
    Called before any operation that writes, commits, or modifies code.
    """
    current = _get_current_branch(cwd)
    if current in PROTECTED_BRANCHES:
        raise ValueError(
            f"Guardrail blocked: cannot run '{operation}' while on '{current}'. "
            f"Checkout a feature branch first."
        )


def _guard_is_on_main(cwd: Path, operation: str) -> None:
    """
    Raises if the current branch is NOT main.
    Called before operations that only make sense on main (pull_main).
    """
    current = _get_current_branch(cwd)
    if current not in PROTECTED_BRANCHES:
        raise ValueError(
            f"Guardrail blocked: '{operation}' must be called from main, "
            f"but current branch is '{current}'."
        )


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
    Pulls the latest commits from origin/main.
    Must be called while on main — blocked on feature branches.
    """
    cwd = _repo_path(project, repo)

    # Guardrail — pull_main only makes sense when on main
    _guard_is_on_main(cwd, "pull_main")

    output = _run(["git", "pull", "origin", "main"], cwd)
    return {"repo": repo, "branch": "main", "output": output}


@tool
def checkout_branch(project: str, repo: str, branch_name: str) -> dict:
    """
    Creates and switches to a new local feature branch.
    Blocked if branch_name is main or any protected branch.
    """
    # Guardrail — cannot checkout a protected branch as a feature branch
    if branch_name in PROTECTED_BRANCHES:
        raise ValueError(
            f"Guardrail blocked: cannot use '{branch_name}' as a feature branch."
        )

    cwd = _repo_path(project, repo)
    _run(["git", "checkout", "-b", branch_name], cwd)
    return {"repo": repo, "branch": branch_name, "status": "checked out"}


@tool
def commit_changes(project: str, repo: str, message: str) -> dict:
    """
    Stages all changes and commits them locally.
    Blocked if currently on main — agent must be on a feature branch to commit.
    The commit message should describe what was changed and reference the issue.
    """
    # Guardrail — commit message cannot be empty
    if not message or not message.strip():
        raise ValueError("Commit message cannot be empty.")

    cwd = _repo_path(project, repo)

    # Guardrail — never commit directly to main
    _guard_not_on_main(cwd, "commit_changes")

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
    return {"repo": repo, "branch": _get_current_branch(cwd), "message": message, "output": output}


@tool
def push_branch(project: str, repo: str, branch_name: str) -> dict:
    """
    Pushes the local feature branch to GitHub (origin).
    Blocked if branch_name is main or if currently on main.
    """
    # Guardrail — cannot push to a protected branch name
    if branch_name in PROTECTED_BRANCHES:
        raise ValueError(f"Guardrail blocked: cannot push to '{branch_name}' directly.")

    cwd = _repo_path(project, repo)

    # Guardrail — current branch must not be main
    _guard_not_on_main(cwd, "push_branch")

    output = _run(["git", "push", "origin", branch_name], cwd)
    return {"repo": repo, "branch": branch_name, "output": output}


@tool
def sync_with_main(project: str, repo: str, branch_name: str) -> dict:
    """
    Updates the feature branch with the latest commits from main.
    Called when GitHub reports the branch is out of date with main.
    Blocked if branch_name is main — cannot sync main with itself.

    If merge conflicts are detected — raises immediately.
    The pipeline stops and the human must resolve conflicts manually.
    """
    # Guardrail — cannot sync main with itself
    if branch_name in PROTECTED_BRANCHES:
        raise ValueError(
            f"Guardrail blocked: cannot sync '{branch_name}' with main — it IS main."
        )

    cwd = _repo_path(project, repo)

    # Ensure we are on the feature branch before merging
    _run(["git", "checkout", branch_name], cwd)

    # Guardrail — confirm we are now on the feature branch, not main
    _guard_not_on_main(cwd, "sync_with_main")

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
        "repo":   repo,
        "branch": branch_name,
        "status": "synced with main",
        "output": result.stdout.strip(),
    }
