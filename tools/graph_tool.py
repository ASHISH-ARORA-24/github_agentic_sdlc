# Neo4j dependency tool for CodeAtlas.
# Looks up structural relationships for a code symbol across all repos in a project.
#
# Usage:
#   PYTHONPATH=. uv run python3 tools/graph_tool.py <project> "<symbol>"

import os
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase

from qa.ask import find_repos_in_project

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


def get_dependencies(project: str, symbol: str) -> list[dict]:
    """
    Finds structural relationships for a symbol across all repos in a project.
    Returns callers, callees, and class membership for every matching node.
    """
    repos = find_repos_in_project(project)
    if not repos:
        return []

    driver  = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    matches = []

    try:
        with driver.session() as session:
            result  = session.run(
                "MATCH (n) WHERE n.name = $symbol AND n.repo IN $repos "
                "RETURN labels(n) AS labels, n.name AS name, n.file AS file, n.repo AS repo",
                {"symbol": symbol, "repos": repos},
            )
            symbols = [r.data() for r in result]

            for item in symbols:
                name      = item["name"]
                file_name = item["file"]
                repo      = item["repo"]
                labels    = item["labels"]

                calls = [r.data() for r in session.run(
                    "MATCH (caller {name: $name, file: $file, repo: $repo})-[:CALLS]->(callee) "
                    "RETURN DISTINCT callee.name AS name, callee.file AS file, callee.repo AS repo",
                    {"name": name, "file": file_name, "repo": repo},
                )]

                called_by = [r.data() for r in session.run(
                    "MATCH (caller)-[:CALLS]->(callee {name: $name, file: $file, repo: $repo}) "
                    "RETURN DISTINCT caller.name AS name, caller.file AS file, caller.repo AS repo",
                    {"name": name, "file": file_name, "repo": repo},
                )]

                classes = [r.data() for r in session.run(
                    "MATCH (c:Class)-[:HAS_METHOD]->(m {name: $name, file: $file, repo: $repo}) "
                    "RETURN DISTINCT c.name AS class_name, c.file AS file, c.repo AS repo",
                    {"name": name, "file": file_name, "repo": repo},
                )]

                matches.append({
                    "project": project, "repo": repo, "file": file_name,
                    "symbol": name, "labels": labels,
                    "calls": calls, "called_by": called_by, "classes": classes,
                })
    finally:
        driver.close()

    return matches


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: PYTHONPATH=. uv run python3 tools/graph_tool.py <project> \"<symbol>\"")
        sys.exit(1)

    results = get_dependencies(sys.argv[1], sys.argv[2])

    if not results:
        print(f"\nNo graph information found for: {sys.argv[2]}")
        sys.exit(0)

    print(f"\nFound {len(results)} matching symbol(s)\n")

    for result in results:
        print("=" * 60)
        print(f"Project : {result['project']}")
        print(f"Repo    : {result['repo']}")
        print(f"File    : {result['file']}")
        print(f"Symbol  : {result['symbol']}")
        print(f"Type    : {', '.join(result['labels'])}")

        print("\nCalls:")
        if result["calls"]:
            for d in result["calls"]:
                print(f"  -> {d['name']} ({d['file']}, repo: {d['repo']})")
        else:
            print("  None")

        print("\nCalled by:")
        if result["called_by"]:
            for c in result["called_by"]:
                print(f"  <- {c['name']} ({c['file']}, repo: {c['repo']})")
        else:
            print("  None")

        print("\nClass:")
        if result["classes"]:
            for cls in result["classes"]:
                print(f"  {cls['class_name']} ({cls['file']})")
        else:
            print("  None")
        print()
