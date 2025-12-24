"""
embedding.py — Orion CNS Embedding System
-----------------------------------------

Provides:
- Lazy loading of the configured embedding model
- Text normalization
- Deterministic embedding via SentenceTransformer
- EMBED_FN callback for ChromaDB collection binding

Default model: Jina V2 Base (768d)
Other supported models: MPNet, OpenAI CLIP variants
Explicitly unsupported: Intfloat family (deprecated)

The embedding system MUST be deterministic across:
- ingestion
- recall
- identity prompt assembly
"""

from __future__ import annotations

import threading
from typing import List

from sentence_transformers import SentenceTransformer
from chromadb.utils.embedding_functions import EmbeddingFunction

from orion_cli.shared.config import get_config
from orion_cli.shared.utils import normalize_text


# -------------------------------------------------------------
# Thread-safe lazy model loader
# -------------------------------------------------------------

_MODEL = None
_MODEL_LOCK = threading.Lock()


def _load_model():
    """
    Load the embedding model specified in the Orion config.
    This function is thread-safe and only loads once.
    """
    global _MODEL

    if _MODEL is not None:
        return _MODEL

    cfg = get_config()
    model_name = cfg.embedding_model

    # Safety: forbid deprecated Intfloat models
    if "intfloat" in model_name.lower():
        raise RuntimeError(
            f"[embedding] Model '{model_name}' is not allowed. "
            "Intfloat models are deprecated in CNS 4.0."
        )

    with _MODEL_LOCK:
        if _MODEL is None:
            _MODEL = SentenceTransformer(model_name)

    return _MODEL


# -------------------------------------------------------------
# Public embedding function
# -------------------------------------------------------------


def embed_text(text: str) -> List[float]:
    """
    Embed a single text input into a list of floats.
    Used by ingestion & recall systems.
    """
    model = _load_model()
    clean = normalize_text(text)
    return model.encode(clean).tolist()


# -------------------------------------------------------------
# ChromaDB callback interface
# -------------------------------------------------------------


class OrionEmbeddingFunction(EmbeddingFunction):
    """
    Adapter that makes our embedding system compatible with Chroma's
    EmbeddingFunction protocol:

        __call__(self, input: List[str]) -> List[List[float]]
    """

    def __call__(self, input: List[str]) -> List[List[float]]:
        if not isinstance(input, list):
            raise TypeError(f"Expected list[str] for input, got {type(input)!r}")

        model = _load_model()
        cleaned = [normalize_text(t) for t in input]
        return model.encode(cleaned).tolist()


# This is what memory_core passes to Chroma
EMBED_FN = OrionEmbeddingFunction()


__all__ = [
    "embed_text",
    "EMBED_FN",
]
