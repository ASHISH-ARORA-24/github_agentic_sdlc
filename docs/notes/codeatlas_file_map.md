# CodeAtlas — File Map

Quick lookup: "where is X implemented in CodeAtlas?"

## Crawling / Indexing

| File | What it does | Key function |
|---|---|---|
| `crawlers/python_ast.py` | Reads one Python file with `ast`, extracts functions/classes/imports/calls | `crawl_file(file_path, source_root)` → dict |
| `crawlers/crawl_project.py` | Orchestrates full project crawl, incremental via `st_mtime` | `crawl_project(project_path)` |
| `chunkers/python_chunker.py` | Reads JSON from output/, stores chunks in ChromaDB. Model: `all-MiniLM-L6-v2` | `chunk_project(project_path)` |
| `neo4j_loader/load_project.py` | Reads JSON, builds Neo4j graph. Two-pass loading | `load_project(project_path)` |

## Q&A (original fixed pipeline)

| File | What it does |
|---|---|
| `qa/ask.py` | Fixed RAG: always calls ChromaDB + Neo4j + Gemini. Kept as baseline. |

## Agent

| File | What it does | Key function |
|---|---|---|
| `agents/code_agent.py` | Main agent. TOOLS list, execute_tool(), agent loop, observability tracing | `run_agent(project, question, verbose, return_trace)` |
| `agents/planner.py` | Converts task → JSON plan | `create_plan(task)` → `{goal, steps: [{id, action}]}` |
| `agents/state.py` | Creates initial workflow state | `create_initial_state(project, task, plan)` → dict |
| `agents/executor.py` | Outer loop: plan → state → execute steps → synthesize | `run_workflow(project, task)` |
| `agents/synthesizer.py` | Produces final recommendation from completed state | `synthesize_result(state)` → str |

## Tools

| File | What it does | Key function |
|---|---|---|
| `tools/code_search.py` | ChromaDB semantic search, project-scoped | `search_code(project, query)` → list of chunks |
| `tools/graph_tool.py` | Neo4j callers/callees/class ownership | `get_dependencies(project, symbol)` |
| `tools/file_tool.py` | Safe file reader, no path traversal | `read_file(project, repo, file_path)` → str |
| `tools/write_file.py` | Overwrites existing files only, strips null bytes | `write_file(project, repo, file_path, content)` |
| `tools/run_tests.py` | Runs pytest via subprocess, pytest commands only | `run_tests(project, repo, test_command)` → `{passed, return_code, stdout, stderr}` |
| `tools/inspect_chromadb.py` | Debug — inspect ChromaDB collection contents | — |

## Guardrails

| File | What it does | Key function |
|---|---|---|
| `guardrails/tool_policy.py` | ALLOW / DENY / REQUIRE_APPROVAL per tool | `authorize_tool(tool_name)` → `{decision, reason}` |
| `guardrails/resource_policy.py` | Path traversal, sensitive filenames, sensitive suffixes | `authorize_file_access(project, repo, file_path, operation)` |
| `guardrails/human_approval.py` | Prints tool+args, asks y/n from stdin | `request_human_approval(tool_name, arguments)` → bool |

## Memory

| File | What it does | Key function |
|---|---|---|
| `memory/memory_store.py` | Load/save/get project-scoped JSON memory | `save_memory(project, key, value)`, `get_memories(project)` |
| `memory/project_memory.json` | The actual JSON store, keyed by project string | — |

## Multi-Agent

| File | What it does | Key function |
|---|---|---|
| `multi_agent_demo/orchestrator.py` | Owns AGENTS registry, handles workflow + detour | `run_orchestrator(project, task)` |
| `multi_agent_demo/planner_agent.py` | Decides which agents needed and in what order | `run_planner_agent(task, available_agents, prior_findings)` |
| `multi_agent_demo/analyst_agent.py` | Investigates code, no modification | `run_analyst_agent(project, task, request)` |
| `multi_agent_demo/coding_agent.py` | Designs code change (read-only in Round 1) | `run_coding_agent(project, task, plan)` |
| `multi_agent_demo/testing_agent.py` | Evaluates test requirements | `run_testing_agent(project, task, coding_result)` |
| `multi_agent_demo/reviewer_agent.py` | Independent review, approved/rejected | `run_reviewer_agent(project, task, coding_result, testing_result)` |

## Evaluation

| File | What it does | Key function |
|---|---|---|
| `evaluation/test_cases.json` | Known tasks: expected_files, forbidden_files, must_pass_tests | — |
| `evaluation/evaluator.py` | 4 deterministic checks + LLM judge | `run_evaluation(project, test_case)` |
| `evaluation/llm_judge.py` | Scores correctness/groundedness/hallucination/clarity | `judge_agent_result(test_case, trace)` |

## Observability

| File | What it does | Key function |
|---|---|---|
| `observability/trace_reporter.py` | Runs agent, prints human-readable trace report | `run_with_trace_report(project, task)` |

## Sample Repos (for testing)

| Path | What it is |
|---|---|
| `source/codeatlas/sample/calculator/` | Simple standalone functions |
| `source/codeatlas/sample/grade_calculator/` | Class-based, imports, multiple files |
| `source/codeatlas/ecommerce/inventory_service/` | Inventory with StockManager, models |
| `source/codeatlas/ecommerce/order_service/` | Order service calling inventory via HTTP |

## Config / Setup

| File | What it is |
|---|---|
| `pyproject.toml` | Dependencies: chromadb, neo4j, openai, google-genai, python-dotenv. Python >=3.13 |
| `.env` (gitignored) | `OPENAI_API_KEY`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` |
| `.env.example` | Safe template committed to git |
| `CLAUDE.md` | Teaching rules, locked tech stack decisions, commit rules |
