import json
import sys
from pathlib import Path

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


def ingest_annotated_jsonl(path: Path, min_length: int = 10) -> None:
    if not path.exists():
        raise FileNotFoundError(path)

    print(f"[episodic-annotated] Ingesting {path}")
    before = memory_stats()
    print(f"[episodic-annotated] Before: {before}")

    added = 0
    skipped = 0

    with path.open("r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[WARN] Line {line_idx}: JSON decode error: {e}")
                skipped += 1
                continue

            user_text = (rec.get("user") or "").strip()
            response_text = (rec.get("response") or "").strip()

            # We store the ASSISTANT response as the episodic text
            if not response_text:
                skipped += 1
                continue

            meta_raw = rec.get("metadata") or {}
            # Add some useful top-level fields into metadata
            meta_raw = {
                **meta_raw,
                "user_prompt": user_text,
                "timestamp": rec.get("timestamp"),
                "source_file": rec.get("source_file"),
                "ingest_source": "annotated_logs_jsonl",
            }

            metadata = flatten_metadata(meta_raw)

            new_id = add_episodic_entry(
                response_text,
                metadata=metadata,
                min_length=min_length,
            )
            if new_id:
                added += 1
                if added <= 5 or added % 50 == 0:
                    print(f"[episodic-annotated] + line {line_idx} -> {new_id}")
            else:
                skipped += 1

    after = memory_stats()
    print(f"[episodic-annotated] After: {after}")
    print(f"[episodic-annotated] Done. Added {added}, skipped {skipped}.")


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        print("Usage: python ingest_annotated_logs.py PATH_TO_annotated_logs.jsonl")
        raise SystemExit(1)
    ingest_annotated_jsonl(Path(argv[1]))


if __name__ == "__main__":
    main(sys.argv)
