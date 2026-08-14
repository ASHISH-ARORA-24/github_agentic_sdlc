# Project Board Tools
#
# All GitHub Project board operations for the SDLC pipeline.
# Uses the GitHub GraphQL API — Projects v2 has no REST support for board operations.
#
# GraphQL endpoint: https://api.github.com/graphql
# Same GITHUB_TOKEN as REST tools — loaded from .env
#
# Structure:
#   Helpers   — graphql_request, get_project_id, get_issue_node_id, get_item_id, get_status_field
#   @tool     — add_issue_to_board, move_task, update_task, close_task

import os
import time
import requests
import yaml
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

# In-memory cache: (project, issue_number) → item_id
# add_issue_to_board writes here so move_task/update_task/close_task
# don't need a slow GraphQL lookup for a freshly added item.
_item_id_cache: dict = {}

GRAPHQL_URL = "https://api.github.com/graphql"


# ── Config ────────────────────────────────────────────────────────────────────

def load_project_config(project: str) -> dict:
    """Reads source/<project>/project.yml and returns the config as a dict."""
    with open(f"source/{project}/project.yml", "r") as f:
        return yaml.safe_load(f)


# ── GraphQL helper ────────────────────────────────────────────────────────────

def graphql_request(query: str, variables: dict, config: dict) -> dict:
    """
    Sends an authenticated GraphQL request to the GitHub API.
    Returns the data dict. Raises on HTTP error or GraphQL error.
    GraphQL always returns 200 — errors are in the response body, not the status code.
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN not found in .env")

    response = requests.post(
        GRAPHQL_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables},
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"GitHub GraphQL HTTP error: {e.response.status_code} — {e.response.text}")

    body = response.json()

    # GraphQL returns 200 even on errors — must check the errors field explicitly
    if "errors" in body:
        raise RuntimeError(f"GitHub GraphQL error: {body['errors']}")

    return body["data"]


# ── Node ID helpers ───────────────────────────────────────────────────────────
# GraphQL uses node IDs (opaque strings like PVT_kwDO...) instead of integers.
# These helpers translate human-readable values into node IDs that mutations need.

def get_project_id(config: dict) -> str:
    """Gets the project board's node ID from its project number in project.yml."""
    owner  = config["github"]["owner"]
    number = config["github"]["project_number"]

    data = graphql_request(
        query="""
            query($owner: String!, $number: Int!) {
              user(login: $owner) {
                projectV2(number: $number) {
                  id
                }
              }
            }
        """,
        variables={"owner": owner, "number": number},
        config=config,
    )
    return data["user"]["projectV2"]["id"]


def get_issue_node_id(config: dict, issue_number: int) -> str:
    """Gets the GitHub node ID of an issue — needed to add it to the project board."""
    owner       = config["github"]["owner"]
    issues_repo = config["github"]["issues_repo"]

    data = graphql_request(
        query="""
            query($owner: String!, $repo: String!, $number: Int!) {
              repository(owner: $owner, name: $repo) {
                issue(number: $number) {
                  id
                }
              }
            }
        """,
        variables={"owner": owner, "repo": issues_repo, "number": issue_number},
        config=config,
    )
    return data["repository"]["issue"]["id"]


def get_item_id(config: dict, issue_number: int) -> str:
    """
    Gets the board item node ID for a given issue number.
    Checks the in-memory cache first — add_issue_to_board writes to it so
    freshly added items are found instantly without a GraphQL round-trip.
    Falls back to a GraphQL query with retries if not in cache.
    """
    project = config.get("project", "")
    cache_key = (project, issue_number)

    # Cache hit — item was just added this session
    if cache_key in _item_id_cache:
        return _item_id_cache[cache_key]

    owner  = config["github"]["owner"]
    number = config["github"]["project_number"]

    ITEMS_QUERY = """
        query($owner: String!, $number: Int!) {
          user(login: $owner) {
            projectV2(number: $number) {
              items(first: 100) {
                nodes {
                  id
                  content {
                    ... on Issue { number }
                  }
                }
              }
            }
          }
        }
    """

    # Retry up to 3 times with 3-second waits — GitHub indexes new items with a delay
    for attempt in range(3):
        data = graphql_request(query=ITEMS_QUERY, variables={"owner": owner, "number": number}, config=config)
        for item in data["user"]["projectV2"]["items"]["nodes"]:
            if item.get("content", {}).get("number") == issue_number:
                return item["id"]
        if attempt < 2:
            time.sleep(3)

    raise ValueError(f"Issue #{issue_number} not found on the project board. Add it first with add_issue_to_board.")


def get_status_field(config: dict) -> dict:
    """
    Gets the Status field ID and a mapping of column name → option ID.
    Used by move_task to find the correct option ID for the target column.
    """
    owner  = config["github"]["owner"]
    number = config["github"]["project_number"]

    data = graphql_request(
        query="""
            query($owner: String!, $number: Int!) {
              user(login: $owner) {
                projectV2(number: $number) {
                  fields(first: 20) {
                    nodes {
                      ... on ProjectV2SingleSelectField {
                        id
                        name
                        options { id name }
                      }
                    }
                  }
                }
              }
            }
        """,
        variables={"owner": owner, "number": number},
        config=config,
    )

    for field in data["user"]["projectV2"]["fields"]["nodes"]:
        if field.get("name") == "Status":
            return {
                "field_id": field["id"],
                "options":  {opt["name"]: opt["id"] for opt in field["options"]},
            }

    raise ValueError("Status field not found on the project board.")


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def add_issue_to_board(project: str, issue_number: int) -> dict:
    """
    Adds a GitHub issue to the project board.
    Must be called after create_issue — before any move_task calls.
    GraphQL: addProjectV2ItemById mutation
    """
    config     = load_project_config(project)
    config["project"] = project   # store project key so get_item_id can build cache key
    project_id = get_project_id(config)
    issue_id   = get_issue_node_id(config, issue_number)

    data = graphql_request(
        query="""
            mutation($projectId: ID!, $contentId: ID!) {
              addProjectV2ItemById(input: {
                projectId: $projectId
                contentId: $contentId
              }) {
                item { id }
              }
            }
        """,
        variables={"projectId": project_id, "contentId": issue_id},
        config=config,
    )

    item_id = data["addProjectV2ItemById"]["item"]["id"]

    # Cache the item_id so move_task/update_task/close_task don't need a slow lookup
    _item_id_cache[(project, issue_number)] = item_id

    return {
        "issue_number": issue_number,
        "item_id":      item_id,
        "status":       "added to board",
    }


@tool
def move_task(project: str, issue_number: int, column: str) -> dict:
    """
    Moves an issue card to a different column on the project board.
    column must be one of the keys in project.yml board_columns:
      backlog | ready | in_progress | in_review | done
    GraphQL: updateProjectV2ItemFieldValue mutation
    """
    config            = load_project_config(project)
    config["project"] = project
    col_name          = config["github"]["board_columns"].get(column)

    # Guardrail — column key must exist in project.yml
    if not col_name:
        valid = list(config["github"]["board_columns"].keys())
        raise ValueError(f"Invalid column '{column}'. Must be one of: {valid}")

    project_id   = get_project_id(config)
    item_id      = get_item_id(config, issue_number)
    status_field = get_status_field(config)
    field_id     = status_field["field_id"]
    option_id    = status_field["options"].get(col_name)

    if not option_id:
        raise ValueError(f"Column '{col_name}' not found on the board Status field.")

    graphql_request(
        query="""
            mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
              updateProjectV2ItemFieldValue(input: {
                projectId: $projectId
                itemId:    $itemId
                fieldId:   $fieldId
                value:     { singleSelectOptionId: $optionId }
              }) {
                projectV2Item { id }
              }
            }
        """,
        variables={
            "projectId": project_id,
            "itemId":    item_id,
            "fieldId":   field_id,
            "optionId":  option_id,
        },
        config=config,
    )

    return {
        "issue_number": issue_number,
        "moved_to":     col_name,
    }


@tool
def update_task(project: str, issue_number: int, title: str = None, body: str = None) -> dict:
    """
    Updates the title or body of an issue on the project board.
    At least one of title or body must be provided.
    GraphQL: updateIssue mutation
    """
    # Guardrail — at least one field must be provided
    if not title and not body:
        raise ValueError("update_task requires at least one of title or body.")

    config            = load_project_config(project)
    config["project"] = project
    issue_id          = get_issue_node_id(config, issue_number)

    data = graphql_request(
        query="""
            mutation($id: ID!, $title: String, $body: String) {
              updateIssue(input: { id: $id, title: $title, body: $body }) {
                issue {
                  number
                  title
                  url
                }
              }
            }
        """,
        variables={"id": issue_id, "title": title, "body": body},
        config=config,
    )

    issue = data["updateIssue"]["issue"]
    return {
        "issue_number": issue["number"],
        "title":        issue["title"],
        "url":          issue["url"],
    }


@tool
def close_task(project: str, issue_number: int) -> dict:
    """
    Archives a task on the project board after the PR is merged and issue is closed.
    Archiving removes it from the active board view without deleting it.
    GraphQL: archiveProjectV2Item mutation
    """
    config            = load_project_config(project)
    config["project"] = project
    project_id        = get_project_id(config)
    item_id           = get_item_id(config, issue_number)

    graphql_request(
        query="""
            mutation($projectId: ID!, $itemId: ID!) {
              archiveProjectV2Item(input: {
                projectId: $projectId
                itemId:    $itemId
              }) {
                item { id }
              }
            }
        """,
        variables={"projectId": project_id, "itemId": item_id},
        config=config,
    )

    return {
        "issue_number": issue_number,
        "status":       "archived from board",
    }


@tool
def add_comment_to_task(project: str, issue_number: int, comment: str) -> dict:
    """
    Posts a comment on a task (issue) on the project board.
    Used to log agent activity — branch created, PR opened, review result, etc.
    GraphQL: addComment mutation
    """
    # Guardrail — comment cannot be empty
    if not comment or not comment.strip():
        raise ValueError("Comment cannot be empty.")

    config            = load_project_config(project)
    config["project"] = project
    issue_id          = get_issue_node_id(config, issue_number)

    data = graphql_request(
        query="""
            mutation($subjectId: ID!, $body: String!) {
              addComment(input: { subjectId: $subjectId, body: $body }) {
                commentEdge {
                  node {
                    id
                    url
                  }
                }
              }
            }
        """,
        variables={"subjectId": issue_id, "body": comment},
        config=config,
    )

    node = data["addComment"]["commentEdge"]["node"]
    return {
        "issue_number": issue_number,
        "comment_id":   node["id"],
        "url":          node["url"],
    }
