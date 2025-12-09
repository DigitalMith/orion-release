"""
Shared namespace for Orion CLI.
Only re-export stable shared utilities.
"""

from .paths import (
    PACKAGE_ROOT,
    DATA_DIR,
    DEFAULT_CONFIG_PATH,
    SCHEMA_PATH,
    CHROMA_DIR,
    EMBEDDING_MODEL_DIR,
    USER_ORION_DIR,
    USER_DATA_DIR,
    USER_PERSONA_PATH,
    USER_IDENTITY_PATH,
)

from .utils import (
    normalize_text,
    read_yaml,
    read_json,
    merge_dicts,
    require,
)

__all__ = [
    # paths
    "PACKAGE_ROOT",
    "DATA_DIR",
    "DEFAULT_CONFIG_PATH",
    "SCHEMA_PATH",
    "CHROMA_DIR",
    "EMBEDDING_MODEL_DIR",
    "USER_ORION_DIR",
    "USER_DATA_DIR",
    "USER_PERSONA_PATH",
    "USER_IDENTITY_PATH",
    # utils
    "normalize_text",
    "read_yaml",
    "read_json",
    "merge_dicts",
    "require",
]
