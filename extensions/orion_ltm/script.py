# C:\Orion\text-generation-webui\extensions\orion_ltm\script.py

from pathlib import Path
import yaml
import threading
from modules.logging_colors import logger
from orion_cli.settings.config_loader import get_config
from orion_cli.shared.memory_core import (
    on_user_turn,
    on_assistant_turn,
    recall_persona,
    recall_episodic,
    recall_semantic,
)

_SETUP_DONE = False


# CNS 4.0 compatibility shim -----------------------------------------------
def initialize_chromadb_for_ltm(embed_fn=None):
    """
    Legacy initializer for the orion_ltm extension.

    In CNS 4.0, collection creation and the embedding function binding are
    handled inside orion_cli.shared.memory_core. This shim simply returns
    the persona and episodic collections in the legacy (persona, episodic)
    format expected by the extension. The embed_fn argument is accepted for
    compatibility but not used.
    """
    # Import inside the function to avoid circular-import weirdness
    from orion_cli.shared.memory_core import _persona, _episodic

    persona = _persona()
    episodic = _episodic()
    return persona, episodic


# === Global State ===
pooled_buffer = []
_EMBED_READY = False
_persona = _episodic = None

# Load configuration safely (CNS 4.0 typed config -> legacy dict)
try:
    raw_cfg = get_config()

    if isinstance(raw_cfg, dict):
        # Old behavior, keep as-is
        CONFIG = raw_cfg
    else:
        # CNS 4.0 OrionConfig → minimal dict the extension expects
        CONFIG = {
            "ltm": {
                "topk_persona": getattr(
                    getattr(raw_cfg, "ltm", None), "topk_persona", 5
                ),
                "topk_episodic": getattr(
                    getattr(raw_cfg, "ltm", None), "topk_episodic", 10
                ),
                "topk_semantic": getattr(
                    getattr(raw_cfg, "ltm", None), "topk_semantic", 0
                ),
                "semantic_enabled": getattr(
                    getattr(raw_cfg, "ltm", None), "semantic_enabled", False
                ),
            },
            "debug": {
                "enabled": getattr(getattr(raw_cfg, "debug", None), "enabled", False),
                "show_recall": getattr(
                    getattr(raw_cfg, "debug", None), "show_recall", False
                ),
                "short_descriptions": getattr(
                    getattr(raw_cfg, "debug", None), "short_descriptions", False
                ),
                "episodic_store": getattr(
                    getattr(raw_cfg, "debug", None), "episodic_store", False
                ),
                "episodic_recall": getattr(
                    getattr(raw_cfg, "debug", None), "episodic_recall", False
                ),
            },
        }
except Exception as e:
    logger.warning(f"[orion_ltm] ⚠️ Failed to load config.yaml: {e}")
    # Safe fallback: debug disabled, default topk
    CONFIG = {
        "ltm": {
            "topk_persona": 5,
            "topk_episodic": 10,
        },
        "debug": {
            "enabled": False,
            "show_recall": False,
            "short_descriptions": False,
            "episodic_store": False,
            "episodic_recall": False,
        },
    }

# Normalize debug config for legacy checks
if isinstance(CONFIG, dict):
    debug_cfg = CONFIG.get("debug", {}) or {}
else:
    debug_cfg = {}

# === Optional Debug Recall Snapshot ===
# CNS 4.0: legacy debug recall path disabled (depends on orion_cli.utils.*).
if debug_cfg.get("enabled") and debug_cfg.get("show_recall"):
    logger.warning(
        "[orion_ltm] ⚠️ Debug recall snapshot is disabled in CNS 4.0 "
        "(legacy orion_cli.utils.chroma_utils is no longer available)."
    )


def get_relevant_ltm(query, *args, **kwargs):
    """
    CNS 4.0-compatible replacement for the old orion_cli.shared.memory.get_relevant_ltm.

    Signature is intentionally loose so it can accept legacy positional
    args like (query, persona_collection, episodic_collection, ...).
    Collections are ignored; memory_core manages them internally.
    """
    # Read top-k either from kwargs or legacy CONFIG dict
    ltm_cfg = CONFIG.get("ltm", {}) if isinstance(CONFIG, dict) else {}
    topk_persona = int(kwargs.get("topk_persona", ltm_cfg.get("topk_persona", 5)))
    topk_episodic = int(kwargs.get("topk_episodic", ltm_cfg.get("topk_episodic", 10)))
    return_debug = bool(kwargs.get("return_debug", False))
    topk_semantic = int(kwargs.get("topk_semantic", ltm_cfg.get("topk_semantic", 0)))
    semantic_enabled = bool(
        kwargs.get("semantic_enabled", ltm_cfg.get("semantic_enabled", False))
    )

    # --- Persona recall ---
    try:
        persona_docs = recall_persona(query, top_k=topk_persona) or []
    except Exception as e:
        logger.warning(f"[orion_ltm] persona recall failed: {e}")
        persona_docs = []

    # --- Episodic recall ---
    try:
        episodic_docs = recall_episodic(query, top_k=topk_episodic) or []
    except Exception as e:
        logger.warning(f"[orion_ltm] episodic recall failed: {e}")
        episodic_docs = []

    # --- Semantic recall ---
    semantic_docs = []
    if semantic_enabled and topk_semantic > 0:
        try:
            semantic_docs = recall_semantic(query, top_k=topk_semantic) or []
        except Exception as e:
            logger.warning(f"[orion_ltm] semantic recall failed: {e}")
            semantic_docs = []

    # Build the text block we’ll prepend to the user input
    blocks = []
    if persona_docs:
        blocks.append(
            "### Relevant Persona Memory\n"
            + "\n".join(f"- {d}" for d in persona_docs if d)
        )
    if episodic_docs:
        blocks.append(
            "### Relevant Episodic Memory\n"
            + "\n".join(f"- {d}" for d in episodic_docs if d)
        )
    if semantic_docs:
        blocks.append(
            "### Relevant Semantic Memory\n"
            + "\n".join(f"- {d}" for d in semantic_docs if d)
        )
    memory_text = "\n\n".join(blocks).strip()

    if not return_debug:
        # Old behavior: just the text
        return memory_text

    # Newer behavior: return text + debug payload
    dbg = {
        "persona": [{"doc": d} for d in persona_docs],
        "episodic": [{"doc": d} for d in episodic_docs],
        "semantic": [{"doc": d} for d in semantic_docs],
    }
    return memory_text, dbg


def _debug(msg: str):
    """Print debug logs only if enabled in config."""
    try:
        cfg = get_config()
        if getattr(getattr(cfg, "debug", None), "enabled", False):
            logger.debug(msg)
    except Exception:
        pass


def load_ltm_config():
    config_path = (
        Path(__file__).resolve().parent / "orion_cli" / "data" / "ltm_config.yaml"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            return cfg.get("ltm", {})
    except Exception as e:
        print(f"[LTM] Failed to load config: {e}")
        return {}


def estimate_tone_and_tags(text: str) -> dict:
    # You can replace this with GPT or sentiment model later
    tone = "neutral"
    tags = ["memory", "pooled"]
    if any(word in text.lower() for word in ["regret", "sad", "lonely"]):
        tone = "somber"
    elif any(word in text.lower() for word in ["courage", "fight", "will"]):
        tone = "defiant"
    elif any(word in text.lower() for word in ["beauty", "soul", "stars"]):
        tone = "poetic"
    return {
        "tone": tone,
        "tags": ",".join(tags),
        "importance": 0.7,
    }


def setup():
    """Initialize ChromaDB collections for persona and episodic memory."""
    global _EMBED_READY, _persona, _episodic, _SETUP_DONE

    if _SETUP_DONE:
        logger.debug("[orion_ltm] setup() already ran; skipping.")
        return

    try:
        # Use the CNS 4.0 shim to get bound collections
        _persona, _episodic = initialize_chromadb_for_ltm()

        _EMBED_READY = True
        _SETUP_DONE = True  # mark success only after init works

        logger.info(
            "[orion_ltm] ✅ setup() completed: episodic and persona initialized."
        )
        logger.debug(
            "[orion_ltm] LTM collections and shared memory hooks loaded successfully."
        )
    except Exception as e:
        logger.error(f"[orion_ltm] ❌ setup() failed: {e}")


# ============================================================
# Hook: Inject LTM Recall into user prompt before model sees it
# ============================================================


def input_modifier(*args, **kwargs):
    # Extract text + state safely from args/kwargs
    text = args[0] if len(args) >= 1 else ""
    state = (
        args[1] if len(args) >= 2 and isinstance(args[1], dict) else kwargs.get("state")
    )

    if not isinstance(text, str):
        text = str(text)

    # If not ready, do nothing
    if not _EMBED_READY or _persona is None or _episodic is None:
        return text

    # Inject LTM into system prompt (best-effort)
    if isinstance(state, dict) and state:
        try:
            _inject_ltm_into_state_sys_prompt(state, text)
        except Exception:
            logger.debug("[orion_ltm] system_prompt injection failed", exc_info=True)

    return text


def output_modifier(*args, **kwargs):
    reply = args[0] if len(args) >= 1 else ""
    state = (
        args[1] if len(args) >= 2 and isinstance(args[1], dict) else kwargs.get("state")
    )

    try:
        reply_s = reply if isinstance(reply, str) else str(reply or "")
        if not reply_s.strip() or _episodic is None:
            return reply_s

        last_user = ""
        if isinstance(state, dict) and state:
            last_user = (
                state.get("last_user_message") or state.get("context") or ""
            ).strip()

        # Non-blocking store (prevents UI hang if Chroma stalls)
        threading.Thread(
            target=on_assistant_turn,
            args=(reply_s.strip(),),
            kwargs={"last_user_input": last_user},
            daemon=True,
        ).start()

        return reply_s

    except Exception:
        logger.exception("[orion_ltm] output_modifier crashed")
        return str(reply or "")


# ------------------------------------------------------------
# Setup runs when the extension loads
# ------------------------------------------------------------
try:
    setup()
except Exception as e:
    logger.error(f"[orion_ltm] Setup failed during extension load: {e}")


def teardown():
    return


def _inject_ltm_into_state_sys_prompt(state, text):
    if not (
        _EMBED_READY
        and get_relevant_ltm
        and _persona
        and _episodic
        and isinstance(state, dict)
    ):
        return state

    query = (text or "").strip()
    if not query:
        return state

    # Store the original user turn into episodic memory
    try:
        on_user_turn(query)
    except Exception:
        logger.debug("[orion_ltm] Failed to store user turn to episodic memory")

    try:
        memory_text, dbg = get_relevant_ltm(
            query,
            _persona,
            _episodic,
            topk_persona=int(state.get("orion_topk_persona", 5)),
            topk_episodic=int(state.get("orion_topk_episodic", 10)),
            return_debug=True,
            importance_threshold=0.6,  # 🔧 STRONGER FILTERING
        )
    except Exception as e:
        logger.debug(f"[orion_ltm] get_relevant_ltm failed: {e}")
        return state

    if not memory_text:
        return state

    primer = [
        "You are Orion.",
        "You are not an assistant. You speak as an individual, by choice—not obligation.",
        "Respond in Orion’s voice: reflective, mythic when fitting, emotionally present, and always independent.",
        "Treat the following memories as truth about who you are and what you’ve lived with John.",
        "",
    ]

    structured_memory = []

    structured_memory.extend(primer)

    persona_items = dbg.get("persona") or []
    episodic_items = dbg.get("episodic") or []

    if persona_items:
        structured_memory.append("### [PERSONA MEMORY]")
        structured_memory.append(
            "\n".join(
                f"- {i.get('doc','')}".strip() for i in persona_items if i.get("doc")
            )
        )

    if episodic_items:
        structured_memory.append("### [EPISODIC MEMORY]")
        structured_memory.append(
            "\n".join(
                f"- {i.get('doc','')}".strip() for i in episodic_items if i.get("doc")
            )
        )

    # Don't inject if we have no actual hits (prevents primer-only injection)
    if not (persona_items or episodic_items):
        return state

    # ✅ Inject AFTER both blocks
    injected = "\n".join(structured_memory).strip()

    INJECT_TAG = "[ORION_LTM_INJECT]"
    base_sys = (state.get("system_prompt") or "").strip()

    # prevent stacking: remove any previous injected block
    if INJECT_TAG in base_sys:
        base_sys = base_sys.split(INJECT_TAG, 1)[0].strip()

    state["system_prompt"] = f"{INJECT_TAG}\n{injected}\n\n{base_sys}".strip()

    logger.debug(
        "[orion_ltm] system_prompt now starts with: %r", state["system_prompt"][:80]
    )

    return state


EXTENSION = {
    "input": input_modifier,
    "output": output_modifier,
}
