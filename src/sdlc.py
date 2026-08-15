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
from src.tools.github_project_board import add_issue_to_board, move_task, close_task, add_comment_to_task
from src.tools.git import checkout_main, pull_main, checkout_branch
from src.hitl.approve_pr import request_pr_approval
from src.agents.analyst import run_analyst
from src.agents.coder import run_coder
from src.agents.reviewer import run_reviewer
from src.agents.synthesizer import synthesize

load_dotenv()

# Maximum times the coder retries after reviewer rejection
MAX_REVIEWER_REJECTIONS = 2
# Maximum times the coder retries after human rejection at HITL
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

        self._move_board("backlog")
        print(f"Board     : {self.config['github']['project_board_url']}")

    def _move_board(self, column: str):
        """Moves the issue card to the given board column. Used at every board transition."""
        move_task.invoke({
            "project":      self.project,
            "issue_number": self.state.github_issue,
            "column":       column,
        })
        print(f"Issue #{self.state.github_issue} → {column.replace('_', ' ').title()}")

    def _close_issue(self, comment: str):
        """
        Posts a comment on the GitHub issue then closes it.
        The comment is the synthesized final response — visible to anyone reading the issue.
        """
        add_comment_to_issue.invoke({
            "project":      self.project,
            "issue_number": self.state.github_issue,
            "comment":      comment,
        })
        print(f"Comment posted on issue #{self.state.github_issue}")

        close_issue(project=self.project, issue_number=self.state.github_issue)
        print(f"Issue #{self.state.github_issue} closed")

    def _close_task_on_board(self, comment: str):
        """
        Posts a comment on the board task, moves it to Done, then archives it.
        The board task and the GitHub issue are two separate things — each gets its own close.
        """
        add_comment_to_task.invoke({
            "project":      self.project,
            "issue_number": self.state.github_issue,
            "comment":      comment,
        })

        self._move_board("done")

        close_task.invoke({
            "project":      self.project,
            "issue_number": self.state.github_issue,
        })
        print(f"Board task #{self.state.github_issue} archived")

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
        print(f"Branch type    : {analysis['branch_type']}")
        print(f"Branch title   : {analysis['branch_title']}")
        print(f"Summary        : {analysis['summary']}")

    def _create_branch(self):
        """
        Assembles the branch name from analyst output, creates it on GitHub,
        then checks it out locally on top of a fresh pull from main.
        """
        branch = (
            f"{self.state.analysis['branch_type']}"
            f"/issue-{self.state.github_issue}"
            f"-{self.state.analysis['branch_title']}"
            f"-agent"
        )
        self.state.branch = branch
        print(f"\n--- Step 4: Create branch ({branch}) ---")

        # Ensure local repo starts from a clean, up-to-date main
        checkout_main.invoke({"project": self.project, "repo": self.state.repo})
        pull_main.invoke({"project": self.project, "repo": self.state.repo})

        # Create the branch on GitHub (remote)
        create_branch.invoke({
            "project":     self.project,
            "repo":        self.state.repo,
            "branch_name": branch,
        })

        # Checkout the branch locally so the coder writes to the right branch
        checkout_branch.invoke({
            "project":     self.project,
            "repo":        self.state.repo,
            "branch_name": branch,
        })

        print(f"Branch ready : {branch}")

    def _run_coder(self, feedback: str = None):
        """
        Runs the coder agent. Saves files_modified and coder_result to state.
        feedback — human rejection reason from a previous HITL step.
                   None on the first run, populated on rework.
        """
        print("\n--- Step 5: Coder ---")

        result = run_coder(
            project=self.project,
            repo=self.state.repo,
            branch=self.state.branch,
            requirement=self.requirement,
            files_to_change=self.state.analysis["files_to_change"],
            feedback=feedback,
        )

        self.state.files_modified = result.get("files_modified", [])
        self.state.coder_result   = result

        print(f"Status         : {result['status']}")
        print(f"Files modified : {result['files_modified']}")
        for i, commit in enumerate(result.get("commits", []), 1):
            print(f"  Commit {i}     : {commit['message']}")
            print(f"  Changes      : {commit['changes']}")
            print(f"  Tests        : {commit['test_results']}")

    def _create_pr(self):
        """
        Opens a pull request from the feature branch to main.
        Posts the PR URL as a comment on the issue for team visibility.
        Saves pr_number to state.
        """
        print("\n--- Step 6: Create PR ---")

        # Build PR body from analyst summary + coder commits
        commits_text = "\n".join(
            f"- {c['message']}" for c in self.state.coder_result.get("commits", [])
        )
        body = (
            f"**Requirement:**\n{self.requirement}\n\n"
            f"**Analysis:**\n{self.state.analysis['summary']}\n\n"
            f"**Commits:**\n{commits_text}\n\n"
            f"Closes #{self.state.github_issue}"
        )

        pr = create_pr.invoke({
            "project": self.project,
            "repo":    self.state.repo,
            "title":   self.requirement,
            "body":    body,
            "branch":  self.state.branch,
        })

        self.state.pr_number = pr["pr_number"]
        print(f"PR #{self.state.pr_number} created: {pr['url']}")

        # Post PR link as a comment on the issue so it's visible on the board card
        add_comment_to_issue.invoke({
            "project":      self.project,
            "issue_number": self.state.github_issue,
            "comment":      f"Pull request opened: {pr['url']}",
        })
        print(f"PR link posted on issue #{self.state.github_issue}")

    def _run_reviewer(self):
        """
        Runs the reviewer agent on the current PR.
        Saves review_result (approved/rejected + reason) to state.
        """
        print("\n--- Step 7: Reviewer ---")

        result = run_reviewer(
            project=self.project,
            repo=self.state.repo,
            pr_number=self.state.pr_number,
            requirement=self.requirement,
        )

        self.state.review_result = result
        print(f"Status : {result['status']}")
        print(f"Reason : {result['reason']}")

    def _hitl(self):
        """
        Blocks and waits for the human to APPROVE or REJECT the PR.
        Saves human_approval (approved bool + reason) to state.
        """
        print("\n--- Step 9: Human approval ---")

        # Build URLs from config so the human has clickable references
        owner       = self.config["github"]["owner"]
        repo        = self.state.repo
        issue_repo  = self.config["github"]["issues_repo"]
        pr_url      = f"https://github.com/{owner}/{repo}/pull/{self.state.pr_number}"
        branch_url  = f"https://github.com/{owner}/{repo}/tree/{self.state.branch}"
        issue_url   = f"https://github.com/{owner}/{issue_repo}/issues/{self.state.github_issue}"
        board_url   = self.config["github"]["project_board_url"]

        # Build a short summary of what was done for the human to see
        commits_text = "\n".join(
            f"  - {c['message']}" for c in self.state.coder_result.get("commits", [])
        )
        summary = (
            f"Requirement: {self.requirement}\n\n"
            f"Analyst summary:\n{self.state.analysis['summary']}\n\n"
            f"Commits made by coder:\n{commits_text}\n\n"
            f"Reviewer verdict: {self.state.review_result['status']}\n"
            f"Reviewer notes: {self.state.review_result['reason']}"
        )

        self.state.human_approval = request_pr_approval(
            summary=summary,
            files_changed=self.state.files_modified,
            pr_url=pr_url,
            branch_url=branch_url,
            issue_url=issue_url,
            board_url=board_url,
        )

    def _synthesize(self, results: list) -> str:
        """
        Calls the synthesizer to produce one clean final response from step results.
        Returns the synthesized text — used as the comment on the issue and board task.
        """
        return synthesize(task=self.requirement, results=results)

    def _merge_and_close(self):
        """
        Merges the PR into main, then closes the issue and archives the board task.
        Called only after human approval.
        """
        print("\n--- Step 10: Merge and close ---")

        # Merge — plain function, LLM can never trigger this
        merge_result = merge_pr(
            project=self.project,
            repo=self.state.repo,
            pr_number=self.state.pr_number,
        )
        print(f"PR #{self.state.pr_number} merged (sha: {merge_result.get('sha', 'n/a')})")

        # Synthesize the final response covering the whole pipeline
        self.state.final_response = self._synthesize([
            {"step_id": 1, "action": "Investigate codebase",     "result": self.state.analysis["summary"]},
            {"step_id": 2, "action": "Implement change + tests", "result": str(self.state.coder_result.get("commits", []))},
            {"step_id": 3, "action": "Agent review",             "result": self.state.review_result["reason"]},
            {"step_id": 4, "action": "Human approval",           "result": "approved and merged"},
        ])

        # Close the issue and archive the board task with the synthesized comment
        self._close_issue(comment=self.state.final_response)
        self._close_task_on_board(comment=self.state.final_response)

        # Optional cleanup — delete the feature branch on GitHub
        try:
            delete_branch.invoke({
                "project":     self.project,
                "repo":        self.state.repo,
                "branch_name": self.state.branch,
            })
            print(f"Branch {self.state.branch} deleted")
        except Exception as e:
            print(f"Branch delete skipped: {e}")

        self.state.status = "done"

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

        status = self.state.analysis["status"]

        if status != "feasible":
            # Early stop — analyst said already_implemented or not_feasible
            self.state.final_response = self._synthesize([{
                "step_id": 1,
                "action":  "Investigate codebase",
                "result":  self.state.analysis["summary"],
            }])
            self._close_issue(comment=self.state.final_response)
            self._close_task_on_board(comment=self.state.final_response)
            self.state.status = "stopped"
            return self.state

        # status == "feasible" — continue to coder and reviewer
        self._move_board("ready")
        self._move_board("in_progress")
        self._create_branch()
        self._run_coder()

        # If coder failed after retries — stop pipeline cleanly
        if self.state.coder_result["status"] == "failed":
            last_commit = self.state.coder_result.get("commits", [{}])[-1]
            self.state.final_response = self._synthesize([{
                "step_id": 1,
                "action":  "Implement code change",
                "result":  last_commit.get("changes", "Coder failed — see commits for details"),
            }])
            self._close_issue(comment=self.state.final_response)
            self._close_task_on_board(comment=self.state.final_response)
            self.state.status = "failed"
            return self.state

        # Happy path — code committed and pushed, open PR
        self._create_pr()

        # ── Reviewer loop ────────────────────────────────────────────────────
        # Reviewer rejects → send feedback back to coder → new commits → re-review
        # Max attempts capped by MAX_REVIEWER_REJECTIONS
        reviewer_rejections = 0
        while True:
            self._run_reviewer()
            if self.state.review_result["status"] == "approved":
                break
            reviewer_rejections += 1
            if reviewer_rejections > MAX_REVIEWER_REJECTIONS:
                print(f"\nReviewer rejected {reviewer_rejections} times — stopping pipeline.")
                self.state.final_response = self._synthesize([{
                    "step_id": 1,
                    "action":  "Agent review",
                    "result":  self.state.review_result["reason"],
                }])
                self._close_issue(comment=self.state.final_response)
                self._close_task_on_board(comment=self.state.final_response)
                self.state.status = "failed"
                return self.state
            # Rework — coder addresses reviewer feedback, then loop back to re-review
            print(f"\nReviewer rejected — sending back to coder (attempt {reviewer_rejections})")
            self._run_coder(feedback=self.state.review_result["reason"])

        # ── Board move + HITL loop ───────────────────────────────────────────
        # Move to In Review only after agent has approved — the board should
        # only show In Review when a human-ready PR actually exists
        self._move_board("in_review")

        human_rejections = 0
        while True:
            self._hitl()
            if self.state.human_approval.get("approved"):
                break
            human_rejections += 1
            if human_rejections > MAX_HUMAN_REJECTIONS:
                print(f"\nHuman rejected {human_rejections} times — stopping pipeline.")
                self.state.final_response = self._synthesize([{
                    "step_id": 1,
                    "action":  "Human approval",
                    "result":  self.state.human_approval.get("reason", "rejected"),
                }])
                self._close_issue(comment=self.state.final_response)
                self._close_task_on_board(comment=self.state.final_response)
                self.state.status = "failed"
                return self.state
            # Rework — coder addresses human feedback, re-review, then re-HITL
            print(f"\nHuman rejected — sending back to coder (attempt {human_rejections})")
            self._run_coder(feedback=self.state.human_approval["reason"])
            self._run_reviewer()   # re-review after rework before asking human again

        # ── Merge and close ──────────────────────────────────────────────────
        self._merge_and_close()

        return self.state


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: PYTHONPATH=. uv run python3 src/sdlc.py <project> "<requirement>"')
        sys.exit(1)

    project     = sys.argv[1]
    requirement = sys.argv[2]

    sdlc = SDLCPipeline(project=project, requirement=requirement)
    state = sdlc.run()
    # Always runs — print result and return state
    print(f"\n{'='*60}")
    print(f"PIPELINE RESULT")
    print(f"{'='*60}")
    print(state.final_response)

