"""
config.py — High-Level Configuration Access for Orion CNS
---------------------------------------------------------

This module exposes a clean interface for obtaining and working with
the Orion CNS configuration. All modules outside the config loader
should import *this* file, not config_loader.py directly.

Example:
    from orion_cli.shared.config import get_config, cfg

Why this layer exists:
- Prevents circular imports
- Keeps shared modules decoupled from loader internals
- Allows future expansion (e.g., computed properties, config sections)
"""

from __future__ import annotations

from functools import lru_cache

from orion_cli.settings.config_loader import (
    get_config as _load_config,
    OrionConfig,
)


# -------------------------------------------------------------
# Canonical config getter
# -------------------------------------------------------------


@lru_cache(maxsize=1)
def cfg() -> OrionConfig:
    """
    Cached accessor for the Orion CNS configuration.
    Returns a Pydantic OrionConfig object.
    """
    return _load_config()


# -------------------------------------------------------------
# Syntactic sugar
# -------------------------------------------------------------


def get_config() -> OrionConfig:
    """
    Preferred public function for retrieving configuration.
    Mirrors cfg(), but spells out intent more clearly.
    """
    return cfg()


__all__ = [
    "cfg",
    "get_config",
    "OrionConfig",
]
