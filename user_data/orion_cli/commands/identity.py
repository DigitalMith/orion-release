"""
identity.py — Typer Commands for Orion Identity Operations
----------------------------------------------------------

These commands expose the identity layer of CNS 4.0, enabling users to:

- Inspect persona slices
- Query identity blocks
- Debug identity behavior

All heavy CNS logic is implemented in:
    orion_cli.shared.identity_core
"""

from __future__ import annotations

import typer

from orion_cli.shared.identity_core import (
    persona_summary,
    build_identity_block,
)


app = typer.Typer(help="Inspect Orion's identity system.")


# -------------------------------------------------------------
# Persona inspection
# -------------------------------------------------------------


@app.command("persona")
def persona_command(
    query: str = typer.Argument(
        "identity",
        help="Query text to retrieve persona-related information.",
    ),
    top_k: int = typer.Option(
        5,
        "--top-k",
        "-k",
        help="Number of persona entries to return.",
    ),
):
    """
    Retrieve persona entries most relevant to the given query.
    """
    hits = persona_summary(query, top_k=top_k)

    if not hits:
        typer.echo("No persona entries found.")
        return

    typer.echo("=== Persona Summary ===")
    for h in hits:
        typer.echo(f"- {h}")


# -------------------------------------------------------------
# Identity block preview
# -------------------------------------------------------------


@app.command("query")
def query_identity(
    query: str = typer.Argument(
        ...,
        help="Query text used to assemble an identity block.",
    )
):
    """
    Build and print a compact identity block.

    This is primarily used for debugging and validating that
    persona memory is behaving as expected.
    """
    block = build_identity_block(query)

    if not block.strip():
        typer.echo("No identity context available.")
        return

    typer.echo("=== Identity Block ===")
    typer.echo(block)


__all__ = ["app"]
