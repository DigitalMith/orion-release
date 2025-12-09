"""
ingest.py — Typer Commands for Persona & Episodic Ingestion
-----------------------------------------------------------

These commands allow users to add persona entries and episodic memories
into Orion's long-term memory store.

All ingestion logic lives in:
    orion_cli.shared.memory_core
"""

from __future__ import annotations

import json
import typer
from pathlib import Path
from orion_cli.shared.utils import read_yaml

from orion_cli.shared.memory_core import (
    add_persona_entry,
    add_episodic_entry,
)

from orion_cli.settings.config_loader import (
    get_config,
    resolve_profile_paths,
)

app = typer.Typer(help="Ingest persona and episodic memory into Orion.")


# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------

def _load_text_source(source: str, is_file: bool) -> str:
    """
    Load text either from a string literal or from a file.
    """
    if is_file:
        path = Path(source)
        if not path.exists():
            raise typer.BadParameter(f"File not found: {source}")

        return path.read_text(encoding="utf-8")

    return source


# -------------------------------------------------------------
# Persona ingestion
# -------------------------------------------------------------

@app.command("persona")
def ingest_persona(
    source: str = typer.Argument(
        ...,
        help="Text to ingest or path to a file containing persona data."
    ),
    file: bool = typer.Option(
        False,
        "--file",
        "-f",
        help="Interpret <source> as a file path.",
    ),
):
    """
    Add a persona memory entry (or entries) to Orion.
    """
    text = _load_text_source(source, file)

    # Split into lines, keep non-empty, but skip comment lines starting with '#'
    lines = [line.rstrip() for line in text.split("\n") if line.strip()]
    count = 0

    for line in lines:
        if line.lstrip().startswith("#"):
            continue  # ignore commented lines

        new_id = add_persona_entry(line)
        if new_id:
            typer.echo(f"Added persona entry: {new_id}")
            count += 1

    typer.echo(f"Completed. {count} persona entries added.")


# -------------------------------------------------------------
# Episodic ingestion
# -------------------------------------------------------------

@app.command("episodic")
def ingest_episodic(
    source: str = typer.Argument(
        ...,
        help="Text or file containing an episodic memory entry."
    ),
    file: bool = typer.Option(
        False,
        "--file",
        "-f",
        help="Interpret <source> as a file path.",
    ),
    min_length: int = typer.Option(
        10,
        "--min-length",
        "-m",
        help="Minimum word count required for ingestion (default: 10).",
    ),
):
    """
    Add an episodic memory entry to Orion.
    """
    text = _load_text_source(source, file)

    new_id = add_episodic_entry(
        text,
        metadata={"ingest_source": "cli"},
        min_length=min_length,
    )

    if new_id:
        typer.echo(f"Added episodic entry: {new_id}")
    else:
        typer.echo("Episodic entry too short or duplicate. Not added.")


# -------------------------------------------------------------
# Persona ingestion via active profile (config-driven)
# -------------------------------------------------------------

def _flatten_metadata(md: dict) -> dict:
    """
    Flatten nested metadata into string-friendly values.

    - Lists become comma-joined strings.
    - Dicts become JSON-encoded strings.
    - Scalars are passed through as-is.
    """
    flat: dict = {}
    for k, v in md.items():
        if isinstance(v, list):
            flat[k] = ",".join(str(x) for x in v)
        elif isinstance(v, dict):
            flat[k] = json.dumps(v, ensure_ascii=False)
        else:
            flat[k] = v
    return flat


@app.command("persona-default")
def ingest_persona_for_active_profile():
    """
    Ingest the persona file for the active Orion profile (YAML-aware).

    - Default profile 'orion_main' uses:
        user_data/orion_cli/data/orion_persona.yaml

    - If ORION_PROFILE is set (e.g. alex_home), it will use:
        user_data/orion/profiles/<profile>/data/persona.yaml
    """
    cfg = get_config()
    _, persona_path = resolve_profile_paths(cfg)

    if not persona_path.exists():
        raise typer.BadParameter(f"Persona file not found: {persona_path}")

    data = read_yaml(persona_path)

    # Normalize to a list of docs
    if isinstance(data, list):
        docs = data
    elif isinstance(data, (dict, str)):
        docs = [data]
    else:
        docs = []

    count = 0

    for doc in docs:
        # Plain string doc (fallback/simple mode)
        if isinstance(doc, str):
            text_entry = doc.strip()
            if not text_entry:
                continue
            metadata = {}

        # Structured YAML doc
        elif isinstance(doc, dict):
            raw_text = doc.get("text", "")
            if not isinstance(raw_text, str):
                continue

            text_entry = raw_text.strip()
            if not text_entry:
                continue

            meta_raw = {k: v for k, v in doc.items() if k != "text"}
            metadata = _flatten_metadata(meta_raw)

        else:
            continue

        new_id = add_persona_entry(text_entry, metadata=metadata)
        if new_id:
            typer.echo(f"Added persona entry: {new_id}")
            count += 1

    typer.echo(
        f"Completed. {count} persona entries added from {persona_path} "
        f"for profile {cfg.profile!r}."
    )


__all__ = ["app"]

