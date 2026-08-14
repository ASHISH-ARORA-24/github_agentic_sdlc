# Reporter
#
# Prints a human-readable trace report from a completed agent run.
# Shows a timeline of LLM calls and tool calls with timing, tokens, and cost.
#
# Usage:
#   from src.observability.reporter import print_report
#   print_report(trace)

def print_report(trace: dict, task: str = "") -> None:
    """Prints a human-readable observability report from an agent trace."""

    print()
    print("=" * 60)
    print("OBSERVABILITY REPORT")
    print("=" * 60)

    if task:
        print(f"Task : {task}")
        print()

    print("TIMELINE")
    print("-" * 60)

    step = 1
    for event in trace.get("events", []):

        if event["type"] == "llm_call":
            print(f"\n{step}. LLM Call")
            print(f"   Tokens  : {event['prompt_tokens']} in + {event['completion_tokens']} out = {event['total_tokens']} total")
            print(f"   Cost    : ${event['cost_usd']:.8f}")

        elif event["type"] == "tool_call":
            status = "✓" if event["success"] else "✗"
            print(f"\n{step}. {event['tool']}  {status}")
            print(f"   Duration: {event['duration_ms']} ms")

        step += 1

    print()
    print("-" * 60)
    print("SUMMARY")
    print("-" * 60)
    print(f"  Total Duration : {trace.get('total_duration_seconds', 0):.3f} sec")
    print(f"  LLM Calls      : {trace.get('total_llm_calls', 0)}")
    print(f"  Tool Calls     : {trace.get('total_tool_calls', 0)}")
    print(f"  Total Tokens   : {trace.get('total_tokens', 0)}")
    print(f"  Estimated Cost : ${trace.get('total_cost_usd', 0):.8f}")
    print("=" * 60)
