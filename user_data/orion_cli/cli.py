"""
cli.py — Orion CNS Command-Line Interface (Root Entrypoint)
-----------------------------------------------------------

This file defines the `orion` command and registers all subcommands.

Subcommands:
    - orion memory ...
    - orion identity ...
    - orion ingest ...
    - orion tools ...

The real logic behind each command lives in shared modules.
Commands are intentionally thin orchestrators.
"""

from __future__ import annotations

import typer
import warnings

from orion_cli.commands.memory import app as memory_app
from orion_cli.commands.identity import app as identity_app
from orion_cli.commands.ingest import app as ingest_app
from orion_cli.commands.tools import app as tools_app
from orion_cli.commands.config import app as config_app
from orion_cli.commands.bootstrap import app as bootstrap_app
from orion_cli.commands.curate import app as promote_app
from orion_cli.commands.semantic import app as semantic_app

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message="Using `TRANSFORMERS_CACHE` is deprecated and will be removed in v5 of Transformers. Use `HF_HOME` instead.",
)

# Root CLI application
app = typer.Typer(
    help="Orion CLI — Cognitive Neural System Tools",
    add_completion=False,
)


# Register subcommands
app.add_typer(memory_app, name="memory")
app.add_typer(identity_app, name="identity")
app.add_typer(ingest_app, name="ingest")
app.add_typer(tools_app, name="tools")
app.add_typer(config_app, name="config")
app.add_typer(bootstrap_app, name="bootstrap")
app.add_typer(promote_app, name="promote")
app.add_typer(semantic_app, name="semantic")


def main():
    """
    Entrypoint used by `orion` script in pyproject.toml.
    """
    app()


if __name__ == "__main__":
    main()
