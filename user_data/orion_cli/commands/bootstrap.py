from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import typer

from orion_cli.settings.config_loader import get_config
from orion_cli.shared.utils import normalize_text
from orion_cli.shared.memory_core import add_semantic_candidate
from orion_cli.shared.archivist_client import run_archivist_extract

app = typer.Typer(help="Bootstrapping tools (build semantic candidates from logs)")


def _load_normalized_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _iter_turns_from_normalized(data: Dict[str, Any]) -> List[Dict[str, Any]]:
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


def _flatten_md(md: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for k, v in md.items():
        if isinstance(v, list):
            flat[k] = ",".join(str(x) for x in v if x is not None)
        elif isinstance(v, dict):
            flat[k] = json.dumps(v, ensure_ascii=False)
        else:
            flat[k] = v
    return flat


def _windows(
    items: List[Dict[str, Any]], window: int, stride: int
) -> List[List[Dict[str, Any]]]:
    if window <= 0:
        return [items]
    stride = max(1, stride)
    out: List[List[Dict[str, Any]]] = []
    for i in range(0, max(1, len(items) - window + 1), stride):
        out.append(items[i : i + window])
    return out


@app.command("semantic-candidates")
def semantic_candidates(
    input: str = typer.Option(
        ...,
        "--input",
        help="Normalized JSON file OR folder containing normalized_*.json files.",
    ),
    window_turns: int = typer.Option(
        20, "--window-turns", help="Messages per extraction window."
    ),
    stride: int = typer.Option(10, "--stride", help="Window stride in messages."),
    max_windows: int = typer.Option(
        0, "--max-windows", help="Limit windows processed (0 = no limit)."
    ),
    min_conf: float = typer.Option(
        0.85, "--min-conf", help="Only store candidates with confidence >= this."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Do not write to Chroma; only write review JSONL."
    ),
    review_out: str = typer.Option(
        "semantic_bootstrap_review.jsonl",
        "--review-out",
        help="Output JSONL review file.",
    ),
):
    """
    Scan normalized chat logs, ask the Archivist model to extract semantic candidates,
    and write them into the semantic_candidates Chroma collection.
    """
    cfg = get_config()
    arch = getattr(cfg, "archivist", None)
    if not arch or not getattr(arch, "enabled", False):
        typer.echo("archivist.enabled is false. Enable archivist in config.yaml first.")
        raise typer.Exit(code=1)

    inp = Path(input)
    if inp.is_dir():
        files = sorted(inp.glob("normalized_*.json"))
        if not files:
            typer.echo(f"No normalized_*.json files found in: {inp}")
            raise typer.Exit(code=1)
    else:
        files = [inp]

    review_path = Path(review_out)
    seen: set[str] = set()
    wrote_review = 0
    wrote_chroma = 0
    windows_processed = 0

    with open(review_path, "w", encoding="utf-8") as review_f:
        for fpath in files:
            data = _load_normalized_json(fpath)
            turns = _iter_turns_from_normalized(data)
            wins = _windows(turns, window=window_turns, stride=stride)

            if max_windows and max_windows > 0:
                wins = wins[:max_windows]

            for w in wins:
                windows_processed += 1
                pooled = [{"role": t["role"], "content": t["content"]} for t in w]

                # Best-effort: skip windows that fail
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
                base_meta.update(_flatten_md(last_md))

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
                    if float(conf) < float(min_conf):
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

                    if dry_run:
                        continue

                    new_id = add_semantic_candidate(norm, metadata=meta)
                    if new_id:
                        wrote_chroma += 1

    typer.echo(
        f"[bootstrap] windows={windows_processed} review_written={wrote_review} chroma_written={wrote_chroma} out={review_path}"
    )
