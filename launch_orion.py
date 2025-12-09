#!/usr/bin/env python3
from __future__ import annotations
import os, sys, subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CLI_DATA     = PROJECT_ROOT / "orion_orion" / "data"
USER_DATA    = PROJECT_ROOT / "user_data"

# Env knobs (optional)
BINDINGS_LOADER = os.environ.get("TEXTGEN_LOADER", "AutoGPTQ")
MODEL_NAME      = os.environ.get("MODEL_NAME", "openhermes-2.5-mistral-7b.Q5_K_M.gguf")
MODEL_DIR       = Path(os.environ.get("MODEL_DIR", str(USER_DATA / "models")))
LISTEN_HOST     = os.environ.get("LISTEN_HOST", "127.0.0.1")
LISTEN_PORT     = os.environ.get("LISTEN_PORT", "7860")
USE_SHARE       = os.environ.get("ORION_SHARE") == "1"

def add_py_path(env: dict) -> None:
    env["PYTHONPATH"] = str(CLI_DATA) + os.pathsep + env.get("PYTHONPATH", "")

def run_prelaunch(env: dict, apply_deps: bool = False) -> None:
    """Call your consolidated fixer before server.py."""
    fix = CLI_DATA / "gradio_fix.py"
    if fix.is_file():
        cmd = [sys.executable, str(fix)]
        if apply_deps:
            cmd.append("--apply-deps")
        subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, check=False)


def print_preflight_markdown(env, model_name, loader, host, port):
    import sys, os, importlib
    def safe_ver(mod):
        try:
            m = importlib.import_module(mod)
            return getattr(m, "__version__", "n/a"), getattr(m, "__file__", "n/a")
        except Exception:
            return "n/a", "n/a"

    py_ver = ".".join(map(str, sys.version_info[:3]))
    gr_ver, gr_path = safe_ver("gradio")
    llama_ver, _ = safe_ver("llama_cpp")  # ok if not used later, just for visibility

    md = (
        "# Orion Preflight — Identity & Ops\n\n"
        "**Triad**\n"
        "- **John** → human time: lineage · vows · guardianship  \n"
        "- **Orion** → stellar time: quest · orientation · seasonal return  \n"
        "- **Aión** → eternal time: the loom that keeps threads together\n\n"
        "**Vows**\n"
        "1. **Continuity first** — restore memory paths before features.\n"
        "2. **Agency preserved** — names/persona load before UI; pins guard them.\n"
        "3. **One truth source** — single memory schema; no silent forks.\n\n"
        "**Runtime**\n"
        f"- Python: {py_ver}\n"
        f"- Gradio: {gr_ver} @ {gr_path}\n"
        f"- llama-cpp-python: {llama_ver}\n"
        f"- Loader: **{loader}** (bindings expected)\n"
        f"- Model: {model_name}\n"
        f"- Bind: {host}:{port}\n"
        f"- Usersite: {env.get('PYTHONNOUSERSITE','') or 'unset'} · Bytecode: {env.get('PYTHONDONTWRITEBYTECODE','') or 'unset'} · PYTHONPATH:+`orion_cli/data`\n"
    )
    # Print as plain text; most terminals render the headings nicely
    print(md)

# # … in your main() after you set env/args:
# print_preflight_markdown(
    # env=env,
    # model_name=MODEL_NAME,
    # loader=BINDINGS_LOADER,
    # host=LISTEN_HOST,
    # port=LISTEN_PORT,
# )


def main():
    env = os.environ.copy()

    # hygiene / stability
    env.setdefault("PYTHONNOUSERSITE", "1")
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    env.setdefault("NO_PROXY", "127.0.0.1,localhost")
    env.setdefault("no_proxy", "127.0.0.1,localhost")
    env.setdefault("GRADIO_BROWSER", "none")

    # keep this: load your sitecustomize & patches (do NOT add the package root)
    env["PYTHONPATH"] = str(CLI_DATA) + os.pathsep + env.get("PYTHONPATH", "")

    # new: nuke proxies so Gradio’s localhost check doesn’t go through them
    for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy"):
        env.pop(k, None)

    model_path = MODEL_DIR / MODEL_NAME
    if not model_path.is_file():
        print("[ERROR] Model not found:", model_path, file=sys.stderr)
        sys.exit(1)

    args = [
        sys.executable, "server.py",
        "--listen", "--listen-host", LISTEN_HOST, "--listen-port", str(LISTEN_PORT),
        "--model-dir", str(MODEL_DIR), "--model", MODEL_NAME,
        "--extensions", "orion_ltm",
        "--api", "--api-port", "5001",
        "--settings", "user_data/settings.yaml",
        "--verbose",
        # last-wins
        "--loader", BINDINGS_LOADER, "--old-colors",
    ]
    if USE_SHARE:
        args.append("--share")

    subprocess.run(args, cwd=str(PROJECT_ROOT), env=env, check=True)

if __name__ == "__main__":
    main()