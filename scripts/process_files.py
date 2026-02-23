#!/usr/bin/env python3
"""
Orchestrator for the knowledge-extraction pipeline.

Usage:
    python process_files.py [--chunk-size N]

What it does:
1. Scans source_data/sources/*.docx for input files.
2. Loads knowledge/state.json (creates if missing). Any newly discovered
   files are registered and state.json is saved immediately.
3. For each file not yet completed, takes the next batch of paragraphs
   (default: 500) via parse_docx and writes a chunk to
   source_data/chunks/chunk_{basename}_{N:04d}.txt.
4. Prints a summary and instructions.

NOTE: state.json is updated here only when registering new files or marking
a file completed. The extraction agent sets processed_up_to after each chunk.
"""

import sys
import os
import json
import argparse

# ---------------------------------------------------------------------------
# Path setup — resolve repo root regardless of CWD
# ---------------------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, '..'))

SOURCE_DATA_DIR = os.path.join(_REPO_ROOT, 'source_data')
SOURCES_DIR     = os.path.join(SOURCE_DATA_DIR, 'sources')
KNOWLEDGE_DIR   = os.path.join(_REPO_ROOT, 'knowledge')
CHUNKS_DIR      = os.path.join(SOURCE_DATA_DIR, 'chunks')
STATE_PATH      = os.path.join(KNOWLEDGE_DIR, 'state.json')

# Add scripts dir so parse_docx can be imported
sys.path.insert(0, _SCRIPT_DIR)
import parse_docx  # noqa: E402


DEFAULT_CHUNK_SIZE = 500


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Load state.json, tolerating missing or empty files."""
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding='utf-8') as f:
            data = json.load(f)
        # Ensure required keys exist even if file was hand-edited or empty
        data.setdefault("detected_language", None)
        data.setdefault("files", {})
        return data
    return {
        "detected_language": None,
        "files": {}
    }


def save_state(state: dict):
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {STATE_PATH}")



# ---------------------------------------------------------------------------
# Chunk prompt generation
# ---------------------------------------------------------------------------

def _jsonl_chunk(docx_path: str, start: int, count: int) -> list:
    """Return a list of paragraph dicts starting at para_index `start`."""
    paras = []
    for para in parse_docx.iter_paragraphs(docx_path):
        if para["para_index"] < start:
            continue
        paras.append(para)
        if len(paras) >= count:
            break
    return paras



def write_chunk_prompt(
    basename: str,
    docx_path: str,
    start: int,
    chunk_size: int,
) -> tuple[str, int, int]:
    """
    Write a chunk data file and return (chunk_path, first_para, last_para).
    """
    os.makedirs(CHUNKS_DIR, exist_ok=True)

    paras = _jsonl_chunk(docx_path, start, chunk_size)
    if not paras:
        return "", start, start

    first_idx = paras[0]["para_index"]
    last_idx  = paras[-1]["para_index"]

    chunk_label = f"{basename}_{first_idx:04d}"
    chunk_path = os.path.join(CHUNKS_DIR, f"chunk_{chunk_label}.txt")

    with open(chunk_path, 'w', encoding='utf-8') as f:
        for para in paras:
            f.write(json.dumps(para, ensure_ascii=False) + "\n")

    return chunk_path, first_idx, last_idx


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate extraction chunk prompts.")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
                        help=f"Paragraphs per chunk (default: {DEFAULT_CHUNK_SIZE})")
    args = parser.parse_args()

    # Ensure output dirs exist
    os.makedirs(CHUNKS_DIR, exist_ok=True)

    # Load knowledge
    state = load_state()

    # Discover DOCX files
    os.makedirs(SOURCES_DIR, exist_ok=True)
    docx_files = sorted(
        f for f in os.listdir(SOURCES_DIR)
        if f.lower().endswith('.docx')
    )

    if not docx_files:
        print("No .docx files found in source_data/sources/.")
        sys.exit(0)

    # Register any new files in state and save immediately
    new_files = [f for f in docx_files if f not in state["files"]]
    if new_files:
        for fname in new_files:
            state["files"][fname] = {
                "total_paras": None,
                "processed_up_to": 0,
            }
            print(f"  Registered new file: {fname}")
        save_state(state)

    generated = []
    skipped   = []

    for fname in docx_files:
        fstate = state["files"][fname]
        docx_path = os.path.join(SOURCES_DIR, fname)

        # Always recount — the file may have grown since last run
        total = parse_docx.count_paragraphs(docx_path)
        fstate["total_paras"] = total

        processed = fstate.get("processed_up_to", 0)

        if processed >= total:
            skipped.append(f"  DONE   {fname}  ({total} paras)")
            continue

        prompt_path, first_idx, last_idx = write_chunk_prompt(
            basename   = fname,
            docx_path  = docx_path,
            start      = processed,
            chunk_size = args.chunk_size,
        )

        if not prompt_path:
            skipped.append(f"  DONE   {fname}  ({total} paras)")
            continue

        generated.append((fname, prompt_path, first_idx, last_idx))

    # Persist updated total_paras counts
    save_state(state)

    # Print summary
    print()
    print("=" * 60)
    print("  process_files.py — extraction pipeline summary")
    print("=" * 60)

    if skipped:
        print("\nCompleted files:")
        for s in skipped:
            print(s)

    if generated:
        print(f"\nGenerated {len(generated)} chunk prompt(s):\n")
        for fname, path, first, last in generated:
            rel = os.path.relpath(path, _REPO_ROOT)
            print(f"  {rel}")
            print(f"    File: {fname}  |  Paragraphs: {first}–{last}")
        print()
        print("Next steps:")
        print("  1. Open each chunk file above.")
        print("  2. Follow the instructions in source_data/extraction_agent.md")
        print("     to extract vocab and grammar, then write the output files.")
        print("  3. Update knowledge/state.json (processed_up_to, detected_language).")
        print("  4. Re-run this script to get the next chunk.")
    else:
        print("\nAll files are fully processed. Nothing to do.")
        print("Run `python source_data/scripts/build_anki.py` to export Anki CSV.")

    print()


if __name__ == '__main__':
    main()
