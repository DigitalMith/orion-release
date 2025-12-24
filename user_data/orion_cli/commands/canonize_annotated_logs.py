from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from orion_cli.settings.config_loader import get_config
from orion_cli.shared.memory_core import add_episodic_entry

SENTINELS = {
    "<|BEGIN-VISIBLE-CHAT|>",
    "<|END-VISIBLE-CHAT|>",
    "<|BEGIN-CHAT|>",
    "<|END-CHAT|>",
}


def sha1_hex_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def sha1_hex_str(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()


def file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def compact_ts(ts: str) -> str:
    # "2025-11-10T08:44:55" -> "20251110T084455"
    out = []
    for ch in ts:
        if ch.isdigit():
            out.append(ch)
        elif ch == "T":
            out.append("T")
    return "".join(out)


def parse_ts_from_source_file(source_file: str) -> Optional[str]:
    # "20251110-08-44-55.json" -> "2025-11-10T08:44:55"
    try:
        stem = Path(source_file).stem
        dt = datetime.strptime(stem, "%Y%m%d-%H-%M-%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def flatten_for_chroma(md: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chroma metadata should be scalar JSON types. We coerce lists/dicts to strings.
    """
    out: Dict[str, Any] = {}
    for k, v in (md or {}).items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, list):
            out[k] = ",".join(str(x) for x in v)
        else:
            out[k] = json.dumps(v, ensure_ascii=False)
    return out


def make_uid(ts: str, role: str, pair_index: int, text: str, source_file: str) -> str:
    # Stable across re-runs; readable; idempotent
    h = sha1_hex_str(f"{source_file}|{ts}|{role}|{text}")[:10]
    return f"ep_{compact_ts(ts)}_{role}_{pair_index:06d}_{h}"


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for obj in rows:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def build_meta_header(
    source_path: str,
    source_sha1: str,
    pair_count: int,
    ts_min: Optional[str],
    ts_max: Optional[str],
) -> Dict[str, Any]:
    return {
        "_meta": {
            "schema": "orion.canon.chatlog.v1",
            "created_local": datetime.now().strftime("%Y-%m-%d"),
            "source_path": source_path,
            "source_sha1": source_sha1,
            "pair_count": pair_count,
            "time_range": {"min": ts_min, "max": ts_max},
            "id_scheme": "ep_<ts>_<role>_<pair_index>_<sha1_10>",
            "notes": "Generated from annotated_logs.jsonl; deterministic IDs; safe for idempotent re-ingest",
        }
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--in", dest="in_path", required=True, help="Path to annotated_logs.jsonl"
    )
    ap.add_argument(
        "--out", dest="out_path", required=True, help="Path to canon output JSONL"
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit canon file only; do not ingest to Chroma",
    )
    ap.add_argument(
        "--skip-sentinels",
        action="store_true",
        help="Skip sentinel pairs like <|BEGIN-VISIBLE-CHAT|>",
    )
    ap.add_argument(
        "--min-length", type=int, default=1, help="Min chars to store as episodic entry"
    )
    args = ap.parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)

    cfg = get_config()  # for chroma_path visibility in logs only

    pairs = []
    ts_vals = []
    for obj in iter_jsonl(in_path):
        if "_meta" in obj:
            # ignore any prior meta line; we'll write our own
            continue
        pairs.append(obj)
        t = obj.get("timestamp")
        if isinstance(t, str) and t.strip():
            ts_vals.append(t.strip())

    ts_vals.sort()
    ts_min = ts_vals[0] if ts_vals else None
    ts_max = ts_vals[-1] if ts_vals else None

    header = build_meta_header(
        source_path=str(in_path),
        source_sha1=file_sha1(in_path),
        pair_count=len(pairs),
        ts_min=ts_min,
        ts_max=ts_max,
    )

    rows_out = [header]

    ingested = 0
    skipped_pairs = 0

    for i, p in enumerate(pairs):
        user = (p.get("user") or "").strip()
        resp = (p.get("response") or "").strip()
        ts = (p.get("timestamp") or "").strip()
        source_file = (p.get("source_file") or "").strip()
        md = dict(p.get("metadata") or {})

        if args.skip_sentinels and user in SENTINELS:
            skipped_pairs += 1
            continue

        if not ts:
            ts_guess = parse_ts_from_source_file(source_file) if source_file else None
            ts = ts_guess or ""

        source_block = {
            "kind": "annotated_logs_jsonl",
            "file": source_file,
            "character": "Orion",
        }

        # Human turn record
        if user:
            uid_h = make_uid(ts, "human", i, user, source_file)
            rows_out.append(
                {
                    "schema": "orion.canon.turn.v1",
                    "id": uid_h,
                    "ts": ts,
                    "role": "human",
                    "text": user,
                    "source": source_block,
                    "meta": {
                        "ingest_source": "annotated_logs_jsonl",
                        "pair_index": i,
                    },
                }
            )

            if not args.dry_run and len(user) >= args.min_length:
                md_h = flatten_for_chroma(
                    {
                        "uid": uid_h,
                        "timestamp": ts,
                        "role": "human",
                        "ingest_source": "annotated_logs_jsonl",
                        "source_file": source_file,
                        "pair_index": i,
                        # keep annotation if you want it on both sides (optional)
                        **md,
                    }
                )
                add_episodic_entry(user, metadata=md_h, min_length=args.min_length)
                ingested += 1

        # LLM turn record
        if resp:
            uid_a = make_uid(ts, "llm", i, resp, source_file)
            rows_out.append(
                {
                    "schema": "orion.canon.turn.v1",
                    "id": uid_a,
                    "ts": ts,
                    "role": "llm",
                    "text": resp,
                    "source": source_block,
                    "meta": {
                        "ingest_source": "annotated_logs_jsonl",
                        "pair_index": i,
                        "user_prompt": user,
                        **md,
                    },
                }
            )

            if not args.dry_run and len(resp) >= args.min_length:
                md_a = flatten_for_chroma(
                    {
                        "uid": uid_a,
                        "timestamp": ts,
                        "role": "llm",
                        "ingest_source": "annotated_logs_jsonl",
                        "source_file": source_file,
                        "pair_index": i,
                        "user_prompt": user,
                        **md,
                    }
                )
                add_episodic_entry(resp, metadata=md_a, min_length=args.min_length)
                ingested += 1

    write_jsonl(out_path, rows_out)

    print(f"[ok] wrote canon: {out_path}")
    print(f"[ok] pairs read: {len(pairs)} | skipped_pairs: {skipped_pairs}")
    if args.dry_run:
        print("[dry-run] did not ingest to Chroma")
    else:
        print(f"[ok] ingested episodic entries: {ingested}")
        print(f"[ok] chroma_path: {cfg.chroma_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
