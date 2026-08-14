# Guardrails Reference

This document lists every guardrail the SDLC pipeline enforces, where it lives,
and what it protects against. Read this before adding a new tool or changing
existing behavior — new tools should follow the same patterns.

## What is a guardrail?

A guardrail is a **deterministic check that runs before an action** — no LLM
involved, no judgment call. It either allows or blocks based on a hard rule.
The LLM cannot bypass a guardrail because the check runs in the tool code,
not in the LLM's decision loop.

Same pattern everywhere:
```
Agent wants to do something
  → Guardrail checks the rule first
    → ALLOW  → action happens
    → BLOCK  → error returned to agent, nothing happened
```

---

## Guardrails by Category

### 1. Repository Validation

**Purpose:** Prevent the LLM from operating on repos that don't exist or don't
belong to this project.

| Guardrail | Where | What it blocks |
|---|---|---|
| Repo must be in `project.yml github.repos` | `git.py:validate_service_repo()` | Typos like `inventory_svc`, hallucinated repos like `super_service` |
| Repo cannot be `issues_repo` | `git.py:validate_service_repo()` | Code operations targeting `change_management` (issues-only repo) |

**Applied in:**
`checkout_main`, `pull_main`, `checkout_branch`, `commit_changes`, `push_branch`,
`sync_with_main`, `create_branch`, `delete_branch`, `create_pr`, `get_pr`,
`get_pr_diff`, `update_pr`, `close_pr`, `merge_pr`, `write_file`, `run_tests`

---

### 2. Branch Protection

**Purpose:** The agent must never work on or commit to the default branch.

**Protected set:** `{main, master, default_branch from project.yml}` — combined
so protection tracks config changes. Hardcoded `{main, master}` is a safety
net that always applies regardless of what config says.

| Guardrail | Where | What it blocks |
|---|---|---|
| Cannot write files on protected branch | `codebase.py:write_file` | Agent editing code while on main |
| Cannot commit on protected branch | `git.py:commit_changes` | Committing directly to main |
| Cannot push to protected branch name | `git.py:push_branch` | `git push origin main` |
| Cannot push while on protected branch | `git.py:push_branch` | Pushing from main to any branch |
| Cannot checkout protected as feature branch | `git.py:checkout_branch` | `git checkout -b main` |
| `pull_main` blocked if not on default | `git.py:pull_main` | Pulling main while on feature branch |
| Cannot sync protected branch with itself | `git.py:sync_with_main` | Merging main into main |
| Cannot delete protected branch | `github.py:delete_branch` | Deleting main via API |
| Cannot open PR from protected branch | `github.py:create_pr` | PR from main → main |

---

### 3. Branch Naming Convention

**Purpose:** Every agent-created branch is visible and auditable.

**Pattern:** `{type}/issue-{number}-{short-title}-agent`
Examples: `feat/issue-42-add-validation-agent`, `fix/issue-7-null-check-agent`

| Guardrail | Where |
|---|---|
| Branch name must match pattern | `github.py:create_branch` |

`type` can be anything lowercase (feat, fix, hotfix, docs, test, etc.) but
the `issue-{number}` and `-agent` suffix are mandatory.

---

### 4. Issue Existence

**Purpose:** Prevent branches and PRs named after fabricated issue numbers.

| Guardrail | Where | What it blocks |
|---|---|---|
| Issue must exist in `issues_repo` before branching | `github.py:create_branch` | `create_branch("feat/issue-99999-fake-agent")` when issue doesn't exist |
| PR body issue number must match branch issue number | `github.py:create_pr` | Branch `feat/issue-42-*-agent` with body `Closes #999` |
| PR body must include `Closes #N` | `github.py:create_pr` | PRs that don't auto-link to any issue |

---

### 5. Commit Message Convention

**Purpose:** Consistent, readable git history.

**Pattern:** Conventional commits — `type: description`
Allowed types: `feat, fix, hotfix, docs, test, chore, refactor, style, perf, build, ci, revert`
Optional scope: `feat(orders): add validation`

| Guardrail | Where |
|---|---|
| Commit message must be non-empty | `git.py:commit_changes` |
| Commit message must match conventional format | `git.py:commit_changes` |

---

### 6. PR Merge Safety

**Purpose:** Only merge agent-created PRs, and only when safe.

| Guardrail | Where | What it blocks |
|---|---|---|
| PR must be open (not merged, not closed) | `github.py:merge_pr` | Re-merging or merging a closed PR |
| PR must be mergeable (no conflicts) | `github.py:merge_pr` | Merging when GitHub reports conflicts |
| PR branch must end with `-agent` suffix | `github.py:merge_pr` | Accidentally merging a human's manual PR |
| `merge_pr` is NOT a `@tool` | `github.py:merge_pr` | LLM cannot trigger merge — orchestrator only, after HITL approval |
| `close_issue` is NOT a `@tool` | `github.py:close_issue` | LLM cannot close issues — orchestrator only, after merge |

---

### 7. PR Close Safety

**Purpose:** Ensure closed PRs always have an audit trail.

| Guardrail | Where |
|---|---|
| Cannot close an already-merged PR | `github.py:close_pr` |
| Cannot close an already-closed PR | `github.py:close_pr` |
| Reason must be non-empty | `github.py:close_pr` |
| Reason posted as comment before closing | `github.py:close_pr` (behavior) |

---

### 8. Required Fields

**Purpose:** Prevent empty or meaningless GitHub artifacts.

| Guardrail | Where |
|---|---|
| Issue title must be non-empty | `github.py:create_issue` |
| Issue body must be non-empty | `github.py:create_issue` |
| Comment on issue must be non-empty | `github.py:add_comment_to_issue` |
| Comment on task must be non-empty | `github_project_board.py:add_comment_to_task` |
| `update_pr` requires at least one of title/body | `github.py:update_pr` |
| `update_task` requires at least one of title/body | `github_project_board.py:update_task` |
| Board column must exist in `project.yml board_columns` | `github_project_board.py:move_task` |

---

### 9. Sensitive File Protection

**Purpose:** Never write to files that could contain secrets or damage the system.

Implemented in `guardrails/write_files.py:authorize_write()` and applied by
`codebase.py:write_file`. Blocks:

- Path traversal attempts (`../../.env`)
- Sensitive filenames (`.env`, `credentials.json`, `id_rsa`)
- Sensitive extensions (`.pem`, `.key`)
- Paths containing sensitive words (`secret`, `token`, `private_key`)
- Creating new files (only allows updating existing files)

---

### 10. Test Command Safety

**Purpose:** Prevent the LLM from running arbitrary shell via `run_tests`.

| Guardrail | Where |
|---|---|
| Command must start with `pytest` | `codebase.py:run_tests` |
| Flags allowlisted: `{-q, -v, -x, -s, -vv}` — all others rejected | `codebase.py:run_tests` |
| Non-flag args must be relative paths inside repo (no absolute, no `..`) | `codebase.py:run_tests` |

---

### 11. Local Git Safety

**Purpose:** Prevent local git state from being corrupted.

| Guardrail | Where |
|---|---|
| Commit fails if no changes staged | `git.py:commit_changes` |
| Merge conflicts detected → merge aborted + human alerted | `git.py:sync_with_main` |

---

## Guardrails Deferred to Orchestrator Logic

These are policy checks that cannot be enforced at the tool level because they
depend on state across multiple tool calls:

- **Tests must pass before merge** — orchestrator tracks last test result and
  refuses to call `merge_pr` if tests failed
- **Max retry limits** — orchestrator counts test failures and human rejections,
  stops the pipeline after N attempts
- **Feasibility check** — orchestrator runs this before starting the pipeline

---

## Design Principles

1. **Guardrails run before the action, not after.** No cleanup on failure.
2. **Guardrails are deterministic.** No LLM involved in the check.
3. **Guardrails have clear error messages.** The agent sees why it was blocked
   and can decide how to proceed.
4. **Guardrails are defense in depth.** Multiple layers protect the same thing
   (e.g. branch protection is enforced in `write_file`, `commit_changes`,
   `push_branch`, and `create_pr`).
5. **Hardcoded safety nets exist alongside config-driven checks.** `main` and
   `master` are always protected even if `project.yml` says otherwise.
6. **Some tools are not `@tool`** — the LLM can only call what we expose.
   `merge_pr` and `close_issue` are plain functions the orchestrator calls
   after HITL approval, so the LLM has no path to trigger them directly.
