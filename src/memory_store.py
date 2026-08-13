# Memory Store
#
# Saves and retrieves long-term project memory.
# Memory is shared across all agents for a given project — it contains
# stable facts about the project that are useful to everyone.
#
# Examples of good memory:
#   test_location     → "tests/ folder"
#   test_framework    → "pytest"
#   naming_convention → "snake_case"
#
# Examples of bad memory (these belong in state, not here):
#   current_step      → "3"
#   last_error        → "File not found"
#   task              → "Add validation to reserve_stock"
#
# Storage: project_memory.json at project root, keyed by project.
# {
#   "codeatlas/ecommerce": [
#       {"key": "test_location", "value": "tests/ folder"},
#       {"key": "test_framework", "value": "pytest"}
#   ]
# }

import json
from pathlib import Path

# JSON file lives at project root — not inside src/
MEMORY_FILE = Path(__file__).parent.parent / "project_memory.json"


def _load() -> dict:
    """Reads the full memory file. Returns empty dict if file does not exist yet."""
    if not MEMORY_FILE.exists():
        return {}
    content = MEMORY_FILE.read_text(encoding="utf-8").strip()
    return json.loads(content) if content else {}


def _save(data: dict) -> None:
    """Writes the full memory dict back to disk."""
    MEMORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_memory(project: str, key: str, value: str) -> dict:
    """
    Saves one reusable fact about the project.
    If the key already exists, updates the value — no duplicates.
    """
    data = _load()

    if project not in data:
        data[project] = []

    # Update if key exists, otherwise append
    existing = next((m for m in data[project] if m["key"] == key), None)
    if existing:
        existing["value"] = value
        status = "updated"
    else:
        data[project].append({"key": key, "value": value})
        status = "created"

    _save(data)
    return {"project": project, "key": key, "value": value, "status": status}


def get_memories(project: str) -> list[dict]:
    """Returns all saved memories for a project as a list of {key, value} dicts."""
    return _load().get(project, [])
