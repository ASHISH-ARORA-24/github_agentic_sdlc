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
