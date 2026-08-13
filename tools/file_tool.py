"""
Source-file reader tool for the CodeAtlas agent.

Reads an exact source file from a repository belonging to a CodeAtlas project.
The tool does NOT allow arbitrary filesystem access.
"""

import sys
from pathlib import Path


# Local folder where CodeAtlas project repositories are cloned.
#
# Expected structure:
#
# projects/
# └── codeatlas/
#     └── ecommerce/
#         ├── inventory_service/
#         ├── order_service/
#         └── payment_service/
#
PROJECTS_ROOT = Path("source")


def read_file(project: str, repo: str, file_path: str) -> dict:
    """
    Read an exact source file from a repository.

    Args:
        project:
            CodeAtlas project identifier.
            Example:
                codeatlas/ecommerce

        repo:
            Repository name.
            Example:
                inventory_service

        file_path:
            File path relative to the repository.
            Example:
                stock_manager.py

    Returns:
        Dictionary containing project, repo, file and source code.
    """

    # Convert:
    #
    # codeatlas/ecommerce
    #
    # into:
    #
    # projects/codeatlas/ecommerce
    project_root = (PROJECTS_ROOT / project).resolve()

    repo_root = (project_root / repo).resolve()

    # Strip repo prefix from file_path if the LLM accidentally includes it.
    # e.g. file_path="inventory_service/stock_manager.py" → "stock_manager.py"
    if file_path.startswith(repo + "/"):
        file_path = file_path[len(repo) + 1:]

    requested_file = (repo_root / file_path).resolve()

    # ---------------------------------------------------------
    # Safety check
    #
    # Prevent things such as:
    #
    # ../../.env
    # /etc/passwd
    #
    # The requested file MUST stay inside the requested repo.
    # ---------------------------------------------------------
    try:
        requested_file.relative_to(repo_root)
    except ValueError:
        raise ValueError(
            f"Access denied: file must be inside repository '{repo}'"
        )

    # repo must exist
    if not repo_root.exists():
        raise FileNotFoundError(
            f"Repository not found: {repo_root}"
        )

    # requested file must exist
    if not requested_file.exists():
        raise FileNotFoundError(
            f"File not found: {requested_file}"
        )

    # do not allow directories
    if not requested_file.is_file():
        raise ValueError(
            f"Path is not a file: {requested_file}"
        )

    content = requested_file.read_text(
        encoding="utf-8"
    )

    return {
        "project": project,
        "repo": repo,
        "file": file_path,
        "content": content,
    }


if __name__ == "__main__":

    if len(sys.argv) < 4:
        print(
            "Usage: PYTHONPATH=. uv run python3 "
            'tools/file_tool.py <project> <repo> "<file>"'
        )

        print("\nExample:")

        print(
            "  PYTHONPATH=. uv run python3 "
            "tools/file_tool.py "
            "codeatlas/ecommerce "
            'inventory_service "stock_manager.py"'
        )

        sys.exit(1)

    project = sys.argv[1]
    repo = sys.argv[2]
    file_path = sys.argv[3]

    try:

        result = read_file(
            project,
            repo,
            file_path,
        )

        print("=" * 60)
        print(f"Project : {result['project']}")
        print(f"Repo    : {result['repo']}")
        print(f"File    : {result['file']}")
        print("=" * 60)

        print(result["content"])

    except Exception as exc:

        print(f"\nError: {exc}")
        sys.exit(1)