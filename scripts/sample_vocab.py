#!/usr/bin/env python3
"""
Sample a random subset of vocabulary entries from the knowledge base.

Intended for use by the exercise generation agent: instead of loading the
entire vocabulary into context, the agent calls this script to get a small,
focused word list for each exercise it is about to generate.

Usage:
    python sample_vocab.py vocab:any --count 20
    python sample_vocab.py food --count 10
    python sample_vocab.py food verbs_basic --count 15

Arguments:
    CATEGORY ...   One or more topic names (as they appear in _index.json),
                   or 'vocab:any' to draw from all topics at once.
    --count N      How many entries to return (default: 20).
                   When N exceeds the available pool the full pool is returned.
    --seed S       Optional integer seed for reproducible sampling (useful for
                   debugging; omit in normal use so samples vary each run).

Output (stdout):
    A JSON array of vocab entry objects, each with an added 'topic' field:
    [
      {"word": "alma", "en": "apple", "topic": "food"},
      ...
    ]

Exit codes:
    0 — success, JSON written to stdout
    1 — no entries found for the requested categories
    2 — argument / file error
"""

import sys
import os
import json
import random
import argparse

# ---------------------------------------------------------------------------
# Paths — resolve relative to this file so the script works from any cwd
# ---------------------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT  = os.path.abspath(os.path.join(_SCRIPT_DIR, '..'))
VOCAB_DIR   = os.path.join(_REPO_ROOT, 'knowledge', 'vocab')
INDEX_PATH  = os.path.join(VOCAB_DIR, '_index.json')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def available_topics() -> list[str]:
    """Return all topic names from _index.json, sorted alphabetically."""
    try:
        with open(INDEX_PATH, encoding='utf-8') as f:
            index: dict[str, int] = json.load(f)
    except FileNotFoundError:
        print(f"Error: vocab index not found at {INDEX_PATH}", file=sys.stderr)
        sys.exit(2)
    return sorted(index.keys())


def load_topic(topic: str) -> list[dict]:
    """
    Load all entries from a single topic file and stamp each one with its
    source topic so callers know where the word came from.
    """
    path = os.path.join(VOCAB_DIR, f"{topic}.json")
    if not os.path.exists(path):
        print(f"Error: topic file not found: {path}", file=sys.stderr)
        sys.exit(2)

    with open(path, encoding='utf-8') as f:
        entries: list[dict] = json.load(f)

    # Add the topic key — vocab files don't store it internally
    for entry in entries:
        entry['topic'] = topic

    return entries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample random vocabulary entries from the knowledge base.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python sample_vocab.py vocab:any --count 20\n"
            "  python sample_vocab.py food verbs_basic --count 15\n"
            "  python sample_vocab.py food --count 5 --seed 42\n"
        ),
    )
    parser.add_argument(
        'categories',
        nargs='+',
        metavar='CATEGORY',
        help="Topic name(s) to sample from, or 'vocab:any' to use all topics.",
    )
    parser.add_argument(
        '--count', '-n',
        type=int,
        default=20,
        metavar='N',
        help="Number of entries to sample (default: 20).",
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        metavar='S',
        help="Random seed for reproducible output (optional).",
    )
    args = parser.parse_args()

    if args.count < 1:
        print("Error: --count must be at least 1.", file=sys.stderr)
        sys.exit(2)

    # 'vocab:any' is the wildcard that expands to every known topic
    if 'vocab:any' in args.categories:
        topics = available_topics()
    else:
        topics = list(args.categories)

    # Build the pool, deduplicating by (word, topic) in case of repeated input
    pool: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for topic in topics:
        for entry in load_topic(topic):
            key = (entry['word'], entry['topic'])
            if key not in seen:
                seen.add(key)
                pool.append(entry)

    if not pool:
        print("No entries found for the requested categories.", file=sys.stderr)
        sys.exit(1)

    # Sample — clamp to pool size so we never ask for more than exists
    rng = random.Random(args.seed)
    sample = rng.sample(pool, min(args.count, len(pool)))

    # Print compact, unicode-safe JSON to stdout
    print(json.dumps(sample, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
