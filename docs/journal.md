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
Iteration 2 — LangChain Tools. Define tools with `@tool`, understand how LangChain auto-generates schemas, and how `project` is injected without the LLM seeing it.

---

## Iteration 3 — Single LangChain Agent ✅

### Step 5 — Built src/agent.py with manual agent loop using LangChain types

**What we did:**
Created `src/agent.py` with a working agent that uses `llm.bind_tools()` and a manual `while True` loop using LangChain message types (`SystemMessage`, `HumanMessage`, `ToolMessage`). Tested with the question "what does reserve_stock do?" — agent called `search_code`, got the result from ChromaDB, and produced a detailed grounded answer with the actual code snippet.

Also added `langchain>=0.3.0` to `pyproject.toml` — added only when needed, not upfront.

**Why we implemented the loop manually:**
`create_tool_calling_agent` and `AgentExecutor` could not be imported from LangChain 1.3.15. But this turned out to be better for learning — the manual loop makes every step visible, which is exactly what this capstone is for.

**What was learned:**

1. **The LLM cannot run tools — it only requests them.** When the LLM says "call search_code with query='def reserve_stock'", it produces a text description. Our code must actually find the tool, run it, and feed the result back. This is true in every agent framework — frameworks only differ in how much they hide this from you.

2. **The Act → Observe block** — this is the standard practice in every agentic system ever built:
   ```python
   tool_fn = tool_by_name[tool_name]       # find the function
   result  = tool_fn.invoke(tool_args)      # run it
   messages.append(ToolMessage(...))        # feed result back to LLM
   ```

3. **`project` is not involved in the loop at all** — it was already solved by `make_tools(project)` closure in Iteration 2. The tools returned already have `project` baked in.

4. **LangChain types vs raw dicts:**

   | CodeAtlas (raw) | LangChain (typed) |
   |---|---|
   | `{"role": "tool", "tool_call_id": ..., "content": ...}` | `ToolMessage(content=..., tool_call_id=...)` |
   | `tool_call.function.name` | `tool_call["name"]` |
   | `json.loads(tool_call.function.arguments)` | `tool_call["args"]` — already a dict |
   | `response.choices[0].message.content` | `response.content` |
   | `response.choices[0].message.tool_calls` | `response.tool_calls` |

5. **AgentExecutor / LangGraph / every framework** wraps exactly this same `while True` loop. They only differ in visibility. Writing it manually first means you can explain it in any interview, with any framework.

6. **bind_tools** — `llm.bind_tools(tools)` tells the LLM which tools are available. In CodeAtlas this was done by passing `tools=TOOLS` to every `client.chat.completions.create()` call. Here we bind once and reuse.

**Files created/changed:**
- `src/agent.py` — manual agent loop using LangChain message types
- `pyproject.toml` — added `langchain>=0.3.0`

**Test result:**
Question: "what does reserve_stock do?"
- Agent called `search_code` once
- Got ChromaDB results back
- Produced a detailed, grounded answer with the full method code

**Next:**
Iteration 4 — Planning + Structured State. Add a planner that converts a task into structured steps, and a state dict that tracks progress through the workflow.

---

## Iteration 2 — LangChain Tools ✅

### Step 4 — Built src/tools.py with @tool decorator and make_tools factory

**What we did:**
Created `src/tools.py` with all five tools using LangChain's `@tool` decorator. Removed the separate `tools/` folder — everything consolidated into `src/`. Solved the hardcoded project problem by introducing `make_tools(project)` — a factory function that creates tools bound to a specific project at runtime.

Also fixed `tools/code_search.py` and `tools/graph_tool.py` which were importing from `qa.ask` (which doesn't exist in this project) — moved those shared helpers into the tools file directly.

**Why:**
- `@tool` replaces the handwritten JSON schema TOOLS list from CodeAtlas
- `make_tools(project)` makes the tools flexible — project comes from the user's request, not hardcoded in the source
- Deleting `tools/` keeps the project simple — `src/` is the only place we build new code

**What was learned:**

1. `@tool` decorator — LangChain reads the function's type hints and docstring and auto-generates the JSON schema that the LLM uses to decide when and how to call the tool. No manual schema writing needed.

2. The LLM only sees parameters it needs to decide — `query`, `symbol`, `repo`, `file_path`. It never sees `project` because that is not an LLM decision.

3. **Closure pattern** — functions defined inside `make_tools(project)` are local to that call. Each call to `make_tools()` creates a fresh set of tool objects that remember the `project` from their creation scope. Two calls to `make_tools()` with different projects create completely independent sets of tools.

4. **Who calls make_tools?** — The agent entry point (`src/agent.py`, built in Iteration 3). The user provides project + question, agent.py calls `make_tools(project)`, creates the agent with those tools, and runs it.

5. `qa/ask.py` from CodeAtlas is **not needed** in this project — it was the old fixed RAG pipeline. We replaced it with an agent that decides which tools to call.

**CodeAtlas comparison:**

| CodeAtlas (manual) | LangChain (Iteration 2) |
|---|---|
| Handwritten TOOLS list (JSON dicts) | `@tool` decorator — schema auto-generated |
| Separate `execute_tool()` dispatcher | No dispatcher — LangChain handles routing |
| `project` injected in `execute_tool()` | `project` injected via `make_tools(project)` closure |
| Two things to maintain: function + schema | One thing: the function with a good docstring |

**Files created/changed:**
- `src/tools.py` — all five tools with `@tool`, `make_tools(project)` factory, helpers inlined
- `tools/` folder — deleted (consolidated into `src/tools.py`)
- `DEVELOPER.md` — updated project structure

**Key design decisions:**
- No hardcoded `PROJECT` — project always comes from the caller
- No separate `tools/` folder — keep it simple, everything in `src/`
- `qa/ask.py` not needed — that was the old fixed pipeline, not used in agent approach

**Next:**
Iteration 3 — Single LangChain Agent. Create `src/agent.py`, bind tools to the model with `llm.bind_tools()`, implement the Reason → Tool → Observe → Reason loop, and compare to the manual `while True` loop from CodeAtlas.

---

## Iteration 1 — LangChain Model Abstraction ✅

### Step 3 — Understood the concept and built src/llm.py

**What we did:**
Added `langchain-openai` to `pyproject.toml`, created `src/llm.py`, and ran a simple LLM call using LangChain's `ChatOpenAI`, `SystemMessage`, and `HumanMessage`. It worked on the first run.

**Why:**
Before writing any agent, we needed to understand how LangChain wraps LLM providers. Every future iteration builds on this — tools, agents, memory, and orchestration all go through this same model interface.

**What was learned:**

1. `ChatOpenAI` is a wrapper around the OpenAI SDK — the actual HTTP call to OpenAI is unchanged. LangChain just standardises the interface.

2. Raw dicts are replaced with message objects:
   - `{"role": "system", "content": "..."}` → `SystemMessage("...")`
   - `{"role": "user", "content": "..."}` → `HumanMessage("...")`
   - `{"role": "assistant", "content": "..."}` → `AIMessage("...")`

3. Response extraction is cleaner:
   - CodeAtlas: `response.choices[0].message.content`
   - LangChain: `response.content`

4. Provider swap = change one line. To switch from OpenAI to Gemini tomorrow:
   - Install `langchain-google-genai`
   - Change `ChatOpenAI` to `ChatGoogleGenerativeAI`
   - Everything else — messages, invoke, response.content — stays identical

5. In CodeAtlas, switching providers meant rewriting every file that touched the LLM. Here it means changing one line in one place.

**How it compares to CodeAtlas:**

| CodeAtlas (manual) | LangChain (Iteration 1) |
|---|---|
| `from openai import OpenAI` | `from langchain_openai import ChatOpenAI` |
| `client = OpenAI(api_key=...)` | `llm = ChatOpenAI(model=..., temperature=0)` |
| `{"role": "user", "content": "..."}` | `HumanMessage("...")` |
| `response.choices[0].message.content` | `response.content` |
| Tied to OpenAI | Swap provider by changing one class |

**Files created:**
- `src/llm.py` — simple LLM call using ChatOpenAI, SystemMessage, HumanMessage

**Dependency added:**
- `langchain-openai>=0.2.0` — added to `pyproject.toml` with a comment explaining why

**Command to run:**
```bash
PYTHONPATH=. uv run python3 src/llm.py
```

**Next:**
Iteration 2 — LangChain Tools. Learn how to define tools using the `@tool` decorator and bind them to the model so the LLM can decide when to call them.

---
