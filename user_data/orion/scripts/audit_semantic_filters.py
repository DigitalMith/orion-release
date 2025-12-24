from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from orion_cli.semantic.filters import (
    is_low_value_candidate,
    strip_leading_greeting_if_meaningful,
)
from orion_cli.shared.utils import normalize_text


INPUT = Path("user_data/orion/workspace/normalized/normalized_legacy.jsonl")
OUTPUT = Path("user_data/orion/workspace/semantic_filter_audit.jsonl")


def extract_text(row: Dict[str, Any]) -> str:
    """Best-effort extraction for common JSONL shapes."""
    for key in ("accepted_text", "text", "content", "message", "value"):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # sometimes nested
    msg = row.get("data") or row.get("payload") or {}
    if isinstance(msg, dict):
        for key in ("text", "content", "message"):
            v = msg.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def main() -> int:
    if not INPUT.exists():
        print(f"[audit] input not found: {INPUT}")
        return 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    scanned = 0
    kept = 0

    with INPUT.open("r", encoding="utf-8") as fin, OUTPUT.open(
        "w", encoding="utf-8"
    ) as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue

            scanned += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue

            raw = extract_text(row)
            if not raw:
                continue

            normalized = normalize_text(raw)
            stripped = strip_leading_greeting_if_meaningful(normalized)

            # mirror candidate gate (minus embedding + chroma insert)
            if len(stripped.split()) < 6:
                continue
            if is_low_value_candidate(stripped, meta=row):
                continue

            fout.write(
                json.dumps(
                    {
                        "original": raw,
                        "normalized": normalized,
                        "accepted_text": stripped,
                        "source_meta": row,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            kept += 1

    print(f"[audit] scanned={scanned} kept={kept}")
    print(f"[audit] output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
