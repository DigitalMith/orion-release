import sys
from pathlib import Path
import json
import re

from orion_cli.shared.memory_core import add_episodic_entry, memory_stats


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


def parse_orion_name_blocks(path: Path):
    text = path.read_text(encoding="utf-8")
    # Split on blank lines
    blocks = re.split(r"\n\s*\n", text.strip(), flags=re.MULTILINE)

    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue

        rec = {}
        for ln in lines:
            if ":" not in ln:
                continue
            key_part, val_part = ln.split(":", 1)
            key = key_part.strip().strip('"')
            val = val_part.strip().strip('"').rstrip(",")
            rec[key] = val

        if "content" in rec:
            yield rec


def ingest_orion_name_chat(path: Path, min_length: int = 10) -> None:
    if not path.exists():
        raise FileNotFoundError(path)

    print(f"[episodic-orion-name] Ingesting {path}")
    before = memory_stats()
    print(f"[episodic-orion-name] Before: {before}")

    added = 0
    skipped = 0

    for idx, rec in enumerate(parse_orion_name_blocks(path), start=1):
        text = (rec.get("content") or "").strip()
        if not text:
            skipped += 1
            continue

        meta_raw = {k: v for k, v in rec.items() if k != "content"}
        meta_raw["ingest_source"] = "orion_name_chat"
        metadata = flatten_metadata(meta_raw)

        new_id = add_episodic_entry(text, metadata=metadata, min_length=min_length)
        if new_id:
            added += 1
            if added <= 5 or added % 5 == 0:
                print(f"[episodic-orion-name] + block {idx} -> {new_id}")
        else:
            skipped += 1

    after = memory_stats()
    print(f"[episodic-orion-name] After: {after}")
    print(f"[episodic-orion-name] Done. Added {added}, skipped {skipped}.")


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        print("Usage: python ingest_orion_name_chat.py PATH_TO_orion_name_chat.jsonl")
        raise SystemExit(1)

    ingest_orion_name_chat(Path(argv[1]))


if __name__ == "__main__":
    main(sys.argv)
