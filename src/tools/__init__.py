# src/tools/__init__.py
#
# Re-exports make_tools so existing imports don't need to change.
# As new tool files are added (github_tools.py etc.), combine them here.
#
# Current:
#   from src.tools import make_tools   ← works, pulls from code_tools.py
#
# Future (when GitHub tools are added):
#   from src.tools.code_tools   import make_code_tools
#   from src.tools.github_tools import make_github_tools
#   def make_tools(project): return make_code_tools(project) + make_github_tools(project)

from src.tools.codebase import make_tools
