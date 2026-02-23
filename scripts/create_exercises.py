#!/usr/bin/env python3
"""
create_exercises.py — Exercise Description Generator
=====================================================

Interactive CLI that lets you define what exercises to generate for the
Azerbaijani language learning app.  The result is saved as:

    exercise_data/outputs/exercises_description.ex

That file is later read by an AI agent (see exercise_data/exercise_generation_agent.md)
which generates the actual exercise content.

Usage:
    python create_exercises.py

Dependencies:
    pip install questionary
"""

import json
import os
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Dependency check — give a helpful message if questionary is missing
# ---------------------------------------------------------------------------

try:
    import questionary
    from questionary import Choice, Separator, Style
except ImportError:
    print()
    print("  Error: the 'questionary' library is not installed.")
    print("  Fix it by running:")
    print()
    print("    pip install questionary")
    print()
    sys.exit(1)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Resolve paths relative to this script so it works from any working directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

VOCAB_INDEX_PATH = os.path.join(_REPO_ROOT, "knowledge", "vocab", "_index.json")
GRAMMAR_PATH     = os.path.join(_REPO_ROOT, "knowledge", "grammar.json")
OUTPUT_PATH      = os.path.join(_REPO_ROOT, "exercise_data", "outputs", "exercises_description.ex")


# ---------------------------------------------------------------------------
# Exercise type registry
#
# Each entry: (file_id, short_label, one-line description)
#   file_id     — the identifier written into the .ex file
#   short_label — shown during the selection menu
#   description — extra context shown next to the label
# ---------------------------------------------------------------------------

EXERCISE_TYPES: list[tuple[str, str, str]] = [
    (
        "translation_az_en",
        "Translation  AZ → EN",
        "Translate an Azerbaijani word or sentence into English",
    ),
    (
        "translation_en_az",
        "Translation  EN → AZ",
        "Translate an English word or sentence into Azerbaijani",
    ),
    (
        "correct_suffix",
        "Correct suffix",
        "A sentence with one word missing its suffix — add the correct suffix",
    ),
    (
        "abcd_gap_fill",
        "ABCD: fill in the gap",
        "Multiple-choice: pick the right word to complete a sentence",
    ),
]


# ---------------------------------------------------------------------------
# Terminal colour / style theme
# ---------------------------------------------------------------------------

STYLE = Style([
    ("qmark",       "fg:#5f9ea0 bold"),   # the "?" prompt marker
    ("question",    "bold"),              # question text
    ("answer",      "fg:#00c896 bold"),   # confirmed answer text
    ("pointer",     "fg:#5f9ea0 bold"),   # the ▶ arrow
    ("highlighted", "fg:#5f9ea0 bold"),   # item currently under the cursor
    ("selected",    "fg:#00c896"),        # checked checkbox item
    ("separator",   "fg:#666666"),        # section divider lines
    ("instruction", "fg:#888888 italic"), # small hint text under prompts
])


# ---------------------------------------------------------------------------
# Knowledge loading
# ---------------------------------------------------------------------------

def load_tag_choices() -> list:
    """
    Build the master tag list shown in the checkbox when picking exercise focus.

    Layout:
        ─── Vocabulary topics ──────────────────
        [vocab:any]  — all vocab topics
        vocab:  adjectives               (51 words)
        vocab:  animals                  (23 words)
        ...
        ─── Grammar concepts ───────────────────
        [grammar:any]  — all grammar concepts
        grammar: Vowel harmony — 2-form (a/ə)
        ...

    Returns a list of Choice and Separator objects ready for questionary.checkbox.
    Tags themselves are stored as plain strings in Choice.value so they write
    directly into the .ex file without any transformation.
    """
    choices = []

    # ── Vocabulary section ────────────────────────────────────────────────────
    choices.append(Separator("─── Vocabulary topics ──────────────────────────────────"))

    # "vocab:any" wildcard — draw from all vocabulary topics without restriction
    choices.append(
        Choice(
            title="[vocab:any]  — any vocabulary topic",
            value="vocab:any",
        )
    )

    try:
        with open(VOCAB_INDEX_PATH, encoding="utf-8") as f:
            vocab_index: dict[str, int] = json.load(f)

        # Sort alphabetically so the list is predictable
        for topic, count in sorted(vocab_index.items()):
            display = f"vocab:  {topic:<26}  ({count:>3} words)"
            choices.append(Choice(title=display, value=f"vocab:{topic}"))

    except FileNotFoundError:
        choices.append(
            Choice(
                title="  (vocab index missing — run the extraction pipeline first)",
                value=None,
                disabled="missing",
            )
        )

    # ── Grammar section ───────────────────────────────────────────────────────
    choices.append(Separator("─── Grammar concepts ───────────────────────────────────"))

    # "grammar:any" wildcard — draw from all grammar concepts without restriction
    choices.append(
        Choice(
            title="[grammar:any]  — any grammar concept",
            value="grammar:any",
        )
    )

    try:
        with open(GRAMMAR_PATH, encoding="utf-8") as f:
            grammar_entries: list[dict] = json.load(f)

        for entry in grammar_entries:
            concept = entry["concept"]
            # Truncate very long names for display; the full name goes into value
            display_name = concept if len(concept) <= 55 else concept[:52] + "…"
            choices.append(
                Choice(title=f"grammar: {display_name}", value=f"grammar:{concept}")
            )

    except FileNotFoundError:
        choices.append(
            Choice(
                title="  (grammar file missing — run the extraction pipeline first)",
                value=None,
                disabled="missing",
            )
        )

    return choices


# ---------------------------------------------------------------------------
# Individual prompt steps
# ---------------------------------------------------------------------------

def prompt_exercise_type() -> tuple[str, str] | None:
    """
    Ask the user to pick one exercise type from the registry.

    Shows type label + description side by side so the choice is clear.
    Returns (type_id, short_label) on success, or None if the user cancels.
    """
    choices = []
    for type_id, label, description in EXERCISE_TYPES:
        choices.append(
            Choice(
                title=f"{label:<30}  {description}",
                value=type_id,
            )
        )

    # Give the user a way to go back to the main menu
    choices.append(Separator())
    choices.append(Choice(title="← Back to main menu", value=None))

    result = questionary.select(
        "Select exercise type:",
        choices=choices,
        style=STYLE,
        use_indicator=True,
    ).ask()

    if result is None:
        return None

    # Retrieve the short label matching this id (for the preview box)
    short_label = next(lbl for tid, lbl, _ in EXERCISE_TYPES if tid == result)
    return result, short_label


def prompt_example_count() -> int | None:
    """
    Ask how many examples (items) this exercise should contain.

    Validates that the answer is a positive integer.
    Returns the count as int, or None if the user cancels.
    """

    def _validate(raw: str) -> bool | str:
        stripped = raw.strip()
        if stripped.isdigit() and int(stripped) >= 1:
            return True
        return "Please enter a positive whole number — e.g. 5 or 10"

    raw = questionary.text(
        "How many example items should this exercise contain?",
        validate=_validate,
        style=STYLE,
    ).ask()

    return int(raw.strip()) if raw is not None else None


def prompt_tags(tag_choices: list) -> list[str] | None:
    """
    Multi-select checkbox where the user picks any combination of topic/grammar tags.

    Tags control what knowledge the generation agent draws from:
      - Selecting "vocab:any"      → agent picks freely from all vocabulary
      - Selecting "grammar:any"    → agent picks freely from all grammar concepts
      - Selecting specific topics  → agent is restricted to those topics/concepts
    Multiple tags are treated as OR: content matching any selected tag may be used.

    Separator rows (value=None) are silently filtered out of the result.
    If the user confirms without selecting anything, defaults to both any-wildcards.

    Returns the list of tag strings, or None if the user cancels (Ctrl-C).
    """
    selected = questionary.checkbox(
        "Select focus tags — what should this exercise draw from?",
        choices=tag_choices,
        style=STYLE,
        instruction="↑↓ to move   space to toggle   enter to confirm",
    ).ask()

    if selected is None:          # user hit Ctrl-C / escape
        return None

    # Drop any None values that come from separator rows being checked
    selected = [s for s in selected if s is not None]

    # Nothing selected → default to both wildcards (avoids an invalid empty tag list)
    return selected if selected else ["vocab:any", "grammar:any"]


# ---------------------------------------------------------------------------
# Full exercise creation dialog
# ---------------------------------------------------------------------------

def create_one_exercise(tag_choices: list) -> dict | None:
    """
    Walk the user through all three prompts for a single exercise:
        1. Exercise type
        2. Number of example items
        3. Focus tags

    Shows a confirmation preview before accepting.
    Returns a dict {type, type_label, count, tags} or None if the user aborts.
    """
    print()   # visual breathing room

    # Step 1 — type
    type_result = prompt_exercise_type()
    if type_result is None:
        return None
    type_id, type_label = type_result

    # Step 2 — count
    count = prompt_example_count()
    if count is None:
        return None

    # Step 3 — tags
    tags = prompt_tags(tag_choices)
    if tags is None:
        return None

    # Preview box so the user can review before committing
    print()
    print("  ┌─ Exercise preview ─────────────────────────────────────┐")
    print(f"  │  Type   : {type_label}")
    print(f"  │  Count  : {count} example(s)")
    print(f"  │  Tags   : {', '.join(tags)}")
    print("  └────────────────────────────────────────────────────────┘")
    print()

    confirmed = questionary.confirm(
        "Add this exercise to the list?",
        default=True,
        style=STYLE,
    ).ask()

    if not confirmed:
        return None

    return {
        "type":       type_id,
        "type_label": type_label,
        "count":      count,
        "tags":       tags,
    }


# ---------------------------------------------------------------------------
# Review / list collected exercises
# ---------------------------------------------------------------------------

def print_exercise_list(exercises: list[dict]) -> None:
    """
    Pretty-print the full list of exercises collected so far.
    Used by the "Review list" menu option.
    """
    if not exercises:
        print()
        print("  (No exercises added yet.)")
        print()
        return

    print()
    print(f"  Exercises collected so far — {len(exercises)} total:")
    print()

    for i, ex in enumerate(exercises, 1):
        tags_str = ", ".join(ex["tags"])
        print(f"  [{i:>2}]  {ex['type_label']}")
        print(f"         Count : {ex['count']} example(s)")
        print(f"         Tags  : {tags_str}")
        print()


# ---------------------------------------------------------------------------
# .ex file serialisation
# ---------------------------------------------------------------------------

def build_ex_content(exercises: list[dict]) -> str:
    """
    Serialise the exercise list into the plain-text .ex format.

    The format is intentionally simple so it is easy for a human or an AI
    agent to read without a parser library.

    Format rules:
      - Lines starting with '#' are comments (ignored by parsers).
      - Each exercise block begins with [exercise:N] (N = 1-based index).
      - 'type'  — one of the EXERCISE_TYPES file_ids.
      - 'count' — positive integer: number of items to generate.
      - 'tags'  — YAML-style list; each item on its own "  - <value>" line.

    Tag value syntax:
      any                — draw from all known material
      vocab:<topic>      — draw from the named vocabulary topic
      grammar:<concept>  — focus on the named grammatical concept
    """
    lines: list[str] = []

    # ── File header ──────────────────────────────────────────────────────────
    lines += [
        "# exercises_description.ex",
        "# Azerbaijani Language Learning — Exercise Descriptions",
        f"# Generated : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"# Exercises  : {len(exercises)}",
        "#",
        "# HOW TO READ THIS FILE",
        "# ──────────────────────────────────────────────────────────────────",
        "# Each [exercise:N] block describes one exercise set to be generated.",
        "#",
        "# Fields:",
        "#   type  — exercise format (see list below)",
        "#   count — how many items to generate for this exercise",
        "#   tags  — what knowledge the exercise should draw from",
        "#",
        "# Exercise types:",
        "#   translation_az_en  — translate Azerbaijani → English",
        "#   translation_en_az  — translate English → Azerbaijani",
        "#   correct_suffix     — supply the grammatically correct suffix",
        "#   abcd_gap_fill      — multiple-choice: pick the word that fills the gap",
        "#",
        "# Tag syntax:",
        "#   vocab:any          — draw from all vocabulary topics",
        "#   grammar:any        — draw from all grammar concepts",
        "#   vocab:<topic>      — draw from that specific vocabulary topic",
        "#   grammar:<concept>  — focus on that specific grammatical structure",
        "#   Multiple tags = OR: any material matching at least one tag may be used.",
        "",
    ]

    # ── Exercise blocks ──────────────────────────────────────────────────────
    for i, ex in enumerate(exercises, 1):
        lines.append(f"[exercise:{i}]")
        lines.append(f"type: {ex['type']}")
        lines.append(f"count: {ex['count']}")
        lines.append("tags:")
        for tag in ex["tags"]:
            lines.append(f"  - {tag}")
        lines.append("")   # blank line between blocks

    return "\n".join(lines)


def save_to_file(exercises: list[dict]) -> bool:
    """
    Write the .ex file to disk.

    If the file already exists, asks the user whether to overwrite.
    Returns True on success, False if the user cancelled.
    """
    if not exercises:
        print()
        print("  Nothing to save — add at least one exercise first.")
        print()
        return False

    # Warn before overwriting an existing file
    if os.path.exists(OUTPUT_PATH):
        print()
        overwrite = questionary.confirm(
            f"File already exists at:\n  {OUTPUT_PATH}\n  Overwrite it?",
            default=False,
            style=STYLE,
        ).ask()
        if not overwrite:
            return False

    # Create the output directory if it does not exist yet
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    content = build_ex_content(exercises)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print()
    print(f"  Saved {len(exercises)} exercise(s) to:")
    print(f"  {OUTPUT_PATH}")
    print()
    return True


# ---------------------------------------------------------------------------
# Main interactive loop
# ---------------------------------------------------------------------------

def main() -> None:
    # Welcome banner
    print()
    print("  ╔══════════════════════════════════════════════════════════╗")
    print("  ║   Azerbaijani Learning — Exercise Description Builder   ║")
    print("  ╠══════════════════════════════════════════════════════════╣")
    print("  ║  Define which exercises to generate.  The result is     ║")
    print("  ║  saved as exercises_description.ex and later processed  ║")
    print("  ║  by an AI agent to produce the actual exercise content. ║")
    print("  ╚══════════════════════════════════════════════════════════╝")
    print()

    # Load the tag list once; reuse for every exercise dialog
    print("  Loading knowledge base…")
    tag_choices = load_tag_choices()

    vocab_count   = sum(1 for c in tag_choices
                        if isinstance(c, Choice) and c.value and c.value.startswith("vocab:"))
    grammar_count = sum(1 for c in tag_choices
                        if isinstance(c, Choice) and c.value and c.value.startswith("grammar:"))
    print(f"  Ready: {vocab_count} vocab topic(s), {grammar_count} grammar concept(s) available as tags.")
    print()

    exercises: list[dict] = []

    while True:
        # ── Main menu ────────────────────────────────────────────────────────
        menu_choices = [
            Choice(title="Add exercise", value="add"),
            Choice(title=f"Review list  ({len(exercises)} exercise(s) so far)", value="review"),
        ]

        # "Save" only appears once there is something to save
        if exercises:
            menu_choices.append(
                Choice(title=f"Save and exit  →  writes exercises_description.ex", value="save")
            )

        menu_choices.append(Separator())
        menu_choices.append(Choice(title="Exit without saving", value="exit"))

        action = questionary.select(
            "What would you like to do?",
            choices=menu_choices,
            style=STYLE,
        ).ask()

        # ── Dispatch ─────────────────────────────────────────────────────────

        if action is None or action == "exit":
            # Confirm before discarding unsaved work
            if exercises:
                confirm = questionary.confirm(
                    f"Discard {len(exercises)} exercise(s) and exit without saving?",
                    default=False,
                    style=STYLE,
                ).ask()
                if not confirm:
                    continue
            print()
            print("  Exiting without saving. Goodbye!")
            print()
            break

        elif action == "add":
            exercise = create_one_exercise(tag_choices)
            if exercise:
                exercises.append(exercise)
                print(f"  Exercise added.  ({len(exercises)} total)")

        elif action == "review":
            print_exercise_list(exercises)

        elif action == "save":
            success = save_to_file(exercises)
            if success:
                print("  Goodbye!")
                print()
                break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
