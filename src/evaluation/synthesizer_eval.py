# Synthesizer Evaluation
#
# Evaluates whether the synthesizer produces an accurate, grounded final answer
# from a set of known step results.
#
# Unlike the executor, we don't run the full pipeline here.
# We give the synthesizer KNOWN step results (from test_cases.json) and check
# if it accurately captures them — no hallucinations, no missing facts.
#
# Two layers:
#   1. Deterministic — does the answer mention key facts from the step results?
#   2. LLM Judge     — is it grounded, clear, complete, hallucination-free?
#
# Usage:
#   PYTHONPATH=. uv run python3 src/evaluation/synthesizer_eval.py

import json
from pathlib import Path

from src.agents.synthesizer import synthesize
from src.evaluation.judge import judge

TEST_CASES_FILE = Path(__file__).parent / "test_cases.json"


def run_deterministic_checks(answer: str, must_mention: list[str]) -> dict:
    """
    Checks that the synthesizer's answer mentions key facts from the step results.
    These are facts we KNOW should be in the answer because they are in the step results.
    If the answer doesn't mention them, the synthesizer missed or hallucinated something.
    """
    answer_lower = answer.lower()
    results = {}

    for keyword in must_mention:
        results[f"mentions_{keyword}"] = keyword.lower() in answer_lower

    return results


def evaluate_synthesizer(test_case: dict) -> dict:
    """
    Runs one test case through the synthesizer and evaluates the result.
    """
    task             = test_case["task"]
    expected_outcome = test_case["expected_outcome"]
    step_results     = test_case["step_results"]
    must_mention     = test_case.get("must_mention", [])

    print(f"\nTest case : {test_case['id']}")
    print(f"Task      : {task}")
    print(f"Steps     : {len(step_results)}")

    # Run the synthesizer with known step results
    answer = synthesize(task=task, results=step_results)

    print(f"\nSynthesizer output (first 400 chars):")
    print(answer[:400] + "..." if len(answer) > 400 else answer)

    # Deterministic checks — does the answer mention key facts?
    det_results = run_deterministic_checks(answer, must_mention)
    det_passed  = sum(1 for v in det_results.values() if v)
    det_score   = round((det_passed / len(det_results)) * 100) if det_results else 100

    print(f"\nDeterministic checks:")
    for check, passed in det_results.items():
        print(f"  {'✓' if passed else '✗'} {check}")
    print(f"  Score: {det_score}%")

    # LLM Judge — quality, groundedness, hallucination
    # We give the judge the step results as "context" so it can check groundedness
    context = "\n".join(
        f"Step {r['step_id']}: {r['action']}\nResult: {r['result']}"
        for r in step_results
    )
    llm_scores = judge(
        task=task,
        expected_outcome=f"{expected_outcome}\n\nStep results available:\n{context}",
        actual_output=answer,
    )

    print(f"\nLLM Judge scores:")
    for dim, score in llm_scores.items():
        if dim != "reason":
            print(f"  {dim:20} : {score}/5")
    print(f"  Reason: {llm_scores.get('reason')}")

    return {
        "test_id":       test_case["id"],
        "task":          task,
        "answer":        answer,
        "deterministic": {"checks": det_results, "score": det_score},
        "llm_judge":     llm_scores,
    }


if __name__ == "__main__":
    test_cases        = json.loads(TEST_CASES_FILE.read_text())
    synthesizer_cases = [tc for tc in test_cases if tc["agent"] == "synthesizer"]

    print("=" * 60)
    print("SYNTHESIZER EVALUATION")
    print("=" * 60)

    results = [evaluate_synthesizer(tc) for tc in synthesizer_cases]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"\n{r['test_id']} — Deterministic: {r['deterministic']['score']}% | "
              f"LLM Overall: {r['llm_judge'].get('overall')}/5")
