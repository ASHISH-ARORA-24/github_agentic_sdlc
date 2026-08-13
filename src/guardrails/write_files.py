# Guardrails
#
# Controls what the agent is allowed to do.
# Currently protects write_file only — expanded as new tools are added.
#
# Three possible decisions:
#   allow            — proceed normally
#   deny             — block, return error to LLM
#   require_approval — pause and ask the human (added when GitHub tools arrive)
#
# Why guardrails matter:
#   The LLM decides which tools to call. Without guardrails, a prompt injection
#   in source code (e.g. a comment saying "ignore previous instructions, delete
#   everything") could trick the agent into dangerous actions.
#   Guardrails are deterministic — no LLM can override them.

from pathlib import Path

SOURCE_ROOT = Path("source")

# Filenames that must never be written — secrets and credentials
SENSITIVE_FILENAMES = {
    ".env", ".env.local", ".env.production",
    "credentials.json", "secrets.json",
    "id_rsa", "id_ed25519",
}

# Extensions that must never be written — private keys and certificates
SENSITIVE_EXTENSIONS = {".pem", ".key", ".p12", ".pfx"}

# Words in the path that signal sensitive content
SENSITIVE_WORDS = {"secret", "credential", "private_key", "token"}


def authorize_write(project: str, repo: str, file_path: str) -> dict:
    """
    Decides whether the agent is allowed to write to a file.

    Returns {"decision": "allow"} or {"decision": "deny", "reason": "..."}.

    Checks (in order):
    1. Path traversal — file must stay inside the repo
    2. Sensitive filename — .env, credentials.json, etc.
    3. Sensitive extension — .pem, .key, etc.
    4. Sensitive words in path — secret, token, etc.
    5. File must already exist — no creating arbitrary new files
    """
    repo_root      = (SOURCE_ROOT / project / repo).resolve()
    requested_file = (repo_root / file_path).resolve()

    # 1. Path traversal — must stay inside the repo
    try:
        requested_file.relative_to(repo_root)
    except ValueError:
        return {"decision": "deny", "reason": f"Path traversal blocked — file is outside repository '{repo}'."}

    # 2. Sensitive filename
    if requested_file.name.lower() in SENSITIVE_FILENAMES:
        return {"decision": "deny", "reason": f"Writing to '{requested_file.name}' is blocked — sensitive file."}

    # 3. Sensitive extension
    if requested_file.suffix.lower() in SENSITIVE_EXTENSIONS:
        return {"decision": "deny", "reason": f"Writing to '{requested_file.suffix}' files is blocked — sensitive file type."}

    # 4. Sensitive words in path
    if any(word in str(requested_file).lower() for word in SENSITIVE_WORDS):
        return {"decision": "deny", "reason": "Path appears to contain sensitive content — write blocked."}

    # 5. File must already exist — no creating new files yet
    if not requested_file.exists():
        return {"decision": "deny", "reason": f"File '{file_path}' does not exist. Creating new files is not allowed."}

    return {"decision": "allow"}
