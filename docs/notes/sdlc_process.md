# GitHub Agentic SDLC — End-to-End Process

This document defines the full lifecycle of a task through the agentic SDLC pipeline.
It is the authoritative reference for which steps exist, in what order, and what the
success and failure paths are.

---

## Configuration

Every project has a `project.yml` file at its root:

```
source/
└── codeatlas/
    └── ecommerce/
        ├── project.yml          ← GitHub URLs + board config for this project
        ├── inventory_service/
        └── order_service/
```

The orchestrator loads this file once at the start of every task. All GitHub tools
read from it — no hardcoded URLs anywhere in the code. Secrets (GITHUB_TOKEN) stay
in `.env`. URLs and column names go in `project.yml`.

---

## The Sequence

```
1.  Requirement
      └── User provides a feature request, bug report, or task description
      └── Orchestrator loads project.yml — repo URLs, board URL, column names

2.  Open task in board (Backlog)
      └── Create a GitHub issue from the requirement
      └── Issue is placed in the Backlog column

3.  Understand the issue
      └── Parse title, description, acceptance criteria
      └── Identify the affected area of the codebase

4.  Move task in board (Ready)
      └── Issue is understood and clearly defined — ready to be worked on

5.  Check if it is possible to resolve
      └── Feasibility check: is the code reachable? is the request in scope?
      └── If not feasible: flag to human and stop

6.  Move task in board (In Progress)
      └── Work is beginning

7.  Create branch
      └── Naming convention: feat/issue-{number}-{short-title}
      └── Example: feat/issue-42-add-validation

8.  Analyse
      └── Search the codebase to understand what needs to change and where
      └── Identify affected files, functions, and dependencies

9.  Code
      └── Make the change — read the file, write the updated version

10. Test
      └── Run the test suite
      └── IF FAIL → fix code → re-test
          Retry up to 3 times
          IF STILL FAILING after 3 attempts → flag to human and stop
      └── IF PASS → continue

11. Commit
      └── Commit the changes with a descriptive message

12. Push
      └── Push the branch to the remote

13. Create PR
      └── Open a pull request from the feature branch to main
      └── PR body includes "Closes #{issue_number}" — GitHub auto-links PR to issue
      └── Add a comment on the issue with the PR URL — visible on the board card
      └── Board task now shows the linked PR for team navigation

14. Agent review
      └── AI reads the PR diff
      └── Checks for correctness, test coverage, naming, obvious bugs
      └── IF ISSUES FOUND → fix → re-test → re-commit → re-push → PR updates automatically
      └── IF APPROVED by agent → continue

15. Move task in board (In Review)
      └── PR is clean and agent-approved — now ready for human eyes

16. Human interaction — APPROVE or REJECT?
      └── Share PR URL with the user
      └── Ask: approve and merge, or reject?
      └── IF REJECT → human provides feedback reason
                    → go back to step 9 (Code) with that feedback
                    → re-test → re-commit → re-push → agent re-reviews
      └── IF APPROVE → continue

17. Merge PR
      └── Approve and merge the pull request into main

18. Close GitHub issue
      └── Close the issue linked to this task

19. Move task in board (Done)
      └── Task is complete

20. (Optional) Delete feature branch
      └── Clean up the remote branch after merge
```

---

## Board States

| Board Column | Entered When |
|---|---|
| Backlog | Issue is created (step 2) |
| Ready | Issue is understood and feasible (step 4) |
| In Progress | Work begins — branch created (step 6) |
| In Review | PR created, agent-approved, awaiting human (step 15) |
| Done | PR merged, issue closed (step 19) |

---

## Failure and Retry Paths

| Failure Point | What Happens |
|---|---|
| Feasibility check fails (step 5) | Flag to human, stop pipeline |
| Tests fail (step 10) | Fix code, re-test — up to 3 retries |
| Tests still failing after 3 retries | Flag to human, stop pipeline |
| Agent review finds issues (step 14) | Fix, re-test, re-commit, re-push, re-review |
| Human rejects PR (step 16) | Return to Code (step 9) with human's feedback |

---

## New Tools Required

These tools do not exist yet and will be built as part of the upcoming iterations:

| Tool | Purpose |
|---|---|
| `load_project_config(project)` | Load `project.yml` — repo URLs, board URL, column names |
| *(future)* `clone_repo` / `crawl` / `chunk` / `load_neo4j` | Setup Agent — bootstrap a new project from `project.yml`. Deferred — crawlers/chunkers/neo4j_loader already work as CLI scripts. |
| `create_issue(title, body)` | Open a GitHub issue |
| `update_board_status(issue, column)` | Move an issue card on the project board |
| `create_branch(name)` | Create and push a new branch |
| `commit_changes(message)` | Stage and commit all changes |
| `push_branch(branch)` | Push the branch to remote |
| `create_pr(title, body, branch)` | Open a pull request (body includes "Closes #{issue_number}") |
| `add_comment_to_issue(issue_number, comment)` | Post PR URL as a comment on the issue — visible on board card |
| `get_pr_diff(pr_number)` | Read the PR diff for agent review |
| `approve_and_merge(pr_number)` | Approve and merge the PR |
| `close_issue(issue_number)` | Close the GitHub issue |
| `delete_branch(branch)` | Delete the remote branch after merge |
