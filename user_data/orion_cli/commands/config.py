"""
config.py — Typer commands for inspecting and diagnosing Orion config.yaml
"""

from __future__ import annotations

import json
import difflib
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set, Tuple

import typer
from pydantic import BaseModel

from orion_cli.settings.config_loader import get_config, OrionConfig
from orion_cli.shared.paths import USER_CONFIG_PATH, DEFAULT_CONFIG_PATH
from orion_cli.shared.utils import read_yaml

app = typer.Typer(help="Config tools (show / doctor)")


# --- knobs -------------------------------------------------------------------

# Keys we intentionally tolerate even if not present in OrionConfig.
# (Example: embed_model_path is sometimes used by embedding loaders.)
EXTRA_OK_TOPLEVEL: Set[str] = {"embed_model_path"}


# --- helpers: model introspection --------------------------------------------


def _is_basemodel_subclass(t: Any) -> bool:
    try:
        return isinstance(t, type) and issubclass(t, BaseModel)
    except Exception:
        return False


def _build_allowed_maps(model: type[BaseModel]) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """
    Returns:
      allowed_children: prefix -> set(valid child keys at that object)
      wildcard_prefixes: prefixes where arbitrary children are allowed (dict-like leaves)
    """
    allowed_children: Dict[str, Set[str]] = defaultdict(set)
    wildcard_prefixes: Set[str] = set()

    def walk(m: type[BaseModel], prefix: str) -> None:
        for name, field in m.__fields__.items():
            allowed_children[prefix].add(name)
            child_prefix = f"{prefix}.{name}" if prefix else name

            # Recurse into nested BaseModels
            if _is_basemodel_subclass(field.type_):
                walk(field.type_, child_prefix)
                continue

            # Dict-like fields: allow arbitrary keys under this prefix (e.g., ltm.boosts)
            if field.type_ in (dict, Dict):
                wildcard_prefixes.add(child_prefix)

    walk(model, "")
    return allowed_children, wildcard_prefixes


def _iter_dict_nodes(d: Any, prefix: str = "") -> Iterable[Tuple[str, Dict[str, Any]]]:
    """
    Yields (prefix, dict_node) for each dict node in a nested structure.
    """
    if isinstance(d, dict):
        yield prefix, d
        for k, v in d.items():
            child_prefix = f"{prefix}.{k}" if prefix else str(k)
            yield from _iter_dict_nodes(v, child_prefix)


def _is_under_wildcard(prefix: str, wildcard_prefixes: Set[str]) -> bool:
    if not prefix:
        return False
    parts = prefix.split(".")
    for i in range(1, len(parts) + 1):
        if ".".join(parts[:i]) in wildcard_prefixes:
            return True
    return False


def _suggest_key(bad: str, valid_keys: Set[str]) -> Optional[str]:
    if not valid_keys:
        return None
    matches = difflib.get_close_matches(bad, sorted(valid_keys), n=1, cutoff=0.78)
    return matches[0] if matches else None


# --- helpers: small validations ----------------------------------------------


def _check_provider_base_url(provider: str, base_url: str) -> Optional[str]:
    p = (provider or "").strip().lower()
    u = (base_url or "").strip().lower()

    if p == "openai_compat":
        if not u.endswith("/v1") and "/v1/" not in u:
            return "archivist.provider=openai_compat usually expects base_url ending in '/v1' (ex: http://localhost:11434/v1)"
    if p == "ollama_native":
        if "/v1" in u:
            return "archivist.provider=ollama_native should NOT include '/v1' (ex: http://localhost:11434)"
    return None


def _check_semantic(cfg: OrionConfig) -> Optional[str]:
    if cfg.ltm.semantic_enabled and int(cfg.ltm.topk_semantic) <= 0:
        return "ltm.semantic_enabled is true but ltm.topk_semantic is 0 (semantic recall will effectively be off)."
    if (not cfg.ltm.semantic_enabled) and int(cfg.ltm.topk_semantic) > 0:
        return "ltm.topk_semantic > 0 but ltm.semantic_enabled is false (semantic recall will be off)."
    return None


# --- commands ----------------------------------------------------------------


@app.command("show")
def show(
    section: str = typer.Option(
        "", "--section", "-s", help="Optional: archivist|ltm|collections|debug|persona"
    ),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON."),
):
    """
    Print effective (merged) configuration as Orion sees it.
    """
    cfg = get_config()

    obj: Any = cfg
    if section:
        sec = section.strip().lower()
        if not hasattr(cfg, sec):
            raise typer.BadParameter(f"Unknown section: {section}")
        obj = getattr(cfg, sec)

    if as_json:
        # Pydantic v1: .dict(); keep paths readable
        payload = obj.dict() if isinstance(obj, BaseModel) else obj
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        typer.echo(str(obj))


@app.command("doctor")
def doctor(
    ping: bool = typer.Option(
        False,
        "--ping",
        help="Try to ping archivist endpoint (Ollama/OpenAI-compat) if enabled.",
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Exit with code 1 if issues are found."
    ),
):
    """
    Diagnose config.yaml: unknown keys, likely typos, and common consistency issues.
    """
    issues: list[str] = []
    notes: list[str] = []

    user_path = Path(USER_CONFIG_PATH)
    default_path = Path(DEFAULT_CONFIG_PATH)

    typer.echo(f"User config:    {user_path}")
    typer.echo(f"Default config: {default_path}")

    raw_user = read_yaml(user_path) if user_path.exists() else {}
    if raw_user is None:
        raw_user = {}

    if not isinstance(raw_user, dict):
        raise RuntimeError(f"User config exists but is not a YAML mapping: {user_path}")

    # Effective config (also validates types)
    cfg = get_config()
    typer.echo("Config parse:   OK")

    # Unknown keys / likely typos
    allowed_children, wildcard_prefixes = _build_allowed_maps(OrionConfig)

    unknown: list[Tuple[str, str, Optional[str]]] = []  # (path, key, suggestion)

    for prefix, node in _iter_dict_nodes(raw_user, ""):
        if _is_under_wildcard(prefix, wildcard_prefixes):
            continue  # arbitrary children allowed here

        valid = allowed_children.get(prefix, set())

        for k in node.keys():
            # Top-level tolerated extras
            if prefix == "" and k in EXTRA_OK_TOPLEVEL:
                continue

            if k not in valid:
                sug = _suggest_key(k, valid)
                path = f"{prefix}.{k}" if prefix else k
                unknown.append((path, k, sug))

    if unknown:
        issues.append(
            f"Found {len(unknown)} unknown key(s) in user config (may be typos; unknown keys are ignored)."
        )
        typer.echo("")
        typer.echo("Unknown keys / suspected typos:")
        for path, k, sug in unknown:
            if sug:
                typer.echo(f"  - {path}  (did you mean: {sug} ?)")
            else:
                typer.echo(f"  - {path}")
    else:
        notes.append("No unknown keys detected in user config.")

    # Consistency checks
    warn = _check_provider_base_url(cfg.archivist.provider, cfg.archivist.base_url)
    if warn:
        issues.append(warn)

    warn = _check_semantic(cfg)
    if warn:
        issues.append(warn)

    # Optional ping
    if ping and cfg.archivist.enabled:
        try:
            import urllib.request

            provider = (cfg.archivist.provider or "").strip().lower()
            base = (cfg.archivist.base_url or "").rstrip("/")

            if provider == "openai_compat":
                url = base + "/models"
            else:
                # ollama_native
                url = base + "/api/tags"

            with urllib.request.urlopen(
                url, timeout=int(cfg.archivist.timeout_s)
            ) as resp:
                _ = resp.read().decode("utf-8", errors="replace")
            notes.append(f"Ping OK: {url}")
        except Exception as e:
            issues.append(f"Ping failed ({cfg.archivist.base_url}): {e}")

    # Summary
    typer.echo("")
    if issues:
        typer.echo("Doctor result:  ISSUES FOUND")
        for i, msg in enumerate(issues, 1):
            typer.echo(f"  {i}) {msg}")
        if strict:
            raise typer.Exit(code=1)
    else:
        typer.echo("Doctor result:  CLEAN")
        for msg in notes:
            typer.echo(f"  - {msg}")
