# State
#
# State is a dictionary that lives for the duration of one task execution.
# It is created at the start, updated after every step, and gone when the task finishes.
#
# Why do we need it?
#   Each step runs its own agent. Without state, step 3 has no idea what step 1 found.
#   State is the shared memory that connects all steps together.
#
# State vs Memory:
#   State  = this task only  ("current step is 3, file found is stock_manager.py")
#   Memory = across all tasks ("this project uses pytest and snake_case")
#
# As the project grows, more fields will be added here:
#   github_issue, branch, files_modified, pr_number, review_result, human_approval
#   — each added in the iteration that needs it.


def create_state(project: str, task: str, plan: dict) -> dict:
    """
    Creates the initial state for a task execution.

    project — which codebase the agent is working on
    task    — the original user request (never changes)
    plan    — the structured plan produced by the planner agent
    """
    return {
        # Who and what
        "project":      project,
        "task":         task,

        # The plan from the planner agent
        "plan":         plan,

        # Execution tracking
        "current_step": 1,
        "results":      [],   # one entry added per completed step
        "status":       "planned",  # planned → in_progress → completed
    }


class SDLCState:
    """
    Holds all state for one SDLC pipeline run.

    Designed as a class so fields are named attributes — cleaner than dict keys,
    self-documenting, and impossible to typo silently.

    The user provides only project + requirement.
    Every other field starts as None and is filled in as the pipeline progresses.

    Field lifecycle:
      repo           — set by analyst agent (which service is affected)
      github_issue   — set after create_issue
      branch         — set after create_branch
      pr_number      — set after create_pr
      analysis       — set after analyst agent runs
      files_modified — set after coder agent runs
      review_result  — set after reviewer agent runs
      human_approval — set after HITL gate
    """

    def __init__(self, project: str, requirement: str):
        # Identity — provided by user, never change
        self.project     = project
        self.requirement = requirement

        # Filled by analyst — which service repo is affected
        self.repo: str = None

        # GitHub objects — filled as pipeline progresses
        self.github_issue: int = None    # issue number
        self.branch:       str = None    # feature branch name
        self.pr_number:    int = None    # pull request number

        # Agent outputs
        self.analysis:       dict = None   # {feasible, repo, files_to_change, summary}
        self.coder_result:   dict = None   # {status, files_modified, commit_message}
        self.files_modified: list = []     # file paths written by the coder
        self.review_result:  dict = None   # {status: approved|rejected, reason}
        self.human_approval: dict = None   # {approved: bool, reason: str}

        # Final synthesized response — set when pipeline ends (any path)
        self.final_response: str = None

        # Pipeline tracking
        self.status: str = "started"
        # started → analysing → coding → reviewing → awaiting_human
        # → merging → done | failed | stopped
