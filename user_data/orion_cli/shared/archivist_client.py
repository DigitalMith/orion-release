from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


@dataclass
class ArchivistResponse:
    raw_text: str
    parsed_json: Optional[Dict[str, Any]]


def _load_reflection_contract_text() -> str:
    """
    Load the frozen semantic reflection contract shipped with the package.
    """
    here = Path(__file__).resolve()
    contract_path = (
        here.parents[1] / "semantic" / "REFLECTION_CONTRACT.md"
    )  # orion_cli/semantic/...
    text = contract_path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"[archivist] Empty reflection contract: {contract_path}")
    return text


def _post_json(
    url: str, payload: Dict[str, Any], timeout_s: int = 60
) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url=url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except HTTPError as e:
        msg = (
            e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        )
        raise RuntimeError(f"[archivist] HTTP {e.code}: {msg}") from e
    except URLError as e:
        raise RuntimeError(f"[archivist] Connection error: {e}") from e


def call_openai_compat_chat(
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 800,
    timeout_s: int = 60,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": False,
    }
    data = _post_json(url, payload, timeout_s=timeout_s)
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError(f"[archivist] Unexpected response shape: {data}")


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start : i + 1]
                try:
                    return json.loads(chunk)
                except Exception:
                    return None
    return None


def run_archivist_extract(
    cfg_archivist: Any, pooled_turns: List[Dict[str, str]]
) -> ArchivistResponse:
    contract = _load_reflection_contract_text()

    system = {
        "role": "system",
        "content": contract,
    }

    user = {
        "role": "user",
        "content": (
            "Analyze the following chat turns and extract ONLY durable semantic facts about the USER.\n"
            "Return JSON that strictly conforms to the contract.\n"
            "Turns:\n" + json.dumps(pooled_turns, ensure_ascii=False)
        ),
    }

    raw = call_openai_compat_chat(
        base_url=str(cfg_archivist.base_url),
        model=str(cfg_archivist.model),
        messages=[system, user],
        temperature=float(getattr(cfg_archivist, "temperature", 0.2)),
        max_tokens=int(getattr(cfg_archivist, "max_tokens", 800)),
        timeout_s=int(getattr(cfg_archivist, "timeout_s", 60)),
    )

    parsed = extract_json_object(raw)
    return ArchivistResponse(raw_text=raw, parsed_json=parsed)
