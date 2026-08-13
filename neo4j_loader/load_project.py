# Neo4j Loader for CodeAtlas.
# Reads the JSON files produced by crawlers/crawl_project.py and builds
# a knowledge graph in Neo4j with nodes (File, Function, Class, Method)
# and relationships (CONTAINS, HAS_METHOD, IMPORTS, CALLS).
#
# Supports incremental updates — files with unchanged timestamps are skipped.
# Stale nodes for deleted functions/classes are removed automatically.
#
# Neo4j driver 6.x requires parameters to be passed as a dict, not kwargs.
#
# Usage:
#   PYTHONPATH=. uv run python3 neo4j_loader/load_project.py source/codeatlas/sample/grade_calculator

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

# load credentials from .env file
load_dotenv()

# Neo4j connection settings — read from .env, never hardcoded
NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


def connect_to_neo4j() -> Driver:
    """
    Connects to the Neo4j database using credentials from .env.

    Returns a Neo4j Driver — the entry point for all database operations.
    The driver manages the connection pool and should be closed when done.
    """
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


def build_node_id(repo: str, file_name: str, *parts: str) -> str:
    """
    Builds a unique stable ID for a node in Neo4j.

    Uses the same format as ChromaDB chunk IDs so they can be correlated:
        grade_calculator::utils.py::calculate_average
        grade_calculator::utils.py::StudentProfile
        grade_calculator::utils.py::StudentProfile::get_summary
    """
    return "::".join([repo, file_name] + list(parts))


def is_file_unchanged_in_neo4j(driver: Driver, file_path: str, timestamp: str) -> bool:
    """
    Checks if the File node in Neo4j already has the current timestamp.

    If the timestamp matches, nothing in the file has changed since the
    last load — skip all processing for this file.
    """
    with driver.session() as session:
        result = session.run(
            "MATCH (f:File {path: $path, last_modified: $timestamp}) RETURN f",
            {"path": file_path, "timestamp": timestamp},
        )
        return result.single() is not None


def create_file_node(driver: Driver, file_data: dict, repo: str) -> None:
    """
    Creates or updates a File node in Neo4j.

    Uses MERGE so re-running never creates duplicate nodes.
    SET updates the properties if the node already exists.
    """
    with driver.session() as session:
        session.run(
            """
            MERGE (f:File {path: $path})
            SET f.name          = $name,
                f.repo          = $repo,
                f.last_modified = $last_modified
            """,
            {
                "path": file_data["path"],
                "name": file_data["file"],
                "repo": repo,
                "last_modified": file_data.get("last_modified", ""),
            },
        )


def create_function_nodes(driver: Driver, file_data: dict, repo: str) -> None:
    """
    Creates Function nodes and connects them to their File node with CONTAINS.

    Each function gets a unique node_id built from repo + file + name.
    Parameters are stored as a JSON string since Neo4j does not support
    nested objects as properties.

    Uses two separate queries — one to create the node, one to create
    the relationship — for clarity and reliability.
    """
    with driver.session() as session:
        for func in file_data.get("functions", []):
            node_id = build_node_id(repo, file_data["file"], func["name"])

            # create or update the function node
            session.run(
                """
                MERGE (fn:Function {node_id: $node_id})
                SET fn.name          = $name,
                    fn.file          = $file,
                    fn.repo          = $repo,
                    fn.docstring     = $docstring,
                    fn.return_type   = $return_type,
                    fn.parameters    = $parameters,
                    fn.calls         = $calls,
                    fn.line_number   = $line_number,
                    fn.last_modified = $last_modified
                """,
                {
                    "node_id": node_id,
                    "name": func["name"],
                    "file": file_data["file"],
                    "repo": repo,
                    "docstring": func.get("docstring", ""),
                    "return_type": func.get("return_type", "unknown"),
                    "parameters": json.dumps(func.get("parameters", [])),
                    "calls": func.get("calls", []),
                    "line_number": func.get("line_number", 0),
                    "last_modified": file_data.get("last_modified", ""),
                },
            )

            # create the CONTAINS relationship from File to Function
            session.run(
                """
                MATCH (f:File {path: $file_path})
                MATCH (fn:Function {node_id: $node_id})
                MERGE (f)-[:CONTAINS]->(fn)
                """,
                {"file_path": file_data["path"], "node_id": node_id},
            )


def create_class_nodes(driver: Driver, file_data: dict, repo: str) -> None:
    """
    Creates Class and Method nodes and connects them with relationships.

    For each class:
    - Creates a Class node connected to its File with CONTAINS
    - Creates a Method node for each method connected to its Class with HAS_METHOD

    This two-level structure in Neo4j mirrors the two-level structure
    in the source code — File → Class → Method.
    """
    with driver.session() as session:
        for cls in file_data.get("classes", []):
            class_node_id = build_node_id(repo, file_data["file"], cls["name"])

            # create or update the class node
            session.run(
                """
                MERGE (c:Class {node_id: $node_id})
                SET c.name          = $name,
                    c.file          = $file,
                    c.repo          = $repo,
                    c.docstring     = $docstring,
                    c.line_number   = $line_number,
                    c.last_modified = $last_modified
                """,
                {
                    "node_id": class_node_id,
                    "name": cls["name"],
                    "file": file_data["file"],
                    "repo": repo,
                    "docstring": cls.get("docstring", ""),
                    "line_number": cls.get("line_number", 0),
                    "last_modified": file_data.get("last_modified", ""),
                },
            )

            # connect class to its file
            session.run(
                """
                MATCH (f:File {path: $file_path})
                MATCH (c:Class {node_id: $node_id})
                MERGE (f)-[:CONTAINS]->(c)
                """,
                {"file_path": file_data["path"], "node_id": class_node_id},
            )

            # create method nodes and connect to class
            for method in cls.get("methods", []):
                method_node_id = build_node_id(repo, file_data["file"], cls["name"], method["name"])

                # create or update the method node
                session.run(
                    """
                    MERGE (m:Method {node_id: $node_id})
                    SET m.name          = $name,
                        m.class         = $class_name,
                        m.file          = $file,
                        m.repo          = $repo,
                        m.docstring     = $docstring,
                        m.return_type   = $return_type,
                        m.parameters    = $parameters,
                        m.calls         = $calls,
                        m.line_number   = $line_number,
                        m.last_modified = $last_modified
                    """,
                    {
                        "node_id": method_node_id,
                        "name": method["name"],
                        "class_name": cls["name"],
                        "file": file_data["file"],
                        "repo": repo,
                        "docstring": method.get("docstring", ""),
                        "return_type": method.get("return_type", "unknown"),
                        "parameters": json.dumps(method.get("parameters", [])),
                        "calls": method.get("calls", []),
                        "line_number": method.get("line_number", 0),
                        "last_modified": file_data.get("last_modified", ""),
                    },
                )

                # connect method to its class
                session.run(
                    """
                    MATCH (c:Class {node_id: $class_node_id})
                    MATCH (m:Method {node_id: $method_node_id})
                    MERGE (c)-[:HAS_METHOD]->(m)
                    """,
                    {"class_node_id": class_node_id, "method_node_id": method_node_id},
                )


def create_import_relationships(driver: Driver, file_data: dict) -> None:
    """
    Creates IMPORTS relationships between File nodes.

    Only creates the relationship if both File nodes already exist in
    Neo4j — we never create dangling relationships to unknown files.

    For from-imports like `from utils import calculate_average`, the
    module name is "utils" — we match File nodes by name within the
    same repo to find the target.
    """
    with driver.session() as session:
        for imp in file_data.get("imports", []):
            module = imp.get("module", "")
            if not module:
                continue

            # match by module name — only links files within the same project
            session.run(
                """
                MATCH (from_file:File {path: $from_path})
                MATCH (to_file:File)
                WHERE to_file.name = $module_name OR to_file.name = $module_name + '.py'
                MERGE (from_file)-[:IMPORTS]->(to_file)
                """,
                {"from_path": file_data["path"], "module_name": module},
            )


def create_call_relationships(driver: Driver, file_data: dict, repo: str) -> None:
    """
    Creates CALLS relationships between Function/Method nodes.

    For each function and method, looks at its calls list and creates
    a CALLS relationship to any matching Function or Method node in the
    same repo. Built-in functions (sum, len, print) are skipped because
    they have no corresponding nodes in our graph — the MATCH simply
    finds nothing and no relationship is created.
    """
    with driver.session() as session:
        # build a flat list of all callables in this file with their node IDs
        all_callables = (
            [(func, build_node_id(repo, file_data["file"], func["name"]))
             for func in file_data.get("functions", [])]
            +
            [(method, build_node_id(repo, file_data["file"], cls["name"], method["name"]))
             for cls in file_data.get("classes", [])
             for method in cls.get("methods", [])]
        )

        for item, caller_node_id in all_callables:
            for called_name in item.get("calls", []):
                # only create CALLS if the callee exists in our graph
                # built-ins (sum, len, print) have no nodes so MATCH returns nothing
                session.run(
                    """
                    MATCH (caller {node_id: $caller_id})
                    MATCH (callee)
                    WHERE (callee:Function OR callee:Method)
                      AND callee.name = $callee_name
                      AND callee.repo = $repo
                    MERGE (caller)-[:CALLS]->(callee)
                    """,
                    {
                        "caller_id": caller_node_id,
                        "callee_name": called_name,
                        "repo": repo,
                    },
                )


def get_existing_node_ids_for_file(driver: Driver, file_name: str) -> set[str]:
    """
    Returns all node IDs currently stored in Neo4j for a given file.

    Queries for Function, Class, and Method nodes belonging to this file.
    Used to detect stale nodes that need to be deleted when a function
    or class is removed from the source code.
    """
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            WHERE (n:Function OR n:Class OR n:Method)
              AND n.file = $file_name
            RETURN n.node_id AS node_id
            """,
            {"file_name": file_name},
        )
        return {record["node_id"] for record in result}


def delete_stale_nodes(driver: Driver, stale_ids: set[str]) -> None:
    """
    Deletes nodes from Neo4j that no longer exist in the source code.

    Uses DETACH DELETE which removes the node AND all its relationships.
    This keeps the graph clean — no orphan relationships pointing to
    deleted functions or classes.
    """
    if not stale_ids:
        return

    with driver.session() as session:
        session.run(
            """
            MATCH (n)
            WHERE n.node_id IN $stale_ids
            DETACH DELETE n
            """,
            {"stale_ids": list(stale_ids)},
        )


def load_file_nodes(driver: Driver, file_data: dict, repo: str) -> dict:
    """
    Pass 1 — creates/updates all nodes for one file.

    Creates File, Function, Class, and Method nodes plus their
    CONTAINS and HAS_METHOD relationships. These are all local to
    one file so ordering does not matter.

    Does NOT create IMPORTS or CALLS — those are cross-file relationships
    that require all nodes to exist first. They are handled in Pass 2.

    Returns a summary dict with status and node counts.
    """
    file_path = file_data["path"]
    file_name = file_data["file"]
    timestamp = file_data.get("last_modified", "")

    # check if this file is already up to date in Neo4j
    if is_file_unchanged_in_neo4j(driver, file_path, timestamp):
        return {"file": file_name, "status": "skipped", "nodes": 0, "deleted": 0}

    # get existing node IDs before we start — needed for stale detection
    existing_ids = get_existing_node_ids_for_file(driver, file_name)

    # build new node IDs from current JSON
    new_ids = set()
    for func in file_data.get("functions", []):
        new_ids.add(build_node_id(repo, file_name, func["name"]))
    for cls in file_data.get("classes", []):
        new_ids.add(build_node_id(repo, file_name, cls["name"]))
        for method in cls.get("methods", []):
            new_ids.add(build_node_id(repo, file_name, cls["name"], method["name"]))

    # create/update all nodes
    create_file_node(driver, file_data, repo)
    create_function_nodes(driver, file_data, repo)
    create_class_nodes(driver, file_data, repo)

    # delete stale nodes
    stale_ids = existing_ids - new_ids
    delete_stale_nodes(driver, stale_ids)

    return {
        "file": file_name,
        "status": "loaded",
        "nodes": len(new_ids),
        "deleted": len(stale_ids),
    }


def load_file_relationships(driver: Driver, file_data: dict, repo: str) -> None:
    """
    Pass 2 — creates all cross-file relationships for one file.

    Creates IMPORTS and CALLS relationships. These are only run after
    all nodes for all files have been created in Pass 1 — this guarantees
    both the source and target nodes exist before linking them.

    Does NOT check timestamps — the caller (load_project) decides which
    files need relationship creation based on Pass 1 results.
    """
    create_import_relationships(driver, file_data)
    create_call_relationships(driver, file_data, repo)


def load_project(project_path: str) -> None:
    """
    Loads all JSON files for a project into Neo4j using a two-pass approach.

    Pass 1 — nodes: for every file, create File, Function, Class, Method nodes.
    Pass 2 — relationships: for every file, create IMPORTS and CALLS edges.

    The two-pass approach ensures all target nodes exist before any
    cross-file relationship is created — fixing the ordering bug where
    CALLS and IMPORTS would fail because the target file had not been
    processed yet.
    """
    project_output_dir = Path("output") / Path(project_path).relative_to("source")
    project_json_path = project_output_dir / "_project.json"

    if not project_json_path.exists():
        print(f"No _project.json found at {project_json_path}")
        print("Run the crawler first: crawlers/crawl_project.py")
        sys.exit(1)

    with open(project_json_path, "r", encoding="utf-8") as f:
        project_meta = json.load(f)

    repo = project_meta["repo"]
    driver = connect_to_neo4j()

    print(f"\nProject  : {project_path}")
    print(f"Repo     : {repo}")
    print(f"Files    : {len(project_meta['files'])}")
    print(f"{'='*60}")

    total_nodes = 0
    total_deleted = 0

    try:
        # load all file data into memory first
        all_file_data = []
        for file_output_path in project_meta["files"]:
            with open(file_output_path, "r", encoding="utf-8") as f:
                all_file_data.append(json.load(f))

        # pass 1 — create all nodes across all files
        # track which files were actually loaded (not skipped)
        # so Pass 2 knows which files need relationship creation
        print("\n  Pass 1 — creating nodes...")
        files_to_link = []
        for file_data in all_file_data:
            summary = load_file_nodes(driver, file_data, repo)
            if summary["status"] == "skipped":
                print(f"    skipped (unchanged): {summary['file']}")
            else:
                print(f"    loaded : {summary['file']} — {summary['nodes']} nodes, {summary['deleted']} deleted")
                total_nodes += summary["nodes"]
                total_deleted += summary["deleted"]
                files_to_link.append(file_data)

        # pass 2 — create cross-file relationships only for files that were loaded
        # unchanged files already have correct relationships from a previous run
        if files_to_link:
            print("\n  Pass 2 — creating relationships...")
            for file_data in files_to_link:
                load_file_relationships(driver, file_data, repo)
                print(f"    linked : {file_data['file']}")

    finally:
        # always close the driver — releases the connection pool
        driver.close()

    print(f"\nDone. Total nodes added/updated: {total_nodes} | Deleted: {total_deleted}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: PYTHONPATH=. uv run python3 neo4j_loader/load_project.py <project_path>")
        sys.exit(1)

    PROJECT_PATH = sys.argv[1]
    load_project(PROJECT_PATH)
