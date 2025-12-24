from __future__ import annotations

import typer

from orion_cli.semantic.promote import promote_candidates

app = typer.Typer(
    help="Promote semantic candidates into semantic memory (curation step)."
)


@app.command("semantic")
def promote_semantic(
    limit: int = typer.Option(50, "--limit", help="Max items to promote."),
    min_conf: float = typer.Option(
        0.0, "--min-conf", help="Only promote candidates with confidence >= this."
    ),
    source: str = typer.Option(
        "", "--source", help="Only promote candidates where metadata.source matches."
    ),
    delete_from_candidates: bool = typer.Option(
        False,
        "--delete-from-candidates",
        help="Delete promoted items from semantic_candidates after promotion.",
    ),
):
    src = source.strip() or None
    promoted, scanned = promote_candidates(
        limit=limit,
        min_conf=min_conf,
        source=src,
        delete_from_candidates=delete_from_candidates,
    )
    typer.echo(
        f"[promote] scanned={scanned} promoted={promoted} delete_from_candidates={delete_from_candidates}"
    )
