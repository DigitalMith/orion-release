"""
tools.py — Developer Utilities and Diagnostics for Orion CLI
------------------------------------------------------------

These commands provide utilities for inspecting:
- configuration
- embedding behavior
- resolved paths
- general CNS diagnostics

All heavy logic is delegated to shared modules.
"""

from __future__ import annotations

import typer
from rich import print as rprint

from orion_cli.shared.config import get_config
# from orion_cli.shared.embedding import embed_text  # Removed top-level only commands that need it.
from orion_cli.shared.paths import (
    PACKAGE_ROOT,
    DEFAULT_CONFIG_PATH,
    EMBEDDING_MODEL_DIR,
    SCHEMA_PATH,
    DEFAULT_CHROMA_PATH,
)


app = typer.Typer(help="Developer tools and diagnostic commands.")


# -------------------------------------------------------------
# Config inspection
# -------------------------------------------------------------

@app.command("config")
def show_config():
    """
    Display the full resolved Orion CNS configuration.
    """
    cfg = get_config()

    rprint("[bold cyan]=== Orion Configuration ===[/bold cyan]")
    rprint(cfg.model_dump())


# -------------------------------------------------------------
# Embedding test
# -------------------------------------------------------------

@app.command("embed")
def embed_test(
    text: str = typer.Argument(
        ...,
        help="Text to embed for testing purposes."
    )
):
    from orion_cli.shared.embedding import embed_text
    """
    Embed text once and print vector length + preview.
    """
    vec = embed_text(text)

    rprint("[bold green]=== Embedding Test ===[/bold green]")
    rprint(f"Input: {text!r}")
    rprint(f"Vector length: {len(vec)}")
    rprint(f"Vector preview: {vec[:8]} ...")


# -------------------------------------------------------------
# Path inspection
# -------------------------------------------------------------

@app.command("paths")
def show_paths():
    """
    Display important Orion CNS filesystem paths.
    """

    rprint("[bold magenta]=== Orion Paths ===[/bold magenta]")
    rprint(f"[white]Package root:        {PACKAGE_ROOT}[/white]")
    rprint(f"[white]Default config:      {DEFAULT_CONFIG_PATH}[/white]")
    rprint(f"[white]Embedding model dir:  {EMBEDDING_MODEL_DIR}[/white]")
    rprint(f"[white]JSON Schema:          {SCHEMA_PATH}[/white]")
    rprint(f"[white]ChromaDB path:        {DEFAULT_CHROMA_PATH}[/white]")


__all__ = ["app"]
