# Iteration 2 — LangChain Tools
#
# All tool implementations live here — no separate tools/ folder.
#
# CodeAtlas comparison:
#   - CodeAtlas: handwritten TOOLS list (JSON dicts) + separate execute_tool() dispatcher
#   - LangChain: @tool decorator auto-generates the schema from type hints and docstring.
#                No dispatcher needed — LangChain handles routing.
#
# Why inject project?
#   The LLM should never choose which project to search.
#   We bind it here so the LLM only sees the parameters it needs to decide.

import os
import subprocess
from pathlib import Path

import chromadb
from src.memory_store import save_memory as _save_memory
from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2
from dotenv import load_dotenv
from langchain_core.tools import tool
from neo4j import GraphDatabase

load_dotenv()

# ── Neo4j connection ──────────────────────────────────────────────────────────
NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# ── Paths ─────────────────────────────────────────────────────────────────────
SOURCE_ROOT = Path("source")
CHROMA_PATH = "chroma_db/"
TOP_K       = 5

# The project is set once here and injected into every tool call.
# The LLM never sees or chooses this value.
PROJECT = "codeatlas/ecommerce"


# ── Helpers ───────────────────────────────────────────────────────────────────

def find_repos_in_project(project: str) -> list[str]:
    """Returns the names of all repos under source/<project>/."""
    project_path = SOURCE_ROOT / project
    if not project_path.exists():
        return []
    return [d.name for d in sorted(project_path.iterdir()) if d.is_dir()]


def search_chromadb(project: str, query: str) -> list[dict]:
    """Searches ChromaDB across all repos in a project."""
    repos   = find_repos_in_project(project)
    client  = chromadb.PersistentClient(path=CHROMA_PATH)
    embed   = ONNXMiniLM_L6_V2()
    results = []

    for repo in repos:
        try:
            collection = client.get_collection(name=repo, embedding_function=embed)
            response   = collection.query(
                query_texts=[query],
                n_results=min(TOP_K, collection.count()),
            )
            for i, doc in enumerate(response["documents"][0]):
                results.append({
                    "repo":     repo,
                    "document": doc,
                    "metadata": response["metadatas"][0][i],
                    "distance": response["distances"][0][i],
                })
        except Exception:
            pass  # repo not indexed yet — skip silently

    return results


# ── Tool factory ──────────────────────────────────────────────────────────────
#
# Why a factory function and not hardcoded tools?
#
# When a user makes a request, they specify which project they want to query:
#   "I want to know about payment logic in project codeatlas/ecommerce"
#
# The project comes from the request — not from the code.
# make_tools(project) creates tools already bound to that project.
# The LLM never sees or chooses the project — it only decides query/symbol/file.
#
# Tomorrow a different user queries a different project:
#   make_tools("microsoft/azure-sdk")
# Same tools, different project, zero code change.

def make_tools(project: str) -> list:
    """
    Creates and returns a list of LangChain tools bound to the given project.
    Call this once per request with the project from the user's input.
    """

    @tool
    def search_code(query: str) -> list:
        """
        Search source code semantically across the codebase.
        Use this to find where functionality, classes, or functions are implemented.
        """
        return search_chromadb(project, query)

    @tool
    def get_dependencies(symbol: str) -> list:
        """
        Get structural relationships for a code symbol — what it calls,
        what calls it, and which class it belongs to.
        Use this for dependency, impact, or caller/callee questions.
        """
        repos = find_repos_in_project(project)
        if not repos:
            return []

        driver  = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        matches = []

        try:
            with driver.session() as session:
                symbols = [r.data() for r in session.run(
                    "MATCH (n) WHERE n.name = $symbol AND n.repo IN $repos "
                    "RETURN labels(n) AS labels, n.name AS name, n.file AS file, n.repo AS repo",
                    {"symbol": symbol, "repos": repos},
                )]

                for item in symbols:
                    name, file_name, repo, labels = item["name"], item["file"], item["repo"], item["labels"]

                    calls     = [r.data() for r in session.run(
                        "MATCH (a {name:$n,file:$f,repo:$r})-[:CALLS]->(b) RETURN DISTINCT b.name AS name,b.file AS file,b.repo AS repo",
                        {"n": name, "f": file_name, "r": repo},
                    )]
                    called_by = [r.data() for r in session.run(
                        "MATCH (a)-[:CALLS]->(b {name:$n,file:$f,repo:$r}) RETURN DISTINCT a.name AS name,a.file AS file,a.repo AS repo",
                        {"n": name, "f": file_name, "r": repo},
                    )]
                    classes   = [r.data() for r in session.run(
                        "MATCH (c:Class)-[:HAS_METHOD]->(m {name:$n,file:$f,repo:$r}) RETURN DISTINCT c.name AS class_name,c.file AS file,c.repo AS repo",
                        {"n": name, "f": file_name, "r": repo},
                    )]

                    matches.append({
                        "project": project, "repo": repo, "file": file_name,
                        "symbol": name, "labels": labels,
                        "calls": calls, "called_by": called_by, "classes": classes,
                    })
        finally:
            driver.close()

        return matches

    @tool
    def read_file(repo: str, file_path: str) -> dict:
        """
        Read the exact source code of a file inside a repository.
        Use this when you need to inspect the complete file content.
        """
        repo_root      = (SOURCE_ROOT / project / repo).resolve()
        requested_file = (repo_root / file_path).resolve()

        try:
            requested_file.relative_to(repo_root)
        except ValueError:
            raise ValueError(f"Access denied: file must be inside repository '{repo}'")

        if not requested_file.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        return {
            "project": project,
            "repo":    repo,
            "file":    file_path,
            "content": requested_file.read_text(encoding="utf-8"),
        }

    @tool
    def write_file(repo: str, file_path: str, content: str) -> dict:
        """
        Overwrite an existing source file inside a repository.
        Use this only when source code needs to be modified.
        The complete new file content must be provided.
        """
        repo_root      = (SOURCE_ROOT / project / repo).resolve()
        requested_file = (repo_root / file_path).resolve()

        try:
            requested_file.relative_to(repo_root)
        except ValueError:
            raise ValueError(f"Access denied: file must be inside repository '{repo}'")

        if not requested_file.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        requested_file.write_text(content.replace("\x00", ""), encoding="utf-8")

        return {"project": project, "repo": repo, "file": file_path, "status": "updated"}

    @tool
    def run_tests(repo: str, test_command: str = "pytest -q") -> dict:
        """
        Run pytest inside a repository and return whether tests passed or failed.
        Use this after modifying code to validate the change.
        """
        repo_root = (SOURCE_ROOT / project / repo).resolve()

        if not repo_root.exists():
            raise FileNotFoundError(f"Repository not found: {repo}")

        if not test_command.startswith("pytest"):
            raise ValueError("Only pytest commands are allowed.")

        env               = os.environ.copy()
        env["PYTHONPATH"] = str(SOURCE_ROOT.resolve())

        result = subprocess.run(
            ["python", "-m"] + test_command.split(),
            cwd=repo_root, capture_output=True, text=True, env=env,
        )

        return {
            "project":     project,
            "repo":        repo,
            "passed":      result.returncode == 0,
            "return_code": result.returncode,
            "stdout":      result.stdout,
            "stderr":      result.stderr,
        }

    @tool
    def save_memory(key: str, value: str) -> dict:
        """
        Save a reusable fact about this project to long-term memory.
        Use this when you discover something stable and useful for future runs —
        such as where test files are, what framework is used, or naming conventions.
        Do not save temporary state, current errors, step numbers, or task-specific information.
        """
        return _save_memory(project=project, key=key, value=value)

    return [search_code, get_dependencies, read_file, write_file, run_tests, save_memory]
