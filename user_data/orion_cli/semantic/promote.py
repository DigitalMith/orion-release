from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from orion_cli.shared.memory_core import _semantic_candidates, add_semantic_entry
from orion_cli.semantic.filters import is_low_value_candidate, confidence


def promote_candidates(
    *,
    limit: int = 50,
    min_conf: float = 0.0,
    source: Optional[str] = None,
    delete_from_candidates: bool = False,
) -> Tuple[int, int]:
    """
    Promote candidates into semantic LTM.

    Selection:
      - optional source filter (metadata["source"])
      - confidence >= min_conf (if present)
      - reject obvious low-value candidates (greetings/compliments) via filters.py

    Returns: (promoted_count, scanned_count)
    """
    c = _semantic_candidates()
    n = c.count()
    if n == 0:
        return (0, 0)

    res = c.get(include=["documents", "metadatas"])
    docs: List[str] = res.get("documents", []) or []
    metas: List[Dict[str, Any]] = res.get("metadatas", []) or []
    ids: List[str] = res.get("ids", []) or []

    promoted = 0
    scanned = 0
    to_delete: List[str] = []

    for doc, meta, cid in zip(docs, metas, ids):
        scanned += 1
        if promoted >= limit:
            break

        meta = meta or {}

        if source and meta.get("source") != source:
            continue

        if confidence(meta) < float(min_conf):
            continue

        if is_low_value_candidate(doc, meta):
            continue

        new_id = add_semantic_entry(doc, metadata=meta)
        if new_id:
            promoted += 1
            if delete_from_candidates:
                to_delete.append(cid)

    if delete_from_candidates and to_delete:
        c.delete(ids=to_delete)

    return (promoted, scanned)
