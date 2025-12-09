"""Command groups for the Orion CLI."""

from .ingest import app as ingest_app
from .identity import app as identity_app
from .memory import app as memory_app
from .tools import app as tools_app

__all__ = [
    "ingest_app",
    "identity_app",
    "memory_app",
    "tools_app",
]
