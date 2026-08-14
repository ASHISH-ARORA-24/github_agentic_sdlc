# Interview Prep — GitHub Agentic SDLC

This file captures key concepts explained during the learning journey,
written in a way that can be directly used in interviews.

Each concept includes: what it is, why it exists, and how it fits into the bigger picture.

---

## Q: What is the difference between Messages and Structured State in an agentic system?

This is one of the most important concepts to understand clearly.

### Short answer

- **Messages** — the conversation history inside one agent run (tool calls within one step)
- **Structured State** — a dictionary that tracks progress across multiple steps of a task

### Full explanation

When an agent calls multiple tools to answer a question, those tool calls and results are tracked in a `messages` list. The LLM reads the entire messages list on every call to know what has happened so far. When the agent finishes, those messages are gone.

But when a task has multiple steps — plan → find code → read file → modify → test — each step runs its own agent. If each step starts with an empty messages list, step 3 has no idea what step 1 found. That is where Structured State comes in.

### Concrete example

```
Task: "Add validation to reserve_stock"
        ↓
Planner creates 5 steps  → saved in STATE
        ↓
━━━ Step 1: Find the code ━━━━━━━━━━━━━━━━
  Agent runs
  messages = [SystemMessage, HumanMessage]
  → calls search_code        (added to messages)
  → calls get_dependencies   (added to messages)
  → final answer: "found stock_manager.py"
  messages die here
  result saved → STATE["results"][0]
        ↓
━━━ Step 2: Read the file ━━━━━━━━━━━━━━━━
  Agent runs fresh (new messages list)
  messages = [SystemMessage, HumanMessage]
  → calls read_file          (added to messages)
  → final answer: "method does X"
  messages die here
  result saved → STATE["results"][1]
        ↓
━━━ Step 3: Modify code ━━━━━━━━━━━━━━━━━
  Agent runs fresh — but reads STATE to know:
    - which file (from step 1)
    - what it does (from step 2)
  ...
```

### Comparison table

| | Messages | Structured State |
|---|---|---|
| Lives | Inside one agent run | Across all steps of a task |
| Tracks | Tool calls within a step | Step results across the whole task |
| Dies | When step finishes | When task finishes |
| Used by | The LLM (to reason) | The orchestrator (to coordinate) |

### One-line summary

> One agent answering a question → **messages**.
> Many steps, each with its own agent run → **structured state** connecting them.

---

## Q: What is an Agent Loop and how does it work?

Every agent framework — LangChain, LangGraph, AutoGen, OpenAI Assistants — is built on the same fundamental loop:

```
LLM says "call tool X with args Y"    ← Reason
Our code runs tool X with args Y      ← Act
Our code feeds result back to LLM     ← Observe
LLM reasons again with new result     ← Reason
... repeat until LLM says "done"
```

The LLM **cannot** run tools itself. It only produces a description of what it wants to call. The application code (or framework) actually executes the tool and feeds the result back.

Frameworks differ only in how much they hide this loop:
- **Manual loop** — you write the while True, you see every step
- **AgentExecutor** — framework owns the loop, you just call `.invoke()`
- **LangGraph** — loop is expressed as a graph with nodes and edges
- **OpenAI Assistants API** — loop runs on OpenAI's servers, invisible to you

Understanding the manual loop means you can reason about any framework.

---

## Q: What is the difference between State and Memory?

| | State | Memory |
|---|---|---|
| Scope | One task execution | Across many tasks |
| Example | "Current step is 3, file found is stock_manager.py" | "This project uses pytest and snake_case" |
| Lives | Until task finishes | Indefinitely |
| Analogy | RAM | Notebook |

State is what the agent knows **right now** for this task.
Memory is what the agent has learned **over time** about the project.

---

## Q: Why does an agent need a Planner?

Without a plan, an agent given a complex task (e.g. "add authentication to this service") will jump in randomly — it might modify code before reading it, or run tests before making any change.

A Planner converts the task into ordered steps first:
1. Understand the requirement
2. Find relevant code
3. Analyse dependencies
4. Make the change
5. Run tests

Then each step is executed in order, with results passed forward via state. This mirrors how a senior engineer approaches a task — think before you act.

---

## Q: What is observability in an agentic system and why does it matter?

### Short answer

Observability means capturing what happened inside an agent run — which LLM calls were made, which tools were called, how long each took, how many tokens were used, and what it cost. Without it you are flying blind.

### Why it matters

An agent run can involve 6 LLM calls and 9 tool calls before producing an answer. If it is slow, expensive, or wrong — you have no idea which step caused it. Observability gives you a timeline so you can answer:
- Which step used the most tokens?
- Which tool is slow?
- Did the planner LLM call cost more than all the executor calls combined?

### How it is implemented here

One shared trace dict is created by the orchestrator at the start of the task and passed to every agent:

```python
obs = new_trace()                            # orchestrator creates it
plan = create_plan(task, obs=obs)            # planner records its LLM call
result = run_agent(project, question, obs=obs)  # executor records LLM + tool calls
final = synthesize(task, results, obs=obs)   # synthesizer records its LLM call
finish_trace(obs)                            # adds total duration
print_report(obs)                            # prints the timeline
```

Every agent also works standalone (when `obs=None`, it creates its own local trace). No agent is forced to share a trace.

### CodeAtlas comparison

CodeAtlas manually built event dicts in `agents/code_agent.py` and printed them in `observability/trace_reporter.py`. Here the same concept is split into two clean files: `tracer.py` records events, `reporter.py` prints them.

---

## Q: What is the Specialist Agent pattern and why is it better than one big agent?

### Short answer

Instead of one agent that plans, executes, and summarizes — you split each responsibility into a separate agent. Each agent does exactly one thing.

### The three agents in this project

| Agent | Responsibility | Has Tools? |
|---|---|---|
| Planner | Break the task into ordered steps | No |
| Executor | Run one step using tools | Yes |
| Synthesizer | Turn all step results into one final answer | No |

### Why this is better than one big agent

1. **Testable** — you can evaluate the planner independently. Give it a task, check if it produces a good plan. No tool calls, no noise.
2. **Replaceable** — if the planner is bad, swap it. If the synthesizer produces weak summaries, improve it. Nothing else changes.
3. **Auditable** — when the final answer is wrong, you know exactly which agent to look at.
4. **Scalable** — the executor loops N times (one per step). The planner runs once. The synthesizer runs once. This is natural.

### The key rule

No agent does two jobs. The planner does not execute. The executor does not plan. The moment an agent does two things, it becomes harder to test, harder to replace, and harder to debug.

### CodeAtlas comparison

CodeAtlas had the same concept in `multi_agent_demo/` — separate planner, analyst, coder, reviewer agents. Here the implementation is simpler: three agents instead of five, with the orchestrator providing the coordination glue.

---

## Q: What does `@tool` do in LangChain?

In a plain OpenAI implementation you write two things:
1. The Python function that does the work
2. A JSON schema describing the function to the LLM — by hand

If you rename a parameter, you update it in two places.

LangChain's `@tool` decorator generates the JSON schema automatically from the function's type hints and docstring. You write the function once. The schema is always in sync.

```python
@tool
def search_code(query: str) -> list:
    """Search source code semantically across the codebase."""
    ...
```

LangChain reads `query: str` and the docstring and produces the correct JSON schema for the LLM automatically.

---

## Q: Why use LangChain instead of calling OpenAI directly?

Calling OpenAI directly works. The reason to use LangChain:

1. **Provider abstraction** — swap `ChatOpenAI` for `ChatAnthropic` or `ChatGoogleGenerativeAI` by changing one class. Nothing else changes.
2. **Typed messages** — `HumanMessage`, `SystemMessage`, `ToolMessage` instead of raw dicts `{"role": "user", "content": "..."}`. Cleaner, less error-prone.
3. **Tool binding** — `llm.bind_tools(tools)` once, instead of passing `tools=` to every API call.
4. **Ecosystem** — memory, evaluation, tracing, vector stores all speak the same interface.

The underlying API call to OpenAI is identical. LangChain is a wrapper, not a replacement.
