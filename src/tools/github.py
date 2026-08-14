# GitHub Tools
#
# All GitHub operations needed by the SDLC pipeline.
# Uses the GitHub REST API directly via the requests library.
#
# Config is loaded from source/<project>/project.yml — no hardcoded URLs or repo names.
# GITHUB_TOKEN is loaded from .env — never hardcoded.

import os
import re
import yaml
import requests
from dotenv import load_dotenv
from langchain_core.tools import tool

# Shared config validators — single source of truth in git.py
from src.tools.git import validate_service_repo

load_dotenv()

# Operations are implemented one by one below.
# Each tool will be decorated with @tool so the agent can call it.


# ── Config ────────────────────────────────────────────────────────────────────

def load_project_config(project: str) -> dict:
    """Reads source/<project>/project.yml and returns the config as a dict."""
    with open(f"source/{project}/project.yml", "r") as f:
        return yaml.safe_load(f)




# ── Shared helpers ────────────────────────────────────────────────────────────

GITHUB_API = "https://api.github.com"

def github_headers() -> dict:
    """Builds the Authorization header using GITHUB_TOKEN from .env.
    Called by every tool — never repeat the header construction inline."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN not found in .env")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

def github_request(method: str, config: dict, repo: str, endpoint: str, payload: dict = None) -> dict:
    """Makes an authenticated REST call to the GitHub API.
    Accepts already-loaded config — tools load config once and pass it in, no double loading."""
    owner = config["github"]["owner"]
    response = requests.request(
        method,
        f"{GITHUB_API}/repos/{owner}/{repo}/{endpoint}",
        headers=github_headers(),
        json=payload,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"GitHub API error: {e.response.status_code} — {e.response.text}")

    # DELETE returns 204 No Content — no body to parse
    if response.status_code == 204 or not response.content:
        return {}
    return response.json()


# ── Issues ────────────────────────────────────────────────────────────────────

# create_issue(project, repo, title, body)
#   Creates a GitHub issue in the project repo.
#   Returns the issue number and URL.
#   REST: POST /repos/{owner}/{repo}/issues

@tool
def create_issue(project: str, title: str, body: str) -> dict:
    """
    Creates a GitHub issue in the central change_management repo for this project.
    The repo is read from project.yml issues_repo — never passed as a parameter.
    Returns the issue number and URL — used in subsequent steps to link the PR.
    """
    # Guardrail — title and body must not be empty
    if not title or not title.strip():
        raise ValueError("Issue title cannot be empty.")
    if not body or not body.strip():
        raise ValueError("Issue body cannot be empty.")

    config      = load_project_config(project)
    issues_repo = config["github"]["issues_repo"]

    data = github_request(
        method="POST",
        config=config,
        repo=issues_repo,
        endpoint="issues",
        payload={"title": title, "body": body},
    )

    return {
        "issue_number": data["number"],
        "url":          data["html_url"],
        "title":        data["title"],
    }

# add_comment_to_issue(project, issue_number, comment)
#   Posts a comment on an existing issue — used to link the PR URL to the issue card.
#   REST: POST /repos/{owner}/{repo}/issues/{issue_number}/comments

@tool
def add_comment_to_issue(project: str, issue_number: int, comment: str) -> dict:
    """
    Posts a comment on an existing issue in the change_management repo.
    Used to link the PR URL to the issue so the team can navigate from board to PR.
    """
    # Guardrail — comment cannot be empty
    if not comment or not comment.strip():
        raise ValueError("Comment cannot be empty.")

    config      = load_project_config(project)
    issues_repo = config["github"]["issues_repo"]

    data = github_request(
        method="POST",
        config=config,
        repo=issues_repo,
        endpoint=f"issues/{issue_number}/comments",
        payload={"body": comment},
    )

    return {
        "comment_id": data["id"],
        "url":        data["html_url"],
    }

# close_issue(project, issue_number)
#   Closes a GitHub issue after the PR is merged.
#   REST: PATCH /repos/{owner}/{repo}/issues/{issue_number}  (state: closed)

def close_issue(project: str, issue_number: int) -> dict:
    """
    Closes a GitHub issue in the change_management repo after the PR is merged.
    NOT a @tool — called only by the orchestrator after merge_pr completes.
    The LLM can never trigger this directly.
    """
    config      = load_project_config(project)
    issues_repo = config["github"]["issues_repo"]

    data = github_request(
        method="PATCH",
        config=config,
        repo=issues_repo,
        endpoint=f"issues/{issue_number}",
        payload={"state": "closed"},
    )

    return {
        "issue_number": data["number"],
        "state":        data["state"],
        "url":          data["html_url"],
    }


# ── Project Board ─────────────────────────────────────────────────────────────

# move_issue_on_board(project, issue_number, column)
#   Moves an issue card to a different column on the GitHub Project board.
#   column is one of: backlog, ready, in_progress, in_review, done
#   Column names are read from project.yml board_columns — must match GitHub exactly.
#   GraphQL: GitHub Projects v2 does not support column moves via REST API.


# ── Branches ──────────────────────────────────────────────────────────────────

# create_branch(project, repo, branch_name)
#   Creates a new branch from main in the given repo.
#   Branch naming convention: feat/issue-{number}-{short-title}-agent
#   REST: GET  /repos/{owner}/{repo}/git/ref/heads/main  → get SHA
#         POST /repos/{owner}/{repo}/git/refs            → create branch

@tool
def create_branch(project: str, repo: str, branch_name: str) -> dict:
    """
    Creates a new branch from main in the given service repo.
    Branch naming convention: feat/issue-{number}-{short-title}-agent
    The -agent suffix makes agent-created branches visible and auditable in the repo.
    """
    # Guardrail — repo must be a declared service repo (blocks typos + issues_repo)
    validate_service_repo(project, repo)

    config         = load_project_config(project)
    default_branch = config["github"]["default_branch"]
    issues_repo    = config["github"]["issues_repo"]

    # Guardrail — enforce naming convention so agent branches are always identifiable.
    # Prefix is decided by the LLM (feat, fix, hotfix, docs, test, etc.)
    # but issue number and -agent suffix are mandatory.
    match = re.match(r"^[a-z]+/issue-(\d+)-.+-agent$", branch_name)
    if not match:
        raise ValueError(
            f"Branch name '{branch_name}' must follow pattern: {{type}}/issue-{{number}}-{{short-title}}-agent"
        )
    branch_issue_number = int(match.group(1))

    # Guardrail — verify the issue actually exists in the issues_repo before creating a branch
    # Prevents branches named after fabricated issue numbers.
    issue_check = requests.get(
        f"{GITHUB_API}/repos/{config['github']['owner']}/{issues_repo}/issues/{branch_issue_number}",
        headers=github_headers(),
    )
    if issue_check.status_code == 404:
        raise ValueError(
            f"Guardrail blocked: issue #{branch_issue_number} does not exist in '{issues_repo}'. "
            f"Create the issue first before branching."
        )

    # Step 1 — get the SHA of the latest commit on main
    ref = github_request(
        method="GET",
        config=config,
        repo=repo,
        endpoint=f"git/ref/heads/{default_branch}",
    )
    sha = ref["object"]["sha"]

    # Step 2 — create the new branch pointing to that SHA
    github_request(
        method="POST",
        config=config,
        repo=repo,
        endpoint="git/refs",
        payload={
            "ref": f"refs/heads/{branch_name}",
            "sha": sha,
        },
    )

    return {
        "branch": branch_name,
        "repo":   repo,
        "sha":    sha,
    }

# delete_branch(project, repo, branch_name)
#   Deletes a remote branch — fallback if auto-delete on merge is not enough.
#   REST: DELETE /repos/{owner}/{repo}/git/refs/heads/{branch_name}

@tool
def delete_branch(project: str, repo: str, branch_name: str) -> dict:
    """
    Deletes a remote branch from the given service repo.
    Normally handled automatically by GitHub after merge — use this as a fallback.
    """
    validate_service_repo(project, repo)

    config         = load_project_config(project)
    default_branch = config["github"]["default_branch"]

    # Guardrail — never allow deleting main or the default branch
    if branch_name == default_branch or branch_name == "main":
        raise ValueError(f"Deleting the default branch '{branch_name}' is not allowed.")

    github_request(
        method="DELETE",
        config=config,
        repo=repo,
        endpoint=f"git/refs/heads/{branch_name}",
    )

    return {
        "branch":  branch_name,
        "repo":    repo,
        "deleted": True,
    }


# ── Pull Requests ─────────────────────────────────────────────────────────────

@tool
def create_pr(project: str, repo: str, title: str, body: str, branch: str) -> dict:
    """
    Opens a pull request from branch → main.
    PR body should include "Closes #{issue_number}" to auto-link the issue.
    Returns pr_number and url — shared with the user during the HITL step.
    REST: POST /repos/{owner}/{repo}/pulls
    """
    # Guardrail — repo must be a declared service repo
    validate_service_repo(project, repo)

    config         = load_project_config(project)
    default_branch = config["github"]["default_branch"]

    # Guardrail — cannot open a PR from the default branch to itself
    if branch == default_branch or branch == "main":
        raise ValueError(f"Cannot create a PR from '{branch}' — PRs must come from a feature branch.")

    # Guardrail — body must include "Closes #" to auto-link the issue
    body_match = re.search(r"Closes #(\d+)", body)
    if not body_match:
        raise ValueError("PR body must include 'Closes #{issue_number}' to link the issue.")

    # Guardrail — PR issue number must match the branch's issue number.
    # Extract from branch (feat/issue-42-...) and from body (Closes #42).
    branch_match = re.match(r"^[a-z]+/issue-(\d+)-.+-agent$", branch)
    if branch_match:
        branch_issue = int(branch_match.group(1))
        body_issue   = int(body_match.group(1))
        if branch_issue != body_issue:
            raise ValueError(
                f"Guardrail blocked: PR body says 'Closes #{body_issue}' but branch is for issue #{branch_issue}. "
                f"Issue numbers must match."
            )

    # Guardrail — base is always the default branch, never anything else
    # Not a parameter — read from config so the LLM cannot change it
    data = github_request(
        method="POST",
        config=config,
        repo=repo,
        endpoint="pulls",
        payload={
            "title": title,
            "body":  body,
            "head":  branch,
            "base":  default_branch,   # always main, always from config
        },
    )

    return {
        "pr_number": data["number"],
        "url":       data["html_url"],
        "title":     data["title"],
        "branch":    branch,
    }


@tool
def get_pr(project: str, repo: str, pr_number: int) -> dict:
    """
    Gets the details of a pull request — title, body, state, branch, author.
    Used to check PR status before taking action.
    REST: GET /repos/{owner}/{repo}/pulls/{pr_number}
    """
    validate_service_repo(project, repo)
    config = load_project_config(project)

    data = github_request(
        method="GET",
        config=config,
        repo=repo,
        endpoint=f"pulls/{pr_number}",
    )

    return {
        "pr_number": data["number"],
        "title":     data["title"],
        "state":     data["state"],
        "branch":    data["head"]["ref"],
        "url":       data["html_url"],
        "merged":    data["merged"],
    }


@tool
def get_pr_diff(project: str, repo: str, pr_number: int) -> list:
    """
    Returns the list of files changed in a pull request with their diffs.
    Used by the Reviewer agent to read exactly what changed before deciding APPROVED or REJECTED.
    REST: GET /repos/{owner}/{repo}/pulls/{pr_number}/files
    """
    validate_service_repo(project, repo)
    config = load_project_config(project)

    files = github_request(
        method="GET",
        config=config,
        repo=repo,
        endpoint=f"pulls/{pr_number}/files",
    )

    return [
        {
            "filename": f["filename"],
            "status":   f["status"],       # added / modified / removed
            "patch":    f.get("patch", ""), # actual diff — absent for binary files
        }
        for f in files
    ]


@tool
def update_pr(project: str, repo: str, pr_number: int, title: str = None, body: str = None) -> dict:
    """
    Updates the title or body of an existing pull request.
    Used when the agent revises the PR after human feedback.
    REST: PATCH /repos/{owner}/{repo}/pulls/{pr_number}
    """
    # Guardrail — at least one field must be provided
    if not title and not body:
        raise ValueError("update_pr requires at least one of title or body.")

    validate_service_repo(project, repo)
    config  = load_project_config(project)
    payload = {}

    if title:
        payload["title"] = title
    if body:
        payload["body"] = body

    data = github_request(
        method="PATCH",
        config=config,
        repo=repo,
        endpoint=f"pulls/{pr_number}",
        payload=payload,
    )

    return {
        "pr_number": data["number"],
        "title":     data["title"],
        "url":       data["html_url"],
    }



@tool
def close_pr(project: str, repo: str, pr_number: int, reason: str) -> dict:
    """
    Closes a pull request without merging and posts the reason as a comment.
    Used when the pipeline is abandoned or the human permanently rejects the PR.
    The reason is recorded on the PR so there is always a clear audit trail.
    REST: POST /repos/{owner}/{repo}/issues/{pr_number}/comments  (post reason first)
          PATCH /repos/{owner}/{repo}/pulls/{pr_number}           (then close)
    """
    # Guardrail — reason cannot be empty
    if not reason or not reason.strip():
        raise ValueError("A reason must be provided when closing a PR without merging.")

    validate_service_repo(project, repo)
    config = load_project_config(project)

    # Guardrail — cannot close an already merged PR
    pr_data = github_request(method="GET", config=config, repo=repo, endpoint=f"pulls/{pr_number}")
    if pr_data["merged"]:
        raise ValueError(f"PR #{pr_number} is already merged — cannot close it.")
    if pr_data["state"] == "closed":
        raise ValueError(f"PR #{pr_number} is already closed.")

    # Post the reason as a comment before closing — creates an audit trail
    github_request(
        method="POST",
        config=config,
        repo=repo,
        endpoint=f"issues/{pr_number}/comments",
        payload={"body": f"Closing PR — Reason: {reason}"},
    )

    # Close the PR
    data = github_request(
        method="PATCH",
        config=config,
        repo=repo,
        endpoint=f"pulls/{pr_number}",
        payload={"state": "closed"},
    )

    return {
        "pr_number": data["number"],
        "state":     data["state"],
        "url":       data["html_url"],
        "reason":    reason,
    }


def merge_pr(project: str, repo: str, pr_number: int) -> dict:
    """
    Merges an approved pull request into main.
    NOT a @tool — called only by the orchestrator after human approval in the terminal.
    The LLM can never trigger this directly.
    REST: PUT /repos/{owner}/{repo}/pulls/{pr_number}/merge
    """
    # Guardrail — repo must be a declared service repo
    validate_service_repo(project, repo)

    config = load_project_config(project)

    # Guardrail — check PR is open and mergeable before attempting merge
    pr_data = github_request(method="GET", config=config, repo=repo, endpoint=f"pulls/{pr_number}")
    if pr_data["merged"]:
        raise ValueError(f"PR #{pr_number} is already merged.")
    if pr_data["state"] == "closed":
        raise ValueError(f"PR #{pr_number} is closed — cannot merge a closed PR.")
    if pr_data.get("mergeable") is False:
        raise ValueError(f"PR #{pr_number} has conflicts and cannot be merged. Resolve conflicts first.")

    # Guardrail — only merge PRs whose branch follows agent naming convention.
    # Prevents accidentally merging a human's manual PR that happens to be open.
    branch_ref = pr_data["head"]["ref"]
    if not branch_ref.endswith("-agent"):
        raise ValueError(
            f"Guardrail blocked: PR #{pr_number} branch '{branch_ref}' does not end with '-agent'. "
            f"Only merge PRs created by the agent pipeline."
        )

    data = github_request(
        method="PUT",
        config=config,
        repo=repo,
        endpoint=f"pulls/{pr_number}/merge",
        payload={"merge_method": "merge"},
    )

    return {
        "pr_number": pr_number,
        "merged":    data["merged"],
        "sha":       data.get("sha"),
        "message":   data["message"],
    }
