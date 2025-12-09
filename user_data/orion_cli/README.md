# Orion CLI — Cognitive Neural System Tools (CNS 4.0)
Orion CLI provides the full logic stack for Orion’s Cognitive Neural System:
configuration, embeddings, long-term memory (persona + episodic), identity
assembly, and developer tooling.

This CLI is designed to be installed inside **text-generation-webui (TGWUI)** and
serves as the canonical source of truth for all Orion logic. The TGWUI extension
(`orion_ltm/`) becomes a thin adapter layer that simply calls into this package.

---

## 🚀 Features

### Long-Term Memory (LTM)
- Persona memory (identity traits, behavioral anchors)
- Episodic memory (conversation context, life events)
- Deduplication, normalization, and safe ingestion
- Cosine-similarity recall using ChromaDB

### Identity System
- Persona-based identity block assembly
- Structured identity template
- Self-state ("VALT") integration hooks
- Extensible design for future autobiographical memory

### Embeddings
- Jina V2 Base (768D) as the primary model
- MPNet and CLIP allowed
- Intfloat models explicitly disabled
- Thread-safe lazy loading
- Embedding callable for ChromaDB

### Configuration (Pydantic v2)
- Default config + JSON schema validation
- Environment variable overrides (e.g., ORION_EMBEDDING_MODEL)
- Unified config interface (`cfg()` / `get_config()`)

### Developer Tools
- Embedding tests
- Path inspection
- Config inspection
- Future diagnostics and workspace utilities

---

## 📦 Installation (Inside TGWUI)

1. Navigate to the CLI folder:

    cd text-generation-webui/user_data/orion_cli

2. Activate TGWUI’s Python virtual environment (if not already active).

3. Install the package in editable mode:

    pip install -e . --no-deps

4. Verify installation:

    orion --help

You should now see subcommands such as:

    orion memory ...
    orion identity ...
    orion ingest ...
    orion tools ...

---

## 🧭 CLI Overview

### Memory Commands
- orion memory recall "<query>"
- orion memory stats

### Identity Commands
- orion identity persona "<query>"
- orion identity query "<text>"

### Ingestion Commands
- orion ingest persona "<text>"
- orion ingest persona persona.yaml --file
- orion ingest episodic "<event>"

### Developer Tools
- orion tools config
- orion tools paths
- orion tools embed "test"

---

## 🧠 Architecture Summary

    orion_cli/
        cli.py                # Top-level Typer entrypoint
        commands/             # Typer command modules
        shared/               # All CNS logic (source of truth)
        settings/             # Pydantic config loader
        data/                 # Templates & schema
        models/               # Embedding model placeholder

### Separation of Concerns

CLI package:  
All cognition, identity, embedding, memory, and configuration logic.

TGWUI extension (orion_ltm/):  
Only the two I/O hooks (input_modifier, output_modifier).  
No logic, no memory operations, no embeddings.

This ensures:
- clean architecture  
- reproducibility  
- testability  
- zero duplication  
- no circular imports  

---

## 🔧 Configuration

Defaults are defined in data/default_config.yaml.

Override any field via environment variables.

Windows:

    set ORION_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-en
    set ORION_DEBUG_MODE=true

Linux / macOS:

    export ORION_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-en

The loader validates config structure through data/schema.json and type-checks using Pydantic v2.

---

## 📚 Data Templates

### Persona Template
File: data/persona_template.yaml  
Human-editable list of persona traits suitable for line-by-line ingestion.

### Identity Template
File: data/identity_template.yaml  
A structured identity reference for advanced CNS configuration.

---

## 🛠 Development

Because the CLI is installed in editable mode, changes take effect immediately:

    pip install -e . --no-deps

Run the CLI directly from source:

    python -m orion_cli.cli --help

---

## 🧩 Future Work

- Minimal TGWUI extension rewrite (true I/O adapter)
- Semantic memory (optional collection)
- Structured identity ingestion
- Workspace tools (snapshots, diffs, audits)
- CNS 4.1 self-state models and synthesis pipeline

---

## 🧑‍💻 Contributing

All CNS logic must remain in shared/.  
Commands must stay thin wrappers that never embed business logic.

---

## © Orion Project — CNS 4.0

Maintained with clarity, stability, and precision.

