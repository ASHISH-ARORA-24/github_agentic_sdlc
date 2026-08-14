# Human-in-the-Loop — PR Approval
#
# The orchestrator calls this after the agent review passes.
# It blocks and waits for the human to type APPROVE or REJECT.
#
# On APPROVE → orchestrator calls merge_pr
# On REJECT  → orchestrator sends the reason back to the Coder agent to rework
#
# This is NOT a @tool — the LLM never calls this.
# Only the orchestrator calls it, at a fixed point in the SDLC pipeline.


def request_pr_approval(
    summary:       str,
    files_changed: list[str],
    pr_url:        str,
    branch_url:    str,
    issue_url:     str,
    board_url:     str,
) -> dict:
    """
    Prints a full summary of the agent's work and asks the human to APPROVE or REJECT.

    Returns:
        {"approved": True}                          — on approval
        {"approved": False, "reason": "<reason>"}  — on rejection, reason sent back to Coder
    """
    print()
    print("=" * 60)
    print("HUMAN APPROVAL REQUIRED")
    print("=" * 60)

    print()
    print("SUMMARY")
    print("-" * 60)
    print(summary)

    print()
    print("FILES CHANGED")
    print("-" * 60)
    for f in files_changed:
        print(f"  - {f}")

    print()
    print("LINKS")
    print("-" * 60)
    print(f"  PR       : {pr_url}")
    print(f"  Branch   : {branch_url}")
    print(f"  Issue    : {issue_url}")
    print(f"  Board    : {board_url}")

    print()
    print("=" * 60)
    print("Type APPROVE to merge, or REJECT followed by your reason.")
    print("Example: REJECT the validation logic is missing edge cases")
    print("=" * 60)

    response = input("\n> ").strip()

    if response.upper().startswith("APPROVE"):
        print("\nApproved. Proceeding to merge.")
        return {"approved": True}
    else:
        # Everything after REJECT is the reason — sent back to the Coder agent
        reason = response[len("REJECT"):].strip() if response.upper().startswith("REJECT") else response
        print(f"\nRejected. Reason: {reason}")
        print("Sending feedback to agent for rework...")
        return {"approved": False, "reason": reason}
