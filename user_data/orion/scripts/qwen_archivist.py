# orion_cli/scripts/qwen_archivist.py
from __future__ import annotations

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_DIR = r"C:\Orion\text-generation-webui\user_data\models\Qwen3-4B-Instruct-2507"

print(f"Loading Qwen3-4B-Instruct-2507 from: {MODEL_DIR}")

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR,
    torch_dtype=torch.float16,
    device_map="auto",
)

SYSTEM_PROMPT = (
    "You are Orion's background archivist. Your job is to read chat logs and "
    "extract stable, reusable facts that will still be true in future sessions. "
    "Ignore small talk, emotions, and one-off details.\n\n"
    "Return your answer as clear bullet points. Do NOT roleplay, just list facts."
)


def extract_semantic_facts(conversation: str) -> str:
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"--- Conversation Start ---\n"
        f"{conversation}\n"
        f"--- Conversation End ---\n\n"
        f"Facts:\n"
    )

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output = model.generate(
        **inputs,
        max_new_tokens=256,
        temperature=0.2,
        top_p=0.9,
        do_sample=True,
    )
    text = tokenizer.decode(output[0], skip_special_tokens=True)
    if "Facts:" in text:
        text = text.split("Facts:", 1)[-1].strip()
    return text


if __name__ == "__main__":
    demo = """
    User: I'm running Orion on Windows from C:\\Orion\\text-generation-webui using PowerShell.
    Assistant: I'll treat that as your main lab environment.
    User: I learn best from short, concrete steps and hands-on repetition, not long theory dumps.
    Assistant: I'll keep explanations compact and practical.
    """

    facts = extract_semantic_facts(demo)
    print("Extracted facts:\n")
    print(facts)
