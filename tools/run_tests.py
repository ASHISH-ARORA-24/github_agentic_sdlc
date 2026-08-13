import subprocess
from pathlib import Path


PROJECTS_ROOT = Path("source")


def run_tests(
    project: str,
    repo: str,
    test_command: str = "pytest -q",
) -> dict:
    """
    Run tests inside a repository.

    Args:
        project:
            Example: codeatlas/ecommerce

        repo:
            Example: inventory_service

        test_command:
            Test command to execute.
            Default: pytest -q

    Returns:
        Test result details.
    """

    project_root = (PROJECTS_ROOT / project).resolve()
    repo_root = (project_root / repo).resolve()

    if not repo_root.exists():
        raise FileNotFoundError(
            f"Repository not found: {repo_root}"
        )

    if not repo_root.is_dir():
        raise ValueError(
            f"Repository path is not a directory: {repo_root}"
        )

    # For this learning iteration, only allow pytest commands.
    if not test_command.startswith("pytest"):
        raise ValueError(
            "Only pytest commands are allowed in this iteration."
        )

    # Use "python -m pytest" instead of bare "pytest" so it always picks
    # up the pytest installed in the current virtual environment rather
    # than looking for a pytest binary in PATH (which may not exist).
    command = ["python", "-m"] + test_command.split()

    # Set PYTHONPATH to the project root's source/ folder so absolute imports
    # like "from codeatlas.ecommerce.inventory_service.models import StockLevel"
    # resolve correctly when running tests from any repo subfolder.
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path("source").resolve())

    result = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
    )

    return {
        "project": project,
        "repo": repo,
        "command": test_command,
        "passed": result.returncode == 0,
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


if __name__ == "__main__":

    import sys
    import json

    if len(sys.argv) < 3:
        print(
            'Usage: PYTHONPATH=. uv run python3 '
            'tools/run_tests.py <project> <repo> ["pytest command"]'
        )

        print()
        print("Example:")
        print(
            '  PYTHONPATH=. uv run python3 '
            'tools/run_tests.py '
            'codeatlas/ecommerce '
            'inventory_service'
        )

        sys.exit(1)

    project = sys.argv[1]
    repo = sys.argv[2]

    test_command = (
        sys.argv[3]
        if len(sys.argv) >= 4
        else "pytest -q"
    )

    result = run_tests(
        project=project,
        repo=repo,
        test_command=test_command,
    )

    print(json.dumps(result, indent=2))