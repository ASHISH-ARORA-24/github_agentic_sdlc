# Capstone Project — GitHub Agentic SDLC

**Project location:** `/home/ashish/project/github_agentic_sdlc/`
**Full spec:** `README.md` in the project root

## What it is

Rebuild the CodeAtlas concepts using **LangChain/LangGraph**, understanding at every step:

> "We manually implemented X in CodeAtlas. LangChain now gives us Y. Here is what it replaces, what it adds, and what we still own in application logic."

**Final goal:** A Multi-Agent SDLC POC where a developer submits a requirement and AI agents automate:
Issue → Branch → Code → Test → PR → Review → Human Approval → Merge → Close Issue

## The Learning Method (mandatory at every iteration)

```
Concept
  ↓
Why do we need it?
  ↓
How did CodeAtlas do it manually?
  ↓
How does LangChain do it?
  ↓
Architecture / flow
  ↓
Small implementation
  ↓
Run it and see output
  ↓
Understand the result
  ↓
Next iteration
```

**Round 1** = concepts + architecture + working implementation
**Round 2** = deep code-level understanding of what was built (no new features)

## The 20 Iterations

### Foundation (1–3)
1. **LangChain Model Abstraction** — ChatOpenAI, messages, model invocation, provider abstraction
   - Compare: direct `client.chat.completions.create()` in `agents/code_agent.py`
2. **LangChain Tools** — `@tool` decorator, tool schemas, `model.bind_tools()`, tool invocation
   - Compare: manual TOOLS list + JSON schemas in `agents/code_agent.py`
3. **Single LangChain Agent** — full Reason→Tool→Observe→Reason loop
   - Compare: `while True` agent loop in `agents/code_agent.py`

### Intelligence (4–5)
4. **Planning + Structured State** — structured outputs, workflow state, task context
   - Compare: `agents/planner.py` + `agents/state.py` + `agents/executor.py`
5. **Memory** — short-term context, long-term memory, retrieval, quality controls
   - Compare: `memory/memory_store.py` + `memory/project_memory.json`
   - Clearly distinguish state vs memory

### Safety (6)
6. **Guardrails + HITL** — tool authorization, resource authorization, path validation, prompt-injection defense, human approval
   - Compare: entire `guardrails/` folder

### Quality (7–8)
7. **Evaluation** — deterministic checks + LLM-as-a-Judge
   - Compare: `evaluation/` folder
8. **Observability/Tracing** — per-LLM-call latency, per-tool latency, tokens, cost, failures
   - Compare: `observability/trace_reporter.py` + events in `agents/code_agent.py`
   - Later: what LangSmith adds on top

### Multi-Agent (9–11)
9. **Specialist Agents** — Planner, Analyst, Coder, Tester, Reviewer — each with one responsibility
10. **Multi-Agent Orchestration** — agent registry, common contract, routing, shared state, agent independence
    - Compare: `multi_agent_demo/orchestrator.py`
11. **Failure/Retry Loops** — tester fails → coder fixes → retest; reviewer rejects → coder fixes → re-review

### GitHub SDLC (12–18)
12. **GitHub Issue Integration** — `create_issue()` tool
13. **GitHub Branch Integration** — `create_branch()`, `checkout_branch()`
14. **Coding + Testing Workflow** — inspect files, modify, run tests, respond to failures
15. **Commit / Push / Pull Request** — `commit_changes()`, `push_branch()`, `create_pull_request()`
16. **AI Reviewer** — independent review → APPROVED or REJECTED + reason
17. **Human Approval + Merge** — HITL gate, merge on approval, rework on rejection
18. **Close GitHub Issue** — verify merge, close originating issue

### End-to-End (19–20)
19. **Full End-to-End SDLC** — connect all pieces into one pipeline
20. **Parallel Multi-Agent Execution** — orchestrator identifies independent tasks, runs concurrently
    - Only after sequential is fully understood

## LangChain vs CodeAtlas Comparison Table

| CodeAtlas (manual) | LangChain abstraction |
|---|---|
| `client.chat.completions.create(...)` | `ChatOpenAI` |
| Manual TOOLS list (JSON dicts) | `@tool` decorator |
| `model.bind_tools()` | same, but declarative |
| `while True` agent loop | `agent.invoke()` / AgentExecutor |
| Manual message list building | `HumanMessage`, `AIMessage`, `ToolMessage` |
| Manual JSON parsing of tool args | handled by framework |
| `tool_call_id` matching | handled by framework |
| `response_format: json_object` | `with_structured_output()` |
| Manual event tracing dict | LangSmith / callbacks |

## LangChain vs LangGraph Decision Rule

Start LangChain-first. Introduce LangGraph only when the workflow becomes sufficiently stateful and graph-oriented — and only after explaining why.

Manual equivalent (what LangGraph solves):
```python
# Without LangGraph — grows messy fast
while True:
    choose next agent
    execute
    update state
    inspect status
    branch
    retry
```

LangGraph gives us:
- **State** — typed, managed
- **Nodes** — agents/functions
- **Edges** — transitions
- **Conditional Edges** — branching
- **Loops** — built-in
- **Persistence** — checkpoints

## Shared State Shape (full SDLC)

```python
{
    "project":        "github-runner",
    "task":           "Add OAuth authentication",
    "github_issue":   123,
    "branch":         "feature/123-oauth",
    "analysis":       {},
    "dependencies":   {},
    "plan":           {},
    "files_modified": [],
    "test_results":   {},
    "pull_request":   456,
    "review_result":  {},
    "human_approval": None,
    "status":         "testing"
}
```

## Common Agent Contract (from README)

```python
run_agent(state=state, instruction=instruction)
→ {
    "agent": "analyst",
    "status": "analysis_ready",
    "result": {},
    "state_updates": {"analysis": {}},
    "request": null
  }

# Orchestrator updates state generically:
state.update(result.get("state_updates", {}))
```

## Current Status

Empty skeleton — only `main.py`, `pyproject.toml`, `README.md`, `.python-version` exist.
Ready to start **Iteration 1: LangChain Model Abstraction**.
