"""
config_loader.py — Unified configuration system for Orion CLI (CNS 4.0)

Responsibilities:
    • Load default config from orion_cli/data/default_config.yaml
    • Load user-specific config from user_data/orion/data/config.yaml (if present)
    • Apply ORION_* environment variable overrides
    • Validate merged config against JSON schema
    • Return typed OrionConfig object
    • Cache results for entire process lifetime

Design:
    - Strict validation: malformed configs raise clear RuntimeError
    - Missing user config is allowed (defaults only)
    - Optional fields fall back to defaults automatically
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

from pydantic import BaseModel, Field, ValidationError

from orion_cli.shared.paths import (
    DEFAULT_CONFIG_PATH,
    SCHEMA_PATH,
    USER_CONFIG_PATH,
    CHROMA_DIR,
)
from orion_cli.shared.utils import (
    read_yaml,
    read_json,
    merge_dicts,
    require,
)

# -------------------------------------------------------------
# Pydantic sub-models
# -------------------------------------------------------------


class PersonaSettings(BaseModel):
    rigidity: float = Field(
        default=0.5,
        description="How strongly Orion should adhere to persona constraints (0–1).",
    )


class ArchivistPoolSettings(BaseModel):
    window_turns: int = Field(default=20)
    min_new_turns: int = Field(default=6)


class ArchivistWriteSettings(BaseModel):
    target: str = Field(default="semantic_candidates")  # refers to collections key
    auto_promote: bool = Field(default=False)
    promote_min_confidence: float = Field(default=0.85)


class ArchivistSettings(BaseModel):
    enabled: bool = Field(default=False)

    # OSS default: OpenAI-compatible
    provider: str = Field(default="openai_compat")  # "openai_compat" | "ollama_native"

    base_url: str = Field(default="http://localhost:11434/v1")
    api_key: str = Field(default="ollama")
    model: str = Field(default="qwen3:4b")

    temperature: float = Field(default=0.2)
    max_tokens: int = Field(default=800)
    timeout_s: int = Field(default=60)

    pool: ArchivistPoolSettings = Field(default_factory=ArchivistPoolSettings)
    write: ArchivistWriteSettings = Field(default_factory=ArchivistWriteSettings)


class LTMSettings(BaseModel):
    topk_persona: int = Field(
        default=5,
        description="Max number of persona memories to recall per query.",
    )
    topk_episodic: int = Field(
        default=10,
        description="Max number of episodic memories to recall per query.",
    )
    importance_threshold: float = Field(
        default=0.0,
        description="Minimum importance score for storing episodic memories.",
    )
    min_score: float = Field(
        default=0.0,
        description="Minimum similarity score for recalled memories.",
    )
    pooling_turns: int = Field(
        default=3,
        description="How many recent turns to pool when deciding episodic storage.",
    )
    boosts: Dict[str, float] = Field(
        default_factory=dict,
        description="Optional per-source or per-tag boosts.",
    )
    topk_semantic: int = Field(
        default=0,
        description="Max number of semantic memories to recall per query (0 disables).",
    )
    semantic_enabled: bool = Field(
        default=False,
        description="Enable semantic memory recall layer.",
    )


class DebugSettings(BaseModel):
    enabled: bool = False
    logic: bool = False
    cognitive: bool = False
    show_recall: bool = False
    episodic_recall: bool = False
    episodic_store: bool = False
    short_descriptions: bool = True


class CollectionsSettings(BaseModel):
    persona: str = Field(default="persona")
    episodic: str = Field(default="orion_episodic_ltm")
    semantic: str = Field(default="orion_semantic_ltm")
    semantic_candidates: str = Field(default="orion_semantic_candidates")


# -------------------------------------------------------------
# OrionConfig model
# -------------------------------------------------------------


class OrionConfig(BaseModel):
    """
    Unified configuration object for Orion CNS.

    Unknown fields in config.yaml are safely ignored so the system can
    evolve without breaking older configs.
    """

    # --- Profile selection ---
    profile: str = Field(
        default="orion_main",
        description="Active Orion profile name (default: orion_main).",
    )
    profiles_root: Path = Field(
        default=Path("user_data/orion/profiles"),
        description="Root directory for Orion profiles.",
    )

    identity_path: Path = Field(
        default=Path("user_data/orion_cli/data/orion_identity.yaml"),
        description="Identity file for the default orion_main profile.",
    )
    persona_path: Path = Field(
        default=Path("user_data/orion_cli/data/orion_persona.yaml"),
        description="Persona file for the default orion_main profile.",
    )

    # --- Chroma + Embeddings ---
    chroma_path: Optional[Path] = Field(
        default=None,
        description="Directory where ChromaDB persistent data is stored. "
        "If omitted, CHROMA_DIR from shared.paths is used.",
    )

    embedding_model: str = Field(
        default="jinaai/jina-embeddings-v2-base-en",
        description="Model identifier for the embedding system.",
    )

    embedding_dim: int = Field(
        default=768,
        description="Expected embedding dimension for the model.",
    )

    # --- Subsystems ---
    persona: PersonaSettings = Field(
        default_factory=PersonaSettings,
        description="Persona-related tuning parameters.",
    )
    ltm: LTMSettings = Field(
        default_factory=LTMSettings,
        description="Long-term memory retrieval and storage settings.",
    )
    debug: DebugSettings = Field(
        default_factory=DebugSettings,
        description="Debug verbosity and tracing controls.",
    )
    collections: CollectionsSettings = Field(
        default_factory=CollectionsSettings,
        description="Chroma collection naming.",
    )
    archivist: ArchivistSettings = Field(
        default_factory=ArchivistSettings,
        description="Optional secondary model for semantic extraction, etc.",
    )

    class Config:
        extra = "ignore"  # Allow unknown keys, ignore them safely.


# -------------------------------------------------------------
# Internal helpers
# -------------------------------------------------------------


def _load_default_config() -> Dict[str, Any]:
    """Load default_config.yaml (required)."""
    data = read_yaml(Path(DEFAULT_CONFIG_PATH))
    require(data is not None, f"Default config not found at: {DEFAULT_CONFIG_PATH}")
    return data


def _load_user_config() -> Dict[str, Any]:
    """Load user config if present; otherwise return empty dict."""
    config_path = Path(USER_CONFIG_PATH)
    if config_path.exists():
        data = read_yaml(config_path)
        require(
            isinstance(data, dict),
            f"User config exists but is invalid YAML: {config_path}",
        )
        return data
    return {}  # no user config → safe fallback


def _env_overrides() -> Dict[str, Any]:
    prefix = "ORION__"
    out: Dict[str, Any] = {}

    def set_nested(d: Dict[str, Any], keys: list[str], value: Any) -> None:
        cur = d
        for k in keys[:-1]:
            cur = cur.setdefault(k, {})
        cur[keys[-1]] = value

    for key, value in os.environ.items():
        if key.startswith(prefix):
            path = key[len(prefix) :].lower().split("__")
            set_nested(out, path, value)

    # Back-compat for old style ORION_FOO=bar (top-level)
    legacy_prefix = "ORION_"
    for key, value in os.environ.items():
        if key.startswith(legacy_prefix) and not key.startswith(prefix):
            field = key[len(legacy_prefix) :].lower()
            out[field] = value

    return out


def _validate_schema(data: Dict[str, Any]) -> None:
    """
    Validate the merged configuration against schema.json.

    This covers structural requirements only. Pydantic enforces field
    types and default values afterwards.
    """
    schema = read_json(Path(SCHEMA_PATH))
    require(
        isinstance(schema, dict),
        f"Schema file missing or invalid: {SCHEMA_PATH}",
    )

    required = schema.get("required", [])
    for key in required:
        require(
            key in data,
            f"Missing required config key: '{key}'",
        )


# -------------------------------------------------------------
# Public API
# -------------------------------------------------------------


@lru_cache(maxsize=1)
def get_config() -> OrionConfig:
    """
    Load, merge, validate, and return the unified OrionConfig object.

    Order of precedence:
        1. default_config.yaml
        2. user config (if exists)
        3. ORION_* environment overrides
    """
    # 1. Load base defaults (required)
    default_cfg = _load_default_config()

    # 2. Load user config if present (optional)
    user_cfg = _load_user_config()

    # 3. Environment overrides
    env_cfg = _env_overrides()

    # Merge order: defaults → user → env
    merged = merge_dicts(default_cfg, user_cfg, env_cfg)

    # Validate structure
    try:
        _validate_schema(merged)
    except Exception as e:
        raise RuntimeError(f"[config] Schema validation failed: {e}") from e

    # Validate types & assign defaults
    try:
        cfg = OrionConfig(**merged)
    except ValidationError as e:
        raise RuntimeError(f"[config] Invalid configuration: {e}") from e

    # Finalize any missing path defaults
    if cfg.chroma_path is None:
        cfg.chroma_path = CHROMA_DIR

    return cfg


def get_active_profile_name(cfg: OrionConfig) -> str:
    """
    Determine the active profile name.

    Order of precedence:
        1. ORION_PROFILE environment variable
        2. cfg.profile (from config files)
    """
    env_profile = os.getenv("ORION_PROFILE")
    if env_profile:
        return env_profile
    return cfg.profile


def resolve_profile_paths(cfg: OrionConfig) -> Tuple[Path, Path]:
    """
    Resolve identity/persona file paths for the active profile.

    - For `orion_main`, use the canonical shipped files under orion_cli/data.
    - For any other profile, use: <profiles_root>/<profile>/data/{identity,persona}.yaml
    """
    profile_name = get_active_profile_name(cfg)

    # Default shipped profile
    if profile_name == "orion_main":
        return cfg.identity_path, cfg.persona_path

    # User-defined profile
    base = cfg.profiles_root / profile_name / "data"
    identity = base / "identity.yaml"
    persona = base / "persona.yaml"
    return identity, persona


__all__ = [
    "get_config",
    "OrionConfig",
    "get_active_profile_name",
    "resolve_profile_paths",
]
