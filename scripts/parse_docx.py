#!/usr/bin/env python3
"""
Parse a DOCX file and emit paragraphs as JSONL with heading detection.

Usage:
    python parse_docx.py <file.docx> [--from N] [--count N]

Options:
    --from N   Start at paragraph index N (0-based, for resume)
    --count N  Emit at most N paragraphs

Each output line is a JSON object:
    { "para_index": int, "section": str, "text": str, "is_heading": bool }
"""

import sys
import os
import re
import json
import zipfile
import argparse

# Allow running from any directory; import sibling module
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)


# ---------------------------------------------------------------------------
# Core XML parsing (enhanced from extract_docx.py to preserve style info)
# ---------------------------------------------------------------------------

def _parse_paragraphs_from_xml(xml: str):
    """
    Parse word/document.xml and yield (style_val, text) for each paragraph.

    style_val is the w:pStyle w:val attribute (e.g. "Heading1", "Normal") or ""
    text is the concatenated w:t content, stripped.
    """
    para_chunks = xml.split('</w:p>')
    for chunk in para_chunks:
        # Extract paragraph style
        style_match = re.search(r'<w:pStyle\s+w:val="([^"]+)"', chunk)
        style_val = style_match.group(1) if style_match else ""

        # Extract text runs
        texts = re.findall(r'<w:t[^>]*>(.*?)</w:t>', chunk, re.DOTALL)
        text = ''.join(texts).strip()

        if text and not text.startswith('<w:'):
            yield style_val, text


def _is_heading_by_style(style_val: str) -> bool:
    """Return True if the DOCX style name indicates a heading."""
    if not style_val:
        return False
    lower = style_val.lower()
    return (
        lower.startswith('heading')
        or lower.startswith('nagłówek')   # Polish Word heading style
        or lower in ('title', 'subtitle', 'tytuł', 'podtytuł')
    )


def _is_heading_by_text(text: str) -> bool:
    """Heuristic heading detection from text content alone."""
    stripped = text.strip()
    if not stripped:
        return False
    # Short ALL-CAPS line (≤ 70 chars, no sentence-ending punctuation mid-line)
    if len(stripped) <= 70 and stripped == stripped.upper() and re.search(r'[A-ZÀ-Ö0-9]', stripped):
        # Exclude lines that are clearly just numbers or punctuation
        if re.search(r'[A-ZÀ-ÖØ-Ý]', stripped):
            return True
    # Lines ending with a colon and shorter than 80 chars are often headers
    if stripped.endswith(':') and len(stripped) <= 80 and '\n' not in stripped:
        return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def iter_paragraphs(docx_path: str):
    """
    Yield paragraph dicts from a DOCX file.

    Each dict has:
        para_index : int  – 0-based position in the document
        section    : str  – heading text of the current section (may be "")
        text       : str  – paragraph text
        is_heading : bool – whether this paragraph is a heading
    """
    with zipfile.ZipFile(docx_path) as z:
        with z.open('word/document.xml') as f:
            xml = f.read().decode('utf-8', errors='replace')

    current_section = ""
    para_index = 0

    for style_val, text in _parse_paragraphs_from_xml(xml):
        is_heading = _is_heading_by_style(style_val) or _is_heading_by_text(text)

        if is_heading:
            current_section = text

        yield {
            "para_index": para_index,
            "section": current_section,
            "text": text,
            "is_heading": is_heading,
        }
        para_index += 1


def count_paragraphs(docx_path: str) -> int:
    """Return the total number of non-empty paragraphs in a DOCX file."""
    return sum(1 for _ in iter_paragraphs(docx_path))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Parse DOCX to JSONL paragraphs with heading detection."
    )
    parser.add_argument("file", help="Path to the .docx file")
    parser.add_argument("--from", dest="start", type=int, default=0,
                        help="Start at paragraph index N (default: 0)")
    parser.add_argument("--count", type=int, default=None,
                        help="Emit at most N paragraphs")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    emitted = 0
    for para in iter_paragraphs(args.file):
        if para["para_index"] < args.start:
            continue
        if args.count is not None and emitted >= args.count:
            break
        print(json.dumps(para, ensure_ascii=False))
        emitted += 1


if __name__ == '__main__':
    main()
