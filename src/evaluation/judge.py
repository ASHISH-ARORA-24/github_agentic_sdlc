# LLM Judge — shared across all agent evaluations
#
# Uses an LLM to score qualities that deterministic code cannot measure:
# correctness, logical order, specificity, groundedness, hallucination.
#
# The judge is a separate LLM call with a strict system prompt.
# It reads the task, the output, and the expected outcome — then scores.

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

JUDGE_SYSTEM_PROMPT = """
You are an evaluation judge for an AI software engineering system.

You will receive:
- The original task
- The expected outcome
- The actual output from an agent

Score each dimension from 0 to 5:
  correctness:  Does the output correctly address the task?
  quality:      Is the output specific, well-structured, and actionable?
  logical_order: Are steps or content in a logical sequence?
  hallucination: 5 = no invented facts. 0 = major hallucinations.

Return JSON only:
{
  "correctness": 0,
  "quality": 0,
  "logical_order": 0,
  "hallucination": 0,
  "overall": 0,
  "reason": "one sentence explanation"
}
"""


def judge(task: str, expected_outcome: str, actual_output: str) -> dict:
    """
    Asks an LLM to score the quality of an agent's output.
    Returns scores for correctness, quality, logical_order, hallucination.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = json.dumps({
        "task":             task,
        "expected_outcome": expected_outcome,
        "actual_output":    actual_output,
    }, indent=2)

    response = llm.invoke([
        SystemMessage(JUDGE_SYSTEM_PROMPT),
        HumanMessage(prompt),
    ])

    return json.loads(response.content)
