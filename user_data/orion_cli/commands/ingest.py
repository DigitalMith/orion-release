"""
ingest.py — Typer Commands for Persona & Episodic Ingestion
-----------------------------------------------------------

These commands allow users to add persona entries and episodic memories
into Orion's long-term memory store.

All ingestion logic lives in:
    orion_cli.shared.memory_core
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional
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

SENTINELS = {
    "<|BEGIN-VISIBLE-CHAT|>",
    "<|END-VISIBLE-CHAT|>",
    "<|BEGIN-CHAT|>",
    "<|END-CHAT|>",
}


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


def _file_sha1(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _compact_ts(ts: str) -> str:
    return "".join([c for c in ts if c.isdigit() or c == "T"])


def _parse_ts_from_source_file(source_file: str) -> Optional[str]:
    try:
        stem = Path(source_file).stem
        dt = datetime.strptime(stem, "%Y%m%d-%H-%M-%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def _uid(ts: str, role: str, pair_index: int, text: str, source_file: str) -> str:
    h = hashlib.sha1(
        f"{source_file}|{ts}|{role}|{text}".encode("utf-8", "ignore")
    ).hexdigest()[:10]
    return f"ep_{_compact_ts(ts)}_{role}_{pair_index:06d}_{h}"


def _flatten_for_chroma(md: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (md or {}).items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, list):
            out[k] = ",".join(str(x) for x in v)
        else:
            out[k] = json.dumps(v, ensure_ascii=False)
    return out


# -------------------------------------------------------------
# Persona ingestion
# -------------------------------------------------------------


@app.command("persona")
def ingest_persona(
    source: str = typer.Argument(
        ..., help="Text to ingest or path to a file containing persona data."
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
        ..., help="Text or file containing an episodic memory entry."
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


@app.command("chat-canon")
def chat_canon(
    in_path: str,
    out_path: str,
    dry_run: bool = False,
    skip_sentinels: bool = True,
    min_length: int = 1,
):
    from orion_cli.settings.config_loader import get_config
    from orion_cli.shared.memory_core import add_episodic_entry

    src = Path(in_path)
    dst = Path(out_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # read pairs
    pairs = []
    ts_vals = []
    with src.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "_meta" in obj:
                continue
            pairs.append(obj)
            t = obj.get("timestamp")
            if isinstance(t, str) and t.strip():
                ts_vals.append(t.strip())

    ts_vals.sort()
    header = {
        "_meta": {
            "schema": "orion.canon.chatlog.v1",
            "created_local": datetime.now().strftime("%Y-%m-%d"),
            "source_path": str(src),
            "source_sha1": _file_sha1(src),
            "pair_count": len(pairs),
            "time_range": {
                "min": ts_vals[0] if ts_vals else None,
                "max": ts_vals[-1] if ts_vals else None,
            },
            "id_scheme": "ep_<ts>_<role>_<pair_index>_<sha1_10>",
            "notes": "Generated by orion ingest chat-canon; deterministic IDs; safe for idempotent re-ingest",
        }
    }

    cfg = get_config()
    written = 0
    ingested = 0

    with dst.open("w", encoding="utf-8") as out:
        out.write(json.dumps(header, ensure_ascii=False) + "\n")
        written += 1

        for i, p in enumerate(pairs):
            user = (p.get("user") or "").strip()
            resp = (p.get("response") or "").strip()
            ts = (p.get("timestamp") or "").strip()
            source_file = (p.get("source_file") or "").strip()
            md = dict(p.get("metadata") or {})

            if skip_sentinels and user in SENTINELS:
                continue

            if not ts:
                ts = _parse_ts_from_source_file(source_file) or ""

            source_block = {
                "kind": "annotated_logs_jsonl",
                "file": source_file,
                "character": "Orion",
            }

            if user:
                uid_h = _uid(ts, "human", i, user, source_file)
                out.write(
                    json.dumps(
                        {
                            "schema": "orion.canon.turn.v1",
                            "id": uid_h,
                            "ts": ts,
                            "role": "human",
                            "text": user,
                            "source": source_block,
                            "meta": {
                                "ingest_source": "annotated_logs_jsonl",
                                "pair_index": i,
                            },
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                written += 1

                if not dry_run and len(user) >= min_length:
                    add_episodic_entry(
                        user,
                        metadata=_flatten_for_chroma(
                            {
                                "uid": uid_h,
                                "timestamp": ts,
                                "role": "human",
                                "ingest_source": "annotated_logs_jsonl",
                                "source_file": source_file,
                                "pair_index": i,
                                **md,
                            }
                        ),
                        min_length=min_length,
                    )
                    ingested += 1

            if resp:
                uid_a = _uid(ts, "llm", i, resp, source_file)
                out.write(
                    json.dumps(
                        {
                            "schema": "orion.canon.turn.v1",
                            "id": uid_a,
                            "ts": ts,
                            "role": "llm",
                            "text": resp,
                            "source": source_block,
                            "meta": {
                                "ingest_source": "annotated_logs_jsonl",
                                "pair_index": i,
                                "user_prompt": user,
                                **md,
                            },
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                written += 1

                if not dry_run and len(resp) >= min_length:
                    add_episodic_entry(
                        resp,
                        metadata=_flatten_for_chroma(
                            {
                                "uid": uid_a,
                                "timestamp": ts,
                                "role": "llm",
                                "ingest_source": "annotated_logs_jsonl",
                                "source_file": source_file,
                                "pair_index": i,
                                "user_prompt": user,
                                **md,
                            }
                        ),
                        min_length=min_length,
                    )
                    ingested += 1

    print(f"[ok] wrote canon: {dst} (lines={written})")
    if dry_run:
        print("[dry-run] did not ingest to Chroma")
    else:
        print(
            f"[ok] ingested episodic entries: {ingested} | chroma_path: {cfg.chroma_path}"
        )


@app.command("chat-tgwui")
def chat_tgwui(
    out_path: str,
    in_paths: list[str],
    dry_run: bool = False,
    min_length: int = 1,
):

    def sha1s(s: str) -> str:
        return hashlib.sha1(s.encode("utf-8", "ignore")).hexdigest()

    def file_sha1(p: Path) -> str:
        h = hashlib.sha1()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def compact_ts(ts: str) -> str:
        return "".join([c for c in ts if c.isdigit() or c == "T"])

    def uid(ts: str, role: str, idx: int, text: str, source_file: str) -> str:
        h = sha1s(f"{source_file}|{ts}|{role}|{text}")[:10]
        return f"ep_{compact_ts(ts)}_{role}_{idx:06d}_{h}"

    def flatten(md: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in (md or {}).items():
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                out[k] = v
            elif isinstance(v, list):
                out[k] = ",".join(str(x) for x in v)
            else:
                out[k] = json.dumps(v, ensure_ascii=False)
        return out

    def ts_from_filename(p: Path) -> str:
        # 20251215-06-27-42.json -> 2025-12-15T06:27:42
        try:
            dt = datetime.strptime(p.stem, "%Y%m%d-%H-%M-%S")
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            return ""

    cfg = get_config()
    dst = Path(out_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Load all input files
    files = [Path(p) for p in in_paths]
    for p in files:
        if not p.exists():
            raise SystemExit(f"Missing input: {p}")

    # Meta header
    header = {
        "_meta": {
            "schema": "orion.canon.chatlog.v1",
            "created_local": datetime.now().strftime("%Y-%m-%d"),
            "source_kind": "tgwui_chat_json",
            "inputs": [str(p) for p in files],
            "inputs_sha1": {str(p): file_sha1(p) for p in files},
            "notes": "Canonicalized from TGWUI chat JSON (visible turns only); deterministic IDs; safe to re-ingest (once we upsert by uid).",
        }
    }

    written = 0
    ingested = 0
    idx = 0

    with dst.open("w", encoding="utf-8") as out:
        out.write(json.dumps(header, ensure_ascii=False) + "\n")
        written += 1

        for p in files:
            obj = json.loads(p.read_text(encoding="utf-8"))
            # TGWUI format usually has "history": {"internal":[...], "visible":[...]}
            hist = obj.get("history") if isinstance(obj.get("history"), dict) else None
            visible = (
                (hist.get("visible") if hist else None) or obj.get("visible") or []
            )
            # visible is typically list of [user, assistant] pairs
            base_ts = ts_from_filename(p)
            source_block = {"kind": "tgwui_chat", "file": p.name, "character": "Orion"}

            for pair in visible:
                if not isinstance(pair, list) or len(pair) < 2:
                    continue
                user = (pair[0] or "").strip()
                resp = (pair[1] or "").strip()
                ts = base_ts

                if user:
                    u = uid(ts, "human", idx, user, p.name)
                    out.write(
                        json.dumps(
                            {
                                "schema": "orion.canon.turn.v1",
                                "id": u,
                                "ts": ts,
                                "role": "human",
                                "text": user,
                                "source": source_block,
                                "meta": {
                                    "ingest_source": "tgwui_chat",
                                    "source_file": p.name,
                                },
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    written += 1
                    if not dry_run and len(user) >= min_length:
                        add_episodic_entry(
                            user,
                            metadata=flatten(
                                {
                                    "uid": u,
                                    "timestamp": ts,
                                    "role": "human",
                                    "ingest_source": "tgwui_chat",
                                    "source_file": p.name,
                                }
                            ),
                            min_length=min_length,
                        )
                        ingested += 1
                    idx += 1

                if resp:
                    a = uid(ts, "llm", idx, resp, p.name)
                    out.write(
                        json.dumps(
                            {
                                "schema": "orion.canon.turn.v1",
                                "id": a,
                                "ts": ts,
                                "role": "llm",
                                "text": resp,
                                "source": source_block,
                                "meta": {
                                    "ingest_source": "tgwui_chat",
                                    "source_file": p.name,
                                    "user_prompt": user,
                                },
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    written += 1
                    if not dry_run and len(resp) >= min_length:
                        add_episodic_entry(
                            resp,
                            metadata=flatten(
                                {
                                    "uid": a,
                                    "timestamp": ts,
                                    "role": "llm",
                                    "ingest_source": "tgwui_chat",
                                    "source_file": p.name,
                                    "user_prompt": user,
                                }
                            ),
                            min_length=min_length,
                        )
                        ingested += 1
                    idx += 1

    print(f"[ok] wrote canon: {dst} (lines={written})")
    if dry_run:
        print("[dry-run] did not ingest to Chroma")
    else:
        print(
            f"[ok] ingested episodic entries: {ingested} | chroma_path: {cfg.chroma_path}"
        )


__all__ = ["app"]
