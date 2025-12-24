import sys
import json
from pathlib import Path

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


def clear_mock_dialog_entries(source_value: str = "mock_dialog") -> None:
    col = _persona()
    try:
        col.delete(where={"source": source_value})
        print(f"[mock] Cleared existing persona entries with source='{source_value}'.")
    except Exception as e:
        print(f"[mock] WARNING: failed to clear mock_dialog entries: {e}")


def ingest_mock_json(path: Path, reset_mock: bool = True) -> None:
    if not path.exists():
        raise FileNotFoundError(path)

    print(f"[mock] Ingesting mock persona from: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("mock_compatible.json must be a list of objects.")

    if reset_mock:
        clear_mock_dialog_entries()

    before = memory_stats()
    print(f"[mock] Before: {before}")

    added = 0
    skipped = 0

    for idx, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            skipped += 1
            continue

        text = (entry.get("text") or "").strip()
        if not text:
            skipped += 1
            continue

        meta_raw = entry.get("metadata") or {}
        # ensure source flag is present
        meta_raw.setdefault("source", "mock_dialog")
        metadata = flatten_metadata(meta_raw)

        new_id = add_persona_entry(text, metadata=metadata)
        if new_id:
            added += 1
            if added <= 3 or added % 5 == 0:
                print(f"[mock] + item {idx} -> {new_id}")
        else:
            skipped += 1

    after = memory_stats()
    print(f"[mock] After: {after}")
    print(f"[mock] Done. Added {added}, skipped {skipped}.")


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        print("Usage: python mock_ingest_overwrite.py PATH_TO_mock_compatible.json")
        raise SystemExit(1)

    mock_path = Path(argv[1])
    ingest_mock_json(mock_path, reset_mock=True)


if __name__ == "__main__":
    main(sys.argv)
