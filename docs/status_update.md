# Capstone Progress — GitHub Agentic SDLC

This file is updated automatically after every iteration is completed.
It is also read at the start of every conversation so Claude knows exactly where we left off.

---

## Current Status

**Phase:** ✅ End-to-end SDLC pipeline complete and validated in production
**Next step:** LangGraph migration (Iteration 11+) — rebuild `sdlc.py` as a graph with typed state, nodes, edges, and conditional edges

### What was completed in the last session (2026-08-15)
- **All three specialist agents built and working:** `src/agents/analyst.py`, `src/agents/coder.py`, `src/agents/reviewer.py`
- **`SDLCPipeline` class** (`src/sdlc.py`) — full pipeline as a class with 12 private methods, `run()` sequences everything
- **`SDLCState` class** (`src/state.py`) — named attributes replacing dict-based state
- **Two rework loops working end to end:**
  - Reviewer rejects → coder rework → re-review (max 2)
  - Human rejects → coder rework → re-review → re-HITL (max 2)
- **Retry caps enforced in code**, not just prompt (3 test fails, 30 iterations)
- **Service repos restructured** as standalone uv projects (`pyproject.toml`, `uv.lock`, direct imports)
- **Real test suite** added to `order_service/tests/test_order_manager.py`
- **Pipeline validated on real GitHub** — 3 successful runs including happy path, early stop, and rework loop
- **Removed:** old `src/orchestrator.py` (replaced by `SDLCPipeline`)

---

## Completed Iterations

### ✅ Iteration 9 — Specialist Agents (2026-08-14)
- Confirmed specialist agent roles: planner (plan only), executor (run tools + agent loop), synthesizer (summarize only)
- Restructured `src/tools/` into a package (`codebase.py` + `__init__.py`) to support future GitHub tools alongside codebase tools
- Each agent has exactly one responsibility — no agent does two jobs
- CodeAtlas comparison: replaces `multi_agent_demo/` where agents were loosely coupled

### ✅ Iteration 8 — Observability (2026-08-14)
- Created `src/observability/tracer.py` — `new_trace()`, `record_llm_call()`, `record_tool_call()`, `finish_trace()`
- Created `src/observability/reporter.py` — `print_report()` prints a human-readable timeline + summary
- Instrumented planner, executor, and synthesizer to record LLM calls via shared `obs` trace
- Orchestrator creates one shared trace, passes it through all agents, prints report at end
- Per-call token usage and cost read from `response.response_metadata["token_usage"]`
- CodeAtlas comparison: replaces `observability/trace_reporter.py` and manual event dicts in `agents/code_agent.py`

### ✅ Iteration 2 — LangChain Tools (2026-08-13)
- Created `src/tools.py` with all five tools using `@tool` decorator
- Introduced `make_tools(project)` factory — project comes from the request, not hardcoded
- Learned: `@tool` auto-generates JSON schema from type hints and docstring
- Learned: closure pattern — tools remember `project` from their creation scope
- Deleted `tools/` folder — consolidated into `src/tools.py`
- CodeAtlas comparison: replaces handwritten TOOLS list + `execute_tool()` dispatcher

### ✅ Iteration 1 — LangChain Model Abstraction (2026-08-13)
- Added `langchain-openai` to `pyproject.toml`
- Created `src/llm.py` with `ChatOpenAI`, `SystemMessage`, `HumanMessage`
- Learned: LangChain wraps providers — swap one class to change provider, nothing else changes
- CodeAtlas comparison: replaces raw `client.chat.completions.create()` and dict-based messages

---

## Iteration Log

### Iteration 1 — LangChain Model Abstraction
- **Status:** ✅ Complete (2026-08-13)
- **Goal:** Understand ChatOpenAI, messages, model invocation, provider abstraction
- **CodeAtlas comparison:** Direct `client.chat.completions.create()` in `agents/code_agent.py`
- **Files to create:** TBD

### Iteration 2 — LangChain Tools
- **Status:** ✅ Complete (2026-08-13)
- **Goal:** Understand `@tool` decorator, tool schemas, `model.bind_tools()`, tool invocation
- **CodeAtlas comparison:** Manual TOOLS list (JSON dicts) in `agents/code_agent.py`
- **Files to create:** TBD

### Iteration 3 — Single LangChain Agent
- **Status:** ✅ Complete (2026-08-13)
- **Goal:** Full Reason → Tool → Observe → Reason loop using LangChain
- **CodeAtlas comparison:** `while True` agent loop in `agents/code_agent.py`
- **Files to create:** TBD

### Iteration 4 — Planning + Structured State
- **Status:** ✅ Complete (2026-08-13)
- **Goal:** Structured outputs, workflow state, task context
- **CodeAtlas comparison:** `agents/planner.py`, `agents/state.py`, `agents/executor.py`
- **Files to create:** TBD

### Iteration 5 — Memory
- **Status:** ✅ Complete (2026-08-13)
- **Goal:** Short-term context, long-term memory, retrieval, quality controls. State vs memory distinction.
- **CodeAtlas comparison:** `memory/memory_store.py`, `memory/project_memory.json`
- **Files to create:** TBD

### Iteration 6 — Guardrails + Human-in-the-Loop
- **Status:** ✅ Partial (2026-08-13) — write_files guardrail done. Tool policy + HITL deferred until GitHub tools are built.
- **Goal:** Tool authorization (ALLOW/DENY/REQUIRE_APPROVAL), resource authorization, prompt-injection defense, human approval
- **CodeAtlas comparison:** Entire `guardrails/` folder
- **Files to create:** TBD

### Iteration 7 — Evaluation
- **Status:** ✅ Complete (2026-08-13)
- **Goal:** Deterministic checks + LLM-as-a-Judge
- **CodeAtlas comparison:** `evaluation/` folder
- **Files to create:** TBD

### Iteration 8 — Observability / Tracing
- **Status:** ✅ Complete (2026-08-14)
- **Goal:** Per-LLM-call latency, per-tool latency, tokens, cost, failures. LangSmith comparison.
- **CodeAtlas comparison:** `observability/trace_reporter.py`, events in `agents/code_agent.py`
- **Files created:** `src/observability/tracer.py`, `src/observability/reporter.py`

### GitHub SDLC Tools — Phase 1 (2026-08-14)
- **Status:** ✅ Complete
- `src/tools/github.py` — all GitHub REST API tools built with guardrails:
  - Issues: `create_issue`, `add_comment_to_issue`, `close_issue` (orchestrator only)
  - Branches: `create_branch`, `delete_branch`
  - PRs: `create_pr`, `get_pr`, `get_pr_diff`, `update_pr`, `close_pr`, `merge_pr` (orchestrator only)
- `src/hitl/approve_pr.py` — human approval gate, blocks pipeline until human types APPROVE/REJECT
- `source/codeatlas/ecommerce/project.yml` — repo URLs, board URL, column names, issues_repo
- Guardrails: naming convention, empty field checks, PR link check, merge safety, branch protection
- **Next:** `src/tools/git.py` — local git operations (checkout, pull, commit, push)

### Iteration 9 — Specialist Agents
- **Status:** ✅ Complete (2026-08-14)
- **Goal:** Planner, Analyst, Coder, Tester, Reviewer — each with one clear responsibility
- **CodeAtlas comparison:** `multi_agent_demo/` folder
- **Files created:** `src/tools/codebase.py`, `src/tools/__init__.py`

### Iteration 10 — Multi-Agent Orchestration
- **Status:** 🔲 Not started
- **Goal:** Agent registry, common contract, routing, shared state, agent independence
- **CodeAtlas comparison:** `multi_agent_demo/orchestrator.py`
- **Files to create:** TBD

### Iteration 11 — Failure / Retry Loops
- **Status:** 🔲 Not started
- **Goal:** tester fails → coder fixes → retest; reviewer rejects → coder fixes → re-review
- **CodeAtlas comparison:** Not implemented in CodeAtlas
- **Files to create:** TBD

### Iteration 12 — GitHub Issue Integration
- **Status:** 🔲 Not started
- **Goal:** `create_issue()` tool wired into the agent
- **CodeAtlas comparison:** Not implemented in CodeAtlas
- **Files to create:** TBD

### Iteration 13 — GitHub Branch Integration
- **Status:** 🔲 Not started
- **Goal:** `create_branch()`, `checkout_branch()`, branch naming rules
- **CodeAtlas comparison:** Not implemented in CodeAtlas
- **Files to create:** TBD

### Iteration 14 — Coding + Testing Workflow
- **Status:** 🔲 Not started
- **Goal:** Coding agent inspects files, modifies, runs tests, responds to failures
- **CodeAtlas comparison:** `tools/write_file.py`, `tools/run_tests.py`, agent loop in `agents/code_agent.py`
- **Files to create:** TBD

### Iteration 15 — Commit / Push / Pull Request
- **Status:** 🔲 Not started
- **Goal:** `commit_changes()`, `push_branch()`, `create_pull_request()` with guardrails
- **CodeAtlas comparison:** Not implemented in CodeAtlas
- **Files to create:** TBD

### Iteration 16 — AI Reviewer
- **Status:** 🔲 Not started
- **Goal:** Reviewer agent independently reviews implementation → APPROVED or REJECTED + reason
- **CodeAtlas comparison:** `multi_agent_demo/reviewer_agent.py`
- **Files to create:** TBD

### Iteration 17 — Human Approval + Merge
- **Status:** 🔲 Not started
- **Goal:** HITL gate before merge, rework path on rejection
- **CodeAtlas comparison:** `guardrails/human_approval.py`
- **Files to create:** TBD

### Iteration 18 — Close GitHub Issue
- **Status:** 🔲 Not started
- **Goal:** After merge, verify and close originating issue
- **CodeAtlas comparison:** Not implemented in CodeAtlas
- **Files to create:** TBD

### Iteration 19 — End-to-End SDLC
- **Status:** 🔲 Not started
- **Goal:** Connect all pieces into one pipeline: Requirement → Issue → Branch → Code → Test → PR → Review → Approval → Merge → Close
- **Files to create:** TBD

### Iteration 20 — Parallel Multi-Agent Execution
- **Status:** 🔲 Not started
- **Goal:** Orchestrator identifies independent tasks and runs agents concurrently
- **Note:** Only after sequential end-to-end is fully understood
- **Files to create:** TBD
