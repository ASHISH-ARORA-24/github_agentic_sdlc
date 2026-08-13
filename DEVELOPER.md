# Developer Guide — GitHub Agentic SDLC

This file contains everything needed to set up and run this project from scratch.
Run these commands in order when setting up for the first time, or after pulling fresh changes.

---

## Prerequisites

- Python 3.13+
- `uv` package manager
- Neo4j Community Edition running locally (default port 7687)
- A `.env` file in the project root (copy from `.env.example` and fill in your values)

---

## Environment Variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Required variables in `.env`:

```
OPENAI_API_KEY=...        # Added in Iteration 1 when we introduce LangChain
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

---

## Step 1 — Install Dependencies

```bash
uv sync
```

**Why:** Downloads and installs all packages listed in `pyproject.toml` into a local virtual environment. Run this once after cloning, and again whenever `pyproject.toml` changes.

---

## Step 2 — Crawl the Source Repositories

The crawler reads Python source files and extracts structured information (functions, classes, imports, calls) using Python's AST module. It saves one JSON file per Python file under `output/`.

```bash
# Ecommerce — Inventory Service
PYTHONPATH=. uv run python3 crawlers/crawl_project.py source/codeatlas/ecommerce/inventory_service

# Ecommerce — Order Service
PYTHONPATH=. uv run python3 crawlers/crawl_project.py source/codeatlas/ecommerce/order_service

# Sample — Calculator
PYTHONPATH=. uv run python3 crawlers/crawl_project.py source/codeatlas/sample/calculator

# Sample — Grade Calculator
PYTHONPATH=. uv run python3 crawlers/crawl_project.py source/codeatlas/sample/grade_calculator
```

**Why:** The crawler is the first step in the indexing pipeline. It converts raw Python code into structured JSON that the chunker and Neo4j loader can read. The crawler only needs to re-run when source files change — it skips unchanged files using timestamps.

**Output:** JSON files under `output/codeatlas/...` mirroring the `source/` folder structure.

---

## Step 3 — Build ChromaDB (Vector Embeddings)

The chunker reads the JSON files produced by the crawler, converts each function/class/method into a text chunk, and stores it as a vector embedding in ChromaDB.

```bash
# Ecommerce — Inventory Service
PYTHONPATH=. uv run python3 chunkers/python_chunker.py source/codeatlas/ecommerce/inventory_service

# Ecommerce — Order Service
PYTHONPATH=. uv run python3 chunkers/python_chunker.py source/codeatlas/ecommerce/order_service

# Sample — Calculator
PYTHONPATH=. uv run python3 chunkers/python_chunker.py source/codeatlas/sample/calculator

# Sample — Grade Calculator
PYTHONPATH=. uv run python3 chunkers/python_chunker.py source/codeatlas/sample/grade_calculator
```

**Why:** ChromaDB stores the meaning of each code chunk as a vector. When an agent searches for "stock reservation logic", ChromaDB finds semantically similar chunks — even if the exact words don't match. The embedding model used is `all-MiniLM-L6-v2` (local, no API key needed).

**Output:** `chroma_db/` folder (gitignored — generated locally, never committed).

---

## Step 4 — Build Neo4j Knowledge Graph

The Neo4j loader reads the same JSON files and builds a knowledge graph of code relationships — which file imports which, which function calls which, which method belongs to which class.

```bash
# Ecommerce — Inventory Service
PYTHONPATH=. uv run python3 neo4j_loader/load_project.py source/codeatlas/ecommerce/inventory_service

# Ecommerce — Order Service
PYTHONPATH=. uv run python3 neo4j_loader/load_project.py source/codeatlas/ecommerce/order_service

# Sample — Calculator
PYTHONPATH=. uv run python3 neo4j_loader/load_project.py source/codeatlas/sample/calculator

# Sample — Grade Calculator
PYTHONPATH=. uv run python3 neo4j_loader/load_project.py source/codeatlas/sample/grade_calculator
```

**Why:** Neo4j handles structural questions that vector search cannot answer — "what functions call reserve_stock?", "what does this file import?", "what is the impact if I change this class?". ChromaDB finds what is semantically similar; Neo4j finds what is structurally connected. Together they give the agent both semantic and structural understanding of the codebase.

**Requires:** Neo4j must be running before these commands are executed.

---

## Full Reset (start fresh)

To wipe ChromaDB and Neo4j and re-index everything from scratch:

```bash
# Delete ChromaDB
rm -rf chroma_db/

# Delete crawled output
rm -rf output/

# Clear Neo4j — run this in Neo4j Browser or cypher-shell
# MATCH (n) DETACH DELETE n

# Then re-run Steps 2, 3, and 4 above
```

---

## Project Structure

```
github_agentic_sdlc/
├── source/           ← sample repos used for testing
│   └── codeatlas/
│       ├── ecommerce/
│       │   ├── inventory_service/
│       │   └── order_service/
│       └── sample/
│           ├── calculator/
│           └── grade_calculator/
├── crawlers/         ← Step 2: AST extraction → JSON
├── chunkers/         ← Step 3: JSON → ChromaDB embeddings
├── neo4j_loader/     ← Step 4: JSON → Neo4j knowledge graph
├── tools/            ← reusable wrappers: code_search, graph_tool, file_tool, write_file, run_tests
├── output/           ← generated (gitignored)
├── chroma_db/        ← generated (gitignored)
├── docs/
│   ├── notes/        ← reference notes about CodeAtlas and the capstone plan
│   ├── status_update.md  ← iteration-level progress tracker
│   └── journal.md    ← detailed step-by-step learning log
├── .env              ← your secrets (gitignored — never commit)
├── .env.example      ← safe template (committed)
├── CLAUDE.md         ← instructions for Claude Code
├── DEVELOPER.md      ← this file
└── pyproject.toml    ← project dependencies
```
