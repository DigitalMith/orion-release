"""
Orion CLI Package
-----------------

This package provides the complete CNS (Cognitive Neural System) logic
for Orion, including configuration, embeddings, memory engines,
identity systems, and Typer-based command-line interfaces.

All functional logic is implemented in:
    - orion_cli/commands/
    - orion_cli/semantic/
    - orion_cli/settings/
    - orion_cli/shared/

The CLI entrypoint is defined in cli.py.
"""

__all__ = [
    "commands" "semantic" "settings" "shared",
]
