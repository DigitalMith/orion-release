from __future__ import annotations

import re
from typing import Any, Dict, Optional, Set

from orion_cli.shared.utils import normalize_text


BAD_TAGS: Set[str] = {"greeting", "compliment", "smalltalk", "pleasantry", "filler"}

# If a candidate contains these, it's probably meaningful even if it starts with "hi"
KEEP_HINTS = {
    "prefer",
    "preference",
    "use",
    "using",
    "always",
    "never",
    "default",
    "windows",
    "powershell",
    "linux",
    "macos",
    "config",
    "yaml",
    "path",
    "folder",
    "directory",
    "repo",
    "github",
    "url",
    "chroma",
    "embedding",
    "model",
    "dimension",
    "endpoint",
    "localhost",
    "api",
}

GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|hiya|yo|greetings)\b|^\s*good\s+(morning|afternoon|evening|day)\b",
    re.IGNORECASE,
)
HOW_ARE_YOU_RE = re.compile(r"^\s*how\s+are\s+you\b", re.IGNORECASE)

COMPLIMENT_RE = re.compile(
    r"^\s*(thank(s| you)|appreciate it|you're the best|you are the best|"
    r"you're amazing|you are amazing|you're awesome|you are awesome|"
    r"wonderful|great job)\b",
    re.IGNORECASE,
)

ACK_RE = re.compile(
    r"^\s*(ok|okay|k|kk|sure|yep|yeah|nah|nope|got it|understood|roger|ack|thanks|thank you|ty|lol|lmao)\b[!. ,]*$",
    re.IGNORECASE,
)

TRUTHBOMB_RE = re.compile(
    r"\b("
    r"as an ai|language model|chatgpt|openai|not sentient|no consciousness|"
    r"i don'?t have feelings|i can'?t feel|i am an assistant|i'?m an assistant|artificial intelligence"
    r")\b",
    re.IGNORECASE,
)

TEMPORAL_RE = re.compile(
    r"\b("
    r"yesterday|today|tonight|tomorrow|last night|last weekend|this weekend|this morning|"
    r"earlier|recently|just now|a while ago|a couple of days|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
    r")\b",
    re.IGNORECASE,
)

STORY_START_RE = re.compile(
    r"^\s*i\s+(went|visited|made it|didn'?t make it|was|were|had|got|woke up|slept|ate|drove|saw|met)\b",
    re.IGNORECASE,
)

URL_RE = re.compile(r"https?://", re.IGNORECASE)
PATH_RE = re.compile(r"\b[A-Za-z]:\\", re.IGNORECASE)


def strip_leading_greeting_if_meaningful(text: str) -> str:
    """
    If text starts with a greeting, strip it ONLY when the remaining text
    looks meaningful (contains KEEP_HINTS). Otherwise return original.
    """
    clean = normalize_doc(text)
    if not clean:
        return clean

    t = clean

    # Remove a leading greeting chunk like:
    # "Hi —", "Hello,", "Good morning:", etc.
    if GREETING_RE.search(t) or HOW_ARE_YOU_RE.search(t):
        # re.split with capture groups can be annoying; safest: just remove greeting with a regex
        t2 = re.sub(
            r"^\s*(hi|hello|hey|hiya|yo|greetings)\b[\s,:\-–—]*",
            "",
            t,
            flags=re.IGNORECASE,
        )
        t2 = re.sub(
            r"^\s*good\s+(morning|afternoon|evening|day)\b[\s,:\-–—]*",
            "",
            t2,
            flags=re.IGNORECASE,
        )
        t2 = re.sub(
            r"^\s*how\s+are\s+you\b[\s,:\-–—]*",
            "",
            t2,
            flags=re.IGNORECASE,
        )

        t2 = normalize_doc(t2)
        if t2 and any(h in t2.lower() for h in KEEP_HINTS):
            return t2

    return clean


def normalize_doc(text: str) -> str:
    return normalize_text(text or "").strip()


def tags_to_set(tags: Any) -> Set[str]:
    if tags is None:
        return set()
    if isinstance(tags, list):
        return {
            str(t).strip().lower() for t in tags if t is not None and str(t).strip()
        }
    if isinstance(tags, str):
        return {t.strip().lower() for t in tags.split(",") if t.strip()}
    s = str(tags).strip().lower()
    return {s} if s else set()


def is_timebound_story(text: str) -> bool:
    """
    Returns True if this looks like an episodic, time-bound story that
    shouldn't become semantic memory.
    We allow it through if it contains a URL/path or KEEP_HINTS.
    """
    t = normalize_doc(text)
    if not t:
        return True

    tl = t.lower()
    wc = len(re.findall(r"[a-z0-9']+", tl))

    # Technical anchors often indicate durable info
    if URL_RE.search(t) or PATH_RE.search(t):
        return False

    # If it contains keep hints, assume it's durable enough
    if any(h in tl for h in KEEP_HINTS):
        return False

    # Strong episodic signals
    if wc >= 6 and TEMPORAL_RE.search(t):
        return True
    if wc >= 6 and STORY_START_RE.match(t):
        return True

    return False


def is_low_value_candidate(text: str, meta: Optional[Dict[str, Any]] = None) -> bool:
    """
    Blocks obvious junk candidates (greetings/compliments/smalltalk),
    but keeps anything that looks like a durable fact/policy/preference.
    """
    clean = normalize_doc(text)
    if not clean:
        return True

    t = clean.lower()
    words = re.findall(r"[a-z0-9']+", t)
    wc = len(words)

    # Hard-block acknowledgements / filler-only
    if wc <= 6 and ACK_RE.match(clean):
        return True

    # Block "truth-bomb" demystification statements from entering semantic
    if TRUTHBOMB_RE.search(clean):
        return True

    # Block time-bound episodic stories
    if is_timebound_story(clean):
        return True

    # If it has strong "keep" hints, do NOT block it
    if any(h in t for h in KEEP_HINTS):
        return False

    # Tag-based blocking (if provided by Archivist)
    if meta and isinstance(meta, dict):
        tags = tags_to_set(meta.get("tags"))
        if tags & BAD_TAGS:
            return True

    # Greeting-only / smalltalk heuristics (short candidates)
    if wc <= 12 and (GREETING_RE.search(t) or HOW_ARE_YOU_RE.search(t)):
        return True

    # Compliments/thanks (also usually short & non-durable)
    if wc <= 18 and COMPLIMENT_RE.search(t):
        return True

    return False


def confidence(meta: Optional[Dict[str, Any]]) -> float:
    if not meta or not isinstance(meta, dict):
        return 0.0
    x = meta.get("confidence", None)
    try:
        return float(x) if x is not None else 0.0
    except Exception:
        return 0.0
