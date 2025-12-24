from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from orion_cli.shared.memory_core import add_semantic_candidate


SEMANTIC_YAML = Path("user_data/orion/data/semantic.yaml")


def main() -> int:
    if not SEMANTIC_YAML.exists():
        print(f"semantic.yaml not found at: {SEMANTIC_YAML}")
        return 1

    data: Dict[str, Any] = (
        yaml.safe_load(SEMANTIC_YAML.read_text(encoding="utf-8")) or {}
    )

    seed_facts: List[str] = data.get("seed_facts") or []
    meta_defaults: Dict[str, Any] = data.get("seed_meta_defaults") or {}

    if not seed_facts:
        print("No seed_facts found in semantic.yaml")
        return 1

    inserted = 0
    for fact in seed_facts:
        fact = (fact or "").strip()
        if not fact:
            continue

        new_id = add_semantic_candidate(fact, metadata=meta_defaults)
        if new_id:
            inserted += 1
            print(f"+ {new_id}: {fact}")
        else:
            print(f"- skipped (filtered or duplicate): {fact}")

    print(f"Done. Inserted {inserted} semantic candidates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
