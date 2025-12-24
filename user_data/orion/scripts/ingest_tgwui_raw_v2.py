from __future__ import annotations

import json
import html
import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from orion_cli.shared.memory_core import add_episodic_entry

_TS_RE = re.compile(r"(\d{8}-\d{2}-\d{2}-\d{2})")  # e.g. 20250502-19-36-17

CHAT_DIR = Path(r"C:\Orion\text-generation-webui\user_data\orion\logs\chat")
REJECTS = CHAT_DIR / "rejects.tgwui_raw_v2.jsonl"

# Strip prompt glue / scaffolding; keep mythic tone if it's real dialogue.
JUNK_MARKERS = (
    "[PERSONA]",
    "<|im_start|>",
    "<|im_end|>",
    "[Missing persona header]",
    "<LTM",
    "</s>",
)


def _looks_junky(s: str) -> bool:
    return any(m in s for m in JUNK_MARKERS)


def _safe_read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _try_parse_json(raw: str) -> Optional[Any]:
    raw = raw.lstrip("\ufeff").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    # Trim to outermost braces (common "extra junk after JSON" failure)
    i = raw.find("{")
    j = raw.rfind("}")
    if i != -1 and j != -1 and j > i:
        trimmed = raw[i : j + 1]
        try:
            return json.loads(trimmed)
        except Exception:
            pass
    return None


def _extract_messages(obj: Any) -> tuple[str, List[Dict[str, str]]]:
    out: List[Dict[str, str]] = []

    # Variant 1: {"messages":[{"role":"user","content":"..."}, ...]}
    if isinstance(obj, dict) and isinstance(obj.get("messages"), list):
        for m in obj["messages"]:
            if isinstance(m, dict):
                role = str(m.get("role", "")).lower() or "unknown"
                content = m.get("content", "")
                if isinstance(content, str) and content.strip():
                    out.append({"role": role, "content": content})
        if out:
            return ("messages", out)

    # Variant 2: {"history":[["u","a"],["u2","a2"]]}
    if isinstance(obj, dict) and isinstance(obj.get("history"), list):
        for pair in obj["history"]:
            if isinstance(pair, list) and len(pair) >= 2:
                u, a = pair[0], pair[1]
                if isinstance(u, str) and u.strip():
                    out.append({"role": "user", "content": u})
                if isinstance(a, str) and a.strip():
                    out.append({"role": "assistant", "content": a})
        if out:
            return ("history", out)

    # Variant 3: {"visible":[[u,a],...]} or {"internal":[[u,a],...]}
    for key in ("visible", "internal"):
        if isinstance(obj, dict) and isinstance(obj.get(key), list):
            for pair in obj[key]:
                if isinstance(pair, list) and len(pair) >= 2:
                    u, a = pair[0], pair[1]
                    if isinstance(u, str) and u.strip():
                        out.append({"role": "user", "content": u})
                    if isinstance(a, str) and a.strip():
                        out.append({"role": "assistant", "content": a})
            if out:
                return (key, out)

    return ("none", [])


def _clean_content(s: str) -> str:
    s = html.unescape(s or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n").strip()
    return s


def _write_reject(source_file: str, reason: str, snippet: str) -> None:
    REJECTS.parent.mkdir(parents=True, exist_ok=True)
    rec = {"source_file": source_file, "reason": reason, "snippet": snippet[:400]}
    with REJECTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _ts_from_filename(name: str) -> str | None:
    """
    Extract ISO timestamp from TGWUI chat filename.
    Expected: YYYYMMDD-HH-MM-SS(.json)
    Returns: 'YYYY-MM-DDTHH:MM:SS' or None if not parseable.
    """
    m = _TS_RE.search(name)
    if not m:
        return None
    dt = datetime.strptime(m.group(1), "%Y%m%d-%H-%M-%S")
    return dt.isoformat(timespec="seconds")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(CHAT_DIR / "canon.episodic_v2.jsonl"))
    ap.add_argument(
        "--commit",
        action="store_true",
        help="Write to Chroma (default: just write JSONL)",
    )
    args = ap.parse_args()

    files = sorted(CHAT_DIR.glob("*.json"))
    if not files:
        print(f"No .json files found in {CHAT_DIR}")
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_f = out_path.open("w", encoding="utf-8")

    built = 0
    ingested = 0
    skipped_junk = 0
    rejected = 0

    try:
        for p in files:
            raw = _safe_read_text(p)
            obj = _try_parse_json(raw)
            if obj is None:
                _write_reject(p.name, "unparseable_json", raw)
                rejected += 1
                continue

            source_format, msgs = _extract_messages(obj)
            if not msgs:
                _write_reject(p.name, "no_messages_found", raw)
                rejected += 1
                continue

            session_id = p.stem
            ts = _ts_from_filename(p.name)

            for idx, m in enumerate(msgs):
                role = (m.get("role") or "").lower()
                if role not in ("user", "assistant"):
                    continue

                content = _clean_content(m.get("content") or "")
                if _looks_junky(content):
                    skipped_junk += 1
                    continue

                meta = {
                    "schema_v": 1,
                    "ingest_source": "tgwui_chat",
                    "source_file": p.name,
                    "session_id": session_id,
                    "turn_index": idx,
                    "role": role,
                    "ts": ts,
                    "memory_class": "dialog_turn",
                    "trust": "verbatim",
                    "importance": None,
                    "priority": None,
                    "confidence": None,
                    "topic": None,
                    "thread_id": None,
                    "entities": [],
                    "kind": None,
                    "voice": None,
                    "era": None,
                }

                # NOTE: doc_id must exist. If you don't have it elsewhere, uncomment one:
                # doc_id = f"{session_id}:{idx}"
                # doc_id = session_id

                doc_id = f"{session_id}:{role}:{idx:04d}"

                # Always write JSONL (rich meta allowed here)
                rec = {"id": doc_id, "document": content, "metadata": meta}
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                built += 1

                # Only commit to Chroma when --commit is set
                if args.commit:
                    # Chroma metadata must be primitive types only (no None/list/dict)
                    meta_chroma = {
                        k: v
                        for k, v in meta.items()
                        if isinstance(v, (str, int, float, bool))
                    }
                    new_id = add_episodic_entry(
                        content, metadata=meta_chroma, min_length=1, doc_id=doc_id
                    )
                    if new_id:
                        ingested += 1
    finally:
        out_f.close()

    print(f"Files scanned: {len(files)}")
    print(f"Built JSONL records: {built}")
    print(f"Ingested turns: {ingested}")
    print(f"Skipped junk turns: {skipped_junk}")
    print(f"Rejected files: {rejected}")
    print(f"JSONL out: {out_path}")
    if REJECTS.exists():
        print(f"Reject log: {REJECTS}")


if __name__ == "__main__":
    main()
