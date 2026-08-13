# Claude Instructions — GitHub Agentic SDLC

## Purpose

This is a learning capstone project. The goal is to rebuild CodeAtlas concepts using LangChain/LangGraph, understanding what each framework abstraction replaces compared to the manual implementation.

Move slowly. Explain before coding. One iteration at a time.

## At the Start of Every Conversation

Read these files before doing any work:

- `docs/notes/codeatlas_overview.md` — what CodeAtlas is, tech stack, repo structure
- `docs/notes/codeatlas_what_is_built.md` — every iteration built in CodeAtlas, commands, what's missing
- `docs/notes/codeatlas_key_concepts.md` — embeddings, RAG, agent loop, tool calling, state vs memory, guardrails, multi-agent, evaluation
- `docs/notes/codeatlas_file_map.md` — quick file lookup for CodeAtlas
- `docs/notes/codeatlas_capstone_plan.md` — 20 iterations, LangChain comparison table, capstone plan
- `docs/status_update.md` — current progress, what was last completed, what is next
- `docs/journal.md` — detailed step-by-step log of everything done so far

## Teaching Philosophy

- **Explain before you code.** Before writing any code, explain what we are about to do and why.
- **Compare to CodeAtlas.** For every LangChain abstraction, explain what CodeAtlas did manually and what LangChain now provides.
- **One iteration at a time.** Complete and understand one chunk before starting the next.
- **No rushing.** Learning is the primary objective, not shipping code.

## Learning Loop (every iteration)

```
Concept → Why do we need it? → How did CodeAtlas do it manually?
  → How does LangChain do it? → Architecture/flow → Small implementation
  → Run it → Understand output → Next iteration
```

## Commit and PR Workflow

- Before committing, ask the user if there is anything else to add or change.
- Never create a commit or PR without explicit confirmation.
- Never add `Co-Authored-By` trailers to commit messages.

## Code Comments

Add comments generously — on every function, every class, every non-trivial block. This is a learning project. Comments should explain the WHY and the reasoning, not just restate what the code does.

## Function Design

Every function must serve exactly one purpose. If a function does two things, split it into two functions.

## Notes

The `docs/notes/` folder contains my reference notes about CodeAtlas and the capstone plan. Update these notes when significant new things are learned or when the capstone plan evolves.

## Status Tracking

Two files track progress. Read both at the start of every conversation.

### `docs/status_update.md` — High-level iteration tracker

Update automatically after every **iteration** is completed. Record:
- Which iteration was completed and the date
- What was built (files created or changed)
- What concept was learned
- What LangChain abstraction was compared to CodeAtlas
- What is next

### `docs/journal.md` — Detailed step-by-step learning log

This is the full record of everything we do. After every individual step — a concept explained, a file created, a command run, a decision made — ask the user:

> "Should we add this step to the journal?"

If yes, append a detailed entry to `docs/journal.md` covering:
- What we did
- Why we did it
- What was learned or decided
- Any commands run and their output
- Files created or changed
- How it compares to CodeAtlas

Never add to the journal without asking first. Build it incrementally, one step at a time.
