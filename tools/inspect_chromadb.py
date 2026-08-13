# ChromaDB Inspector for CodeAtlas.
# A debugging tool that lets you see exactly what is stored in ChromaDB —
# which collections exist, how many chunks are in each, and the full
# content of every chunk including its text and metadata.
#
# Usage:
#   # list all collections (repos indexed so far)
#   PYTHONPATH=. uv run python3 tools/inspect_chromadb.py
#
#   # inspect all chunks in a specific collection (repo)
#   PYTHONPATH=. uv run python3 tools/inspect_chromadb.py grade_calculator
#
#   # search for chunks matching a query
#   PYTHONPATH=. uv run python3 tools/inspect_chromadb.py grade_calculator "calculate average"

import sys

import chromadb
from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2


# number of results to return when searching
TOP_K_RESULTS = 3


def get_client() -> chromadb.PersistentClient:
    """
    Connects to the local ChromaDB instance.

    Reads from the chroma_db/ folder in the project root.
    If the folder does not exist, ChromaDB will report no collections.
    """
    return chromadb.PersistentClient(path="chroma_db/")


def list_collections(client: chromadb.PersistentClient) -> None:
    """
    Lists all collections (repos) currently stored in ChromaDB.

    Each collection corresponds to one indexed repo. Shows the
    collection name and total number of chunks stored.
    """
    collections = client.list_collections()

    if not collections:
        print("\nNo collections found in ChromaDB.")
        print("Run the chunker first: chunkers/python_chunker.py")
        return

    print(f"\n{'='*60}")
    print(f"ChromaDB Collections ({len(collections)} repos indexed)")
    print(f"{'='*60}")

    for col in collections:
        collection = client.get_collection(
            name=col.name,
            embedding_function=ONNXMiniLM_L6_V2(),
        )
        count = collection.count()
        print(f"\n  Repo    : {col.name}")
        print(f"  Chunks  : {count}")


def inspect_collection(client: chromadb.PersistentClient, repo: str) -> None:
    """
    Prints all chunks stored in a collection in a readable format.

    Shows the chunk ID, metadata, and the full text of each chunk.
    Groups chunks by file for easier reading.
    """
    try:
        collection = client.get_collection(
            name=repo,
            embedding_function=ONNXMiniLM_L6_V2(),
        )
    except Exception:
        print(f"\nCollection '{repo}' not found.")
        print("Available collections:")
        for col in client.list_collections():
            print(f"  - {col.name}")
        return

    results = collection.get()
    ids = results["ids"]
    documents = results["documents"]
    metadatas = results["metadatas"]

    print(f"\n{'='*60}")
    print(f"Collection : {repo}")
    print(f"Chunks     : {len(ids)}")
    print(f"{'='*60}")

    # group chunks by file for readable output
    by_file: dict[str, list] = {}
    for i, chunk_id in enumerate(ids):
        file_name = metadatas[i].get("file", "unknown")
        if file_name not in by_file:
            by_file[file_name] = []
        by_file[file_name].append((chunk_id, documents[i], metadatas[i]))

    for file_name, chunks in sorted(by_file.items()):
        print(f"\n--- {file_name} ({len(chunks)} chunks) ---")
        for chunk_id, text, metadata in chunks:
            print(f"\n  ID       : {chunk_id}")
            print(f"  Type     : {metadata.get('type', 'unknown')}")
            print(f"  Name     : {metadata.get('name', 'unknown')}")
            if metadata.get("class"):
                print(f"  Class    : {metadata.get('class')}")
            print(f"  Modified : {metadata.get('last_modified', 'unknown')}")
            print(f"  Text     :")
            # indent each line of the text for readability
            for line in text.split("\n"):
                print(f"    {line}")


def search_collection(
    client: chromadb.PersistentClient,
    repo: str,
    query: str,
) -> None:
    """
    Searches a collection for chunks semantically similar to a query.

    This is exactly what CodeAtlas will do when a user asks a question —
    convert the query to a vector and find the closest matching chunks.
    Useful for verifying that the right chunks are being retrieved.
    """
    try:
        collection = client.get_collection(
            name=repo,
            embedding_function=ONNXMiniLM_L6_V2(),
        )
    except Exception:
        print(f"\nCollection '{repo}' not found.")
        return

    results = collection.query(
        query_texts=[query],
        n_results=min(TOP_K_RESULTS, collection.count()),
    )

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    print(f"\n{'='*60}")
    print(f"Search Query : {query}")
    print(f"Collection   : {repo}")
    print(f"Top {TOP_K_RESULTS} Results  :")
    print(f"{'='*60}")

    for i, chunk_id in enumerate(ids):
        # distance is how far apart the vectors are — lower is more similar
        similarity = round(1 - distances[i], 4)
        print(f"\nRank     : {i + 1}")
        print(f"ID       : {chunk_id}")
        print(f"Type     : {metadatas[i].get('type', 'unknown')}")
        print(f"Name     : {metadatas[i].get('name', 'unknown')}")
        print(f"File     : {metadatas[i].get('file', 'unknown')}")
        print(f"Similarity: {similarity}")
        print(f"Text preview:")
        # show first 200 characters of the chunk text
        preview = documents[i][:200].replace("\n", " ")
        print(f"  {preview}...")


if __name__ == "__main__":
    client = get_client()

    if len(sys.argv) == 1:
        # no arguments — list all collections
        list_collections(client)

    elif len(sys.argv) == 2:
        # one argument — inspect a specific collection
        list_collections(client)
        inspect_collection(client, sys.argv[1])

    elif len(sys.argv) == 3:
        # two arguments — search a collection with a query
        search_collection(client, sys.argv[1], sys.argv[2])

    else:
        print("Usage:")
        print("  PYTHONPATH=. uv run python3 tools/inspect_chromadb.py")
        print("  PYTHONPATH=. uv run python3 tools/inspect_chromadb.py <repo>")
        print("  PYTHONPATH=. uv run python3 tools/inspect_chromadb.py <repo> <query>")
