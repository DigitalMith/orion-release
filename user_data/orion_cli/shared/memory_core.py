"""
memory_core.py — Orion CNS Long-Term Memory Engine (Persona + Episodic)
-----------------------------------------------------------------------

Implements the core LTM functions:
- ChromaDB client initialization
- Persona collection
- Episodic memory collection
- Safe insertion (dedup, normalized text)
- Similarity-based recall
- Memory statistics and introspection

This module contains *all* memory logic.
The Typer commands simply call these functions.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings

from orion_cli.shared.config import get_config
from orion_cli.shared.embedding import EMBED_FN, embed_text
from orion_cli.shared.utils import normalize_text


# -------------------------------------------------------------
# Resolve Chroma path
# -------------------------------------------------------------

def _resolve_chroma_path() -> Path:
    cfg = get_config()
    raw = cfg.chroma_path

    # Allow relative paths (common inside TGWUI)
    if not os.path.isabs(str(raw)):
        return Path(os.path.join(os.getcwd(), raw)).resolve()

    return Path(raw).resolve()


# -------------------------------------------------------------
# Client initialization (singleton)
# -------------------------------------------------------------

_client = None

def _get_client():
    global _client

    if _client is not None:
        return _client

    persist_path = _resolve_chroma_path()
    persist_path.mkdir(parents=True, exist_ok=True)

    _client = chromadb.PersistentClient(
        path=str(persist_path),
        settings=Settings(anonymized_telemetry=False),
    )

    return _client


# -------------------------------------------------------------
# Collection helpers
# -------------------------------------------------------------

def _get_collection(name: str):
    return _get_client().get_or_create_collection(
        name=name,
        embedding_function=EMBED_FN,
        metadata={"hnsw:space": "cosine"},
    )


# Primary collections
PERSONA_COLLECTION = "orion_persona"
EPISODIC_COLLECTION = "orion_episodic_ltm"


def _persona():
    return _get_collection(PERSONA_COLLECTION)


def _episodic():
    return _get_collection(EPISODIC_COLLECTION)


# -------------------------------------------------------------
# Ingestion (Persona + Episodic)
# -------------------------------------------------------------

def add_persona_entry(text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Insert a persona document into its collection.
    Returns the ID assigned to the inserted memory.
    """
    clean = normalize_text(text)
    col = _persona()

    vector = embed_text(clean)
    new_id = f"persona-{col.count()+1}"

    col.upsert(
        ids=[new_id],
        embeddings=[vector],
        documents=[clean],
        metadatas=[metadata or {}],
    )

    return new_id


def add_episodic_entry(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    min_length: int = 10,
) -> Optional[str]:
    """
    Insert an episodic memory entry, with safeguards:

    - Reject trivial or extremely short entries
    - Normalize text
    - Deduplicate against existing memory
    """
    clean = normalize_text(text)

    if len(clean.split()) < min_length:
        return None  # trivial entry → skip

    col = _episodic()

    # Dedup check
    if col.count() > 0:
        hits = col.query(
            query_texts=[clean],
            n_results=1,
        )

        if hits.get("distances") and hits["distances"][0][0] < 0.05:
            # Near-duplicate → skip
            return None

    vector = embed_text(clean)
    new_id = f"episodic-{col.count()+1}"

    col.upsert(
        ids=[new_id],
        embeddings=[vector],
        documents=[clean],
        metadatas=[metadata or {}],
    )

    return new_id


# -------------------------------------------------------------
# Recall
# -------------------------------------------------------------

def recall_persona(query: str, top_k: int = 5) -> List[str]:
    """
    Retrieve persona entries most relevant to `query`.
    Returns a list of persona document strings.
    """
    col = _persona()

    if col.count() == 0:
        return []

    res = col.query(query_texts=[query], n_results=top_k)
    docs = res.get("documents", [[]])[0]

    return docs or []


def recall_episodic(query: str, top_k: int = 5) -> List[str]:
    """
    Retrieve episodic memories most relevant to `query`.
    """
    col = _episodic()

    if col.count() == 0:
        return []

    res = col.query(query_texts=[query], n_results=top_k)
    docs = res.get("documents", [[]])[0]

    return docs or []


# -------------------------------------------------------------
# Statistics
# -------------------------------------------------------------

def memory_stats() -> Dict[str, Any]:
    """
    Return summary statistics for persona & episodic memory.
    """
    p = _persona()
    e = _episodic()

    return {
        "persona_entries": p.count(),
        "episodic_entries": e.count(),
    }


def on_user_turn(text: str, **metadata) -> None:
    """
    Legacy hook used by the orion_ltm extension for user messages.

    Thin wrapper around add_episodic_entry so CNS 3.x-style extension
    code keeps working on CNS 4.0.
    """
    meta = {"role": "user", "source": "tgwui"}
    if metadata:
        meta.update(metadata)
    add_episodic_entry(text, metadata=meta, min_length=10)


def on_assistant_turn(text: str, **metadata) -> None:
    """
    Legacy hook used by the orion_ltm extension for assistant messages.
    """
    meta = {"role": "assistant", "source": "tgwui"}
    if metadata:
        meta.update(metadata)
    add_episodic_entry(text, metadata=meta, min_length=10)


__all__ = [
    "add_persona_entry",
    "add_episodic_entry",
    "recall_persona",
    "recall_episodic",
    "memory_stats",
    "PERSONA_COLLECTION",
    "EPISODIC_COLLECTION",
    "on_user_turn",
    "on_assistant_turn",
]
