# Knowledge Format

Describes the structure of all files under `knowledge/`.

## Immutability rule

**All knowledge files are append-only. Never edit or remove existing entries.**

- Load the existing file, add new entries at the end, write the whole file back.
- If an entry for the same `word` (vocab) or `concept` (grammar) already exists, skip it — do not update, overwrite, or deduplicate existing entries.
- `_index.json` counts must reflect the actual length of each topic file after appending.

---

## `knowledge/vocab/{topic}.json`

A JSON array of vocabulary entries. One file per topic (e.g. `greetings.json`, `food.json`).

**Topic naming**: lowercase, alphanumeric + underscores (e.g. `verbs_imperative`, `days_of_week`).

```json
[
  {
    "word":        "salam",
    "en":          "hello / greetings",
    "source_file": "a12.docx",
    "para_index":  14
  }
]
```

| Field         | Type    | Required | Notes                                         |
|---------------|---------|----------|-----------------------------------------------|
| `word`        | string  | yes      | Azerbaijani word or phrase                    |
| `en`          | string  | yes      | English translation(s)                        |
| `source_file` | string  | yes      | DOCX filename (e.g. `"a12.docx"`)             |
| `para_index`  | integer | yes      | Paragraph index where the word was found      |

---

## `knowledge/vocab/_index.json`

Lightweight map of topic → entry count. Must stay in sync with actual file lengths.

```json
{
  "greetings": 12,
  "food": 8
}
```

---

## `knowledge/grammar.json`

A JSON array of grammar concept objects.

```json
[
  {
    "concept":     "Plural suffix -lar / -lər",
    "description": "Nouns take -lar after back vowels (a, ı, o, u) and -lər after front vowels (e, i, ö, ü). Vowel harmony applies.",
    "example":     "kitab → kitablar, ev → evlər",
    "source_file": "a12.docx"
  }
]
```

| Field         | Type           | Required | Notes                          |
|---------------|----------------|----------|--------------------------------|
| `concept`     | string         | yes      | Short name for the concept     |
| `description` | string         | yes      | Clear English explanation      |
| `example`     | string or null | no       | Illustrative example           |
| `source_file` | string         | yes      | DOCX filename                  |

---

## `knowledge/state.json`

Pipeline processing state. Updated by the extraction agent after each chunk.

```json
{
  "detected_language": "Azerbaijani",
  "files": {
    "a12.docx": {
      "total_paras": 312,
      "processed_up_to": 40
    }
  }
}
```

| Field                           | Type           | Notes                                                          |
|---------------------------------|----------------|----------------------------------------------------------------|
| `detected_language`             | string or null | Set on first chunk                                             |
| `files.{name}.total_paras`      | int or null    | Recomputed on every run of `process_files.py`                  |
| `files.{name}.processed_up_to`  | int            | Next paragraph index to process; set by agent after each chunk |

A file is considered complete when `processed_up_to >= total_paras`. This is checked live on each run, so if the source file grows the pipeline will automatically continue.
