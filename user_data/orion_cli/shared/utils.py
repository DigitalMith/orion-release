"""
utils.py — General Utility Helpers for Orion CLI
------------------------------------------------

This module collects small, reusable helper functions that do not belong
to any specific subsystem (config, memory, identity, embedding, etc.).

Guidelines:
- No Orion-specific business logic should live here.
- Keep these functions pure and minimal.
"""

from __future__ import annotations

import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


# -------------------------------------------------------------
# YAML / JSON helpers
# -------------------------------------------------------------

def read_yaml(path: Path) -> Any:
    """
    Load YAML safely. Supports:
    - single-document YAML
    - multi-document YAML (returns a list)
    """
    with open(path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))

    # If only one document, return it directly
    if len(docs) == 1:
        return docs[0]

    return docs


def write_yaml(path: Path, data: Any) -> None:
    """
    Write data to a YAML file with UTF-8 encoding.
    """
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def read_json(path: Path) -> Any:
    """
    Load a JSON file into Python objects.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """
    Write Python objects to a JSON file with pretty formatting.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# -------------------------------------------------------------
# Safe dictionary helpers
# -------------------------------------------------------------

def merge_dicts(*dicts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge any number of dictionaries shallowly.
    Later dictionaries override earlier ones.
    Skips None values safely.
    """
    result: Dict[str, Any] = {}

    for d in dicts:
        if not d:
            continue
        for k, v in d.items():
            result[k] = v

    return result


def ensure_list(x: Any) -> list:
    """
    Convert a value into a list, if not already one.
    """
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


# -------------------------------------------------------------
# String helpers
# -------------------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Light normalization for embedding input:
    - trim whitespace
    - collapse internal spacing
    """
    return " ".join(text.strip().split())


# -------------------------------------------------------------
# Validation helpers
# -------------------------------------------------------------

def require(condition: bool, message: str) -> None:
    """
    Raise a ValueError if condition is False. Used for simple assertions
    in config loading or ingestion workflows.
    """
    if not condition:
        raise ValueError(message)


__all__ = [
    "read_yaml",
    "write_yaml",
    "read_json",
    "write_json",
    "merge_dicts",
    "ensure_list",
    "normalize_text",
    "require",
]
