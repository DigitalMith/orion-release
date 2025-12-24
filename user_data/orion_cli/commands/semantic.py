from __future__ import annotations

import typer
import json
from pathlib import Path
from typing import Any, Dict
from orion_cli.semantic.onboarding_preview import load_and_generate
from orion_cli.shared.config import get_config
from orion_cli.shared.archivist_client import run_archivist_extract
from orion_cli.shared.memory_core import (
    _semantic,
    _semantic_candidates,
    add_semantic_candidate,
)


app = typer.Typer(help="Semantic tools: list/export/import for semantic + candidates.")


def _col(target: str):
    t = (target or "").strip().lower()
    if t in {"c", "cand", "candidates", "semantic_candidates"}:
        return _semantic_candidates(), "semantic_candidates"
    return _semantic(), "semantic"


@app.command("list")
def list_semantic(
    target: str = typer.Option("semantic", "--target", help="semantic | candidates"),
    limit: int = typer.Option(25, "--limit", help="Max rows to show."),
    source: str = typer.Option("", "--source", help="Filter by meta.source."),
):
    col, name = _col(target)
    n = col.count()
    if n == 0:
        typer.echo(f"[list] {name}: empty")
        raise typer.Exit()

    src = source.strip() or None
    lim = max(1, min(int(limit), n))
    offset = max(0, n - lim)

    r = col.get(limit=lim, offset=offset, include=["documents", "metadatas"])
    ids = r.get("ids", []) or []
    docs = r.get("documents", []) or []
    metas = r.get("metadatas", []) or []

    shown = 0
    for i, d, m in zip(ids, docs, metas):
        m = m or {}
        if src and m.get("source") != src:
            continue
        conf = m.get("confidence", None)
        typer.echo(f"- {i} :: {d}  (source={m.get('source')}, conf={conf})")
        shown += 1

    typer.echo(f"[list] {name}: shown={shown} total={n}")


@app.command("export")
def export_semantic(
    target: str = typer.Option("semantic", "--target", help="semantic | candidates"),
    out: str = typer.Option(
        "semantic_export.jsonl", "--out", help="Output JSONL file path."
    ),
):
    col, name = _col(target)
    n = col.count()
    outp = Path(out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    batch = 500
    wrote = 0
    with outp.open("w", encoding="utf-8") as f:
        for off in range(0, n, batch):
            r = col.get(
                limit=min(batch, n - off),
                offset=off,
                include=["documents", "metadatas"],
            )
            ids = r.get("ids", []) or []
            docs = r.get("documents", []) or []
            metas = r.get("metadatas", []) or []
            for i, d, m in zip(ids, docs, metas):
                f.write(
                    json.dumps(
                        {"id": i, "text": d, "meta": (m or {})}, ensure_ascii=False
                    )
                    + "\n"
                )
                wrote += 1

    typer.echo(f"[export] target={name} wrote={wrote} file={outp}")


@app.command("import")
def import_semantic(
    target: str = typer.Option("semantic", "--target", help="semantic | candidates"),
    inp: str = typer.Option(..., "--in", help="Input JSONL file."),
    source_tag: str = typer.Option(
        "import", "--source-tag", help="meta.source to stamp if missing."
    ),
):
    from orion_cli.shared.memory_core import add_semantic_entry, add_semantic_candidate

    col, name = _col(target)
    inpath = Path(inp)
    if not inpath.exists():
        raise typer.BadParameter(f"Input file not found: {inpath}")

    added = 0
    read = 0

    with inpath.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            read += 1
            obj: Dict[str, Any] = json.loads(line)

            text = obj.get("text") or obj.get("doc") or obj.get("document") or ""
            meta = obj.get("meta") or obj.get("metadata") or obj.get("metadatas") or {}
            if not isinstance(meta, dict):
                meta = {}

            meta.setdefault("source", source_tag)

            if name == "semantic_candidates":
                new_id = add_semantic_candidate(text, metadata=meta)
            else:
                new_id = add_semantic_entry(text, metadata=meta)

            if new_id:
                added += 1

    typer.echo(f"[import] target={name} read={read} added={added} file={inpath}")


@app.command("preview-onboarding")
def preview_onboarding(path: Path = typer.Option(..., "--path", exists=True)):
    lines = load_and_generate(path)

    if not lines:
        typer.echo("[onboarding] No candidate inputs generated.")
        raise typer.Exit(0)

    # ---- Preview 1: show generated inputs ----
    typer.echo("\n[onboarding] Generated candidate inputs:\n")
    for i, line in enumerate(lines, 1):
        typer.echo(f"{i:>2}. {line}")
    typer.echo("")

    if not typer.confirm("Continue with onboarding (no writes yet)?"):
        typer.echo("[onboarding] Aborted. Edit semantic.yaml and retry.")
        raise typer.Exit(0)

    # ---- Preflight: run Archivist, but do NOT write ----
    cfg = get_config()
    arch = getattr(cfg, "archivist", None)
    if not arch or not getattr(arch, "enabled", False):
        typer.echo(
            "[onboarding] Archivist is disabled. Enable it in config.yaml to ingest safely."
        )
        raise typer.Exit(1)

    decisions = []  # each: {"line": str, "ok": bool, "facts": list[dict]}

    for line in lines:
        pooled = [{"role": "user", "content": line}]
        res = run_archivist_extract(arch, pooled)
        out = res.parsed_json or {}

        ok = (
            isinstance(out, dict)
            and out.get("relevant") is True
            and isinstance(out.get("facts"), list)
            and len(out["facts"]) > 0
        )
        facts = out.get("facts") if ok else []
        decisions.append({"line": line, "ok": ok, "facts": facts})

    ok_count = sum(1 for d in decisions if d["ok"])
    bad_count = len(decisions) - ok_count

    typer.echo("\n[onboarding] Archivist preflight results (no writes yet):\n")
    for i, d in enumerate(decisions, 1):
        mark = "✅" if d["ok"] else "❌"
        typer.echo(f"{i:>2}. {mark} {d['line']}")

        # Show the first returned fact (usually 1:1). Keep concise.
        if d["ok"] and d["facts"]:
            f0 = d["facts"][0]
            if isinstance(f0, dict):
                text = (f0.get("text") or "").strip()
                cat = (f0.get("category") or "").strip()
                conf = f0.get("confidence", None)
                if text:
                    suffix = ""
                    if cat:
                        suffix += f"{cat}"
                    if conf is not None:
                        suffix += (", " if suffix else "") + f"{conf}"
                    typer.echo(f"      ↳ {text}" + (f"  [{suffix}]" if suffix else ""))

    typer.echo(f"\n[onboarding] Preflight summary: ✅ {ok_count}  ❌ {bad_count}\n")

    if not typer.confirm("Continue and stage accepted facts into semantic_candidates?"):
        # Clean up ONLY onboarding-staged candidates (leave chat candidates alone)
        try:
            from orion_cli.shared.memory_core import _semantic_candidates

            col = _semantic_candidates()
            # Chroma supports metadata filtering via `where`
            r = col.get(where={"source": "semantic_onboarding"}, include=[])
            ids = (r or {}).get("ids", []) or []
            if ids:
                col.delete(ids=ids)
            typer.echo(
                f"[onboarding] Aborted. Deleted {len(ids)} onboarding candidate(s)."
            )
        except Exception:
            # Best-effort cleanup; don't crash the CLI if delete fails
            typer.echo(
                "[onboarding] Aborted. (Cleanup failed; no further changes made.)"
            )

        raise typer.Exit(0)

    # ---- Write phase: stage only accepted facts (reuse preflight results) ----
    lines_sent = 0
    lines_rejected = 0
    facts_seen = 0
    facts_staged = 0

    for d in decisions:
        if not d["ok"]:
            lines_rejected += 1
            continue

        lines_sent += 1
        for f in d["facts"]:
            if not isinstance(f, dict):
                continue

            text = (f.get("text") or "").strip()
            category = (f.get("category") or "").strip()
            conf = f.get("confidence", 0.0)

            if not text or not category:
                continue

            try:
                conf = float(conf)
            except Exception:
                conf = 0.0

            facts_seen += 1

            meta = {
                "source": "semantic_onboarding",
                "model": str(getattr(arch, "model", "")),
                "category": category,
                "confidence": conf,
            }

            new_id = add_semantic_candidate(text, metadata=meta, min_length=0)
            if new_id:
                facts_staged += 1

    typer.echo(
        f"[onboarding] Done. lines_total={len(lines)} lines_sent={lines_sent} "
        f"lines_rejected={lines_rejected} facts_seen={facts_seen} facts_staged={facts_staged}"
    )
