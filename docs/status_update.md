# Capstone Progress — GitHub Agentic SDLC

This file is updated automatically after every iteration is completed.
It is also read at the start of every conversation so Claude knows exactly where we left off.

---

## Current Status

**Phase:** Iteration 5 — Memory
**Next step:** Add long-term project memory that persists across tasks. Distinguish state (this task) vs memory (all tasks).

---

## Completed Iterations

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
- **Status:** 🔲 Not started
- **Goal:** Short-term context, long-term memory, retrieval, quality controls. State vs memory distinction.
- **CodeAtlas comparison:** `memory/memory_store.py`, `memory/project_memory.json`
- **Files to create:** TBD

### Iteration 6 — Guardrails + Human-in-the-Loop
- **Status:** 🔲 Not started
- **Goal:** Tool authorization (ALLOW/DENY/REQUIRE_APPROVAL), resource authorization, prompt-injection defense, human approval
- **CodeAtlas comparison:** Entire `guardrails/` folder
- **Files to create:** TBD

### Iteration 7 — Evaluation
- **Status:** 🔲 Not started
- **Goal:** Deterministic checks + LLM-as-a-Judge
- **CodeAtlas comparison:** `evaluation/` folder
- **Files to create:** TBD

### Iteration 8 — Observability / Tracing
- **Status:** 🔲 Not started
- **Goal:** Per-LLM-call latency, per-tool latency, tokens, cost, failures. LangSmith comparison.
- **CodeAtlas comparison:** `observability/trace_reporter.py`, events in `agents/code_agent.py`
- **Files to create:** TBD

### Iteration 9 — Specialist Agents
- **Status:** 🔲 Not started
- **Goal:** Planner, Analyst, Coder, Tester, Reviewer — each with one clear responsibility
- **CodeAtlas comparison:** `multi_agent_demo/` folder
- **Files to create:** TBD

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
