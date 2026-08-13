# Iteration 1 — LangChain Model Abstraction
#
# This file demonstrates the LangChain way of talking to an LLM.
#
# CodeAtlas did this manually:
#   client = OpenAI()
#   response = client.chat.completions.create(model=..., messages=[{"role": "user", ...}])
#   answer = response.choices[0].message.content
#
# LangChain does this with a clean interface:
#   llm = ChatOpenAI()
#   response = llm.invoke([HumanMessage("...")])
#   answer = response.content
#
# The underlying OpenAI API call is identical — LangChain is just a wrapper.
# The benefit: swap ChatOpenAI for ChatAnthropic and nothing else changes.

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# Load OPENAI_API_KEY from .env
load_dotenv()

# Create the LLM — same model we used in CodeAtlas
# temperature=0 means deterministic responses (no randomness)
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def ask(question: str) -> str:
    """Send a question to the LLM and return the answer."""

    messages = [
        SystemMessage("You are a helpful software engineering assistant."),
        HumanMessage(question),
    ]

    response = llm.invoke(messages)

    # response is an AIMessage object — .content gives us the text
    return response.content


if __name__ == "__main__":
    answer = ask("What is the difference between a vector database and a graph database? Answer in 3 lines.")
    print(answer)
