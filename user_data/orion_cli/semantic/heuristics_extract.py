from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, List


KEEP_PHRASES = (
    "i prefer",
    "i like",
    "my favorite",
    "i use",
    "i want",
    "i need",
    "i am on",
    "i work on",
    "i'm on",
    "powershell",
    "windows",
    "linux",
    "macos",
    "config.yaml",
    "chroma",
    "embedding",
    "ollama",
    "localhost",
    "http://",
    "https://",
    "github.com",
    "c:\\",
)

PATH_RE = re.compile(r"\b[A-Za-z]:\\")
URL_RE = re.compile(r"https?://", re.IGNORECASE)


def _extract_texts(obj: Any) -> Iterable[str]:
    """
    Extract message-like text from your normalized format and common variants.

    Your format (confirmed):
      - {"user_text": "...", "assistant_text": "...", ...}

    Also supports:
      - {"text": "..."} / {"content": "..."} / {"message": "..."} / {"value": "..."}
      - {"message": {"content": "..."}}
      - {"messages": [{"role":..., "content":...}, ...]}
      - {"turns": [...]} or {"data": [...]} or list-of-dicts
    """
    if obj is None:
        return

    if isinstance(obj, list):
        for item in obj:
            yield from _extract_texts(item)
        return

    if isinstance(obj, dict):
        # Your normalized keys + common keys
        for k in ("user_text", "assistant_text", "text", "content", "message", "value"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                yield v

        # Nested message dict
        v = obj.get("message")
        if isinstance(v, dict):
            c = v.get("content") or v.get("text")
            if isinstance(c, str) and c.strip():
                yield c

        # OpenAI-ish messages array
        msgs = obj.get("messages")
        if isinstance(msgs, list):
            for m in msgs:
                if isinstance(m, dict):
                    c = m.get("content") or m.get("text")
                    if isinstance(c, str) and c.strip():
                        yield c

        # Other container arrays
        for k in ("turns", "data", "items", "entries", "log"):
            v = obj.get(k)
            if isinstance(v, list):
                for item in v:
                    yield from _extract_texts(item)


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    out: List[str] = []
    for p in parts:
        s = " ".join(p.strip().split())
        if s:
            out.append(s)
    return out


def _is_keeper(s: str) -> bool:
    sl = s.lower()
    if any(k in sl for k in KEEP_PHRASES):
        return True
    if PATH_RE.search(s):
        return True
    if URL_RE.search(s):
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--max", dest="max_out", type=int, default=0, help="0 = no limit")
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    wrote = 0
    read_lines = 0
    parsed = 0
    extracted_texts = 0
    keeper_sents = 0

    with inp.open("r", encoding="utf-8") as f, out.open("w", encoding="utf-8") as w:
        for line in f:
            read_lines += 1
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                parsed += 1
            except Exception:
                continue

            for t in _extract_texts(obj):
                extracted_texts += 1
                for s in _sentences(t):
                    if not _is_keeper(s):
                        continue
                    keeper_sents += 1
                    if s in seen:
                        continue
                    seen.add(s)
                    w.write(
                        json.dumps(
                            {
                                "text": s,
                                "meta": {
                                    "source": "heuristics",
                                    "confidence": 1.0,
                                    "tags": "heuristic",
                                },
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    wrote += 1
                    if args.max_out and wrote >= args.max_out:
                        break
                if args.max_out and wrote >= args.max_out:
                    break
            if args.max_out and wrote >= args.max_out:
                break

    print(
        f"[heuristics] lines={read_lines} parsed={parsed} extracted_texts={extracted_texts} keeper_sents={keeper_sents} wrote={wrote} out={out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
