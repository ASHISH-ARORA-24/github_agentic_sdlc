# Orchestrator
#
# The orchestrator has NO LLM and NO tools.
# It is pure coordination logic — nothing more.
#
# Responsibilities:
#   1. Call the planner agent to get a structured plan
#   2. Create state to track progress
#   3. Execute each step by calling the agent
#   4. Update state after every step
#   5. Call the synthesizer to produce a clean final answer
#
# The orchestrator does NOT:
#   - Call any LLM directly
#   - Use any tools directly
#   - Know how the planner works internally
#   - Know how the agent works internally
#   It only knows: call planner → create state → loop → call agent → update state → synthesize
#
# Usage:
#   PYTHONPATH=. uv run python3 src/orchestrator.py "codeatlas/ecommerce" "Add validation to reserve_stock"

import sys
from src.planner_agent import create_plan
from src.state         import create_state
from src.agent         import run_agent
from src.synthesizer   import synthesize


def run_orchestrator(project: str, task: str) -> dict:
    """
    Runs the full planning + execution workflow for a task.

    project — which codebase to work on
    task    — what needs to be done

    Returns the final state with all step results and the final answer.
    """

    print(f"\n{'='*60}")
    print(f"ORCHESTRATOR")
    print(f"{'='*60}")
    print(f"Project : {project}")
    print(f"Task    : {task}")

    # ── Step 1: Plan ──────────────────────────────────────────────────────────
    # Ask the planner agent to break the task into steps.
    # The orchestrator doesn't call an LLM here — planner_agent does that.
    print("\n--- Planning ---")
    plan = create_plan(task)

    print(f"Goal  : {plan['goal']}")
    print(f"Steps :")
    for step in plan["steps"]:
        print(f"  {step['id']}. {step['action']}")

    # ── Step 2: Create State ──────────────────────────────────────────────────
    # State holds the plan, tracks current step, and accumulates results.
    state = create_state(project=project, task=task, plan=plan)
    state["status"] = "in_progress"

    # ── Step 3: Execute each step ─────────────────────────────────────────────
    # Orchestrator loops through steps. For each step:
    #   - Extracts what the agent needs from state (no state dict passed to agent)
    #   - Calls the agent with project + step instruction
    #   - Saves the result back into state
    print(f"\n--- Executing {len(plan['steps'])} steps ---")

    for step in plan["steps"]:
        step_id     = step["id"]
        step_action = step["action"]

        print(f"\nStep {step_id}: {step_action}")

        # Build context from previous results so each step knows what was found before
        context = ""
        if state["results"]:
            previous = "\n".join(
                f"Step {r['step_id']} result: {r['result'][:300]}"
                for r in state["results"]
            )
            context = f"\n\nContext from previous steps:\n{previous}"

        # Call the agent — no state dict passed, just project + question
        question = step_action + context
        result   = run_agent(project=project, question=question)

        # Orchestrator updates state — agent never touches state directly
        state["results"].append({
            "step_id": step_id,
            "action":  step_action,
            "result":  result,
        })
        state["current_step"] = step_id + 1

        print(f"Done.")

    # ── Step 4: Synthesize ────────────────────────────────────────────────────
    # Ask the synthesizer to produce one clean final answer from all step results.
    # The orchestrator doesn't call an LLM here — synthesizer does that.
    print("\n--- Synthesizing final answer ---")
    final_answer = synthesize(task=task, results=state["results"])
    state["final_answer"] = final_answer
    state["status"]       = "completed"

    print(f"\n{'='*60}")
    print(f"FINAL ANSWER")
    print(f"{'='*60}")
    print(final_answer)

    return state


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: PYTHONPATH=. uv run python3 src/orchestrator.py <project> "<task>"')
        sys.exit(1)

    project = sys.argv[1]
    task    = sys.argv[2]

    run_orchestrator(project=project, task=task)
