from pathlib import Path


PROJECTS_ROOT = Path("source")


def write_file(
    project: str,
    repo: str,
    file_path: str,
    content: str,
) -> dict:
    """
    Safely overwrite a source file inside a repository.

    The requested file must stay inside:
        projects/<project>/<repo>/

    Args:
        project:
            Example: codeatlas/ecommerce

        repo:
            Example: inventory_service

        file_path:
            Path relative to repository root.
            Example: main.py

        content:
            Complete new file content.

    Returns:
        Information about the modified file.
    """

    project_root = (PROJECTS_ROOT / project).resolve()
    repo_root    = (project_root / repo).resolve()

    # Strip repo prefix from file_path if the LLM accidentally includes it.
    # e.g. file_path="inventory_service/stock_manager.py" → "stock_manager.py"
    if file_path.startswith(repo + "/"):
        file_path = file_path[len(repo) + 1:]

    requested_file = (repo_root / file_path).resolve()

    # ---------------------------------------------------------
    # SAFETY: prevent escaping outside the selected repository
    # ---------------------------------------------------------
    try:
        requested_file.relative_to(repo_root)
    except ValueError:
        raise ValueError(
            f"Access denied: file must be inside repository '{repo}'"
        )

    if not repo_root.exists():
        raise FileNotFoundError(
            f"Repository not found: {repo_root}"
        )

    # For Iteration 3, only modify files that already exist.
    # Do not allow the agent to create arbitrary new files yet.
    if not requested_file.exists():
        raise FileNotFoundError(
            f"File not found: {requested_file}"
        )

    if not requested_file.is_file():
        raise ValueError(
            f"Path is not a file: {requested_file}"
        )

    # Save old content so later we could support rollback/diff.
    old_content = requested_file.read_text(
        encoding="utf-8"
    )

    # Strip null bytes — LLMs sometimes encode special characters (e.g. em-dashes)
    # as \x00 in JSON responses, which produces binary files unreadable by editors.
    clean_content = content.replace("\x00", "")

    requested_file.write_text(
        clean_content,
        encoding="utf-8"
    )

    return {
        "project": project,
        "repo": repo,
        "file": file_path,
        "status": "updated",
        "old_size": len(old_content),
        "new_size": len(content),
    }


if __name__ == "__main__":

    import sys

    if len(sys.argv) < 5:
        print(
            'Usage: PYTHONPATH=. uv run python3 '
            'tools/write_file.py <project> <repo> "<file>" "<content>"'
        )

        print()
        print("Example:")
        print(
            '  PYTHONPATH=. uv run python3 '
            'tools/write_file.py '
            'codeatlas/ecommerce '
            'inventory_service '
            '"main.py" '
            '"# test content"'
        )

        sys.exit(1)

    project = sys.argv[1]
    repo = sys.argv[2]
    file_path = sys.argv[3]
    content = sys.argv[4]

    result = write_file(
        project=project,
        repo=repo,
        file_path=file_path,
        content=content,
    )

    print(result)