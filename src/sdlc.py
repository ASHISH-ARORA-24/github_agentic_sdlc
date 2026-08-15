# SDLC Pipeline
#
# Runs the full GitHub SDLC lifecycle for one requirement.
#
# Designed as a class because the pipeline carries state across many steps
# and has retry loops (test failures, human rejection) where the same
# method needs to be called more than once cleanly.
#
# Public interface — one method:
#   pipeline = SDLCPipeline(project, requirement)
#   pipeline.run()
#
# Private methods (_prefix) — one per pipeline stage:
#   Each method reads from self.state and writes results back.
#   The orchestration logic lives only in run().
#
# Who does what:
#   SDLCPipeline methods  — call GitHub/git tools directly (no LLM)
#   _run_analyst()        — delegates to analyst agent (LLM reasoning)
#   _run_coder()          — delegates to coder agent (LLM reasoning)
#   _run_reviewer()       — delegates to reviewer agent (LLM reasoning)
#
# Usage:
#   PYTHONPATH=. uv run python3 src/sdlc.py codeatlas/ecommerce "Add validation to reserve_stock"

import sys
from dotenv import load_dotenv

from src.state import SDLCState
from src.tools.github import (
    load_project_config,
    create_issue,
    add_comment_to_issue,
    close_issue,
    create_branch,
    delete_branch,
    create_pr,
    merge_pr,
)
from src.tools.github_project_board import add_issue_to_board, move_task
from src.tools.git import checkout_main, pull_main, checkout_branch
from src.hitl.approve_pr import request_pr_approval
from src.agents.analyst import run_analyst

load_dotenv()

# Maximum times the coder retries after human rejection
MAX_HUMAN_REJECTIONS = 2


class SDLCPipeline:
    """
    Runs the full GitHub SDLC pipeline for one requirement.

    The pipeline is a fixed sequence of named steps.
    State accumulates in self.state as each step completes.
    Retry loops live in run() — they call the same private methods again.
    """

    def __init__(self, project: str, requirement: str):
        """
        Loads config and creates the initial state.
        No GitHub calls happen here — only setup.
        """
        self.project     = project
        self.requirement = requirement
        self.config      = load_project_config(project)
        self.state       = SDLCState(project=project, requirement=requirement)

        print(f"\n{'='*60}")
        print(f"SDLC PIPELINE")
        print(f"{'='*60}")
        print(f"Project     : {self.project}")
        print(f"Requirement : {self.requirement}")

    # ── Pipeline steps ────────────────────────────────────────────────────────

    def _create_issue(self):
        """Creates a GitHub issue from the requirement. Saves issue number to state."""
        print("\n--- Step 1: Create issue ---")

        issue = create_issue.invoke({
            "project": self.project,
            "title":   self.requirement,
            "body":    (
                f"**Requirement submitted via agent pipeline.**\n\n"
                f"{self.requirement}\n\n"
                f"_This issue was created automatically. "
                f"The analyst agent will add technical findings as a comment._"
            ),
        })

        self.state.github_issue = issue["issue_number"]
        print(f"Issue #{self.state.github_issue} created: {issue['url']}")

    def _add_to_board(self):
        """Adds the issue to the project board and moves it to Backlog."""
        print("\n--- Step 2: Add to board (Backlog) ---")

        add_issue_to_board.invoke({
            "project":      self.project,
            "issue_number": self.state.github_issue,
        })

        move_task.invoke({
            "project":      self.project,
            "issue_number": self.state.github_issue,
            "column":       "backlog",
        })

        board_url = self.config["github"]["project_board_url"]
        print(f"Issue #{self.state.github_issue} → Backlog")
        print(f"Board     : {board_url}")

    def _run_analyst(self):
        """
        Runs the analyst agent. Saves analysis (feasible, repo, files, summary) to state.
        After this, self.state.repo is known and self.state.analysis.feasible is set.
        """
        print("\n--- Step 3: Analyst ---")

        analysis = run_analyst(project=self.project, requirement=self.requirement)

        # Save the full analysis and pull repo up to state — everything after this reads state.repo
        self.state.analysis = analysis
        self.state.repo     = analysis["repo"]

        print(f"Status         : {analysis['status']}")
        print(f"Repo           : {analysis['repo']}")
        print(f"Files to change: {analysis['files_to_change']}")
        print(f"Summary        : {analysis['summary']}")

    def _create_branch(self):
        """
        Creates the remote feature branch and checks it out locally.
        Branch name follows convention: feat/issue-{number}-{slug}-agent
        """
        pass

    def _run_coder(self, feedback: str = None):
        """
        Runs the coder agent. Saves files_modified to state.
        feedback — human rejection reason from a previous HITL step.
                   None on the first run, populated on rework.
        """
        pass

    def _create_pr(self):
        """
        Opens a pull request from the feature branch to main.
        Posts the PR URL as a comment on the issue.
        Saves pr_number to state.
        """
        pass

    def _run_reviewer(self):
        """
        Runs the reviewer agent. Saves review_result (approved/rejected + reason) to state.
        """
        pass

    def _hitl(self):
        """
        Blocks and waits for human to APPROVE or REJECT.
        Saves human_approval (approved bool + reason) to state.
        """
        pass

    def _merge_and_close(self):
        """Merges the PR, closes the issue, moves board to Done, deletes branch."""
        pass

    # ── Orchestration ─────────────────────────────────────────────────────────

    def run(self) -> SDLCState:
        """
        Sequences all pipeline steps. Owns all retry loops.

        Retry loops:
          - Coder test failures    → handled inside the coder agent (max 3 retries)
          - Human rejection        → run() calls _run_coder(feedback) again (max 2 times)

        Returns the final state object.
        """
        self._create_issue()
        self._add_to_board()
        self._run_analyst()

        # Status check — only continue if analyst says feasible
        # already_implemented and not_feasible both stop the pipeline
        status = self.state.analysis["status"]
        if status != "feasible":
            print(f"\nPipeline stopped — {status}: {self.state.analysis['summary']}")
            self.state.status = "stopped"
            return self.state

        return self.state


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: PYTHONPATH=. uv run python3 src/sdlc.py <project> "<requirement>"')
        sys.exit(1)

    project     = sys.argv[1]
    requirement = sys.argv[2]

    sdlc = SDLCPipeline(project=project, requirement=requirement)
    sdlc.run()
