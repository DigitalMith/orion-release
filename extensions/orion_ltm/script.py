# C:\Orion\text-generation-webui\extensions\orion_ltm\script.py

from pathlib import Path
import yaml
from modules import chat
from modules.logging_colors import logger
from orion_cli.settings.config_loader import get_config
from orion_cli.shared.memory_core import (
    on_user_turn,
    on_assistant_turn,
    recall_persona,
    recall_episodic,
)


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
                "topk_persona": getattr(getattr(raw_cfg, "ltm", None), "topk_persona", 5),
                "topk_episodic": getattr(getattr(raw_cfg, "ltm", None), "topk_episodic", 10),
            },
            "debug": {
                "enabled": getattr(getattr(raw_cfg, "debug", None), "enabled", False),
                "show_recall": getattr(getattr(raw_cfg, "debug", None), "show_recall", False),
                "short_descriptions": getattr(getattr(raw_cfg, "debug", None), "short_descriptions", False),
                "episodic_store": getattr(getattr(raw_cfg, "debug", None), "episodic_store", False),
                "episodic_recall": getattr(getattr(raw_cfg, "debug", None), "episodic_recall", False),
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

    memory_text = "\n\n".join(blocks).strip()

    if not return_debug:
        # Old behavior: just the text
        return memory_text

    # Newer behavior: return text + debug payload
    dbg = {
        "persona": [{"doc": d} for d in persona_docs],
        "episodic": [{"doc": d} for d in episodic_docs],
    }
    return memory_text, dbg


def _debug(msg: str):
    """Print debug logs only if enabled in config."""
    try:
        cfg = get_config()
        if cfg.get("debug", {}).get("enabled"):
            logger.info(f"[DEBUG] {msg}")
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
    global _EMBED_READY, _persona, _episodic

    try:
        # Use the CNS 4.0 shim to get bound collections
        _persona, _episodic = initialize_chromadb_for_ltm()

        _EMBED_READY = True
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
    """
    TGWUI hook: runs before the model sees the user message.
    This is where we run recall() and prepend memory hits.

    We accept *args, **kwargs to be robust against different
    TGWUI extension calling conventions.
    """

    # Extract text + state safely from args/kwargs
    text = args[0] if len(args) >= 1 else ""
    state = args[1] if len(args) >= 2 and isinstance(args[1], dict) else kwargs.get("state", {})

    if not isinstance(text, str):
        text = str(text)

    # If the embedding system isn't ready, return unchanged
    if not _EMBED_READY or _persona is None or _episodic is None:
        return text

    try:
        # Preferred path: new API with return_debug
        try:
            memory_text, dbg = get_relevant_ltm(
                text,
                _persona,
                _episodic,
                topk_persona=int(CONFIG.get("ltm", {}).get("topk_persona", 5)),
                topk_episodic=int(CONFIG.get("ltm", {}).get("topk_episodic", 10)),
                return_debug=True,
            )
        except TypeError:
            # Fallback for older versions: no return_debug supported
            memory_text = get_relevant_ltm(text, _persona, _episodic)
            dbg = {}

    except Exception as e:
        logger.error(f"[orion_ltm] recall hook failed: {e}")
        return text

    if not memory_text:
        return text

    # Debug print if enabled via config.yaml
    debug_cfg = CONFIG.get("debug", {})
    if debug_cfg.get("enabled") and debug_cfg.get("show_recall"):
        logger.debug("=== Orion LTM Recall Snapshot ===")

        persona_hits = dbg.get("persona") or []
        episodic_hits = dbg.get("episodic") or []

        if persona_hits:
            logger.debug("--- Persona Recall ---")
            for i, item in enumerate(persona_hits[:3]):
                doc = (item.get("doc") or "")[:200]
                logger.debug(f"[{i}] {doc}...")

        if episodic_hits:
            logger.debug("--- Episodic Recall ---")
            for i, item in enumerate(episodic_hits[:3]):
                doc = (item.get("doc") or "")[:200]
                logger.debug(f"[{i}] {doc}...")

        if not persona_hits and not episodic_hits:
            # At least show the raw memory_text if debug is on
            logger.debug("(no structured hits; raw memory text)")
            logger.debug(memory_text[:400])

        logger.debug("==========================")

    # Prepend memory to user prompt
    return memory_text + "\n\n" + text


def output_modifier(*args, **kwargs):
    """
    Persist assistant replies as episodic memory (best-effort).

    Called on model outputs; we use it to feed Orion's episodic memory.
    We accept *args, **kwargs so we don't depend on a specific TGWUI
    calling convention.
    """
    text = args[0] if len(args) >= 1 else ""
    state = args[1] if len(args) >= 2 and isinstance(args[1], dict) else kwargs.get("state", {})

    try:
        reply = (text or "").strip()
        if not reply or len(reply.split()) < 10 or _episodic is None:
            return text

        last_user = ""
        if isinstance(state, dict):
            last_user = (state.get("context") or "").strip()

        # CNS 4.0: uses internal episodic binding; no positional collection arg
        on_assistant_turn(reply, last_user_input=last_user)

    except Exception as e:
        logger.error(f"[orion_ltm] output_modifier failed: {e}")

    return text


# ------------------------------------------------------------
# Setup runs when the extension loads
# ------------------------------------------------------------
try:
    setup()
except Exception as e:
    logger.error(f"[orion_ltm] Setup failed during extension load: {e}")


def teardown():
    """Optional cleanup hook."""
    global _INITIALIZED
    if _INITIALIZED:
        _debug("Tearing down LTM collections (no persistence affected).")
        _INITIALIZED = False


def before_chat_input(text):
    """Handle user input before chat generation (store to episodic)."""
    try:
        if _episodic:
            from orion_cli.shared.memory import on_user_turn

            # CNS 4.0: episodic collection is handled internally
            on_user_turn(text)
            _debug("User input stored to episodic memory.")
        else:
            _debug("Episodic collection not available at input time.")
    except Exception as e:
        logger.warning(f"[orion_ltm] Failed to process user input: {e}")


def after_chat_output(reply, last_user_input=None):
    """Handle assistant output after generation (store to episodic)."""
    try:
        if _episodic:
            from orion_cli.shared.memory import on_assistant_turn

            # CNS 4.0: no positional episodic argument
            on_assistant_turn(reply, last_user_input=last_user_input)
            _debug("Assistant reply stored to episodic memory.")
        else:
            _debug("Episodic collection not available at output time.")
    except Exception as e:
        logger.warning(f"[orion_ltm] Failed to store assistant turn: {e}")


def _inject_ltm_into_state_sys_prompt(state, text=None):
    if not (
        _EMBED_READY
        and get_relevant_ltm
        and _persona
        and _episodic
        and isinstance(state, dict)
    ):
        return state

    query = (state.get("context") or "").strip()
    if not query:
        return state

    # Store the original user turn into episodic memory
    try:
        on_user_turn(query, _episodic)
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

    # Inject structured LTM into prompt
    sys_prompt = (state.get("system_prompt") or "").strip()

    structured_memory = []
    if "persona_hits" in dbg and dbg["persona_hits"]:
        structured_memory.append("### [PERSONA MEMORY]")
        structured_memory.append(
            "\n".join(
                f"- {line}"
                for line in memory_text.split("\n")
                if line.startswith("[PERSONA]")
            )
        )

    if "episodic_hits" in dbg and dbg["episodic_hits"]:
        structured_memory.append("### [EPISODIC MEMORY]")
        structured_memory.append(
            "\n".join(
                f"- {line}"
                for line in memory_text.split("\n")
                if line.startswith("[EPISODIC]")
            )
        )

EXTENSION = {
    "input": input_modifier,
    "output": output_modifier,
}

try:
    setup()
except Exception as e:
    logger.error(f"[orion_ltm] Setup failed during extension load: {e}")