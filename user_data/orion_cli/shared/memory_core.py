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
import hashlib
import time
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import chromadb
from chromadb.config import Settings

from orion_cli.shared.config import get_config
from orion_cli.shared.embedding import EMBED_FN, embed_text
from orion_cli.shared.utils import normalize_text
from orion_cli.shared.paths import CHROMA_DIR, PACKAGE_ROOT

# Optional semantic filters (safe import)
try:
    from orion_cli.semantic.filters import (
        is_low_value_candidate,
        strip_leading_greeting_if_meaningful,
    )
except Exception:

    def is_low_value_candidate(text: str, meta=None) -> bool:
        return False

    def strip_leading_greeting_if_meaningful(text: str) -> str:
        return text


# -------------------------------------------------------------
# Resolve Chroma path
# -------------------------------------------------------------


def _resolve_chroma_path() -> Path:
    """
    Resolve the ChromaDB path with the following precedence:

    1. ORION_CHROMA_DIR env var (absolute or relative)
    2. config.yaml -> chroma_path (absolute or relative)
       - relative paths are resolved against the TGWUI project root
    3. Default CHROMA_DIR from paths.py (user_data/orion/chromadb)
    """

    # 1) Environment override wins
    env_raw = os.getenv("ORION_CHROMA_DIR")
    if env_raw:
        p = Path(env_raw)
        if not p.is_absolute():
            # Resolve relative to TGWUI root
            tgwui_root = PACKAGE_ROOT.parent.parent
            p = tgwui_root / p
        return p.resolve()

    # 2) Config value (may be None / empty / missing)
    cfg = get_config()
    raw = getattr(cfg, "chroma_path", None)

    if raw:
        p = Path(str(raw))

        if p.is_absolute():
            return p.resolve()

        # Treat relative chroma_path as relative to TGWUI root
        tgwui_root = PACKAGE_ROOT.parent.parent
        return (tgwui_root / p).resolve()

    # 3) Fallback: canonical default
    return CHROMA_DIR.resolve()


# -------------------------------------------------------------
# Client initialization (singleton)
# -------------------------------------------------------------

_client = None

# --- Archivist pooling (process-local) ---------------------------------------
_ARCHIVIST_BUFFER: List[Dict[str, str]] = []
_ARCHIVIST_NEW_TURNS: int = 0


def _semantic_nag_if_needed() -> None:
    """
    ADHD-proof reminder: prints a short console message that Option B is pending.
    Rate-limited and best-effort (never breaks chat flow).
    """
    global _SEMANTIC_NAG_LAST_TS

    try:
        cfg = get_config()

        # Enable via config OR env var
        nag_on = bool(getattr(getattr(cfg, "debug", None), "semantic_nag", False)) or (
            os.getenv("ORION_SEMANTIC_NAG", "").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        if not nag_on:
            return

        # Only nag when semantic system is in play (Archivist or semantic recall enabled)
        arch = getattr(cfg, "archivist", None)
        semantic_in_play = bool(arch and getattr(arch, "enabled", False)) or bool(
            getattr(cfg.ltm, "semantic_enabled", False)
        )
        if not semantic_in_play:
            return

        # Rate limit: once per ~60 seconds
        now = time.time()
        if now - _SEMANTIC_NAG_LAST_TS < 60.0:
            return
        _SEMANTIC_NAG_LAST_TS = now

        # The message
        print(
            "[Orion] SEMANTIC REMINDER: Option B pending → add status/created_at metadata + active-only recall + supersession."
        )

    except Exception:
        return


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

SEMANTIC_COLLECTION = "orion_semantic_ltm"
SEMANTIC_CANDIDATES_COLLECTION = "orion_semantic_candidates"


# --- Config-driven collection names (with safe defaults) ---
_CONFIG_CACHE = None


def _orion_config_path() -> Path:
    # memory_core.py lives at: user_data/orion_cli/shared/memory_core.py
    # user_data is parents[2]; config is at: user_data/orion/data/config.yaml
    return Path(__file__).resolve().parents[2] / "orion" / "data" / "config.yaml"


def _load_orion_config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    p = _orion_config_path()
    try:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                _CONFIG_CACHE = yaml.safe_load(f) or {}
        else:
            _CONFIG_CACHE = {}
    except Exception:
        _CONFIG_CACHE = {}
    return _CONFIG_CACHE


def _collection_name(*keys: str, default: str) -> str:
    cfg = _load_orion_config()
    colmap = cfg.get("collections", {}) if isinstance(cfg, dict) else {}
    if isinstance(colmap, dict):
        for k in keys:
            v = colmap.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return default


def _episodic():
    name = _collection_name("episodic", "episodic_ltm", default=EPISODIC_COLLECTION)
    return _get_collection(name)


def _persona():
    name = _collection_name("persona", default=PERSONA_COLLECTION)
    return _get_collection(name)


def _semantic():
    name = _collection_name("semantic", default=SEMANTIC_COLLECTION)
    return _get_collection(name)


def _semantic_candidates():
    name = _collection_name(
        "semantic_candidates", default=SEMANTIC_CANDIDATES_COLLECTION
    )
    return _get_collection(name)


def add_persona_entry(text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Insert a persona document into its collection.
    Returns the ID assigned to the inserted memory.
    """
    clean = normalize_text(text)
    col = _persona()

    vector = embed_text(clean)
    new_id = f"persona-{col.count()+1}"

    upsert_kwargs = dict(
        ids=[new_id],
        embeddings=[vector],
        documents=[clean],
    )

    if metadata is not None:
        # Chroma v0.5+ requires non-empty dicts if metadatas is provided
        upsert_kwargs["metadatas"] = [metadata]

    col.upsert(**upsert_kwargs)

    return new_id


def add_episodic_entry(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    min_length: int = 10,
    doc_id: Optional[str] = None,
) -> Optional[str]:
    clean = normalize_text(text)

    if len(clean.split()) < min_length:
        return None  # trivial entry → skip

    col = _episodic()
    vector = embed_text(clean)

    # Dedup check (embedding-based)
    if col.count() > 0:
        hits = col.query(
            query_embeddings=[vector],
            n_results=1,
            include=["distances"],
        )
        if hits.get("distances") and hits["distances"][0][0] < 0.05:
            return None

    new_id = doc_id or f"episodic-{col.count()+1}"

    upsert_kwargs = dict(
        ids=[new_id],
        embeddings=[vector],
        documents=[clean],
    )

    if metadata is not None:
        # Chroma metadata must be primitive types only (no None/list/dict)
        safe = {
            k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool))
        }
        if safe:
            upsert_kwargs["metadatas"] = [safe]

    col.upsert(**upsert_kwargs)
    return new_id


def _run_archivist_if_ready() -> None:
    global _ARCHIVIST_NEW_TURNS, _ARCHIVIST_BUFFER

    cfg = get_config()

    arch = getattr(cfg, "archivist", None)
    if not arch or not getattr(arch, "enabled", False):
        return

    # increment only on assistant turns (one “cycle”)
    _ARCHIVIST_NEW_TURNS += 1

    min_new = int(getattr(arch.pool, "min_new_turns", 6))
    window = int(getattr(arch.pool, "window_turns", 20))

    if _ARCHIVIST_NEW_TURNS < min_new:
        return

    # pool last N turns (then filter to USER-only turns to prevent assistant contamination)
    pooled_all = _ARCHIVIST_BUFFER[-window:] if window > 0 else list(_ARCHIVIST_BUFFER)
    pooled = [
        t
        for t in pooled_all
        if isinstance(t, dict)
        and t.get("role") == "user"
        and (t.get("content") or "").strip()
    ]

    if not pooled:
        return

    try:
        from orion_cli.shared.archivist_client import run_archivist_extract

        res = run_archivist_extract(arch, pooled)
        data = res.parsed_json or {}

        # Contract schema: { "relevant": bool, "facts": [ {text, category, confidence} ] }
        if not isinstance(data, dict) or data.get("relevant") is not True:
            return

        facts = data.get("facts", [])
        if not isinstance(facts, list) or not facts:
            return

        for f in facts:
            if not isinstance(f, dict):
                continue

            text = f.get("text")
            category = f.get("category")
            conf = f.get("confidence", 0.0)

            if not isinstance(text, str) or not text.strip():
                continue
            if not isinstance(category, str) or not category.strip():
                continue
            if not isinstance(conf, (int, float)):
                conf = 0.0

            meta = {
                "source": "archivist",
                "model": str(getattr(arch, "model", "")),
                "category": category.strip(),
                "confidence": float(conf),
            }

            add_semantic_candidate(text.strip(), metadata=meta)

    except Exception:
        # Best-effort: NEVER break TGWUI chat flow if the archivist fails
        return

    finally:
        # reset counter, keep buffer trimmed
        _ARCHIVIST_NEW_TURNS = 0
        if window > 0 and len(_ARCHIVIST_BUFFER) > window * 2:
            _ARCHIVIST_BUFFER = _ARCHIVIST_BUFFER[-window * 2 :]


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
    CANON v2 episodic recall (user-first grounding) + intent-sensitive selection.

    Stage A: retrieve USER turns only (role == "user"), fetch top_k*5
    Pair: include immediate assistant continuation by deterministic ID
          f"{session_id}:assistant:{turn_index+1:04d}"

    Fallback: assistant-only hits only if insufficient (cap 2), demote long prose.
    """
    col = _episodic()
    if col.count() == 0:
        return []

    anchors: List[dict] = []

    # --- helpers -------------------------------------------------------------

    def _looks_greeting_or_phatic(s: str) -> bool:
        sl = (s or "").strip().lower()
        if not sl:
            return True
        PHATIC = (
            "good morning",
            "good night",
            "hey",
            "hi",
            "hello",
            "how are you",
            "how are you feeling",
            "what are you doing",
            "i'm so happy",
            "thanks",
            "thank you",
        )
        return any(p in sl for p in PHATIC)

    def _info_density(s: str) -> float:
        # extremely simple proxy: longer + more "technical-ish" tokens
        # (we only use this when query is dev-like)
        if not s:
            return 0.0
        tokens = s.split()
        n = len(tokens)
        if n == 0:
            return 0.0
        techish = sum(
            1
            for t in tokens
            if any(
                ch in t for ch in ("\\", "/", "_", ".", ":", "-", "(", ")", "[", "]")
            )
        )
        return (min(n, 80) / 80.0) + (min(techish, 12) / 12.0)

    def _safe_int(x, default=None):
        try:
            return int(x)
        except Exception:
            return default

    def _is_continuity_query(q: str) -> bool:
        ql = (q or "").lower()
        markers = (
            "what do you remember",
            "do you remember",
            "remember",
            "last time",
            "recent",
            "where did we leave off",
            "where were we",
            "remind me",
            "what were we talking about",
            "our last chat",
            "previous chat",
        )
        return any(m in ql for m in markers)

    def _is_low_substance_user_turn(s: str) -> bool:
        sl = (s or "").strip().lower()
        if not sl:
            return True

        phatic = (
            "can you hear me",
            "are you there",
            "hello",
            "hi",
            "hey",
            "good morning",
            "good night",
            "how are you",
            "how are you feeling",
            "what are you doing",
            "busy busy",
        )

        # short + phatic usually isn't continuity-bearing in your dataset
        if any(p in sl for p in phatic) and len(sl.split()) <= 16:
            return True

        # ultra-short tends to be non-grounding
        if len(sl.split()) < 6:
            return True

        return False

    def _parse_dt_from_meta(md: dict) -> datetime | None:
        """
        Prefer md['ts'] (your ingest uses 'ts').
        Fall back to session_id like 20250502-19-36-17.
        """
        if not isinstance(md, dict):
            return None

        ts = md.get("ts")
        if isinstance(ts, str) and ts.strip():
            t = ts.strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y%m%d-%H-%M-%S"):
                try:
                    return datetime.strptime(t, fmt)
                except Exception:
                    pass

        sid = md.get("session_id")
        if isinstance(sid, str) and sid.strip():
            try:
                return datetime.strptime(sid.strip(), "%Y%m%d-%H-%M-%S")
            except Exception:
                return None

        return None

    # If user asked for continuity and our similarity-selected anchors are mostly
    # greetings/check-ins, switch to "most recent user turns" to prevent invented narrative.
    if _is_continuity_query(query) and anchors:
        low = sum(1 for a in anchors if _is_low_substance_user_turn(a.get("doc", "")))
        if (low / max(1, len(anchors))) >= 0.60:
            # Pull ALL user turns and sort by dt locally (Chroma versions vary on sorting support).
            got = col.get(
                where={"role": "user"}, include=["documents", "metadatas", "ids"]
            )

            all_docs = got.get("documents") or []
            all_mds = got.get("metadatas") or []
            all_ids = got.get("ids") or []

            rows = []
            for d, md, _id in zip(all_docs, all_mds, all_ids):
                if not isinstance(md, dict):
                    continue
                if str(md.get("role", "")).lower() != "user":
                    continue

                dt = _parse_dt_from_meta(md)
                if dt is None:
                    continue

                sid = md.get("session_id")
                tidx = md.get("turn_index")

                # tolerate int-like strings
                try:
                    tidx = int(tidx)
                except Exception:
                    continue

                if not isinstance(sid, str) or not sid.strip():
                    continue

                rows.append((dt, sid, tidx, (d or "").strip(), _id))

            # newest first
            rows.sort(key=lambda t: t[0], reverse=True)
            rows = rows[: int(top_k)]

            # Rebuild anchors as the most recent real user turns
            anchors = [
                {"session_id": sid, "turn_index": tidx, "doc": doc, "id": _id}
                for _, sid, tidx, doc, _id in rows
            ]
    # --- end CANON v2 recency fallback ------------------------------------------

    # --- Stage A: user-only retrieve ----------------------------------------

    fetch_k = max(int(top_k) * 5, int(top_k))

    clean_q = normalize_text(query)
    vec = embed_text(clean_q)

    res = col.query(
        query_embeddings=[vec],
        n_results=fetch_k,
        where={"role": "user"},
        include=["documents", "metadatas", "distances"],
    )

    docs = (res.get("documents") or [[]])[0] or []
    mds = (res.get("metadatas") or [[]])[0] or []
    dists = (res.get("distances") or [[]])[0] or []
    ids = (res.get("ids") or [[]])[0] or []  # returned even if not in include
    # score anchors (small rerank layer) + dedupe sessions
    scored: List[Dict[str, Any]] = []
    seen_key = set()

    for doc, md, dist, _id in zip(docs, mds, dists, ids):
        if not isinstance(md, dict):
            continue

        sid = md.get("session_id")
        tidx = _safe_int(md.get("turn_index"))
        role = (md.get("role") or "").strip().lower()

        if role != "user":
            continue
        if not isinstance(sid, str) or not sid.strip():
            continue
        if tidx is None:
            continue

        key = (sid, tidx)
        if key in seen_key:
            continue
        seen_key.add(key)

        doc_s = (doc or "").strip()
        if not doc_s:
            continue

        dt = _parse_dt_from_meta(md)

        # Chroma cosine distance: lower is better. Convert to similarity-ish.
        base = 0.0
        try:
            base = 1.0 - float(dist)
        except Exception:
            base = 0.0

        # Primary: semantic similarity.
        score = base

        # Secondary: prefer informative user anchors.
        score += 0.12 * float(_info_density(doc_s))

        # Strongly avoid phatic check-ins on continuity queries.
        if _is_continuity_query(query) and _is_low_substance_user_turn(doc_s):
            score -= 0.35
        elif _is_low_substance_user_turn(doc_s):
            score -= 0.10

        scored.append(
            {
                "score": score,
                "dt": dt,
                "session_id": sid,
                "turn_index": tidx,
                "doc": doc_s,
                "id": _id,
            }
        )

    # Sort by score, then by recency (if available)
    scored.sort(key=lambda x: (x["score"], x.get("dt") or datetime.min), reverse=True)

    # Prefer diversity: at most one anchor per session_id (backfill if needed)
    anchors: List[Dict[str, Any]] = []
    seen_sessions = set()
    chosen_ids = set()

    for a in scored:
        if a["session_id"] in seen_sessions:
            continue
        anchors.append(a)
        seen_sessions.add(a["session_id"])
        chosen_ids.add(a["id"])
        if len(anchors) >= int(top_k):
            break

    if len(anchors) < int(top_k):
        for a in scored:
            if a["id"] in chosen_ids:
                continue
            anchors.append(a)
            chosen_ids.add(a["id"])
            if len(anchors) >= int(top_k):
                break
    # If user asked for continuity and our similarity-selected anchors are mostly
    # greetings/check-ins, switch to "most recent user turns" to prevent invented narrative.
    if _is_continuity_query(query) and anchors:
        low = sum(1 for a in anchors if _is_low_substance_user_turn(a.get("doc", "")))
        if (low / len(anchors)) >= 0.60:
            got = col.get(
                where={"role": "user"}, include=["documents", "metadatas", "ids"]
            )

            all_docs = got.get("documents") or []
            all_mds = got.get("metadatas") or []
            all_ids = got.get("ids") or []

            rows = []
            for d, md, _id in zip(all_docs, all_mds, all_ids):
                if not isinstance(md, dict):
                    continue
                if str(md.get("role", "")).lower() != "user":
                    continue

                dt = _parse_dt_from_meta(md)
                if dt is None:
                    continue

                sid = md.get("session_id")
                tidx = md.get("turn_index")
                try:
                    tidx = int(tidx)
                except Exception:
                    continue

                if not isinstance(sid, str) or not sid.strip():
                    continue

                rows.append((dt, sid, tidx, (d or "").strip(), _id))

            rows.sort(key=lambda t: t[0], reverse=True)
            rows = rows[: int(top_k)]

            anchors = [
                {"session_id": sid, "turn_index": tidx, "doc": doc, "id": _id}
                for _, sid, tidx, doc, _id in rows
            ]

    out: List[str] = []

    # --- Pair each anchor with immediate assistant turn (deterministic id) ---
    for a in anchors:
        sid = a["session_id"]
        tidx = a["turn_index"]
        user_doc = a["doc"]

        assistant_doc = ""
        assistant_id = f"{sid}:assistant:{tidx+1:04d}"

        try:
            got = col.get(ids=[assistant_id], include=["documents", "metadatas"])
            p_docs = got.get("documents") or []
            if p_docs and isinstance(p_docs[0], str):
                assistant_doc = p_docs[0].strip()
        except Exception:
            assistant_doc = ""

        # cap assistant context (keeps “mythic flourish” from dominating)
        if assistant_doc and len(assistant_doc) > 400:
            assistant_doc = assistant_doc[:400].rstrip() + "…"

        if assistant_doc:
            out.append(f"User: {user_doc}\nAssistant: {assistant_doc}")
        else:
            out.append(f"User: {user_doc}")

    # --- Assistant-only fallback (cap 2) ------------------------------------

    if len(out) < int(top_k):
        need = int(top_k) - len(out)
        cap = min(2, need)

        ares = col.query(
            query_embeddings=[vec],
            n_results=max(cap * 5, cap),
            where={"role": "assistant"},
            include=["documents", "distances"],
        )
        a_docs = (ares.get("documents") or [[]])[0] or []
        a_dists = (ares.get("distances") or [[]])[0] or []

        # Demote long assistant prose hard in fallback
        cands = []
        for d, dist in zip(a_docs, a_dists):
            if not isinstance(d, str):
                continue
            s = d.strip()
            if not s:
                continue
            try:
                base = 1.0 - float(dist)
            except Exception:
                base = 0.0
            penalty = 0.0
            if len(s) > 400:
                penalty += 0.30
            cands.append((base - penalty, s))

        cands.sort(key=lambda t: t[0], reverse=True)
        for _, s in cands[:cap]:
            if len(s) > 400:
                s = s[:400].rstrip() + "…"
            out.append(f"Assistant (fallback): {s}")

    return out


def add_semantic_entry(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    min_length: int = 6,
) -> Optional[str]:
    """
    Insert a semantic memory entry (live semantic LTM).

    Dedupe is done by content-hash ID so repeated promotions don't create duplicates.
    """
    clean = normalize_text(text)

    if len(clean.split()) < min_length:
        return None

    col = _semantic()

    hid = hashlib.sha1(clean.encode("utf-8")).hexdigest()[:16]
    new_id = f"semantic-{hid}"

    # If it already exists, skip
    try:
        existing = col.get(ids=[new_id], include=[])
        if existing and existing.get("ids"):
            return None
    except Exception:
        pass

    vector = embed_text(clean)

    upsert_kwargs = dict(ids=[new_id], embeddings=[vector], documents=[clean])
    if metadata is not None:
        upsert_kwargs["metadatas"] = [metadata]

    col.upsert(**upsert_kwargs)
    return new_id


def add_semantic_candidate(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    min_length: int = 6,
) -> Optional[str]:
    """
    Insert a semantic candidate (staging). Less strict than semantic LTM.

    Dedupe is done by content-hash ID so repeated candidates don't create duplicates.
    """
    clean = normalize_text(text)
    clean = strip_leading_greeting_if_meaningful(clean)

    if len(clean.split()) < min_length:
        return None

    if is_low_value_candidate(clean, metadata):
        return None

    col = _semantic_candidates()

    # Content-addressed ID (stable across runs)
    hid = hashlib.sha1(clean.encode("utf-8")).hexdigest()[:16]
    new_id = f"semcand-{hid}"

    # If it already exists, skip
    try:
        existing = col.get(ids=[new_id], include=[])
        if existing and existing.get("ids"):
            return None
    except Exception:
        # If get() fails, we still proceed (best-effort)
        pass

    vector = embed_text(clean)

    upsert_kwargs = dict(ids=[new_id], embeddings=[vector], documents=[clean])
    if metadata is not None:
        upsert_kwargs["metadatas"] = [metadata]

    col.upsert(**upsert_kwargs)
    return new_id


def recall_semantic(query: str, top_k: int = 6) -> List[str]:
    """
    Retrieve semantic memories most relevant to `query`.
    """
    col = _semantic()

    if col.count() == 0:
        return []

    res = col.query(query_texts=[query], n_results=top_k)
    docs = res.get("documents", [[]])[0]
    return docs or []


# -------------------------------------------------------------
# Statistics
# -------------------------------------------------------------


def memory_stats() -> Dict[str, Any]:
    p = _persona()
    e = _episodic()
    s = _semantic()
    c = _semantic_candidates()

    return {
        "persona_entries": p.count(),
        "episodic_entries": e.count(),
        "semantic_entries": s.count(),
        "semantic_candidate_entries": c.count(),
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

    _ARCHIVIST_BUFFER.append({"role": "user", "content": text})
    _semantic_nag_if_needed()


def on_assistant_turn(text: str, **metadata) -> None:
    """
    Legacy hook used by the orion_ltm extension for assistant messages.
    """
    meta = {"role": "assistant", "source": "tgwui"}
    if metadata:
        meta.update(metadata)
    add_episodic_entry(text, metadata=meta, min_length=10)

    _ARCHIVIST_BUFFER.append({"role": "assistant", "content": text})
    _run_archivist_if_ready()
    _semantic_nag_if_needed()


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
    "_persona",
    "_episodic",
    "_semantic",
    "_semantic_candidates",
    "SEMANTIC_COLLECTION",
    "SEMANTIC_CANDIDATES_COLLECTION",
    "add_semantic_entry",
    "add_semantic_candidate",
    "recall_semantic",
]
