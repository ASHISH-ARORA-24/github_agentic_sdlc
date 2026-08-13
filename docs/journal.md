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
