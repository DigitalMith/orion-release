# bootstrap_semantic_candidates.py
# Place this in: C:\Orion\text-generation-webui\user_data\orion_cli\scripts\bootstrap_semantic_candidates.py

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from orion_cli.settings.config_loader import get_config
from orion_cli.shared.utils import normalize_text
from orion_cli.shared.memory_core import add_semantic_candidate
from orion_cli.shared.archivist_client import run_archivist_extract


def load_normalized_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def iter_turns_from_normalized(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normalized shape:
      entries: [ { user, response, timestamp, metadata }, ... ]
    """
    out: List[Dict[str, Any]] = []
    for e in data.get("entries", []):
        user = e.get("user", "")
        resp = e.get("response", "")
        ts = e.get("timestamp", None)
        md = e.get("metadata", {}) if isinstance(e.get("metadata", {}), dict) else {}

        if (
            isinstance(user, str)
            and user.strip()
            and not user.strip().startswith("<|BEGIN-")
        ):
            out.append(
                {
                    "role": "user",
                    "content": user.strip(),
                    "timestamp": ts,
                    "metadata": md,
                }
            )
        if isinstance(resp, str) and resp.strip():
            out.append(
                {
                    "role": "assistant",
                    "content": resp.strip(),
                    "timestamp": ts,
                    "metadata": md,
                }
            )
    return out


def flatten_md(md: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chroma metadata prefers scalar-ish values.
    Lists -> comma string, dict -> JSON string.
    """
    flat: Dict[str, Any] = {}
    for k, v in md.items():
        if isinstance(v, list):
            flat[k] = ",".join(str(x) for x in v if x is not None)
        elif isinstance(v, dict):
            flat[k] = json.dumps(v, ensure_ascii=False)
        else:
            flat[k] = v
    return flat


def make_windows(
    items: List[Dict[str, Any]], window: int, stride: int
) -> List[List[Dict[str, Any]]]:
    if window <= 0:
        return [items]
    stride = max(1, stride)
    out: List[List[Dict[str, Any]]] = []
    for i in range(0, max(1, len(items) - window + 1), stride):
        out.append(items[i : i + window])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Bootstrap semantic candidates from normalized chat logs (writes to Chroma)."
    )
    ap.add_argument(
        "--input",
        required=True,
        help="Normalized JSON file OR folder containing normalized_*.json files.",
    )
    ap.add_argument(
        "--window_turns", type=int, default=20, help="Messages per extraction window."
    )
    ap.add_argument("--stride", type=int, default=10, help="Window stride in messages.")
    ap.add_argument(
        "--max_windows",
        type=int,
        default=0,
        help="Limit windows processed (0 = no limit).",
    )

    ap.add_argument(
        "--min_conf",
        type=float,
        default=0.85,
        help="Only store candidates with confidence >= this.",
    )
    ap.add_argument(
        "--dry_run",
        action="store_true",
        help="Do not write to Chroma; only write review JSONL.",
    )
    ap.add_argument(
        "--review_out",
        default="semantic_bootstrap_review.jsonl",
        help="Output JSONL review file.",
    )

    args = ap.parse_args()

    cfg = get_config()
    arch = getattr(cfg, "archivist", None)
    if not arch or not getattr(arch, "enabled", False):
        raise SystemExit(
            "archivist.enabled is false. Enable archivist in config.yaml before running."
        )

    inp = Path(args.input)
    files: List[Path]
    if inp.is_dir():
        files = sorted(inp.glob("normalized_*.json"))
        if not files:
            raise SystemExit(f"No normalized_*.json files found in: {inp}")
    else:
        files = [inp]

    review_path = Path(args.review_out)
    seen: set[str] = set()
    wrote_review = 0
    wrote_chroma = 0
    windows_processed = 0

    with open(review_path, "w", encoding="utf-8") as review_f:
        for fpath in files:
            data = load_normalized_json(fpath)
            turns = iter_turns_from_normalized(data)
            wins = make_windows(turns, window=args.window_turns, stride=args.stride)

            if args.max_windows and args.max_windows > 0:
                wins = wins[: args.max_windows]

            for w in wins:
                windows_processed += 1

                pooled = [{"role": t["role"], "content": t["content"]} for t in w]

                # Best-effort: if one window fails, keep going
                try:
                    res = run_archivist_extract(arch, pooled)
                except Exception:
                    continue

                obj = res.parsed_json or {}
                cands = obj.get("candidates", []) if isinstance(obj, dict) else []
                if not isinstance(cands, list):
                    continue

                last = w[-1] if w else {}
                last_md = (
                    last.get("metadata", {})
                    if isinstance(last.get("metadata", {}), dict)
                    else {}
                )
                base_meta = {
                    "source": "bootstrap",
                    "source_file": fpath.name,
                    "timestamp": last.get("timestamp"),
                    "archivist_model": str(getattr(arch, "model", "")),
                }
                base_meta.update(flatten_md(last_md))

                for c in cands:
                    if not isinstance(c, dict):
                        continue

                    text = c.get("text", "")
                    conf = c.get("confidence", 0.0)
                    tags = c.get("tags", "")

                    if not isinstance(text, str) or not text.strip():
                        continue
                    if not isinstance(conf, (int, float)):
                        conf = 0.0
                    if float(conf) < float(args.min_conf):
                        continue

                    if isinstance(tags, list):
                        tags = ",".join(str(t) for t in tags if t is not None)
                    elif tags is None:
                        tags = ""
                    else:
                        tags = str(tags)

                    norm = normalize_text(text)
                    if norm in seen:
                        continue
                    seen.add(norm)

                    meta = dict(base_meta)
                    meta.update({"confidence": float(conf), "tags": tags})

                    record = {"text": norm, "meta": meta}
                    review_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    wrote_review += 1

                    if args.dry_run:
                        continue

                    new_id = add_semantic_candidate(norm, metadata=meta)
                    if new_id:
                        wrote_chroma += 1

    print(
        f"[bootstrap] windows={windows_processed} review_written={wrote_review} chroma_written={wrote_chroma} out={review_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
