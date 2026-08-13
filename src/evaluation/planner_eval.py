# Planner Evaluation
#
# Runs the planner against known test cases and scores the result.
#
# Two layers:
#   1. Deterministic — code checks the plan structure
#   2. LLM Judge     — scores the quality of the plan
#
# Usage:
#   PYTHONPATH=. uv run python3 src/evaluation/planner_eval.py

import json
from pathlib import Path

from src.agents.planner import create_plan
from src.evaluation.judge import judge

TEST_CASES_FILE = Path(__file__).parent / "test_cases.json"

# Keywords that indicate investigation steps
INVESTIGATE_KEYWORDS = {"search", "find", "locate", "look", "read", "review", "check", "identify"}

# Keywords that indicate modification steps
MODIFY_KEYWORDS = {"add", "modify", "implement", "update", "change", "write", "create"}

# Keywords that indicate test steps
TEST_KEYWORDS = {"test", "run", "verify", "validate", "ensure", "confirm"}


def check_investigation_before_modification(steps: list[dict]) -> bool:
    """
    Checks that the FIRST investigation step comes before the FIRST modification step.
    Uses first_investigate (not last) — otherwise late search steps (e.g. "search for tests")
    would incorrectly overwrite the position and produce a false failure.
    """
    first_investigate = len(steps)
    first_modify      = len(steps)

    for i, step in enumerate(steps):
        action = step["action"].lower()
        if any(kw in action for kw in INVESTIGATE_KEYWORDS):
            first_investigate = min(first_investigate, i)
        if any(kw in action for kw in MODIFY_KEYWORDS):
            first_modify = min(first_modify, i)

    return first_investigate < first_modify or first_modify == len(steps)


def check_has_test_step(steps: list[dict]) -> bool:
    """Checks that at least one step involves testing."""
    return any(
        any(kw in step["action"].lower() for kw in TEST_KEYWORDS)
        for step in steps
    )


def run_deterministic_checks(plan: dict, checks: dict) -> dict:
    """
    Runs all deterministic checks against the plan.
    Returns a dict of check_name → passed (bool).
    """
    steps = plan.get("steps", [])

    results = {}

    # Check minimum steps
    min_steps = checks.get("min_steps", 3)
    results["min_steps"] = len(steps) >= min_steps

    # Check investigation before modification
    if checks.get("must_investigate_before_modify"):
        results["investigate_before_modify"] = check_investigation_before_modification(steps)

    # Check test step exists
    if checks.get("must_have_test_step"):
        results["has_test_step"] = check_has_test_step(steps)

    # Check plan has a goal
    results["has_goal"] = bool(plan.get("goal", "").strip())

    return results


def evaluate_planner(test_case: dict) -> dict:
    """
    Runs one test case through the planner and evaluates the result.
    Returns deterministic scores + LLM judge scores.
    """
    task             = test_case["task"]
    expected_outcome = test_case["expected_outcome"]
    checks           = test_case.get("checks", {})

    print(f"\nTest case : {test_case['id']}")
    print(f"Task      : {task}")

    # Run the planner
    plan = create_plan(task)

    print(f"Goal      : {plan.get('goal')}")
    print(f"Steps     : {len(plan.get('steps', []))}")

    # Deterministic checks
    det_results = run_deterministic_checks(plan, checks)
    det_passed  = sum(1 for v in det_results.values() if v)
    det_score   = round((det_passed / len(det_results)) * 100) if det_results else 0

    print(f"\nDeterministic checks:")
    for check, passed in det_results.items():
        print(f"  {'✓' if passed else '✗'} {check}")
    print(f"  Score: {det_score}%")

    # LLM Judge
    plan_text = f"Goal: {plan.get('goal')}\n\nSteps:\n" + "\n".join(
        f"{s['id']}. {s['action']}" for s in plan.get("steps", [])
    )
    llm_scores = judge(task=task, expected_outcome=expected_outcome, actual_output=plan_text)

    print(f"\nLLM Judge scores:")
    for dim, score in llm_scores.items():
        if dim != "reason":
            print(f"  {dim:20} : {score}/5")
    print(f"  Reason: {llm_scores.get('reason')}")

    return {
        "test_id":        test_case["id"],
        "task":           task,
        "plan":           plan,
        "deterministic":  {"checks": det_results, "score": det_score},
        "llm_judge":      llm_scores,
    }


if __name__ == "__main__":
    test_cases = json.loads(TEST_CASES_FILE.read_text())
    planner_cases = [tc for tc in test_cases if tc["agent"] == "planner"]

    print("=" * 60)
    print("PLANNER EVALUATION")
    print("=" * 60)

    results = [evaluate_planner(tc) for tc in planner_cases]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"\n{r['test_id']} — Deterministic: {r['deterministic']['score']}% | "
              f"LLM Overall: {r['llm_judge'].get('overall')}/5")
