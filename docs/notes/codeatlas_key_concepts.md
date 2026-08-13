# CodeAtlas — Key Concepts

These are the concepts already understood from CodeAtlas. Reference these when comparing manual implementation to LangChain abstractions in the capstone.

---

## Embeddings

- An embedding is a list of numbers representing the *meaning* of text
- Similar meaning → similar numbers → close in vector space
- The **same model must be used at index time and query time** — changing the model corrupts all stored vectors
- CodeAtlas uses `all-MiniLM-L6-v2` (80MB, runs on CPU, no GPU needed)
- ChromaDB calls the model internally — you never call it yourself
- `collection.upsert(ids, documents, metadatas)` — adds or updates, no duplicates

---

## RAG — Retrieval Augmented Generation

```
User question
  → Find nearest vectors in ChromaDB (semantic similarity)
  → Enrich with Neo4j graph context (structural relationships)
  → Build prompt: "Answer using ONLY this context: ..."
  → Send to LLM → grounded answer
```

Why combine vector + graph:
- ChromaDB: "what is this code about" (semantic)
- Neo4j: "what calls this function, what does it import" (structural)

---

## AST — Abstract Syntax Tree

- `ast.parse(source)` → tree of nodes
- `ast.walk(tree)` → every node regardless of nesting
- `tree.body` → only top-level statements
- `class_node.body` → only that class's methods
- Key node types: `FunctionDef`, `ClassDef`, `Import`, `ImportFrom`, `ast.Call`, `ast.Assign`
- `ast.get_docstring(node)` → extracts docstring safely
- `ast.unparse(node)` → converts annotation to readable string (e.g. `list[str]`)
- `ast.get_source_segment(source, node)` → extracts exact source code for a node
- Filter `self` out of method parameters — it's not a real param

---

## Neo4j / Knowledge Graph

- Nodes: `File`, `Function`, `Class`, `Method`
- Relationships: `CONTAINS`, `HAS_METHOD`, `IMPORTS`, `CALLS`
- `MERGE` — creates if not exists, matches if exists (idempotent)
- `DETACH DELETE` — removes node + all its relationships
- Two-pass loading: Pass 1 creates all nodes, Pass 2 creates relationships
  - Why: target nodes must exist before you can create a relationship to them
- Driver 6.x: parameters as `{"key": value}` dict

---

## Agent Loop (manual, plain Python)

```python
messages = [system_message, {"role": "user", "content": question}]

while True:
    response = client.chat.completions.create(
        model=OPENAI_MODEL, messages=messages, tools=TOOLS, tool_choice="auto"
    )
    message = response.choices[0].message
    messages.append(message)

    if not message.tool_calls:
        return message.content          # final answer

    for tool_call in message.tool_calls:
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        result = execute_tool(tool_name, arguments)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,   # MUST match the tool call
            "content": json.dumps(result),
        })
```

Key points:
- `tool_choice="auto"` → LLM decides whether to call a tool or answer directly
- `tool_call_id` → every tool result must reference its tool call ID
- `messages` list = entire conversation history, sent with every request
- OpenAI has no memory — the history IS the memory
- Self-correction: if a tool returns an error, the LLM sees it and can retry

---

## Tool Schema (OpenAI function calling format)

```python
{
    "type": "function",
    "function": {
        "name": "search_code",
        "description": "What the LLM reads to decide when to call this tool.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "..."},
            },
            "required": ["query"],
        },
    },
}
```

Key: only expose parameters the LLM needs to decide. `project` is NOT in the schema — injected silently by code.

---

## State vs Memory

**State** = information for this execution only:
```python
{
    "task": "Add OAuth support",
    "plan": {...},
    "current_step": 3,
    "files_found": [...],
    "status": "in_progress"
}
```

**Memory** = reusable knowledge across multiple executions:
```python
{
    "test_framework": "pytest",
    "naming_convention": "snake_case",
    "retry_library": "tenacity",
}
```

Rules for memory:
- Save: stable conventions, frameworks, patterns, project-specific facts
- Do NOT save: step numbers, current errors, speculative conclusions, temporary state

In CodeAtlas: state = Python dict passed through executor; memory = `memory/project_memory.json`

---

## Guardrails — Three Layers

```
LLM wants to call tool
  ↓
Layer 1: Tool Policy — is this tool allowed? (ALLOW / DENY / REQUIRE_APPROVAL)
  ↓
Layer 2: Resource Policy — is this file/path safe? (path traversal? .env? secrets?)
  ↓
Layer 3: Human Approval — if REQUIRE_APPROVAL, ask user y/n
  ↓
Execute tool
```

Sensitive filenames blocked: `.env`, `credentials.json`, `id_rsa`, `id_ed25519`
Sensitive suffixes blocked: `.pem`, `.key`, `.p12`, `.pfx`
Sensitive words in path: `secret`, `credential`, `private_key`, `token`

**Prompt injection defense:** Deterministic guardrails are the real enforcement. A comment in source code cannot bypass `resource_policy.py`.

---

## Multi-Agent Design Decisions

**Why multiple agents instead of one agent with many tools?**
- Each agent has one job, one system prompt, one set of tools
- Reviewer hasn't seen the coder's reasoning — gives a true second opinion
- Independent agents can run concurrently

**Orchestrator pattern:**
- Orchestrator knows the agent registry (what exists, what each does)
- Orchestrator does NOT know how agents work internally
- Agents are completely ignorant of each other
- Planner decides which agents are needed and in what order

**AGENTS registry (dict-based dispatch, no if/else):**
```python
AGENTS = {
    "analyst": {"description": ..., "invoke": lambda ...: run_analyst_agent(...), "result_key": "analysis"},
    "coder":   {"description": ..., "invoke": lambda ...: run_coding_agent(...),  "result_key": "coding_result"},
}
# Adding a new agent = one dict entry
```

---

## Evaluation — Two Layers

**Deterministic (what code can measure):**
1. Did agent read/write the expected files?
2. Did agent avoid forbidden files?
3. Did tests pass (if required)?
4. Did agent write files it wasn't supposed to?

**LLM Judge (what code cannot measure):**
- Correctness, Groundedness, Task completion, Hallucination, Clarity — each 0 to 5

---

## Observability — What to Trace

For every agent run:
- `llm_call_end` → duration_ms, prompt_tokens, completion_tokens, estimated_cost_usd
- `tool_call_end` → tool name, duration_ms, success (bool)
- Summary: total duration, LLM calls, tool calls, input/output/total tokens, estimated cost, failures
