from __future__ import annotations

import os
from pathlib import Path

"""
Centralized path definitions for Orion CLI.

- PACKAGE_ROOT: static CLI package (code + templates)
- USER_ORION_DIR: dynamic Orion user data root (config, memory, embeddings, cache)
  - Default: <PACKAGE_ROOT parent>/orion
  - Override via ORION_USER_DIR
"""

# -------------------------------------------------------------------
# Orion CLI Package Root (static code + templates)
# Example:
#   C:/Orion/text-generation-webui/user_data/orion_cli
# -------------------------------------------------------------------
PACKAGE_ROOT = Path(__file__).resolve().parent.parent


# -------------------------------------------------------------------
# Orion User Data Root (dynamic state, embeddings, memory, persona)
#
# Default:
#   C:/Orion/text-generation-webui/user_data/orion
#
# Can be overridden by env var ORION_USER_DIR
# -------------------------------------------------------------------
DEFAULT_USER_ORION_DIR = PACKAGE_ROOT.parent / "orion"

USER_ORION_DIR = Path(os.getenv("ORION_USER_DIR", DEFAULT_USER_ORION_DIR))
USER_ORION_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------------
# User Config + Persona + Identity
#
#   <USER_ORION_DIR>/data/
# -------------------------------------------------------------------
USER_DATA_DIR = USER_ORION_DIR / "data"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

USER_CONFIG_PATH = USER_DATA_DIR / "config.yaml"
USER_PERSONA_PATH = USER_DATA_DIR / "persona.yaml"
USER_IDENTITY_PATH = USER_DATA_DIR / "identity.yaml"


# -------------------------------------------------------------------
# ChromaDB persistent memory store
#
#   <USER_ORION_DIR>/chromadb/
# -------------------------------------------------------------------
CHROMA_DIR = USER_ORION_DIR / "chromadb"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Backwards-compat alias for older code
DEFAULT_CHROMA_PATH = CHROMA_DIR


# -------------------------------------------------------------------
# Embedding Model Downloads (pinned / curated)
#
#   <USER_ORION_DIR>/embeddings/
# -------------------------------------------------------------------
EMBEDDING_MODEL_DIR = USER_ORION_DIR / "embeddings"
EMBEDDING_MODEL_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------------
# HuggingFace Cache
#
#   <USER_ORION_DIR>/hf_cache/
#
# HF_HOME is only set here if the user has not already chosen a value.
# -------------------------------------------------------------------
HF_CACHE_DIR = USER_ORION_DIR / "hf_cache"
HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_HF_CACHE_PATH = HF_CACHE_DIR

if "HF_HOME" not in os.environ:
    os.environ["HF_HOME"] = str(HF_CACHE_DIR)


# -------------------------------------------------------------------
# Orion Workspace Area (scratchpad / tools / files)
#
#   <USER_ORION_DIR>/workspace/
# -------------------------------------------------------------------
WORKSPACE_DIR = USER_ORION_DIR / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------------
# Static Package Data (templates, schema)
#
#   <PACKAGE_ROOT>/data/
# -------------------------------------------------------------------
DATA_DIR = PACKAGE_ROOT / "data"

DEFAULT_CONFIG_PATH = DATA_DIR / "config_template.yaml"
SCHEMA_PATH = DATA_DIR / "schema.json"


__all__ = [
    "PACKAGE_ROOT",
    "USER_ORION_DIR",
    "USER_DATA_DIR",
    "USER_CONFIG_PATH",
    "USER_PERSONA_PATH",
    "USER_IDENTITY_PATH",
    "CHROMA_DIR",
    "DEFAULT_CHROMA_PATH",
    "EMBEDDING_MODEL_DIR",
    "HF_CACHE_DIR",
    "DEFAULT_HF_CACHE_PATH",
    "WORKSPACE_DIR",
    "DATA_DIR",
    "DEFAULT_CONFIG_PATH",
    "SCHEMA_PATH",
]
