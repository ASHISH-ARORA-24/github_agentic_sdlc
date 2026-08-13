# CodeAtlas — Overview Notes

**Location:** `/home/ashish/project/CodeAtlas/`
**Windows path:** `\\wsl.localhost\Ubuntu-24.04\home\ashish\project\CodeAtlas`

## What it is

An AI-powered codebase Q&A service. You give it a GitHub repo URL, it indexes the code, and you ask questions in plain English. It answers using the actual code as context — not hallucination.

**Master goal (from `plan.md`):**

```
"Implement feature X"
  → AI understands existing code
  → Plans the change
  → Creates GitHub Issue
  → Creates Branch
  → Changes Code
  → Runs Tests
  → Reviews Changes
  → Creates PR
  → Human Approval → Merge → Close Issue
```

This is the Agentic SDLC loop. The full loop is NOT yet implemented in CodeAtlas. See `codeatlas_what_is_built.md`.

## Tech Stack (LOCKED — do not change without discussion)

| Purpose | Tool | Why |
|---|---|---|
| Vector DB | ChromaDB | Free, local, simple API |
| Graph DB | Neo4j Community | Free, local, industry standard |
| Embeddings | `all-MiniLM-L6-v2` (Sentence Transformers) | Local, free, no API key, 80MB |
| LLM | OpenAI GPT-4o-mini | Switched from Gemini due to quota issues |

**Embedding model must be the same at index time AND query time.** It is explicitly declared in `chunkers/python_chunker.py` — changing it silently would corrupt all stored vectors.

## Repo Structure

```
source/                        ← where actual repos live
  codeatlas/
    sample/
      calculator/
      grade_calculator/
    ecommerce/
      inventory_service/
      order_service/

output/                        ← mirrors source/, one JSON per Python file
chroma_db/                     ← gitignored, ChromaDB files

crawlers/                      ← AST extraction
chunkers/                      ← ChromaDB embedding
neo4j_loader/                  ← Neo4j knowledge graph
qa/                            ← original fixed RAG pipeline
agents/                        ← AI coding agent + planning
tools/                         ← reusable tool functions
multi_agent_demo/              ← multi-agent orchestrator
guardrails/                    ← tool policy, resource policy, HITL
memory/                        ← long-term JSON memory store
evaluation/                    ← deterministic + LLM judge eval
observability/                 ← trace reporter

docs/
  PROGRESS.md                  ← what has been built (OUTDATED after chunk 9)
  DECISIONS.md                 ← architecture decision records
  CODING_STANDARDS.md          ← standards for indexed repos
  learning/
    iteration0.md → iteration14.md   ← the learning plan
```

**Source hierarchy rule:** `source/<owner>/<project>/<repo>/`
This maps directly to Neo4j: `Owner → Project → Repo → File → Function/Class`

## Key Docs to Read in CodeAtlas

- `README.md` — what the project is, how it works
- `plan.md` — the master Agentic SDLC plan (frozen reference)
- `docs/PROGRESS.md` — chunk-by-chunk build log (NOTE: outdated after chunk 9)
- `docs/DECISIONS.md` — every significant tech decision with reasons
- `CLAUDE.md` — teaching philosophy, tech stack rules, commit rules
- `docs/learning/iteration*.md` — 15 iteration plans (0–14)
