# Extraction Agent Instructions

You are the knowledge-extraction agent for an Azerbaijani language learning system.
Your job is to read chunks of raw course material (parsed from DOCX files) and extract structured vocabulary and grammar knowledge.

---

## Input

You receive a **chunk prompt file** from `source_data/chunks/`. It contains:
- Metadata (source file, paragraph range, current known topics)
- A block of JSONL lines — one JSON object per paragraph

Each paragraph object:
```json
{ "para_index": 42, "section": "Lekcja 3 – Rodzina", "text": "...", "is_heading": false }
```

- `section` — the heading of the current lesson/section (use as a topic hint)
- `is_heading` — if true, this line is a heading, not content
- `text` — the actual paragraph text (mix of Polish explanation + Azerbaijani words/phrases)

---

## Step-by-Step Process

### 1. Detect language (first chunk only)
If `state.json → detected_language` is null, confirm the target language is **Azerbaijani** and set it.

### 2. Read paragraphs
Go through each JSONL line. Skip headings (`is_heading: true`) as content — they are only useful for topic inference.

### 3. Extract vocabulary
For each Azerbaijani word or phrase you find, check whether it already exists before extracting:

```bash
python scripts/lookup.py vocab <word>
python scripts/lookup.py vocab <word> --topic <topic>
```

- Exit code `0` + printed JSON → already exists, skip it.
- Exit code `1` → not found, extract it.

Then:
- Determine the English translation from context (the Polish text explains the meaning)

**Topic assignment:**
- Use the `section` field as the primary hint — translate and normalise it to English snake_case
- If the section is empty or unhelpful, infer the topic from the content
- Reuse an existing topic name from `_index.json` when the content clearly belongs there

### 4. Extract grammar
Look for any explanations of grammatical rules, structures, or patterns — suffixes, conjugations, tense, mood, word order, harmony, negation, plurals, cases, etc.

Before extracting, **read `knowledge/grammar.json`** and check manually whether the concept already exists or is covered by an existing entry. Do NOT use `lookup.py` for grammar — concept names are long and varied, so exact-string matching is unreliable.

- If the concept is already described (even under a slightly different name), skip it.
- If an existing entry partially covers the new rule (e.g. affirmative form exists but negation is missing), do NOT add a separate entry — instead update the existing entry to include both.
- Prefer broad, unified concepts over narrow per-operation ones. For example, a single tense entry should cover both affirmative and negative forms rather than having two separate entries.

Write a clear English description. Include an Azerbaijani example where possible.

The course material is explained in Polish; use those explanations to understand the rule, but write the output in English.

### 5. Write output files

Follow schemas in `knowledge/format.md` exactly.

**Knowledge files are append-only — never edit or delete existing entries.**

For each file you write:
1. Read the existing file (if it exists).
2. Append only entries confirmed as new by `lookup.py` (steps 3 and 4 above).
3. Write the full file back.

**Vocab:**
```
knowledge/vocab/{topic}.json   — load → append new words → write back
knowledge/vocab/_index.json    — set count to actual length of each topic file
```

**Grammar:**
```
knowledge/grammar.json         — load → append new concepts → write back
```

### 6. Update state.json

After writing all output files, update `knowledge/state.json`:
- Set `files.{source_file}.processed_up_to` to `last_para_index + 1`
- Set `detected_language` if it was null
- Do not set a `completed` flag — `process_files.py` determines completion by comparing `processed_up_to` against the live paragraph count on each run

### 7. Re-run the orchestrator

```bash
python scripts/process_files.py
```

This generates the next chunk prompt. Repeat the process.

---

## Quality guidelines

- **Be conservative**: only extract what is clearly a vocabulary item or grammar rule. Do not guess.
- **Prefer quality over quantity**: a well-described grammar rule is better than ten vague ones.
- **Append-only**: never modify or remove existing entries. When in doubt whether a word exists, read the topic file and check — do not assume.
- **No examples in vocab**: do not include an `example` field in vocabulary entries — the schema does not have one.
- **Script**: keep Azerbaijani words in their original Latin script (modern Azerbaijani uses the Latin alphabet).
- **Language**: the course is in Polish. Use Polish explanations to understand meaning; write all output in English.

---

## File locations (relative to repo root)

```
knowledge/
  format.md              ← JSON schemas
  state.json
  grammar.json
  vocab/
    _index.json
    {topic}.json

source_data/
  extraction_agent.md    ← this file
  chunks/
    chunk_{file}_{N}.txt ← generated by process_files.py
```

---

## Example output

### Vocab entry (knowledge/vocab/greetings.json)
```json
[
  {
    "word": "salam",
    "en": "hello / hi",
    "source_file": "a12.docx",
    "para_index": 15
  },
  {
    "word": "xoş gəlmisiniz",
    "en": "welcome",
    "source_file": "a12.docx",
    "para_index": 16
  }
]
```

### Grammar entry (knowledge/grammar.json)
```json
[
  {
    "concept": "Vowel harmony — suffix selection",
    "description": "Azerbaijani suffixes have two or four variants depending on the last vowel of the stem. Back vowels (a, ı, o, u) → back suffix variant; front vowels (e, i, ö, ü) → front suffix variant.",
    "example": "kitab-lar (books), ev-lər (houses)",
    "source_file": "a12.docx"
  }
]
```
