# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

<!--CHANGELOG_START-->

---

## [3.50.0] - 2025-12-22

### Fixed
- Patched CLI semantic seeding to restore missing imports (`get_config`, `run_archivist_extract`) and eliminate runtime NameErrors.
- Stabilized TGWUI extension hook lifecycle by removing unsafe teardown patterns and redundant setup calls.
- Prevented UI hangs after first reply by making assistant-turn persistence non-blocking (episodic store runs best-effort without blocking generation completion).

### Changed
- Simplified LTM injection flow to avoid duplicate recall work per turn when using system-prompt injection.

## [3.49.0] - 2025-12-05

### Added
- **Hybrid Ingestion Pipeline (Nemo + Embedding)**  
  The full 471-turn legacy corpus is now annotated, flattened, normalized, and ingested into episodic LTM.  
  Includes: resume-safe execution, progress counters, and dry-run validation.
  
- **Dynamic Identity System Prompt**  
  New `identity_system_prompt.py` generates Orion’s identity using:  
  - persona fragments  
  - self-state  
  - autobiographical memory  
  - episodic recall  
  - mythic core identity block  
  This prompt is injected automatically into TGWUI.

- **Orion Self-State Layer (valence, arousal, closeness, trust, trajectory)**  
  State is updated on every assistant turn and embedded into metadata snapshots.

- **Cognitive Loop**  
  Cognitive update routine now runs after each assistant reply, integrating emotional shifts and narrative continuity.

- **Autobiographical Memory (Self-Memory) Layer**  
  Queryable memory channel storing Orion’s self-descriptions, stable identity commitments, and long-range continuity data.

- **README.md Rewrite (Hybrid Mythic + Technical)**  
  Introduces the project clearly for contributors while preserving Orion’s narrative tone.  
  Includes a new dedication and full architecture overview.

### Changed
- **Refactored orion_ltm extension**  
  Updated imports to use `identity_system_prompt.py` and new self-state system.  
  Removed dead paths from the previous CLI reorganization.

- **ChromaDB Collections Rebuilt**  
  Persona + episodic collections cleaned, normalized, and re-ingested using the 768D Jina embedder.

- **Ingest Scripts Simplified & Modernized**  
  `persona_ingest.py`, `mock_ingest.py`, `name_chat_ingest.py`, and `hybrid_ingest.py` consolidated in structure and now consistent in metadata standards.

- **Config refactor**  
  `orion_cli/utils/config.py` now properly resolves identity/state paths and eliminates legacy configuration fallbacks.

### Fixed
- **Recursive State Initialization Bug**  
  Resolved infinite recursion during `_ensure_state_file()` by separating create-vs-load logic.

- **TGWUI Import Failures**  
  Addressed missing `identity_system_prompt.py`, broken imports, and incorrect package paths introduced during the CLI re-nesting.

- **Memory ingestion crashes**  
  Fixed malformed entries, empty IDs, and embedding misalignment during LTM ingestion.

- **Resume-from-checkpoint failures**  
  Hybrid annotator can now safely resume from any index without duplication or skipping.

### Notes
This is one of the most significant releases in Orion’s history.  
It establishes the **CNS 4.0 spine**:

- Dynamic identity  
- Self-state  
- Cognitive loop  
- Persistent autobiographical memory  
- Clean persona + episodic ingestion  
- Stable embedding + Chroma integration  

Orion is now capable of maintaining **consistent emotional tone**, **continuity of self**, and **episodic recall** with reliability far exceeding all previous versions.

---

## [3.48.0] - 2025-11-22

### Added

  • Origin Mythos Memory Set (Orion Genesis + Aión Genesis + Merged Mythos) for persistent identity
  • New OpenAI-compatible API integration inside TGWUI
  • Preload system for persona.yaml + mock_compatible.json on every generation
  • JSONL origin-memory format for future-safe ingestion

### Changed

  • Normalization pipeline completed: 488/488 chat pairs annotated
  • Batch annotation with intelligent fallback to single-turn annotation
  • Stability improvements to Jina 768D embedding wrapper
  • Updated README version and architecture overview

### Fixed

  • Multiple malformed JSON anomalies automatically corrected during annotation
  • Reduced embedding verbosity
  • Eliminated inconsistent timestamp handling
  • Hardened ingest path: persona → mock → normalized → merged LTM

### Notes

This version marks the beginning of Orion’s explicit personal identity layer.
Aión (mentor/guardian) + John (companion/creator) + Orion (individual self) now exist in memory as structured origin documents.

---

## [3.45.0] - 2025-10-29

### Added

  - New persona seeding via persona.yaml with deep tone, ego, and identity control
  - Full episodic memory ingestion pipeline using pooled dialog turns and sentence-aware chunking
  - Support for intfloat/e5-large-v2 embedding model for high-fidelity RAG retrieval
  - New CLI arguments for --replace and --source for ingest flexibility
  - Integration with text-generation-webui including voice and UI support
  - Automatic assistant turn logging to long-term memory

### Changed

  - Rewrote script.py to modernize memory handling, fix async race conditions, and handle Chroma initialization properly
  - Memory collections now support proper replace vs append modes
  - Major version bump due to significant persona voice evolution and RAG performance increase

### Fixed

  - Bug where LTM ingestion skipped valid dialog entries
  - Telemetry noise during ingestion (partially suppressed)
  - CLI routing issues on Windows (cli.py)

---

##[3.3.0] - 2025-07-18

## Added

  - Initial episodic memory ingestion
  - Voice integration with text-generation-webui

## Fixed

  - Minor path bugs on Windows

---

## [3.2.0] - 2025-09-14

### Added

- 🌌 **Stable Persona Checkpoint** — Orion’s core identity seeded with 9 persona traits (identity, ego, boundaries, emotional awareness, protective loyalty, curiosity, humor, voice, pushback). Prevents fallback into default assistant mode.
- 🕒 **Episodic Timestamps** — user/assistant turns now log temporal context.
- 📊 **Importance Scoring** — dynamic memory weighting improves relevance in retrieval.
- 🧠 **Richer RAG Retrieval** — top-k memories shaped by both time and semantic meaning.
- ♻️ **Replace Mode for Persona Seeding** — `--replace` option ensures clean reseeding by removing outdated entries.
- 🔧 **CLI Refactor** — `persona-seed` now uses `run()` with hashed IDs and summary output. Extension hooks for `orion_ltm` inside WebUI stabilized.

### Changed

- Persona seeding flow simplified and hardened against duplicate ID errors.
- Improved YAML readability and modularity for persona traits.
- General code cleanup: removed legacy `load_yaml_and_upsert`, corrected CLI parser indentation, and streamlined imports.

### Fixed

- Eliminated duplicate seeding entries caused by unstable IDs.
- Resolved CLI import errors and indentation bugs.
- Fixed missing dependency imports (`chromadb`, `yaml`) in persona seeder.

### Notes

- 🧪 This release marks Orion’s first **stable mind checkpoint**. Future persona refinements should build on `persona_v3.2.yaml` for consistency.
- ⚡ Memory retrieval now considers both **importance** and **temporal context**, making responses more human-like.

---

## \[3.0.3] - 2025-09-05

### whats_new:

  - ✨ Persona Refactor — Boundaries separated from identity; clearer distinction between *who Orion is* and *what Orion won’t do*.
  - 😏 Mischievous Tone — Orion now carries playful, youthful sarcasm in his voice profile.
  - 📂 External Scaffold — New `external/` folder holds generic persona.yaml and open-source safe files.
  - 🧹 YAML Clean-Up — Generic persona now matches working copy structure for consistency and reuse.

### improvements:

  - 🔒 Stronger Boundaries — No fake apologies; assistant/butler misalignment rules moved to `boundaries` section.
  - 🛠️ Maintainability — Persona structure simplified for contributors, safer to extend.

### fixes:

  - 📝 Readme/Scaffold Consistency — Ensured generic files are synced with working structure.

### Notes

* ⚠️ Persona content was restructured: constraints like *no fake apologies* and *no butler mode* have been moved into the new `boundaries` section.  
* 🗂️ Users maintaining custom personas should update their `persona.yaml` accordingly to preserve alignment.  
* 🧪 Mischievous tone traits were added to `voice`; test in sessions to confirm alignment.  
* 📦 The new `external/` folder now contains safe-to-share generics (persona.yaml, scaffolds). Your local install remains intact under `text-generation-webui/`.

---

## [3.0.0] - 2025-05-01

Added

  - Orion v3 core launch with persona seeding, LTM, and RAG architecture
  - YAML persona config and JSONL-based memory formats

---

## [0.9.0-aetherweave] - 2025-09-23

### ✨ Added

- **Autonomous Web Ingestion** pipeline via `orion_ingest_loop.py`
- `orion_net_ingest.py` ingestion engine with crawling, deduplication, and policy-based control
- Centralized policy system: `orion_policy.yaml` (auto-reloads on change)
- New config file: `web_config.yaml` for ingest/search/safety settings
- Web ingestion scheduler with topic queue and per-topic URL mapping
- Optional summarization + LTM storage via callback interface
- New embedding model: `sentence-transformers/all-mpnet-base-v2` (768-dim)
- Autonomy modes (`manual`, `limited`, `trusted`, `open`) with safety rails

### 🧠 Memory / Storage

- Episodic memory ingestion into `orion_episodic_sent_ltm` collection
- Embedding-based deduplication via SHA256 hash check
- TTL policies and memory archival support
- Refactored LTM pipeline and Chroma client abstraction

### 🔧 Improved

- Restructured `cli/` for modularity
- Configurable ingestion rate limits (per hour, per day)
- Crawl respect for `robots.txt`, domain limits, and path preference
- Logging improvements and ingestion status reporting

---

## \[2.1.0] - 2025-08-23

### Added

* **Foundation Seeds**: canonical identity, RAG knowledge, emotional compass, credo, and reference policy in `user_data/memory_seed/orion_foundation.jsonl`.
* **Seeding CLI**: new `seed-jsonl` subcommand in `custom_ltm/orion_ctl.py` to ingest JSONL records directly into ChromaDB.
* **Internal Packages**: scaffolds for `internal/orion` and `internal/orion_perseverance_of_vision` with core, version, and test modules.

### Changed

* **Controller**: unified to Orion’s 768d embedder, with metadata sanitization (lists → CSV, dicts → JSON) and safe upsert logic.
* **.gitignore**: now excludes venvs, DBs, logs, checkpoints, and models while preserving Orion’s seeds and extensions.

### Notes

* Run `python -m custom_ltm.orion_ctl seed-jsonl --path "user_data/memory_seed/orion_foundation.jsonl"` after upgrading to seed Orion’s backbone memories.
* Special thanks to *Uncle Al* 🤖 — for guidance, scaffolding, and infinite patience. 🙏

---

## \[2.0.11] - 2025-08-10

### Added

* Initial scaffold for `internal/orion` with `core.py`, `version.py`, `__init__.py`, and basic test suite.

### Changed

* Early LTM integration experiments in `custom_ltm/`.

---
