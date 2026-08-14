# Synthesizer
#
# The synthesizer has NO tools. It only uses the LLM to summarize.
#
# Job: take the completed state (all step results) and produce one
#      clean, coherent final answer that a developer can actually read.
#
# Why do we need it?
#   Each step produces its own raw output — search results, file contents,
#   test output, etc. By the end there are 6-9 separate results.
#   Nobody wants to read all of that. The synthesizer reads everything
#   and writes one clear summary: what was found, what was changed,
#   what was tested, what is the outcome.
#
# No tools — pure LLM reasoning over the accumulated state results.
#
# CodeAtlas comparison:
#   Same as agents/synthesizer.py in CodeAtlas.


from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.observability.tracer import new_trace, record_llm_call, finish_trace

load_dotenv()

SYNTHESIZER_SYSTEM_PROMPT = """
You are a senior software engineer writing a final summary of completed work.

You will receive:
- The original task
- The results from each step of the execution

Write a clear, concise summary that covers:
1. What was investigated and found
2. What change was made and where
3. What tests were run and whether they passed
4. The final outcome

Be specific — mention actual file names, method names, and test results.
Do not repeat raw output. Summarize it clearly for a developer to read.
"""


def synthesize(task: str, results: list[dict], obs: dict = None) -> str:
    """
    Takes the task and all step results from state and produces
    one clean final summary using the LLM.

    obs — optional shared observability trace from the orchestrator.
          If not provided, creates a standalone trace (for direct testing).
    """
    standalone = obs is None
    if standalone:
        obs = new_trace()

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    steps_text = "\n\n".join(
        f"Step {r['step_id']}: {r['action']}\nResult: {r['result']}"
        for r in results
    )

    prompt = f"""
Original task:
{task}

Step-by-step results:
{steps_text}
"""

    messages = [
        SystemMessage(SYNTHESIZER_SYSTEM_PROMPT),
        HumanMessage(prompt),
    ]

    response = llm.invoke(messages)
    record_llm_call(obs, response)      # ← record token usage + cost

    if standalone:
        finish_trace(obs)

    return response.content
