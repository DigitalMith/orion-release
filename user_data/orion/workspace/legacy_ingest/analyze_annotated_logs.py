import json
from pathlib import Path


def main(path: Path, min_length: int = 10):
    if not path.exists():
        raise FileNotFoundError(path)

    total = 0
    json_error = 0
    no_response = 0
    short_response = 0
    long_enough = 0

    short_examples = []

    with path.open("r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            total += 1

            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                json_error += 1
                continue

            resp = (rec.get("response") or "").strip()
            if not resp:
                no_response += 1
                continue

            # approximate what add_episodic_entry(min_length=10) cares about:
            # number of words in the response
            words = resp.split()
            if len(words) < min_length:
                short_response += 1
                if len(short_examples) < 10:
                    short_examples.append((line_idx, len(words), resp))
            else:
                long_enough += 1

    print(f"File: {path}")
    print(f"Total non-empty lines       : {total}")
    print(f"JSON parse errors           : {json_error}")
    print(f"Missing/empty response      : {no_response}")
    print(f"Short responses (<{min_length} words): {short_response}")
    print(f"Long-enough responses       : {long_enough}")
    print()

    if short_examples:
        print("Examples of short responses:")
        for idx, n_words, txt in short_examples:
            print(f"  Line {idx}: {n_words} words -> {txt!r}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python analyze_annotated_logs.py PATH_TO_annotated_logs.jsonl")
        raise SystemExit(1)
    main(Path(sys.argv[1]))
