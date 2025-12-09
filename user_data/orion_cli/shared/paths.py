from __future__ import annotations
from pathlib import Path
import os

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

USER_ORION_DIR = Path(
    os.getenv("ORION_USER_DIR", DEFAULT_USER_ORION_DIR)
)

# Ensure base directory exists
USER_ORION_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------------
# User Config + Persona + Identity
#
#   C:/Orion/text-generation-webui/user_data/orion/data/
# -------------------------------------------------------------------
USER_DATA_DIR = USER_ORION_DIR / "data"
USER_DATA_DIR.mkdir(exist_ok=True)

USER_CONFIG_PATH = USER_DATA_DIR / "config.yaml"
USER_PERSONA_PATH = USER_DATA_DIR / "persona.yaml"
USER_IDENTITY_PATH = USER_DATA_DIR / "identity.yaml"


# -------------------------------------------------------------------
# ChromaDB persistent memory store
#
#   C:/Orion/text-generation-webui/user_data/orion/chromadb/
# -------------------------------------------------------------------
CHROMA_DIR = USER_ORION_DIR / "chromadb"
CHROMA_DIR.mkdir(exist_ok=True)
# Backwards-compat aliases for older code
DEFAULT_CHROMA_PATH = CHROMA_DIR


# -------------------------------------------------------------------
# Embedding Model Downloads
#
#   C:/Orion/text-generation-webui/user_data/orion/embeddings/
# -------------------------------------------------------------------
EMBEDDING_MODEL_DIR = USER_ORION_DIR / "embeddings"
EMBEDDING_MODEL_DIR.mkdir(exist_ok=True)


# -------------------------------------------------------------------
# HuggingFace Cache
#
#   C:/Orion/text-generation-webui/user_data/orion/hf_cache/
# -------------------------------------------------------------------
HF_CACHE_DIR = USER_ORION_DIR / "hf_cache"
HF_CACHE_DIR.mkdir(exist_ok=True)
DEFAULT_HF_CACHE_PATH = HF_CACHE_DIR  # if anything expects it


# -------------------------------------------------------------------
# Orion Workspace Area (scratchpad / tools / files)
#
#   C:/Orion/text-generation-webui/user_data/orion/workspace/
# -------------------------------------------------------------------
WORKSPACE_DIR = USER_ORION_DIR / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)


# -------------------------------------------------------------------
# Static Package Data (templates, schema)
#
#   C:/Orion/text-generation-webui/user_data/orion_cli/data/
# -------------------------------------------------------------------
DATA_DIR = PACKAGE_ROOT / "data"

DEFAULT_CONFIG_PATH = DATA_DIR / "default_config.yaml"
SCHEMA_PATH = DATA_DIR / "schema.json"


__all__ = [
    "PACKAGE_ROOT",
    "USER_ORION_DIR",
    "USER_DATA_DIR",
    "USER_CONFIG_PATH",
    "USER_PERSONA_PATH",
    "USER_IDENTITY_PATH",
    "CHROMA_DIR",
    "EMBEDDING_MODEL_DIR",
    "HF_CACHE_DIR",
    "WORKSPACE_DIR",
    "DATA_DIR",
    "DEFAULT_CONFIG_PATH",
    "SCHEMA_PATH",
]
