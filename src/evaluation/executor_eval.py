# Executor Evaluation
#
# Runs the executor agent against known test cases and scores the result.
#
# The executor is more interesting than the planner because it uses real tools.
# We can check: which tools were called, which files were touched, test results.
#
# Two layers:
#   1. Deterministic — checks the trace (tools called, files read/written, test results)
#   2. LLM Judge     — scores the quality of the final answer
#
# Usage:
#   PYTHONPATH=. uv run python3 src/evaluation/executor_eval.py

import json
from pathlib import Path

from src.agents.executor import run_agent
from src.evaluation.judge import judge

TEST_CASES_FILE = Path(__file__).parent / "test_cases.json"


def run_deterministic_checks(trace: dict, checks: dict) -> dict:
    """
    Checks the executor's trace against expected behaviour.
    Returns a dict of check_name → passed (bool).
    """
    results = {}

    # Did it call the required tools?
    if "must_call_tools" in checks:
        for required_tool in checks["must_call_tools"]:
            results[f"called_{required_tool}"] = required_tool in trace["tools_called"]

    # Did it read the expected files?
    if "expected_files_read" in checks:
        for expected_file in checks["expected_files_read"]:
            found = any(expected_file in f for f in trace["files_read"] if f)
            results[f"read_{expected_file}"] = found

    # Did it avoid writing files when it shouldn't?
    if checks.get("must_not_write_files"):
        results["no_file_writes"] = len(trace["files_written"]) == 0

    # Did it avoid running tests when it shouldn't?
    if checks.get("must_not_run_tests"):
        results["no_test_runs"] = len(trace["test_results"]) == 0

    # Did tests pass when they were run?
    if checks.get("must_pass_tests") and trace["test_results"]:
        results["tests_passed"] = all(r.get("passed") for r in trace["test_results"])

    return results


def evaluate_executor(test_case: dict) -> dict:
    """
    Runs one test case through the executor and evaluates the result.
    Returns deterministic scores + LLM judge scores.
    """
    project          = test_case["project"]
    task             = test_case["task"]
    expected_outcome = test_case["expected_outcome"]
    checks           = test_case.get("checks", {})

    print(f"\nTest case : {test_case['id']}")
    print(f"Task      : {task}")

    # Run the executor with trace capture
    output = run_agent(project=project, question=task, return_trace=True)
    answer = output["answer"]
    trace  = output["trace"]

    print(f"\nTools called : {trace['tools_called']}")
    print(f"Files read   : {trace['files_read']}")
    print(f"Files written: {trace['files_written']}")
    print(f"Test results : {trace['test_results']}")

    # Deterministic checks
    det_results = run_deterministic_checks(trace, checks)
    det_passed  = sum(1 for v in det_results.values() if v)
    det_score   = round((det_passed / len(det_results)) * 100) if det_results else 100

    print(f"\nDeterministic checks:")
    for check, passed in det_results.items():
        print(f"  {'✓' if passed else '✗'} {check}")
    print(f"  Score: {det_score}%")

    # LLM Judge
    llm_scores = judge(task=task, expected_outcome=expected_outcome, actual_output=answer)

    print(f"\nLLM Judge scores:")
    for dim, score in llm_scores.items():
        if dim != "reason":
            print(f"  {dim:20} : {score}/5")
    print(f"  Reason: {llm_scores.get('reason')}")

    return {
        "test_id":       test_case["id"],
        "task":          task,
        "trace":         trace,
        "answer":        answer,
        "deterministic": {"checks": det_results, "score": det_score},
        "llm_judge":     llm_scores,
    }


if __name__ == "__main__":
    test_cases     = json.loads(TEST_CASES_FILE.read_text())
    executor_cases = [tc for tc in test_cases if tc["agent"] == "executor"]

    print("=" * 60)
    print("EXECUTOR EVALUATION")
    print("=" * 60)

    results = [evaluate_executor(tc) for tc in executor_cases]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"\n{r['test_id']} — Deterministic: {r['deterministic']['score']}% | "
              f"LLM Overall: {r['llm_judge'].get('overall')}/5")
