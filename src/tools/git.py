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
# Guardrail principle: the agent must NEVER work on or commit to the default branch.
# Protected branches = {main, master, default_branch from project.yml}
#   - main + master are hardcoded safety nets — always blocked no matter what
#   - default_branch is read from project.yml so protection tracks the actual config

import subprocess
import yaml
from pathlib import Path
from langchain_core.tools import tool

# Hardcoded safety net — always blocked regardless of what project.yml says.
_HARDCODED_PROTECTED = {"main", "master"}


def _repo_path(project: str, repo: str) -> Path:
    """Returns the absolute path to the local repo directory."""
    path = Path(f"source/{project}/{repo}").resolve()
    if not path.exists():
        raise FileNotFoundError(f"Repo not found locally: {path}")
    return path


def _protected_branches(project: str) -> set[str]:
    """
    Returns the full set of protected branches for this project:
    hardcoded {main, master} PLUS default_branch from project.yml.
    Called by every guardrail so protection stays in sync with config.
    """
    config_path = Path(f"source/{project}/project.yml")
    default_branch = "main"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            default_branch = config.get("github", {}).get("default_branch", "main")
    return _HARDCODED_PROTECTED | {default_branch}


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


def _guard_not_on_protected(project: str, cwd: Path, operation: str) -> None:
    """
    Raises if the current branch is any protected branch (main, master, default_branch).
    Called before any operation that writes, commits, or modifies code.
    """
    current   = _get_current_branch(cwd)
    protected = _protected_branches(project)
    if current in protected:
        raise ValueError(
            f"Guardrail blocked: cannot run '{operation}' while on protected branch '{current}'. "
            f"Checkout a feature branch first. Protected: {sorted(protected)}"
        )


def _guard_is_on_default(project: str, cwd: Path, operation: str) -> None:
    """
    Raises if the current branch is NOT the default branch.
    Called before operations that only make sense on the default branch (pull_main).
    """
    current   = _get_current_branch(cwd)
    protected = _protected_branches(project)
    if current not in protected:
        raise ValueError(
            f"Guardrail blocked: '{operation}' must be called from the default branch, "
            f"but current branch is '{current}'."
        )


# ── Operations ────────────────────────────────────────────────────────────────

@tool
def checkout_main(project: str, repo: str) -> dict:
    """
    Switches the local repo to the default branch (usually main).
    Called at the start of every task to ensure we begin from a clean base.
    """
    cwd = _repo_path(project, repo)
    _run(["git", "checkout", "main"], cwd)
    return {"repo": repo, "branch": "main", "status": "checked out"}


@tool
def pull_main(project: str, repo: str) -> dict:
    """
    Pulls the latest commits from origin/main.
    Must be called while on the default branch — blocked on feature branches.
    """
    cwd = _repo_path(project, repo)

    # Guardrail — pull_main only makes sense when on the default branch
    _guard_is_on_default(project, cwd, "pull_main")

    output = _run(["git", "pull", "origin", "main"], cwd)
    return {"repo": repo, "branch": "main", "output": output}


@tool
def checkout_branch(project: str, repo: str, branch_name: str) -> dict:
    """
    Creates and switches to a new local feature branch.
    Blocked if branch_name matches any protected branch (main, master, default_branch).
    """
    # Guardrail — cannot checkout a protected branch as a feature branch
    protected = _protected_branches(project)
    if branch_name in protected:
        raise ValueError(
            f"Guardrail blocked: cannot use protected branch '{branch_name}' as a feature branch. "
            f"Protected: {sorted(protected)}"
        )

    cwd = _repo_path(project, repo)
    _run(["git", "checkout", "-b", branch_name], cwd)
    return {"repo": repo, "branch": branch_name, "status": "checked out"}


@tool
def commit_changes(project: str, repo: str, message: str) -> dict:
    """
    Stages all changes and commits them locally.
    Blocked if currently on a protected branch (main, master, default_branch).
    The commit message should describe what was changed and reference the issue.
    """
    # Guardrail — commit message cannot be empty
    if not message or not message.strip():
        raise ValueError("Commit message cannot be empty.")

    cwd = _repo_path(project, repo)

    # Guardrail — never commit directly to a protected branch
    _guard_not_on_protected(project, cwd, "commit_changes")

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
    Blocked if branch_name is protected or if currently on a protected branch.
    """
    # Guardrail — cannot push to a protected branch name
    protected = _protected_branches(project)
    if branch_name in protected:
        raise ValueError(
            f"Guardrail blocked: cannot push to protected branch '{branch_name}'. "
            f"Protected: {sorted(protected)}"
        )

    cwd = _repo_path(project, repo)

    # Guardrail — current branch must not be protected
    _guard_not_on_protected(project, cwd, "push_branch")

    output = _run(["git", "push", "origin", branch_name], cwd)
    return {"repo": repo, "branch": branch_name, "output": output}


@tool
def sync_with_main(project: str, repo: str, branch_name: str) -> dict:
    """
    Updates the feature branch with the latest commits from main.
    Called when GitHub reports the branch is out of date with main.
    Blocked if branch_name is a protected branch — cannot sync protected with itself.

    If merge conflicts are detected — raises immediately.
    The pipeline stops and the human must resolve conflicts manually.
    """
    # Guardrail — branch_name must not be a protected branch
    protected = _protected_branches(project)
    if branch_name in protected:
        raise ValueError(
            f"Guardrail blocked: cannot sync protected branch '{branch_name}' with main. "
            f"Protected: {sorted(protected)}"
        )

    cwd = _repo_path(project, repo)

    # Ensure we are on the feature branch before merging
    _run(["git", "checkout", branch_name], cwd)

    # Guardrail — confirm we are now on the feature branch, not a protected one
    _guard_not_on_protected(project, cwd, "sync_with_main")

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
