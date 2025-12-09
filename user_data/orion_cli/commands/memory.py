"""
memory.py — Typer Commands for Orion CNS Memory Operations
----------------------------------------------------------

This module exposes user-facing memory commands for the Orion CLI.

All heavy logic lives in:
    orion_cli.shared.memory_core

Commands implemented here:
- recall: Retrieve persona or episodic memory
- stats: Show memory statistics

Usage examples:
    orion memory recall "tell me about yourself"
    orion memory recall --persona "identity traits"
    orion memory stats
"""

from __future__ import annotations

import typer
from typing import Optional

from orion_cli.shared.memory_core import (
    recall_persona,
    recall_episodic,
    memory_stats,
)

app = typer.Typer(help="Inspect and query Orion's long-term memory stores.")


# -------------------------------------------------------------
# Recall command
# -------------------------------------------------------------

@app.command("recall")
def recall_command(
    query: str = typer.Argument(..., help="Query text for memory recall."),
    persona: bool = typer.Option(
        False,
        "--persona",
        "-p",
        help="Search only the persona memory collection.",
    ),
    episodic: bool = typer.Option(
        False,
        "--episodic",
        "-e",
        help="Search only the episodic memory collection.",
    ),
    top_k: int = typer.Option(
        5,
        "--top-k",
        "-k",
        help="Number of results to return (default: 5).",
    ),
):
    """
    Recall relevant persona or episodic memories.
    If neither --persona nor --episodic is provided, both collections are searched.
    """
    # Determine target
    search_persona = persona or not episodic
    search_episodic = episodic or not persona

    output = []

    if search_persona:
        hits = recall_persona(query, top_k)
        if hits:
            typer.echo("=== Persona Memory ===")
            for h in hits:
                typer.echo(f"- {h}")
            typer.echo("")

    if search_episodic:
        hits = recall_episodic(query, top_k)
        if hits:
            typer.echo("=== Episodic Memory ===")
            for h in hits:
                typer.echo(f"- {h}")

    if not search_persona and not search_episodic:
        typer.echo("No memory category selected.")


# -------------------------------------------------------------
# Stats command
# -------------------------------------------------------------

@app.command("stats")
def stats_command():
    """
    Display memory statistics for persona and episodic storage.
    """
    stats = memory_stats()

    typer.echo("=== Orion Memory Stats ===")
    typer.echo(f"Persona entries:   {stats['persona_entries']}")
    typer.echo(f"Episodic entries:  {stats['episodic_entries']}")


__all__ = ["app"]
