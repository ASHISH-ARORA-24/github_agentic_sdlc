# CodeAtlas — What Has Been Built

**IMPORTANT:** `docs/PROGRESS.md` in CodeAtlas shows "Iteration 2 — State + Planning: Not started" — this is WRONG/OUTDATED. The code for iterations 2–9 is fully implemented. PROGRESS.md was not kept up to date after the early chunks.

## Iteration 0 — RAG Pipeline ✅

The original end-to-end flow. No agents yet.

```
Repo (source/)
  → Python AST (crawlers/python_ast.py)
  → JSON (output/)
  → Embeddings (chunkers/python_chunker.py) → ChromaDB
  → Relationships (neo4j_loader/load_project.py) → Neo4j
  → Question → qa/ask.py → ChromaDB + Neo4j → Gemini/OpenAI → Answer
```

**Key files:**
- `crawlers/python_ast.py` — reads a Python file, extracts functions/classes/imports/calls using Python's `ast` module
- `crawlers/crawl_project.py` — orchestrates the full project, incremental crawling via file timestamps, saves JSON per file
- `chunkers/python_chunker.py` — reads JSON, stores chunks in ChromaDB with `upsert()`, stale chunk deletion
- `neo4j_loader/load_project.py` — two-pass: Pass 1 creates nodes (File, Function, Class, Method), Pass 2 creates relationships (IMPORTS, CALLS, CONTAINS, HAS_METHOD)
- `qa/ask.py` — original fixed RAG Q&A, kept for comparison

**Commands:**
```bash
PYTHONPATH=. uv run python3 crawlers/crawl_project.py source/codeatlas/ecommerce/inventory_service
PYTHONPATH=. uv run python3 chunkers/python_chunker.py source/codeatlas/ecommerce/inventory_service
PYTHONPATH=. uv run python3 neo4j_loader/load_project.py source/codeatlas/ecommerce/inventory_service
PYTHONPATH=. uv run python3 qa/ask.py codeatlas/ecommerce "question"
```

**Chunk IDs in ChromaDB:** `repo::relative/path/from/source/filename.py::symbol_name`
(full relative path, not just basename — fixes file collision bug for same-named files in different dirs)

---

## Iteration 1 — First Agent ✅

Replaced fixed RAG with an agent that *decides* which tools to use.

**Key file:** `agents/code_agent.py`

Agent loop pattern (plain Python, no framework):
```python
messages = [system_message, user_question]
while True:
    response = openai.chat.completions.create(model=..., messages=messages, tools=TOOLS, tool_choice="auto")
    message = response.choices[0].message
    if not message.tool_calls:
        return message.content      # final answer
    for tool_call in message.tool_calls:
        result = execute_tool(tool_call)
        messages.append(tool_result)  # feed back into conversation
```

**Tools:** `search_code`, `get_dependencies`, `read_file`

**Tool files:**
- `tools/code_search.py` — wraps ChromaDB semantic search, project-scoped
- `tools/graph_tool.py` — wraps Neo4j, returns callers/callees/class ownership
- `tools/file_tool.py` — safely reads source files, no path traversal

**Key insight:** `project` is injected server-side — the LLM never chooses which project to search.

**Command:**
```bash
PYTHONPATH=. uv run python3 agents/code_agent.py codeatlas/ecommerce "question"
```

---

## Iteration 2 — State + Planning ✅

Added a planner that converts a task into structured steps, then executes each step.

**Key files:**
- `agents/planner.py` — asks OpenAI to produce a JSON plan: `{goal, steps: [{id, action}]}`
- `agents/state.py` — `create_initial_state(project, task, plan)` → dict
- `agents/executor.py` — outer loop: create_plan → create_initial_state → execute_plan → synthesize
- `agents/synthesizer.py` — takes completed state, produces final engineering recommendation

**Command:**
```bash
PYTHONPATH=. uv run python3 agents/executor.py codeatlas/ecommerce "Add logging when stock reservation fails"
```

---

## Iteration 3 — Code-Changing Agent ✅

Added write and test tools. Agent can now modify files and validate changes.

**Key files:**
- `tools/write_file.py` — safely overwrites an existing file only (no new file creation)
- `tools/run_tests.py` — runs pytest via subprocess, only allows pytest commands

---

## Iteration 4 — Long-Term Memory ✅

**Key file:** `memory/memory_store.py`
**Storage:** `memory/project_memory.json` (keyed by project string)

**Functions:** `save_memory(project, key, value)`, `get_memories(project)`, `load_memory()`

Memory is injected into the system prompt at agent start. Agent can call `save_memory` to persist new learnings.

**Rule:** Save stable reusable knowledge. Do NOT save step numbers, current errors, or speculative conclusions.

---

## Iteration 5 — GitHub SDLC ❌ NOT IMPLEMENTED

The big gap. Tools planned but never built:
- `create_issue()`, `create_branch()`, `checkout_branch()`
- `commit_changes()`, `push_branch()`, `create_pull_request()`
- `merge_pull_request()`, `close_issue()`

Comment in `guardrails/tool_policy.py` reserves space for these.

---

## Iteration 6 — Guardrails ✅

**Key files:**
- `guardrails/tool_policy.py` — ALLOW / DENY / REQUIRE_APPROVAL per tool
- `guardrails/resource_policy.py` — path traversal, sensitive filenames, sensitive suffixes, sensitive words
- `guardrails/human_approval.py` — prints tool+args, calls `input()` for y/n

**Enforcement flow:** authorize_tool() → authorize_file_access() → request_human_approval() → execute_tool()

---

## Iteration 7 — Evaluation ✅

**Key files:**
- `evaluation/test_cases.json` — known tasks with expected/forbidden files
- `evaluation/evaluator.py` — 4 deterministic checks + LLM judge
- `evaluation/llm_judge.py` — scores correctness/groundedness/task_completion/hallucination/clarity (0–5 each)

**Command:**
```bash
PYTHONPATH=. uv run python3 evaluation/evaluator.py codeatlas/ecommerce <test_id>
```

---

## Iteration 8 — Observability ✅

**Key file:** `observability/trace_reporter.py`

Tracing built into `agents/code_agent.py`. Events: agent_start, llm_call_end (tokens + cost), tool_call_end (duration + success), agent_end.

`run_agent(return_trace=True)` returns the full trace dict.

**Command:**
```bash
PYTHONPATH=. uv run python3 observability/trace_reporter.py codeatlas/ecommerce "question"
```

---

## Iteration 9 — Multi-Agent Orchestrator ✅

**Key files:**
- `multi_agent_demo/orchestrator.py` — AGENTS registry, run_orchestrator(), handles need_information detour
- `multi_agent_demo/planner_agent.py` — decides workflow: `{status: plan_ready, result: {workflow: [...]}}`
- `multi_agent_demo/analyst_agent.py` — investigates code, no modification
- `multi_agent_demo/coding_agent.py` — designs code change (read-only in Round 1)
- `multi_agent_demo/testing_agent.py` — evaluates test requirements
- `multi_agent_demo/reviewer_agent.py` — independent review, returns approved/rejected

**Command:**
```bash
PYTHONPATH=. uv run python3 multi_agent_demo/orchestrator.py codeatlas/ecommerce "Add validation for negative stock"
```

---

## What Is NOT Implemented

| Iteration | Topic |
|---|---|
| 5 | GitHub SDLC tools |
| 10 | MCP server |
| 11 | LangGraph orchestration |
| 12–14 | Security, Scaling, Cloud (conceptual only) |
