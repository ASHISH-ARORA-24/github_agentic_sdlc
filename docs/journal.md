# Capstone Learning Journal — GitHub Agentic SDLC

This is the detailed step-by-step record of everything done in this project.

Each entry is added after completing a step, only when the user confirms.

Format per entry:
- **What we did** — the action taken
- **Why** — the reasoning or decision behind it
- **What was learned** — concept, insight, or comparison to CodeAtlas
- **Files / Commands** — anything created or run
- **Next** — what comes after this step

---

## Session 1 — 2026-08-13

### Step 1 — Project setup and notes

**What we did:**
Read the entire CodeAtlas project (`/home/ashish/project/CodeAtlas`) and the capstone README (`/home/ashish/project/github_agentic_sdlc/README.md`). Created reference notes and set up the project scaffolding for the capstone.

**Why:**
Before writing any code, we needed a complete picture of what was already built in CodeAtlas and what the capstone needs to achieve. The notes ensure that future conversations start with full context without re-reading the entire CodeAtlas project.

**What was learned:**
- CodeAtlas has 9 iterations fully implemented (RAG pipeline, agent loop, planning, code-changing tools, memory, guardrails, evaluation, observability, multi-agent orchestrator)
- The one big gap in CodeAtlas is the GitHub SDLC tools (create_issue, create_branch, commit, push, PR, merge, close_issue)
- The capstone goal is to rebuild these concepts using LangChain/LangGraph, comparing each abstraction to what CodeAtlas did manually
- The capstone has 20 planned iterations

**Files created:**
- `CLAUDE.md` — instructions for Claude at the start of every conversation
- `docs/notes/codeatlas_overview.md` — CodeAtlas overview, tech stack, repo structure
- `docs/notes/codeatlas_what_is_built.md` — every iteration with files, commands, gaps
- `docs/notes/codeatlas_key_concepts.md` — embeddings, RAG, agent loop, guardrails, multi-agent, evaluation
- `docs/notes/codeatlas_file_map.md` — quick file lookup for CodeAtlas
- `docs/notes/codeatlas_capstone_plan.md` — 20 iterations, LangChain comparison table, capstone plan
- `docs/status_update.md` — high-level iteration tracker
- `docs/journal.md` — this file

**Next:**
Start Iteration 1 — LangChain Model Abstraction.

---

### Step 2 — Copied foundation from CodeAtlas and built ChromaDB + Neo4j

**What we did:**
Copied the data infrastructure from CodeAtlas into the new capstone project. Created `DEVELOPER.md` with all setup commands and explanations. Built a fresh ChromaDB and Neo4j from scratch by running the crawl → chunk → load pipeline across all four sample repos.

**Why:**
The crawlers, chunkers, neo4j_loader, and sample source repos are pure data infrastructure — no LLM, no OpenAI, no LangChain involved. There is no reason to rebuild them. They are the foundation every future agent will depend on. Copying them lets us focus the capstone on what is actually new: the LangChain/LangGraph agent layer.

We also made a deliberate decision: **add dependencies only when we need them**. LangChain is not in `pyproject.toml` yet. It will be added in Iteration 1 when we actually use it — so we understand why it is being added.

**What was learned / decided:**
- What to copy vs what to rebuild — copy the data layer, rebuild the agent layer
- `pyproject.toml` starts with only `chromadb`, `neo4j`, `python-dotenv` — nothing more
- `.env` and `chroma_db/` are gitignored — secrets and generated files never go into git
- `output/` is also gitignored — crawled JSON is generated locally, not committed
- The pipeline always runs in order: crawl → chunk → load Neo4j. Each step depends on the previous one.

**Files created:**
- `DEVELOPER.md` — full setup guide with every command explained
- `crawlers/`, `chunkers/`, `neo4j_loader/`, `tools/` — copied from CodeAtlas
- `source/codeatlas/` — sample repos (ecommerce + calculator) copied from CodeAtlas
- `.env.example` — safe template committed to git
- `.gitignore` — updated to ignore `.env`, `chroma_db/`, `output/`

**Commands run:**
```bash
# Crawl (AST extraction → JSON)
PYTHONPATH=. uv run python3 crawlers/crawl_project.py source/codeatlas/ecommerce/inventory_service
PYTHONPATH=. uv run python3 crawlers/crawl_project.py source/codeatlas/ecommerce/order_service
PYTHONPATH=. uv run python3 crawlers/crawl_project.py source/codeatlas/sample/calculator
PYTHONPATH=. uv run python3 crawlers/crawl_project.py source/codeatlas/sample/grade_calculator

# Chunk (JSON → ChromaDB embeddings)
PYTHONPATH=. uv run python3 chunkers/python_chunker.py source/codeatlas/ecommerce/inventory_service
PYTHONPATH=. uv run python3 chunkers/python_chunker.py source/codeatlas/ecommerce/order_service
PYTHONPATH=. uv run python3 chunkers/python_chunker.py source/codeatlas/sample/calculator
PYTHONPATH=. uv run python3 chunkers/python_chunker.py source/codeatlas/sample/grade_calculator

# Load Neo4j (JSON → knowledge graph)
PYTHONPATH=. uv run python3 neo4j_loader/load_project.py source/codeatlas/ecommerce/inventory_service
PYTHONPATH=. uv run python3 neo4j_loader/load_project.py source/codeatlas/ecommerce/order_service
PYTHONPATH=. uv run python3 neo4j_loader/load_project.py source/codeatlas/sample/calculator
PYTHONPATH=. uv run python3 neo4j_loader/load_project.py source/codeatlas/sample/grade_calculator
```

**Results:**
- Crawl: 12 JSON files generated across 4 repos
- ChromaDB: 55 chunks embedded and stored
- Neo4j: 55 nodes created with full relationship graph

**How it compares to CodeAtlas:**
Identical — same scripts, same pipeline, same output. Nothing changed here. This is intentional. The capstone adds the LangChain/LangGraph layer on top of this foundation without touching the data pipeline.

**Next:**
Iteration 1 — LangChain Model Abstraction. Add `langchain` and `langchain-openai` to `pyproject.toml`, understand what `ChatOpenAI` replaces, and send our first message to an LLM the LangChain way.

---
