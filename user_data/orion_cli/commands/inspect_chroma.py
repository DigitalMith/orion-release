from __future__ import annotations

import json


def main() -> int:
    # 1) Load Orion config (preferred)
    try:
        from orion_cli.settings.config_loader import get_config

        cfg = get_config()
        chroma_path = str(getattr(cfg, "chroma_path", None) or "user_data/Chroma-DB")
        col_names = []
        cols = getattr(cfg, "collections", None)
        if cols:
            for k in ("persona", "episodic", "semantic", "semantic_candidates"):
                v = getattr(cols, k, None)
                if isinstance(v, str) and v.strip():
                    col_names.append(v.strip())
        # fallback if config doesn’t define them
        if not col_names:
            col_names = [
                "persona",
                "orion_episodic_ltm",
                "orion_semantic_ltm",
                "orion_semantic_candidates",
            ]
    except Exception:
        chroma_path = "user_data/Chroma-DB"
        col_names = [
            "persona",
            "orion_episodic_ltm",
            "orion_semantic_ltm",
            "orion_semantic_candidates",
        ]

    # 2) Connect to Chroma in persistent mode (read-only usage here)
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=chroma_path,
        settings=Settings(anonymized_telemetry=False),
    )

    print(f"[inspect] chroma_path = {chroma_path}")
    print("[inspect] collections (requested) =", col_names)
    print()

    for name in col_names:
        try:
            col = client.get_collection(name)
        except Exception as e:
            print(f"== {name} == (missing or error: {e})")
            print()
            continue

        try:
            count = col.count()
        except Exception:
            count = "unknown"

        print(f"== {name} == count={count}")

        # Peek returns ids/documents/metadatas if present; does not modify DB
        try:
            peek = col.peek(limit=3)
            # Make it readable
            print(json.dumps(peek, indent=2, ensure_ascii=False)[:4000])
        except Exception as e:
            print(f"(peek failed: {e})")

        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
