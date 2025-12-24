import sys
import json
from pathlib import Path

import yaml

from orion_cli.shared.memory_core import _persona, add_persona_entry, memory_stats


def flatten_metadata(meta: dict) -> dict:
    flat = {}
    for k, v in (meta or {}).items():
        if isinstance(v, list):
            flat[k] = ",".join(str(x) for x in v)
        elif isinstance(v, dict):
            flat[k] = json.dumps(v, ensure_ascii=False)
        else:
            flat[k] = v
    return flat


def reset_persona_collection() -> None:
    col = _persona()
    # Chroma convention: delete(where={}) → delete all docs
    try:
        col.delete(where={})
        print("[persona] Cleared existing persona collection.")
    except Exception as e:
        print(f"[persona] WARNING: failed to clear persona collection: {e}")


def ingest_persona_yaml(path: Path, reset: bool = True) -> None:
    if not path.exists():
        raise FileNotFoundError(path)

    print(f"[persona] Ingesting persona from: {path}")

    # Multi-document YAML (--- between docs)
    with path.open("r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))

    if reset:
        reset_persona_collection()

    before = memory_stats()
    print(f"[persona] Before: {before}")

    added = 0
    skipped = 0

    for idx, doc in enumerate(docs, start=1):
        if not doc or not isinstance(doc, dict):
            skipped += 1
            continue

        raw_text = doc.get("text", "")
        if not isinstance(raw_text, str):
            skipped += 1
            continue

        text_entry = raw_text.strip()
        if not text_entry:
            skipped += 1
            continue

        meta_raw = {k: v for k, v in doc.items() if k != "text"}
        metadata = flatten_metadata(meta_raw)

        new_id = add_persona_entry(text_entry, metadata=metadata)
        if new_id:
            added += 1
            if added <= 5 or added % 20 == 0:
                print(f"[persona] + doc {idx} -> {new_id}")
        else:
            skipped += 1

    after = memory_stats()
    print(f"[persona] After: {after}")
    print(f"[persona] Done. Added {added}, skipped {skipped}.")


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        print("Usage: python persona_ingest_overwrite.py PATH_TO_persona.yaml")
        raise SystemExit(1)

    persona_path = Path(argv[1])
    ingest_persona_yaml(persona_path, reset=True)


if __name__ == "__main__":
    main(sys.argv)
