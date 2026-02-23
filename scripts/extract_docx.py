#!/usr/bin/env python3
"""
Extract text from Azerbaijani course DOCX files.
Usage: python3 extract_docx.py <file.docx> [start_char] [end_char]
"""

import zipfile
import re
import sys
import os


def extract_docx_clean(path):
    """Extract all text from a DOCX file, one paragraph per line."""
    with zipfile.ZipFile(path) as z:
        with z.open('word/document.xml') as f:
            xml = f.read().decode('utf-8', errors='replace')

    paragraphs = re.split(r'</w:p>', xml)
    result = []
    for para in paragraphs:
        texts = re.findall(r'<w:t[^>]*>(.*?)</w:t>', para, re.DOTALL)
        line = ''.join(texts).strip()
        if line and not line.startswith('<w:'):
            result.append(line)
    return result


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    args = sys.argv[1:]
    path = args[0]
    if not os.path.exists(path):
        print(f"Error: file not found: {path}")
        sys.exit(1)

    lines = extract_docx_clean(path)
    start = int(args[1]) if len(args) > 1 else 0
    end = int(args[2]) if len(args) > 2 else None
    text = '\n'.join(lines)
    print(text[start:end])


if __name__ == '__main__':
    main()
