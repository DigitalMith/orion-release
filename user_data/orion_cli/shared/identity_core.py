"""
identity_core.py — Orion CNS Identity Layer
-------------------------------------------

Identity in CNS 4.0 is defined as the union of:

- Persona memory (who Orion is supposed to be)
- Autobiographical hints (optional future extension)
- Self-state signals (emotional & relational state)
- The user's query context

This module provides the core identity functions used by:
- CLI commands (identity show/test)
- TGWUI extension (during prompt assembly)
"""

from __future__ import annotations

from typing import List, Dict, Any

from orion_cli.shared.memory_core import recall_persona
from orion_cli.shared.utils import normalize_text


# -------------------------------------------------------------
# Persona recall helpers
# -------------------------------------------------------------


def persona_summary(query: str, top_k: int = 5) -> List[str]:
    """
    Retrieve persona entries most relevant to the query.
    Provides a semantic slice of Orion's identity.
    """
    clean = normalize_text(query)
    return recall_persona(clean, top_k=top_k)


# -------------------------------------------------------------
# Autobiographical memory (stub; CNS 4.x may expand)
# -------------------------------------------------------------


def autobiographical_summary(query: str, top_k: int = 3) -> List[str]:
    """
    Placeholder for optional autobiographical memory extension.
    For now, return empty list and leave space for future CNS layers.
    """
    return []


# -------------------------------------------------------------
# Self-state integration hook
# -------------------------------------------------------------


def inject_self_state_block(state: Dict[str, Any]) -> str:
    """
    Convert the self-state dictionary into a readable block.
    The TGWUI extension will eventually supply the state object.

    Example result:
        Valence: 0.2
        Arousal: 0.5
        Closeness: 0.3
        Trust: 0.4
        Trajectory: "stable"
    """
    if not state:
        return ""

    return (
        f"Valence: {state.get('valence')}\n"
        f"Arousal: {state.get('arousal')}\n"
        f"Closeness: {state.get('closeness')}\n"
        f"Trust: {state.get('trust')}\n"
        f"Trajectory: {state.get('trajectory')}"
    )


# -------------------------------------------------------------
# Identity block synthesis
# -------------------------------------------------------------


def build_identity_block(query: str) -> str:
    """
    Build a compact identity block using:
    - persona recall
    - autobiographical placeholders
    - self-state (injected externally by caller)

    The TGWUI extension will call this before feeding into the LLM.
    """
    lines = []

    # Persona
    persona_hits = persona_summary(query, top_k=5)
    if persona_hits:
        lines.append("## Persona")
        for p in persona_hits:
            lines.append(f"- {p}")

    # Autobiographical (stub for future CNS layers)
    autobio_hits = autobiographical_summary(query, top_k=3)
    if autobio_hits:
        lines.append("")
        lines.append("## Autobiographical")
        for a in autobio_hits:
            lines.append(f"- {a}")

    return "\n".join(lines)
