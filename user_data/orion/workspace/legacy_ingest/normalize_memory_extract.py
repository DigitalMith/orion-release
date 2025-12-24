import sys
import json
import re
from pathlib import Path
from typing import List, Optional

from orion_cli.shared.memory_core import add_episodic_entry, memory_stats


# ===========================
# SIMPLE TEXT SPLITTERS
# ===========================


def split_paragraphs(text: str) -> List[str]:
    """Split on blank lines."""
    blocks = re.split(r"\n\s*\n", text.strip(), flags=re.MULTILINE)
    return [b.strip() for b in blocks if b.strip()]


def split_bullets(text: str) -> List[str]:
    """Split on bullet-style lines, keep each bullet as its own chunk."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    chunks = []
    current = []

    def flush():
        if current:
            chunk = "\n".join(current).strip()
            if chunk:
                chunks.append(chunk)

    for ln in lines:
        if re.match(r"^\s*[-*•]\s+", ln):
            flush()
            current[:] = [ln]
        elif ln.strip():
            current.append(ln)
        else:
            flush()
            current = []

    flush()
    return chunks


def split_smart(text: str) -> List[str]:
    """
    Hybrid mode:
    - split on blank lines
    - treat single-line headings (ending ':' or ALL CAPS) as their own chunk if short
    """
    paragraphs = split_paragraphs(text)
    chunks: List[str] = []

    for para in paragraphs:
        lines = para.splitlines()
        if len(lines) == 1:
            line = lines[0].strip()
            if len(line) <= 80 and (line.endswith(":") or line.isupper()):
                chunks.append(line)
            else:
                chunks.append(para.strip())
        else:
            chunks.append(para.strip())

    return [c for c in chunks if c]


def normalize_tags(tags: str) -> List[str]:
    if not tags:
        return []
    parts = [t.strip() for t in tags.split(",")]
    return [p for p in parts if p]


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


# ===========================
# NEMO ANNOTATOR (OPTIONAL)
# ===========================

# Based on nemo_annotate_and_ingest.py, adapted to single-text chunks. :contentReference[oaicite:1]{index=1}

ANNOTATOR_PROMPT = """
You are the Orion CNS episodic annotator.

Given a short text snippet from the user's world (notes, reflections, memories, or narrative),
produce a compact JSON object with this structure:

{
  "text": "<short distilled memory or summary of the snippet>",
  "tone": ["...", "..."],
  "affect": {
      "primary": "...",
      "valence": 0.0,
      "arousal": 0.0
  },
  "archetype": "...",
  "semantic": ["tag1","tag2","tag3"],
  "context": ["relational","intentional"],
  "weight": 0.0,
  "importance": 0.0,
  "confidence": 0.0,
  "temporal": {
      "weekday": "...",
      "tod": "...",
      "relative": null
  }
}

Rules:
- tone: 1–3 high-signal adjectives.
- affect.primary: dominant emotion.
- valence: -1.0 to +1.0
- arousal: 0.0 to 1.0
- archetype: Wanderer, Oracle, Seer, Sage, Trickster-Wanderer, etc.
- semantic: 3–6 strongest conceptual tags.
- context: identity, meaning, bonding, conflict, reflection, etc.
- weight/importance/confidence: floats 0–1.

Return ONLY JSON. No commentary.
"""


def temporal_defaults() -> dict:
    # For manual pasted docs we often don't have real timestamps;
    # keep a neutral temporal block so schema stays consistent.
    return {
        "weekday": None,
        "tod": None,
        "relative": None,
    }


_nemo_model = None  # lazy-loaded


def get_nemo_model(nemo_path: Optional[Path] = None):
    global _nemo_model
    if _nemo_model is not None:
        return _nemo_model

    # Default to same layout as nemo_annotate_and_ingest.py: ROOT/user_data/models/...
    root = Path(__file__).resolve()
    # .../text-generation-webui/user_data/orion/workspace/ingest_ready/normalize_memory_extract.py
    # parents[5] should be C:\Orion
    try:
        ROOT = root.parents[5]
    except IndexError:
        ROOT = root.parents[-1]

    if nemo_path is None:
        nemo_path = (
            ROOT / "user_data" / "models" / "Mistral-Nemo-Instruct-2407-Q6_K.gguf"
        )

    print(f"[NEMO] Loading model: {nemo_path}")
    from llama_cpp import Llama  # imported only if annotation is requested

    _nemo_model = Llama(
        model_path=str(nemo_path),
        n_gpu_layers=-1,
        n_ctx=2048,
        vocab_only=False,
    )
    return _nemo_model


def annotate_chunk_with_nemo(
    text: str, source_label: str = "", nemo_path: Optional[Path] = None
) -> Optional[dict]:
    """
    Run the Nemo annotator on a single text chunk and return the parsed JSON dict,
    or None if annotation fails.
    """
    nemo = get_nemo_model(nemo_path)

    prompt = (
        ANNOTATOR_PROMPT
        + f"""

Snippet source: {source_label or "manual_paste"}

TEXT:
{text}
"""
    )

    resp = nemo.create_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=0.5,
    )

    raw = resp["choices"][0]["message"]["content"].strip()
    try:
        data = json.loads(raw)
    except Exception:
        print(
            "[NEMO] WARN: Invalid JSON from Nemo, skipping annotation for this chunk."
        )
        return None

    # Ensure temporal key exists
    defaults = temporal_defaults()
    if "temporal" not in data or not isinstance(data["temporal"], dict):
        data["temporal"] = defaults
    else:
        for k, v in defaults.items():
            data["temporal"].setdefault(k, v)

    return data


# ===========================
# CORE EXTRACT + INGEST
# ===========================


def extract_and_ingest(
    path: Path,
    mode: str = "smart",
    source_label: str = "",
    tags: str = "",
    memory_type: str = "note",
    min_length: int = 10,
    annotate_nemo: bool = False,
    nemo_model_path: Optional[str] = None,
    out_jsonl: Optional[Path] = None,  # <--- NEW
):
    if not path.exists():
        raise FileNotFoundError(path)

    text = path.read_text(encoding="utf-8")
    print(f"[extract] Loading: {path}")

    if mode == "paragraph":
        chunks = split_paragraphs(text)
    elif mode == "bullet":
        chunks = split_bullets(text)
    elif mode == "smart":
        chunks = split_smart(text)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    print(f"[extract] Found {len(chunks)} candidate chunks (mode={mode}).")

    tag_list = normalize_tags(tags)
    before = memory_stats()
    print(f"[extract] Before: {before}")

    added = 0
    skipped = 0

    nemo_path_obj = Path(nemo_model_path) if nemo_model_path else None

    # ---------- JSONL ARCHIVE SETUP (THIS IS STEP 2) ----------
    jsonl_fh = None
    if out_jsonl is not None:
        jsonl_file = out_jsonl.resolve()
        print(f"[extract] Archiving normalized chunks to: {jsonl_file}")
        jsonl_fh = jsonl_file.open("w", encoding="utf-8")
    # ----------------------------------------------------------

    for idx, chunk in enumerate(chunks, start=1):
        words = chunk.split()
        if len(words) < min_length:
            skipped += 1
            continue

        # Base metadata
        meta_raw = {
            "ingest_source": "manual_paste",
            "source_label": source_label or path.name,
            "memory_type": memory_type,
            "seq": idx,
        }
        if tag_list:
            meta_raw["tags"] = tag_list

        # Optional Nemo enrichment
        if annotate_nemo:
            try:
                annotated = annotate_chunk_with_nemo(
                    chunk,
                    source_label=source_label or path.name,
                    nemo_path=nemo_path_obj,
                )
            except Exception as e:
                print(f"[NEMO] ERROR while annotating chunk {idx}: {e}")
                annotated = None

            if annotated:
                meta_raw.update(
                    {
                        "nemo_summary": annotated.get("text"),
                        "nemo_tone": annotated.get("tone"),
                        "nemo_affect": annotated.get("affect"),
                        "nemo_archetype": annotated.get("archetype"),
                        "nemo_semantic": annotated.get("semantic"),
                        "nemo_context": annotated.get("context"),
                        "nemo_weight": annotated.get("weight"),
                        "nemo_importance": annotated.get("importance"),
                        "nemo_confidence": annotated.get("confidence"),
                        "nemo_temporal": annotated.get("temporal"),
                    }
                )

        # ---------- WRITE TO JSONL IF REQUESTED ----------
        if jsonl_fh is not None:
            record = {
                "text": chunk,
                "metadata": meta_raw,  # unflattened for archive
            }
            jsonl_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        # -------------------------------------------------

        # Flatten for DB ingest
        metadata = flatten_metadata(meta_raw)

        new_id = add_episodic_entry(
            chunk,
            metadata=metadata,
            min_length=min_length,
        )
        if new_id:
            added += 1
            if added <= 5 or added % 10 == 0:
                print(f"[extract] + chunk {idx} ({len(words)} words) -> {new_id}")
        else:
            skipped += 1

    # Close JSONL file if we opened it
    if jsonl_fh is not None:
        jsonl_fh.close()

    after = memory_stats()
    print(f"[extract] After: {after}")
    print(f"[extract] Done. Added {added}, skipped {skipped} (too short/duplicate).")


# ===========================
# CLI ENTRYPOINT
# ===========================


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print(
            "Usage:\n"
            "  python normalize_memory_extract.py PATH "
            "[--mode paragraph|bullet|smart] "
            "[--source LABEL] [--tags tag1,tag2] "
            "[--type note|journal|doc] [--min-length N] "
            "[--annotate-nemo] [--nemo-model PATH] [--out-jsonl PATH]"
        )
        raise SystemExit(1)

    path = Path(argv[1])

    mode = "smart"
    source_label = ""
    tags = ""
    memory_type = "note"
    min_length = 10
    annotate_nemo = False
    nemo_model_path = None
    out_jsonl: Optional[Path] = None  # <--- NEW

    i = 2
    while i < len(argv):
        arg = argv[i]
        if arg == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1]
            i += 2
        elif arg == "--source" and i + 1 < len(argv):
            source_label = argv[i + 1]
            i += 2
        elif arg == "--tags" and i + 1 < len(argv):
            tags = argv[i + 1]
            i += 2
        elif arg == "--type" and i + 1 < len(argv):
            memory_type = argv[i + 1]
            i += 2
        elif arg == "--min-length" and i + 1 < len(argv):
            min_length = int(argv[i + 1])
            i += 2
        elif arg == "--annotate-nemo":
            annotate_nemo = True
            i += 1
        elif arg == "--nemo-model" and i + 1 < len(argv):
            nemo_model_path = argv[i + 1]
            i += 2
        elif arg == "--out-jsonl" and i + 1 < len(argv):
            out_jsonl = Path(argv[i + 1])
            i += 2
        else:
            print(f"Unknown argument: {arg}")
            raise SystemExit(1)

    extract_and_ingest(
        path,
        mode=mode,
        source_label=source_label,
        tags=tags,
        memory_type=memory_type,
        min_length=min_length,
        annotate_nemo=annotate_nemo,
        nemo_model_path=nemo_model_path,
        out_jsonl=out_jsonl,
    )


if __name__ == "__main__":
    main(sys.argv)
