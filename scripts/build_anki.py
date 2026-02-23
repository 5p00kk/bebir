#!/usr/bin/env python3
"""
Build an Anki-compatible text file from all vocab topic files.

Usage:
    python build_anki.py [--output PATH]

Output (default: anki_export.txt at repo root):
    Tab-separated, UTF-8, no header row.
    Columns: word (Azerbaijani), english, topic, example

Anki import:
    Import → select file → Fields separated by Tab → map fields manually.
"""

import sys
import os
import json
import csv
import argparse

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT  = os.path.abspath(os.path.join(_SCRIPT_DIR, '..'))

VOCAB_DIR   = os.path.join(_REPO_ROOT, 'knowledge', 'vocab')
INDEX_PATH  = os.path.join(VOCAB_DIR, '_index.json')
DEFAULT_OUT = os.path.join(_REPO_ROOT, 'anki_export.txt')


def load_all_vocab() -> list[dict]:
    """Load every {topic}.json from knowledge/vocab/ and return flat list."""
    if not os.path.isdir(VOCAB_DIR):
        print(f"Error: vocab directory not found: {VOCAB_DIR}", file=sys.stderr)
        sys.exit(1)

    entries = []
    for fname in sorted(os.listdir(VOCAB_DIR)):
        if fname.startswith('_') or not fname.endswith('.json'):
            continue
        topic = fname[:-5]  # strip .json
        path  = os.path.join(VOCAB_DIR, fname)
        with open(path, encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Warning: skipping {fname} (JSON error: {e})", file=sys.stderr)
                continue
        if not isinstance(data, list):
            print(f"Warning: skipping {fname} (expected a JSON array)", file=sys.stderr)
            continue
        for entry in data:
            if not isinstance(entry, dict):
                continue
            entries.append({
                "word":    entry.get("word", ""),
                "english": entry.get("en", ""),
                "topic":   topic,
                "example": entry.get("example") or "",
            })
    return entries


def write_csv(entries: list[dict], output_path: str):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
        for e in entries:
            writer.writerow([e["word"], e["english"], e["topic"], e["example"]])


def main():
    parser = argparse.ArgumentParser(description="Build Anki CSV from vocab files.")
    parser.add_argument("--output", default=DEFAULT_OUT,
                        help=f"Output CSV path (default: {DEFAULT_OUT})")
    args = parser.parse_args()

    entries = load_all_vocab()

    if not entries:
        print("No vocab entries found. Has the extraction agent run yet?")
        sys.exit(0)

    write_csv(entries, args.output)

    rel = os.path.relpath(args.output, _REPO_ROOT)
    print(f"Wrote {len(entries)} entries to {rel}")

    # Print per-topic breakdown
    from collections import Counter
    counts = Counter(e["topic"] for e in entries)
    print("\nPer-topic counts:")
    for topic, n in sorted(counts.items()):
        print(f"  {topic:<30} {n}")


if __name__ == '__main__':
    main()
