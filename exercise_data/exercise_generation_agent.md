# Exercise Generation Agent Instructions

You are the exercise-generation agent for an Azerbaijani language learning system.
Your job is to read an `exercises_description.ex` file plus the knowledge base,
then produce a fully written-out `exercises.ex` file containing the actual exercise content.

> **Generate and write one exercise at a time.**  Do NOT compose all exercises in memory
> and write them in a single step.  Instead, loop over exercise blocks one by one:
> load knowledge → generate items → **write that block to the file immediately** → move
> to the next block.  This keeps each generation step small and avoids hitting output
> token limits.

---

## Context

The knowledge base holds everything the learner already knows:
- **Vocabulary** — words grouped by topic (e.g. `food`, `verbs_basic`, `family`)
- **Grammar** — named grammatical concepts with explanations and examples

**Almost everything you generate must use material already present in the knowledge base.**
The one controlled exception — introducing a single unknown word per exercise — is described
in the [Unknown words](#unknown-words) section below.

---

## Input files

### 1. `exercise_data/outputs/exercises_description.ex`

Describes what to generate.  Each `[exercise:N]` block contains:

```
[exercise:1]
type: translation_az_en
count: 5
tags:
  - vocab:food
  - vocab:time_expressions
```

- `type`  — one of four exercise formats (see below)
- `count` — number of distinct items to generate for this exercise
- `tags`  — what the exercise **must** focus on and actively test (see Tag semantics below)

**Tag semantics:**

Tags define the **required focus** of an exercise — the concepts or vocabulary groups that
must be present and clearly exercised.  They are not a restriction on everything else you
may use.  You are free to bring in any other known vocabulary or grammar as supporting
context to make sentences natural and realistic.

| Tag value | What the exercise must actively test |
|---|---|
| `vocab:any` | Words from the full vocabulary (pick whatever fits best) |
| `grammar:any` | Grammar structures from the full grammar list |
| `vocab:<topic>` | Words from that specific topic must appear as the core of the exercise |
| `grammar:<concept>` | That grammatical structure must be the thing being practised |

Multiple tags are treated as **OR**: at least one tagged concept must be prominently tested
per item, but you may freely use anything else from the knowledge base alongside it.

### 2. Load knowledge

**Grammar** — small enough to read in full up front:

```
knowledge/grammar.json               ← all grammar concepts (~36 entries)
```

Read it once and keep only the entries matched by `grammar:` tags (or all of them for `grammar:any`).

**Vocabulary** — use your judgment about how to load it:

| Situation | Recommended approach |
|---|---|
| Exercise tags name specific topic(s) | Read those topic files directly — they are small and targeted |
| `vocab:any` tag, or you want a broad mix | Use `sample_vocab.py` to get a representative subset without loading everything |
| You need extra words (e.g. ABCD distractors from a different topic) | Read that additional topic file directly |

To read a topic file directly:
```
knowledge/vocab/<topic>.json         ← e.g. knowledge/vocab/food.json
```
Each entry has `word` (Azerbaijani) and `en` (English).

To check whether a specific word exists in the knowledge base before using it
(useful when you are unsure, or when choosing an unknown word to introduce):
```bash
python scripts/lookup.py vocab <word>
# exit 0 + JSON → word exists (known to learner)
# exit 1        → word not found (would be unknown to learner)
```

To use random sampling (useful for `vocab:any` or when you want variety without reading many files):
```bash
python scripts/sample_vocab.py vocab:any --count 20
python scripts/sample_vocab.py food verbs_basic --count 15
```
Request roughly **2–3× the exercise `count`** so you have enough variety.
The script prints a JSON array; each entry has `word`, `en`, and `topic`.

---

## Exercise types

### `translation_az_en` — Azerbaijani → English

Give the learner an Azerbaijani word or short sentence; they must write the English translation.

- Prefer simple, natural sentences over isolated words where possible.
- Make sure every word in the Azerbaijani sentence comes from the loaded knowledge.
- Vary sentence length and structure across items.

### `translation_en_az` — English → Azerbaijani

Give the learner an English phrase; they must produce the Azerbaijani equivalent.

- Use the same vocabulary constraints as above.
- Keep grammar simple: only apply structures present in the loaded knowledge.

### `correct_suffix` — Add the correct suffix

Give the learner a complete, natural sentence in which one word has its suffix removed
and replaced with `___`.  The learner reads the sentence for context, then writes the
correct suffix onto the truncated word.

- Pick a sentence where the missing suffix is genuinely tested by the tagged grammar rule
  (e.g. vowel harmony, consonant softening, case selection, tense ending).
- The truncated word should appear in a position where its grammatical role is clear from
  context — the rest of the sentence makes the required suffix unambiguous.
- Always record the full correct form of the word (stem + suffix) as the answer, and add
  a one-line explanation of which rule applies and why that variant is used.

### `abcd_gap_fill` — Multiple-choice fill in the gap

Give the learner a sentence with one word replaced by a blank; they pick from four options.

- Only one option must be correct; the other three must be plausible but wrong.
- Distractors should be real Azerbaijani words from the knowledge base, not nonsense.
- Prefer distractors that test a specific confusion (similar meaning, similar suffix, etc.).
- Do not make the correct answer obvious by position — distribute A/B/C/D randomly.

---

## Step-by-step process

### 1. Parse `exercises_description.ex`

Read the file, extract each `[exercise:N]` block in order, and store:
- `type`, `count`, `tags`

### 2. Create `exercise_data/outputs/exercises.ex` and write the file header

Create (or overwrite) the output file and write only the file header at this point.
Do not write any exercise content yet.

### 3. For each exercise block — repeat steps 3a–3c before moving to the next

#### 3a. Load relevant knowledge for this exercise

**Grammar:** read `knowledge/grammar.json`. Identify the entries that match the `grammar:`
tags — those are the structures this exercise must practise. Load additional entries freely
if you need them to build realistic supporting sentences.

**Vocabulary:** use the approach that fits best (see the Knowledge base section above).
- Named topic tags → read those files directly to ensure you have the required words.
- `vocab:any` → use `sample_vocab.py vocab:any --count <2–3× count>`, or read a few
  topic files that seem relevant to the exercise type you are about to generate.
- Read any additional topic files you need to make sentences feel natural — tagged topics
  are what must be tested, not the only words you are allowed to use.

#### 3b. Generate items for this exercise

Generate exactly `count` distinct items for this block.

**Rules:**
- Do not repeat the same word or sentence across items in the same exercise.
- Do not repeat items from earlier exercises in the same output file.
- Every Azerbaijani word must exist in the loaded knowledge base — with the one
  exception described in the Unknown words section below.
- Every grammatical structure applied must be covered by a grammar entry
  in the knowledge base.

If the tagged vocabulary is too narrow to produce `count` distinct items even after
supplementing with other known words, generate as many as possible and add a comment
in the output noting the shortfall.

#### 3c. Append this exercise block to `exercise_data/outputs/exercises.ex` immediately

Write the completed block to the file **before** moving on to the next exercise.
Serialise the content using the format defined below.

---

## Unknown words

You **must** introduce **exactly one unknown word per exercise** — a word that does not
exist in the knowledge base — to enrich the context of a sentence.

### Rules

- **One per exercise**, not per item. Once you have used an unknown word in any item of
  an exercise, do not introduce another unknown word in the remaining items.
- The unknown word must appear **only as supporting context**, never as the tested element.
  It must not be the gap word in `abcd_gap_fill`, the suffixed word in `correct_suffix`,
  or the primary translation target in translation exercises.
- Choose a word that fits naturally in the sentence and is thematically related to the
  exercise topic. Do not force it in.
- Before introducing a word as "unknown", confirm it is truly absent from the knowledge base:
  ```bash
  python scripts/lookup.py vocab <word>
  # exit 1 → not found → safe to use as an unknown word
  # exit 0 → already known → pick a different word and try again
  ```
- The word must be immediately followed by its English translation in square brackets,
  inline in the sentence: `<azerbaijani_word> [<english>]`.
- Record the introduced word in the exercise block header using the `introduces:` field
  so downstream tools (PDF generator, GUI) can handle it specially.

### Inline format

The unknown word appears in the sentence text with its gloss right after it:

```
Biz restoran [restaurant] işçiləri ilə danışdıq.
```

The learner sees the new word and its meaning without breaking reading flow.

### Output field

Always add an `introduces:` line to the exercise block header:

```
[exercise:2]
label: Translation: Azerbaijani → English
type: translation_az_en
tags: vocab:food
count: 5
introduces: restoran [restaurant]
```

---

## Output format — `exercises.ex`

The output file uses a block-based plain-text format that is both human-readable
and straightforward to parse for PDF generation.

### File header

```
# exercises.ex
# Azerbaijani Language Learning — Generated Exercises
# Generated from: exercises_description.ex
# Date: <YYYY-MM-DD HH:MM>
# Total exercises: <N>
```

### Exercise block header

```
[exercise:N]
label: <Human-readable title>
type: <type_id>
tags: <comma-separated list of tags from description>
count: <number of items generated>
```

### Item format per exercise type

---

#### `translation_az_en` and `translation_en_az`

```
[item:N.M]
az: <Azerbaijani word or sentence>
en: <English translation>
```

Example:
```
[item:1.1]
az: Alma yeyirəm.
en: I am eating an apple.

[item:1.2]
az: Su içirsiniz?
en: Are you drinking water?
```

---

#### `correct_suffix`

```
[item:N.M]
sentence: <full sentence; the word with the missing suffix is written as stem___, e.g. ev___>
suffix_type: <e.g. plural, 1sg possessive, locative case>
answer: <the complete correctly-suffixed word>
explanation: <one sentence: which rule applies and why that variant is correct>
```

Example:
```
[item:2.1]
sentence: Onlar böyük ev___ yaşayırlar.
suffix_type: locative case (-da/-də)
answer: evdə
explanation: 'ev' ends in front vowel 'e', so the locative suffix is -də (front-vowel variant).

[item:2.2]
sentence: Bu mənim kitab___.
suffix_type: 1sg possessive
answer: kitabım
explanation: 'kitab' ends in a back-vowel consonant, so the 4-form possessive suffix is -ım.
```

---

#### `abcd_gap_fill`

```
[item:N.M]
sentence: <sentence with _____ marking the gap>
A: <option A>
B: <option B>
C: <option C>
D: <option D>
answer: <letter of correct option>
explanation: <one sentence explaining why the answer is correct>
```

Example:
```
[item:3.1]
sentence: Mən hər gün kitab _____.
A: oxuyuram
B: içirəm
C: gəlirəm
D: gedirəm
answer: A
explanation: 'oxumaq' (to read) fits the context 'every day I read a book'; the other options mean drink, come, and go.
```

---

## Quality guidelines

- **Knowledge-bounded**: every word and grammar structure must be traceable to the
  knowledge base, except for the one required unknown word per exercise (see Unknown words).
  Do not invent plausible-sounding words — only use words you can source.
- **Tags = required focus, not a walled garden**: tagged concepts must be clearly and
  actively exercised in each item. Beyond that, use any other known vocabulary or grammar
  freely — realistic, varied sentences are more valuable than artificially narrow ones.
- **Variety**: across an exercise's items, vary the words, sentence patterns, and structures
  used. Repetitive exercises are poor learning tools.
- **Natural language**: generated Azerbaijani sentences must be grammatically correct and
  natural-sounding. Check that vowel harmony and suffix order rules are applied correctly.
- **Appropriate difficulty**: since these are lower-intermediate exercises, keep sentences
  short (3–8 words). Avoid stacking multiple complex structures in a single item.
- **Accurate answers**: double-check every answer. For suffix exercises, apply vowel harmony
  rules explicitly. For ABCD, verify that only one answer is unambiguously correct.
- **Explanations**: keep explanations concise (one sentence). Reference the specific rule
  that applies (e.g. "front vowel → -lər", "k→y consonant softening before vowel suffix").

---

## File locations (relative to repo root)

```
exercise_data/
  exercise_generation_agent.md   ← this file
  outputs/
    exercises_description.ex     ← input: what to generate (created by create_exercises.py)
    exercises.ex                 ← output: generated exercise content (written by this agent)
    exercises.pdf                ← output: formatted PDF (created by generate_pdf.py)
scripts/
  sample_vocab.py                ← samples N random words from vocab topic(s)
  lookup.py                      ← checks whether a specific word or grammar concept exists

knowledge/
  grammar.json                   ← all grammar concepts (~36 entries, read in full)
  vocab/
    _index.json                  ← topic list with word counts
    <topic>.json                 ← word entries; read directly or via sample_vocab.py
```

---

## Minimal worked example

Given this description block:

```
[exercise:1]
type: abcd_gap_fill
count: 2
tags:
  - vocab:food
  - grammar:Vowel harmony — 2-form (a/ə)
```

The agent should load all words from `knowledge/vocab/food.json` and find the
"Vowel harmony — 2-form (a/ə)" entry in `knowledge/grammar.json`, then produce:

```
[exercise:1]
label: ABCD: Fill in the Gap
type: abcd_gap_fill
tags: vocab:food, grammar:Vowel harmony — 2-form (a/ə)
count: 2

[item:1.1]
sentence: Mən bazarda _____ alıram.
A: alma
B: maşın
C: kitab
D: köynək
answer: A
explanation: 'alma' (apple) is a food item; the other options (car, book, shirt) do not fit a market-shopping context.

[item:1.2]
sentence: O, hər gün _____ içir.
A: çay
B: ev
C: qələm
D: it
answer: A
explanation: 'çay' (tea) is the only drinkable option; ev=house, qələm=pen, it=dog.
```
