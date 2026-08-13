# Python Chunker for CodeAtlas.
# Reads the JSON files produced by crawlers/crawl_project.py and converts
# them into text chunks stored in ChromaDB as vector embeddings.
#
# Supports incremental updates — if a file's timestamp has not changed
# since the last run, its chunks are skipped. If a function was deleted,
# its stale chunk is removed from ChromaDB automatically.
#
# ChromaDB handles the embedding conversion internally using Sentence
# Transformers — we just pass text and it stores the vector.
#
# Usage:
#   PYTHONPATH=. uv run python3 chunkers/python_chunker.py source/codeatlas/sample/grade_calculator

import json
import sys
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

# Maximum number of tokens allowed per chunk.
# Sentence Transformers has a 512 token limit — we use 400 to be safe
# and leave room for the metadata context we add to the text.
# Functions exceeding this are split by lines into multiple chunks.
MAX_CHUNK_TOKENS = 400


def count_tokens(text: str) -> int:
    """
    Estimates the number of tokens in a text string.

    Uses whitespace splitting as a simple approximation — one word ≈ one token.
    This is not perfectly accurate but good enough for our chunk size check.
    A proper tokenizer (like tiktoken) can be used in Iteration 2 for precision.
    """
    return len(text.split())


def split_text_by_lines(text: str, max_tokens: int) -> list[str]:
    """
    Splits a long text into multiple chunks by line boundaries.

    Each chunk contains as many lines as possible without exceeding max_tokens.
    This is Option A splitting — simple line-based. Option B (AST-aware logical
    block splitting) is planned for Iteration 2. See docs/DECISIONS.md.

    Returns a list of text strings, one per chunk.
    """
    lines = text.split("\n")
    chunks = []
    current_chunk_lines = []
    current_token_count = 0

    for line in lines:
        line_tokens = count_tokens(line)

        if current_token_count + line_tokens > max_tokens and current_chunk_lines:
            # current chunk is full — save it and start a new one
            chunks.append("\n".join(current_chunk_lines))
            current_chunk_lines = [line]
            current_token_count = line_tokens
        else:
            current_chunk_lines.append(line)
            current_token_count += line_tokens

    # add the last remaining chunk
    if current_chunk_lines:
        chunks.append("\n".join(current_chunk_lines))

    return chunks


def build_chunk_id(repo: str, file_name: str, *parts: str) -> str:
    """
    Builds a unique, stable ID for a chunk in ChromaDB.

    Uses :: as separator between parts. The ID encodes exactly where
    the chunk came from so ChromaDB can update it in place on re-runs
    instead of creating duplicates.

    Examples:
        grade_calculator::utils.py::calculate_average
        grade_calculator::utils.py::StudentProfile
        grade_calculator::utils.py::StudentProfile::get_summary
        grade_calculator::utils.py::calculate_average::1_of_3
    """
    return "::".join([repo, file_name] + list(parts))


def build_function_text(func: dict, file_name: str) -> str:
    """
    Builds the rich text string for a standalone function chunk.

    Combines all available information — name, file, parameters, return type,
    calls, docstring, and source code — into one text block. The richer the
    text, the better the embedding captures the function's meaning.
    """
    params = ", ".join(
        f"{p['name']} ({p['type']})" for p in func.get("parameters", [])
    )
    calls = ", ".join(func.get("calls", [])) or "none"

    return f"""Function: {func['name']}
File: {file_name}
Parameters: {params or 'none'}
Returns: {func.get('return_type', 'unknown')}
Calls: {calls}
Docstring: {func.get('docstring', '')}
Code:
{func.get('source_code', '')}"""


def build_method_text(method: dict, class_name: str, file_name: str) -> str:
    """
    Builds the rich text string for a class method chunk.

    Same as function text but includes the class name for context.
    This is important — without the class name, ChromaDB cannot
    distinguish between two methods with the same name in different classes.
    """
    params = ", ".join(
        f"{p['name']} ({p['type']})" for p in method.get("parameters", [])
    )
    calls = ", ".join(method.get("calls", [])) or "none"

    return f"""Method: {method['name']}
Class: {class_name}
File: {file_name}
Parameters: {params or 'none'}
Returns: {method.get('return_type', 'unknown')}
Calls: {calls}
Docstring: {method.get('docstring', '')}
Code:
{method.get('source_code', '')}"""


def build_class_text(cls: dict, file_name: str) -> str:
    """
    Builds the rich text string for a class chunk.

    Captures the class-level meaning — name, docstring, and list of methods.
    Each method also gets its own separate chunk — this chunk answers
    "what is StudentProfile?" while method chunks answer "how does get_summary work?"
    """
    method_names = ", ".join(m['name'] for m in cls.get("methods", []))

    return f"""Class: {cls['name']}
File: {file_name}
Methods: {method_names or 'none'}
Docstring: {cls.get('docstring', '')}
Code:
{cls.get('source_code', '')}"""


def add_chunks_to_chromadb(
    collection: chromadb.Collection,
    chunk_id: str,
    text: str,
    metadata: dict,
) -> None:
    """
    Adds one or more chunks to ChromaDB for a given piece of code.

    If the text fits within MAX_CHUNK_TOKENS, adds a single chunk.
    If the text is too long, splits it into multiple chunks and adds
    each with a sequence suffix in the ID (e.g. ::1_of_3, ::2_of_3).

    ChromaDB automatically converts the text to a vector embedding
    using Sentence Transformers — we just pass the text.
    """
    if count_tokens(text) <= MAX_CHUNK_TOKENS:
        # fits in one chunk — add directly
        collection.upsert(
            documents=[text],
            metadatas=[metadata],
            ids=[chunk_id],
        )
    else:
        # too long — split into multiple chunks
        parts = split_text_by_lines(text, MAX_CHUNK_TOKENS)
        total = len(parts)

        for index, part in enumerate(parts, start=1):
            part_metadata = {**metadata, "chunk": index, "total_chunks": total}
            part_id = f"{chunk_id}::{index}_of_{total}"
            collection.upsert(
                documents=[part],
                metadatas=[part_metadata],
                ids=[part_id],
            )


def get_existing_chunk_ids(collection: chromadb.Collection, file_key: str) -> set[str]:
    """
    Returns all chunk IDs currently stored in ChromaDB for a given file.

    Queries ChromaDB by the file metadata field to find all chunks
    belonging to this file. Used to detect stale chunks that need deletion.

    file_key is the unique identifier for the file:
    e.g. "grade_calculator::utils.py"
    """
    results = collection.get(where={"file_key": file_key})
    return set(results["ids"])


def is_file_unchanged_in_chromadb(
    collection: chromadb.Collection,
    file_key: str,
    timestamp: str,
) -> bool:
    """
    Checks if a file's chunks in ChromaDB are already up to date.

    Queries ChromaDB for any chunk belonging to this file with the
    same timestamp. If one exists, the file has not changed since the
    last chunking run — skip it.
    """
    results = collection.get(
        where={"$and": [{"file_key": {"$eq": file_key}}, {"last_modified": {"$eq": timestamp}}]}
    )
    return len(results["ids"]) > 0


def chunk_file(collection: chromadb.Collection, file_data: dict, repo: str) -> dict:
    """
    Processes one JSON file and upserts all its chunks into ChromaDB.

    Returns a summary dict with counts of chunks added, updated, and deleted.

    Steps:
    1. Check if file timestamp matches ChromaDB — skip if unchanged
    2. Get existing chunk IDs for this file from ChromaDB
    3. Build and upsert new chunks (functions, classes, methods)
    4. Delete any stale chunk IDs that no longer exist
    """
    file_name = file_data["file"]
    file_path = file_data.get("path", "")
    timestamp = file_data.get("last_modified", "")

    # Extract the relative path from "source/" to handle files with the same name
    # in different folders (e.g. inventory_service/main.py vs order_service/main.py).
    # This makes the file_key globally unique across the project.
    if file_path and file_path.startswith("source/"):
        relative_path = file_path[7:]  # strip "source/" prefix
    else:
        relative_path = file_name

    file_key = f"{repo}::{relative_path}"

    # check if this file's chunks are already up to date
    if is_file_unchanged_in_chromadb(collection, file_key, timestamp):
        return {"file": file_name, "status": "skipped", "chunks": 0, "deleted": 0}

    # get existing chunk IDs before we start — needed for stale detection
    existing_ids = get_existing_chunk_ids(collection, file_key)
    new_ids = set()

    # base metadata shared across all chunks from this file
    base_metadata = {
        "file": file_name,
        "file_key": file_key,
        "project": repo,
        "last_modified": timestamp,
    }

    # --- chunk standalone functions ---
    for func in file_data.get("functions", []):
        chunk_id = build_chunk_id(repo, relative_path, func["name"])
        text = build_function_text(func, file_name)
        metadata = {**base_metadata, "type": "function", "name": func["name"]}
        add_chunks_to_chromadb(collection, chunk_id, text, metadata)
        new_ids.add(chunk_id)

    # --- chunk classes and their methods ---
    for cls in file_data.get("classes", []):
        # one chunk for the class itself
        class_chunk_id = build_chunk_id(repo, relative_path, cls["name"])
        class_text = build_class_text(cls, file_name)
        class_metadata = {**base_metadata, "type": "class", "name": cls["name"]}
        add_chunks_to_chromadb(collection, class_chunk_id, class_text, class_metadata)
        new_ids.add(class_chunk_id)

        # one chunk per method
        for method in cls.get("methods", []):
            method_chunk_id = build_chunk_id(repo, relative_path, cls["name"], method["name"])
            method_text = build_method_text(method, cls["name"], file_name)
            method_metadata = {
                **base_metadata,
                "type": "method",
                "name": method["name"],
                "class": cls["name"],
            }
            add_chunks_to_chromadb(collection, method_chunk_id, method_text, method_metadata)
            new_ids.add(method_chunk_id)

    # --- delete stale chunks ---
    stale_ids = existing_ids - new_ids
    if stale_ids:
        collection.delete(ids=list(stale_ids))

    return {
        "file": file_name,
        "status": "updated",
        "chunks": len(new_ids),
        "deleted": len(stale_ids),
    }


def chunk_project(project_path: str) -> None:
    """
    Chunks all JSON files for a project and stores them in ChromaDB.

    Reads _project.json to get the repo name and list of JSON files,
    then processes each file incrementally — skipping unchanged files
    and removing stale chunks for deleted functions or classes.
    """
    # build the output path for this project
    project_output_dir = Path("output") / Path(project_path).relative_to("source")
    project_json_path = project_output_dir / "_project.json"

    if not project_json_path.exists():
        print(f"No _project.json found at {project_json_path}")
        print("Run the crawler first: crawlers/crawl_project.py")
        sys.exit(1)

    with open(project_json_path, "r", encoding="utf-8") as f:
        project_meta = json.load(f)

    repo = project_meta["repo"]

    # connect to ChromaDB — creates chroma_db/ folder if it does not exist
    client = chromadb.PersistentClient(path="chroma_db/")

    # explicitly declare the embedding model so it never changes accidentally.
    # all-MiniLM-L6-v2 is a general-purpose text model — fast and lightweight.
    # the same model must be used here and at query time, or vectors will be incompatible.
    # see docs/DECISIONS.md for why this model was chosen and when to upgrade.
    embedding_function = ONNXMiniLM_L6_V2()

    # get or create a collection for this project
    # a collection is like a table in a relational database
    collection = client.get_or_create_collection(
        name=repo,
        embedding_function=embedding_function,
    )

    print(f"\nProject  : {project_path}")
    print(f"Repo     : {repo}")
    print(f"Files    : {len(project_meta['files'])}")
    print(f"{'='*60}")

    total_chunks = 0
    total_deleted = 0

    for file_output_path in project_meta["files"]:
        with open(file_output_path, "r", encoding="utf-8") as f:
            file_data = json.load(f)

        summary = chunk_file(collection, file_data, repo)

        if summary["status"] == "skipped":
            print(f"  skipped (unchanged): {summary['file']}")
        else:
            print(f"  chunked: {summary['file']} — {summary['chunks']} chunks, {summary['deleted']} deleted")
            total_chunks += summary["chunks"]
            total_deleted += summary["deleted"]

    print(f"\nDone. Total chunks added/updated: {total_chunks} | Deleted: {total_deleted}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: PYTHONPATH=. uv run python3 chunkers/python_chunker.py <project_path>")
        sys.exit(1)

    PROJECT_PATH = sys.argv[1]
    chunk_project(PROJECT_PATH)
