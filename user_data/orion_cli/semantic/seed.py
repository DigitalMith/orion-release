from __future__ import annotations

from pathlib import Path

import yaml

from orion_cli.shared.memory_core import add_semantic_candidate
from orion_cli.settings.config_loader import get_config
from orion_cli.shared.archivist_client import run_archivist_extract


def seed_from_yaml(path: Path) -> int:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    seed_facts = data.get("seed_facts") or []
    meta_defaults = data.get("seed_meta_defaults") or {}

    cfg = get_config()
    arch = getattr(cfg, "archivist", None)
    if not arch or not getattr(arch, "enabled", False):
        raise RuntimeError("Archivist must be enabled to ingest semantic.yaml safely.")

    inserted = 0
    for raw in seed_facts:
        raw = (raw or "").strip()
        if not raw:
            continue

        pooled = [{"role": "user", "content": raw}]
        res = run_archivist_extract(arch, pooled)
        out = res.parsed_json or {}

        if not isinstance(out, dict) or out.get("relevant") is not True:
            continue

        for f in out.get("facts") or []:
            text = (f.get("text") or "").strip()
            cat = (f.get("category") or "").strip()
            conf = f.get("confidence", 0.0)

            if not text or not cat:
                continue

            meta = dict(meta_defaults)
            meta.update(
                {
                    "source": "semantic_onboarding",
                    "category": cat,
                    "confidence": float(conf),
                }
            )
            if add_semantic_candidate(text, metadata=meta):
                inserted += 1

    return inserted
