# Project crawler for CodeAtlas.
# Accepts a project path under source/, crawls all Python files using
# python_ast.py, and saves the results as JSON files under output/
# mirroring the exact folder structure of the source project.
#
# Supports incremental crawling — if a file has not changed since the
# last crawl (based on last modified timestamp), it is skipped.
# Deleting the output folder forces a full re-crawl.
#
# Usage:
#   uv run crawlers/crawl_project.py source/codeatlas/sample/grade_calculator
#
# Output:
#   output/codeatlas/sample/grade_calculator/_project.json
#   output/codeatlas/sample/grade_calculator/main.json
#   output/codeatlas/sample/grade_calculator/utils.json

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from crawlers.python_ast import crawl_file, find_python_files


def build_output_path(source_file_path: str) -> Path:
    """
    Converts a source file path to its mirrored output path.

    Replaces the leading 'source' folder with 'output' and changes
    the .py extension to .json. Everything else in the path stays identical
    so the output folder structure exactly mirrors the source structure.

    Example:
        source/codeatlas/sample/grade_calculator/lib/utils.py
        → output/codeatlas/sample/grade_calculator/lib/utils.json
    """
    source_path = Path(source_file_path)

    # get the path relative to the 'source' folder
    relative_path = source_path.relative_to("source")

    # replace 'source' with 'output' and change extension to .json
    return Path("output") / relative_path.with_suffix(".json")


def get_file_timestamp(file_path: str) -> str:
    """
    Returns the last modified timestamp of a file as an ISO format string.

    Uses UTC timezone so timestamps are consistent regardless of where
    the crawler is run. This timestamp is stored in the JSON and used
    on the next run to decide whether the file needs re-crawling.
    """
    mtime = Path(file_path).stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()


def is_file_unchanged(file_path: str, output_path: Path) -> bool:
    """
    Checks if a source file has changed since it was last crawled.

    Returns True if:
    - The output JSON exists AND
    - The file's current last modified timestamp matches what is stored in the JSON

    Returns False if:
    - The output JSON does not exist (never crawled or output was deleted)
    - The timestamps do not match (file was modified since last crawl)
    """
    if not output_path.exists():
        return False

    current_timestamp = get_file_timestamp(file_path)

    with open(output_path, "r", encoding="utf-8") as f:
        existing = json.load(f)

    return existing.get("last_modified") == current_timestamp


def save_json(data: dict, output_path: Path) -> None:
    """
    Saves a dict as a formatted JSON file at the given path.

    Creates all parent directories if they do not exist — this is what
    mirrors the source folder structure in the output folder automatically.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        # indent=2 makes the JSON human-readable for debugging
        json.dump(data, f, indent=2)


def attach_timestamp_to_result(result: dict, timestamp: str) -> dict:
    """
    Attaches the file-level last modified timestamp to the crawl result
    and reflects it onto every function, method, and class extracted
    from that file.

    Since the OS only tracks timestamps at the file level, all items
    extracted from the same file share the same timestamp. This is accurate
    enough for incremental crawling — if anything in the file changed,
    the file timestamp changes and everything gets re-crawled.
    """
    result["last_modified"] = timestamp

    for func in result.get("functions", []):
        func["last_modified"] = timestamp

    for cls in result.get("classes", []):
        cls["last_modified"] = timestamp
        for method in cls.get("methods", []):
            method["last_modified"] = timestamp

    return result


def build_project_metadata(project_path: str, file_output_paths: list[str]) -> dict:
    """
    Builds the _project.json metadata file for a crawled project.

    This file acts as the index for the project — it records who owns it,
    what it is called, when it was crawled, and which JSON files were produced.
    The chunker reads this file first to know what to process.
    """
    path_parts = Path(project_path).parts

    # extract owner, project, repo from the source path structure
    # source/codeatlas/sample/grade_calculator → owner=codeatlas, project=sample, repo=grade_calculator
    source_index = list(path_parts).index("source")
    owner   = path_parts[source_index + 1] if len(path_parts) > source_index + 1 else "unknown"
    project = path_parts[source_index + 2] if len(path_parts) > source_index + 2 else "unknown"
    repo    = path_parts[source_index + 3] if len(path_parts) > source_index + 3 else "unknown"

    return {
        "owner": owner,
        "project": project,
        "repo": repo,
        "crawled_at": datetime.now(tz=timezone.utc).isoformat(),
        "files": file_output_paths,
    }


def crawl_project(project_path: str) -> None:
    """
    Crawls all Python files in a project and saves the results as JSON.

    For each Python file:
    1. Gets the file's last modified timestamp
    2. Checks if the output JSON already exists with the same timestamp
       - If yes → skip (file unchanged since last crawl)
       - If no  → crawl the file and save the JSON
    3. Attaches the timestamp to the result and all its functions/classes
    4. Mirrors the source path to an output path and saves the JSON

    Also saves a _project.json metadata file as the index for the project.
    """
    python_files = find_python_files(project_path)

    if not python_files:
        print(f"No Python files found in {project_path}")
        return

    print(f"\nProject  : {project_path}")
    print(f"Files    : {len(python_files)}")
    print(f"{'='*60}")

    file_output_paths = []

    for file_path in python_files:
        output_path = build_output_path(file_path)

        # check if file has changed since last crawl
        if is_file_unchanged(file_path, output_path):
            print(f"  skipped (unchanged): {file_path}")
            file_output_paths.append(str(output_path))
            continue

        # get the file's last modified timestamp before crawling
        timestamp = get_file_timestamp(file_path)

        # extract structured data using the AST crawler
        result = crawl_file(file_path)

        # attach the timestamp to the result and all its children
        result = attach_timestamp_to_result(result, timestamp)

        # save to JSON
        save_json(result, output_path)

        file_output_paths.append(str(output_path))
        print(f"  crawled: {output_path}")

    # save the project metadata index file
    metadata = build_project_metadata(project_path, file_output_paths)
    project_output_dir = Path("output") / Path(project_path).relative_to("source")
    project_json_path = project_output_dir / "_project.json"
    save_json(metadata, project_json_path)

    print(f"  saved  : {project_json_path}")
    print(f"\nDone. Output saved to: output/")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run crawlers/crawl_project.py <project_path>")
        sys.exit(1)

    PROJECT_PATH = sys.argv[1]
    crawl_project(PROJECT_PATH)
