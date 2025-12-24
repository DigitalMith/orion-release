# Orion CNS 4.0 — `config.yaml` Quick Reference (Canonical + Notes)

This README documents how Orion loads configuration and provides a canonical `config.yaml` example you can copy/paste.

---

## Where `config.yaml` lives

User config (you edit this):
- `text-generation-webui/user_data/orion/data/config.yaml`

Defaults (shipped with Orion):
- `text-generation-webui/orion_cli/data/default_config.yaml`

---

## Load order (precedence)

Orion merges configuration in this order (later wins):
1) default_config.yaml  
2) user config.yaml  
3) environment overrides  

Orion uses a deep merge, so nested overrides (like `archivist.base_url`) won’t wipe sibling settings.

---

## Environment overrides

Recommended nested format (double-underscore):
- `ORION__ARCHIVIST__BASE_URL=http://localhost:11434/v1`
- `ORION__LTM__TOPK_SEMANTIC=6`

Legacy top-level format (still supported):
- `ORION_EMBEDDING_DIM=768`

PowerShell example (temporary override):
- `$env:ORION__ARCHIVIST__BASE_URL='http://example.test/v1'`
- run Orion / a test command
- `Remove-Item Env:ORION__ARCHIVIST__BASE_URL`

---

## Canonical `config.yaml` example

Copy/paste into:
`user_data/orion/data/config.yaml`

(Plain YAML below — no nested fences so it copies cleanly.)

# === Orion CNS 4.0 User Configuration ===

# Storage path for ChromaDB
chroma_path: "user_data/orion/chromadb"

# use "vendor/model_name" as used by HF embedding frameworks
embed_model_path: "user_data/orion/embeddings/jinaai-jina-v2-base-en"
embedding_model: "jinaai/jina-embeddings-v2-base-en"
embedding_dim: 768

# === Persona Rigidity ===
persona:
  rigidity: 0.5

# === Debug Settings ===
debug:
  enabled: true
  logic: false
  cognitive: false
  show_recall: true
  episodic_recall: true
  episodic_store: true
  short_descriptions: true

# === LTM Recall Tuning (optional) ===
ltm:
  topk_persona: 5
  topk_episodic: 10
  topk_semantic: 6
  semantic_enabled: true

# Optional: explicit collection names
collections:
  semantic: "orion_semantic_ltm"
  semantic_candidates: "orion_semantic_candidates"

# === Archivist Model (Semantic Extractor) ===
archivist:
  enabled: true

  # Best OSS default:
  provider: "openai_compat"   # "openai_compat" | "ollama_native"

  # For Ollama OpenAI-compatible server:
  base_url: "http://localhost:11434/v1"
  api_key: "ollama"           # ignored by Ollama, but keeps OpenAI-style clients happy

  # IMPORTANT: this must match the model tag installed in Ollama
  model: "qwen3:4b"           # example; use your actual tag

  # Generation controls
  temperature: 0.2
  max_tokens: 800
  timeout_s: 60

  # How much chat Orion sends for extraction
  pool:
    window_turns: 20          # last N turns
    min_new_turns: 6          # only run after at least N new turns (if you automate)

  # Safety: stage first, then promote manually
  write:
    target: "semantic_candidates"  # collection key from `collections:`
    auto_promote: false
    promote_min_confidence: 0.85

---

## Notes on key sections

### Embeddings
- `embedding_model` and `embedding_dim` must match whatever embedding backend Orion uses.
- `embed_model_path` is install-specific (optional depending on your embedding loader).

### LTM (persona / episodic / semantic)
- `topk_*` controls how many memories are recalled for each layer.
- Semantic recall is typically active when:
  - `ltm.semantic_enabled: true` AND
  - `ltm.topk_semantic > 0`

### Collections
- `collections.semantic_candidates` is intentionally separate from semantic LTM.
  This keeps the system safer: candidates can be reviewed/promoted later.

### Archivist provider + base_url rules
- If `provider: openai_compat` then base_url should include `/v1`, e.g.:
  - `http://localhost:11434/v1`  (Ollama)
  - `http://localhost:1234/v1`   (LM Studio server, if enabled)
  - `http://localhost:8000/v1`   (vLLM OpenAI server, example)

- If `provider: ollama_native` then base_url should NOT include `/v1`:
  - `http://localhost:11434`

---

## Quick sanity checks (PowerShell)

1) Confirm config loads:
- `python -c "from orion_cli.settings.config_loader import get_config; print('OK')"`

2) Print key blocks:
- `python -c "from orion_cli.settings.config_loader import get_config; c=get_config(); print(c.ltm); print(c.collections); print(c.archivist)"`

3) Confirm nested env override works:
- `$env:ORION__ARCHIVIST__BASE_URL='http://example.test/v1'; python -c "from orion_cli.settings.config_loader import get_config; print(get_config().archivist.base_url)"; Remove-Item Env:ORION__ARCHIVIST__BASE_URL"
