"""
Code search tool for the CodeAtlas agent.

This tool searches ChromaDB across all repositories belonging
to a CodeAtlas project.
"""

from qa.ask import search_chromadb


def search_code(project: str, query: str) -> list[dict]:
    """
    Search for code relevant to a natural-language query.

    Args:
        project:
            CodeAtlas project identifier.
            Example: "codeatlas/ecommerce"

        query:
            Natural-language description of the code we want to find.

    Returns:
        Relevant code chunks across all repositories in the project.
    """

    results = search_chromadb(project, query)

    return results

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: PYTHONPATH=. uv run python3 tools/code_search.py <project> <query>")
        print("\nExample:")
        print("  PYTHONPATH=. uv run python3 tools/code_search.py codeatlas/ecommerce \"stock reservation\"")
        sys.exit(1)

    project = sys.argv[1]
    query = sys.argv[2]

    results = search_code(project, query)

    print(f"\nFound {len(results)} results\n")

    for result in results:

        metadata = result["metadata"]

        print(
            f"Repo: {result['repo']} | "
            f"Type: {metadata.get('type')} | "
            f"Name: {metadata.get('name')} | "
            f"File: {metadata.get('file')}"
        )