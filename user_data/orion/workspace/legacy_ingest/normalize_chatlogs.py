import json
from pathlib import Path
from datetime import datetime

CHATLOG_DIR = Path("orion_cli/data/chat_logs")
NORMALIZED_FILE = Path("orion_cli/data/normalized_logs.jsonl")
ERROR_FILE = Path("orion_cli/data/normalize_errors.jsonl")


def extract_dialogues(data):
    if "internal" in data and isinstance(data["internal"], list):
        return data["internal"]
    if "visible" in data and isinstance(data["visible"], list):
        return data["visible"]
    return None


def extract_timestamp(metadata):
    # Try to find the earliest timestamp from metadata
    timestamps = []
    for entry in metadata.values():
        ts = entry.get("timestamp")
        if ts:
            try:
                dt = datetime.strptime(ts, "%b %d, %Y %H:%M")
                timestamps.append(dt)
            except ValueError:
                continue
    if timestamps:
        return min(timestamps).isoformat()
    return datetime.now().isoformat()


def normalize_file(file):
    with open(file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    dialog_pairs = extract_dialogues(data)
    if not dialog_pairs:
        raise ValueError("No valid dialogue pairs found.")

    timestamp = extract_timestamp(data.get("metadata", {}))
    entries = []
    for i, pair in enumerate(dialog_pairs):
        if not isinstance(pair, list) or len(pair) != 2:
            continue
        user, assistant = pair
        if not user.strip() and not assistant.strip():
            continue

        entries.append(
            {
                "catalog": "chatlog",
                "kind": "user_assistant",
                "timestamp": timestamp,
                "weight": 0.6,
                "importance": 0.7,
                "tone": [],
                "tags": [],
                "text": f"User: {user}\nAssistant: {assistant}",
            }
        )
    return entries


def main():
    all_entries = []
    errors = []

    for file in CHATLOG_DIR.rglob("*.json"):
        try:
            entries = normalize_file(file)
            all_entries.extend(entries)
        except Exception as e:
            errors.append({"file": file.name, "error": str(e)})

    if all_entries:
        with open(NORMALIZED_FILE, "w", encoding="utf-8") as f:
            for entry in all_entries:
                f.write(json.dumps(entry) + "\n")
        print(f"✅ Normalized {len(all_entries)} entries from {CHATLOG_DIR}")
    else:
        print(f"⚠️ No normalized data to write from {CHATLOG_DIR}")

    if errors:
        with open(ERROR_FILE, "w", encoding="utf-8") as f:
            for err in errors:
                f.write(json.dumps(err) + "\n")
        print(f"⚠️ Logged {len(errors)} errors to {ERROR_FILE}")
    else:
        print("✅ No errors encountered. Skipping error log file.")


if __name__ == "__main__":
    print("Device set to use cpu")
    main()
