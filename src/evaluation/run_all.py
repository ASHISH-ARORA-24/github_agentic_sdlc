# Run All Evaluations
#
# Runs evaluation for all three agents — planner, executor, synthesizer —
# then passes all results to the synthesizer to produce one final evaluation report.
#
# Why use the synthesizer for the report?
#   The synthesizer already does exactly one thing: take multiple results and
#   produce one clean human-readable summary. Evaluation results are just
#   another type of results to summarize. No new code needed.
#
# Usage:
#   PYTHONPATH=. uv run python3 src/evaluation/run_all.py

import json
from pathlib import Path

from src.evaluation.planner_eval     import evaluate_planner
from src.evaluation.executor_eval    import evaluate_executor
from src.evaluation.synthesizer_eval import evaluate_synthesizer
from src.agents.synthesizer          import synthesize

TEST_CASES_FILE = Path(__file__).parent / "test_cases.json"


def format_planner_result(result: dict) -> str:
    """Formats one planner evaluation result into a readable string."""
    det   = result["deterministic"]
    judge = result["llm_judge"]
    checks = ", ".join(
        f"{'✓' if v else '✗'} {k}" for k, v in det["checks"].items()
    )
    return (
        f"Task: {result['task']}\n"
        f"Deterministic: {det['score']}% ({checks})\n"
        f"LLM Judge: {judge.get('overall')}/5 — {judge.get('reason')}"
    )


def format_executor_result(result: dict) -> str:
    """Formats one executor evaluation result into a readable string."""
    det   = result["deterministic"]
    judge = result["llm_judge"]
    trace = result["trace"]
    return (
        f"Task: {result['task']}\n"
        f"Tools called: {trace['tools_called']}\n"
        f"Files written: {trace['files_written']}\n"
        f"Deterministic: {det['score']}%\n"
        f"LLM Judge: {judge.get('overall')}/5 — {judge.get('reason')}"
    )


def format_synthesizer_result(result: dict) -> str:
    """Formats one synthesizer evaluation result into a readable string."""
    det   = result["deterministic"]
    judge = result["llm_judge"]
    checks = ", ".join(
        f"{'✓' if v else '✗'} {k}" for k, v in det["checks"].items()
    )
    return (
        f"Task: {result['task']}\n"
        f"Deterministic: {det['score']}% ({checks})\n"
        f"LLM Judge: {judge.get('overall')}/5 — {judge.get('reason')}"
    )


def run_all() -> str:
    """
    Runs all agent evaluations and returns a final synthesized report.
    """
    test_cases = json.loads(TEST_CASES_FILE.read_text())

    planner_cases     = [tc for tc in test_cases if tc["agent"] == "planner"]
    executor_cases    = [tc for tc in test_cases if tc["agent"] == "executor"]
    synthesizer_cases = [tc for tc in test_cases if tc["agent"] == "synthesizer"]

    # ── Run all evaluations ───────────────────────────────────────────────────

    print("=" * 60)
    print("RUNNING ALL EVALUATIONS")
    print("=" * 60)

    print("\n--- PLANNER ---")
    planner_results = [evaluate_planner(tc) for tc in planner_cases]

    print("\n--- EXECUTOR ---")
    executor_results = [evaluate_executor(tc) for tc in executor_cases]

    print("\n--- SYNTHESIZER ---")
    synthesizer_results = [evaluate_synthesizer(tc) for tc in synthesizer_cases]

    # ── Format results as step results for the synthesizer ────────────────────
    # We reuse the synthesizer's existing interface — it takes a list of
    # {step_id, action, result} dicts. We just format our evaluation findings
    # into that shape.

    step_results = []

    step_results.append({
        "step_id": 1,
        "action":  f"Planner evaluation — {len(planner_results)} test case(s)",
        "result":  "\n\n".join(format_planner_result(r) for r in planner_results),
    })

    step_results.append({
        "step_id": 2,
        "action":  f"Executor evaluation — {len(executor_results)} test case(s)",
        "result":  "\n\n".join(format_executor_result(r) for r in executor_results),
    })

    step_results.append({
        "step_id": 3,
        "action":  f"Synthesizer evaluation — {len(synthesizer_results)} test case(s)",
        "result":  "\n\n".join(format_synthesizer_result(r) for r in synthesizer_results),
    })

    # ── Synthesize the final report ───────────────────────────────────────────

    print("\n--- GENERATING FINAL REPORT ---")

    report = synthesize(
        task=(
            "Produce a final evaluation report for the GitHub Agentic SDLC system. "
            "Summarize how each agent performed, highlight any weaknesses found, "
            "and give an overall assessment of the system quality."
        ),
        results=step_results,
    )

    print("\n" + "=" * 60)
    print("FINAL EVALUATION REPORT")
    print("=" * 60)
    print(report)

    return report


if __name__ == "__main__":
    run_all()
