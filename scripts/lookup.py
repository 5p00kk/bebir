#!/usr/bin/env python3
"""
Check whether a vocab word or grammar concept already exists in the knowledge base.

Usage:
    python lookup.py vocab <word>            # check across all topic files
    python lookup.py vocab <word> --topic T  # check within a specific topic
    python lookup.py grammar <concept>       # check grammar.json

Exit codes:
    0 — entry found (prints matching entry as JSON)
    1 — entry not found (prints nothing)
    2 — usage error
"""

import sys
import os
import json
import argparse

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT  = os.path.abspath(os.path.join(_SCRIPT_DIR, '..'))
KNOWLEDGE_DIR = os.path.join(_REPO_ROOT, 'knowledge')
VOCAB_DIR     = os.path.join(KNOWLEDGE_DIR, 'vocab')
GRAMMAR_PATH  = os.path.join(KNOWLEDGE_DIR, 'grammar.json')


def lookup_vocab(word: str, topic: str | None) -> dict | None:
    word_lower = word.strip().lower()

    if topic:
        files = [os.path.join(VOCAB_DIR, f"{topic}.json")]
    else:
        files = [
            os.path.join(VOCAB_DIR, f)
            for f in os.listdir(VOCAB_DIR)
            if not f.startswith('_') and f.endswith('.json')
        ]

    for path in files:
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            entries = json.load(f)
        for entry in entries:
            if entry.get('word', '').strip().lower() == word_lower:
                return entry

    return None


def lookup_grammar(concept: str) -> dict | None:
    concept_lower = concept.strip().lower()

    if not os.path.exists(GRAMMAR_PATH):
        return None

    with open(GRAMMAR_PATH, encoding='utf-8') as f:
        entries = json.load(f)

    for entry in entries:
        if entry.get('concept', '').strip().lower() == concept_lower:
            return entry

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Check if a vocab word or grammar concept already exists."
    )
    sub = parser.add_subparsers(dest='command')

    vocab_p = sub.add_parser('vocab', help='Look up a vocab word')
    vocab_p.add_argument('word', help='Azerbaijani word or phrase to look up')
    vocab_p.add_argument('--topic', default=None,
                         help='Limit search to a specific topic file')

    grammar_p = sub.add_parser('grammar', help='Look up a grammar concept')
    grammar_p.add_argument('concept', help='Concept name to look up')

    args = parser.parse_args()

    if args.command == 'vocab':
        result = lookup_vocab(args.word, args.topic)
    elif args.command == 'grammar':
        result = lookup_grammar(args.concept)
    else:
        parser.print_help()
        sys.exit(2)

    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
