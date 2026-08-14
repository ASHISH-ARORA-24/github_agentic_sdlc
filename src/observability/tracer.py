# Tracer
#
# Captures events during an agent run — LLM calls, tool calls, timing, tokens, cost.
# Every event is added to the trace dict with a timestamp.
#
# GPT-4o-mini pricing (per 1M tokens):
#   Input:  $0.150
#   Output: $0.600

import time

# GPT-4o-mini pricing per token
INPUT_PRICE_PER_TOKEN  = 0.150 / 1_000_000
OUTPUT_PRICE_PER_TOKEN = 0.600 / 1_000_000


def new_trace() -> dict:
    """Creates a fresh trace dict for one agent run."""
    return {
        "events":          [],   # chronological list of events
        "total_llm_calls": 0,
        "total_tool_calls": 0,
        "total_tokens":    0,
        "total_cost_usd":  0.0,
        "start_time":      time.perf_counter(),
    }


def record_llm_call(trace: dict, response) -> dict:
    """
    Records one LLM call — token usage, cost, and duration.
    Reads token usage from LangChain's response_metadata.
    Returns the event dict so the caller can use start_time for duration.
    """
    usage = response.response_metadata.get("token_usage", {})

    prompt_tokens     = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens      = usage.get("total_tokens", 0)
    cost              = (prompt_tokens * INPUT_PRICE_PER_TOKEN) + (completion_tokens * OUTPUT_PRICE_PER_TOKEN)

    # Update totals
    trace["total_llm_calls"] += 1
    trace["total_tokens"]    += total_tokens
    trace["total_cost_usd"]  += cost

    event = {
        "type":             "llm_call",
        "prompt_tokens":    prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens":     total_tokens,
        "cost_usd":         round(cost, 8),
    }
    trace["events"].append(event)
    return event


def record_tool_call(trace: dict, tool_name: str, duration_ms: float, success: bool) -> None:
    """Records one tool call — name, duration, success."""
    trace["total_tool_calls"] += 1
    trace["events"].append({
        "type":        "tool_call",
        "tool":        tool_name,
        "duration_ms": round(duration_ms, 2),
        "success":     success,
    })


def finish_trace(trace: dict) -> dict:
    """Adds total duration to the trace and returns it."""
    trace["total_duration_seconds"] = round(
        time.perf_counter() - trace["start_time"], 3
    )
    return trace
