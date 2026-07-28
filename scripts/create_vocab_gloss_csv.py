#!/usr/bin/env python3
"""Create a word/gloss/metadata CSV from a plain text file."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_OUTPUT = Path("outputs/vocab_glosses.csv")
DEFAULT_WIKTIONARY_CACHE = Path("outputs/wiktionary_gloss_cache.json")
WORD_BOUNDARY_CHARS = {"'", "-", "\u2019"}
LANGUAGE_NAMES = {
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "grc": "Ancient Greek",
    "it": "Italian",
    "la": "Latin",
    "pt": "Portuguese",
}


def is_word_char(char: str) -> bool:
    category = unicodedata.category(char)
    return category[0] in {"L", "M"} or char in WORD_BOUNDARY_CHARS


def normalize_word(word: str, lowercase: bool) -> str:
    word = unicodedata.normalize("NFC", word.strip("'-\u2019"))
    if lowercase:
        word = word.casefold()
    return word


def extract_words(text: str, lowercase: bool = True) -> list[str]:
    words: list[str] = []
    current_chars: list[str] = []

    for char in text:
        if is_word_char(char):
            current_chars.append(char)
        elif current_chars:
            word = normalize_word("".join(current_chars), lowercase)
            if word:
                words.append(word)
            current_chars = []

    if current_chars:
        word = normalize_word("".join(current_chars), lowercase)
        if word:
            words.append(word)

    return words


def sniff_delimiter(path: Path) -> str:
    sample = path.read_text(encoding="utf-8-sig")[:4096]
    if "\t" in sample:
        return "\t"
    return ","


def load_glosses(path: Path | None, lowercase: bool) -> dict[str, str]:
    if path is None:
        return {}

    delimiter = sniff_delimiter(path)
    glosses: dict[str, str] = {}

    with path.open(newline="", encoding="utf-8-sig") as glossary_file:
        reader = csv.DictReader(glossary_file, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Glossary file has no header row: {path}")

        fieldnames = {field.casefold(): field for field in reader.fieldnames}
        if "word" not in fieldnames or "gloss" not in fieldnames:
            raise ValueError(f"Glossary file must have word and gloss columns: {path}")

        word_field = fieldnames["word"]
        gloss_field = fieldnames["gloss"]
        for row in reader:
            word = normalize_word(row[word_field], lowercase)
            gloss = row[gloss_field].strip()
            if word:
                glosses[word] = gloss

    return glosses


def load_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def fetch_wiktionary_wikitext(word: str) -> str | None:
    params = urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "titles": word,
        }
    )
    request = Request(
        f"https://en.wiktionary.org/w/api.php?{params}",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; source-text-pipelines/0.1; "
                "+https://github.com/JamieGainer/source-text-pipelines)"
            )
        },
    )
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None

    revisions = pages[0].get("revisions", [])
    if not revisions:
        return None

    slots = revisions[0].get("slots", {})
    main_slot = slots.get("main", {})
    return main_slot.get("content")


def extract_language_section(wikitext: str, language_name: str) -> str | None:
    heading = re.compile(rf"^==\s*{re.escape(language_name)}\s*==\s*$", re.MULTILINE)
    match = heading.search(wikitext)
    if not match:
        return None

    next_heading = re.search(r"^==[^=].*==\s*$", wikitext[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(wikitext)
    return wikitext[match.end() : end]


def clean_wiktionary_definition(definition: str) -> str:
    definition = re.sub(r"^#+\s*", "", definition).strip()
    definition = re.sub(r"<!--.*?-->", "", definition)
    definition = re.sub(r"<ref\b.*?</ref>", "", definition, flags=re.DOTALL)
    definition = re.sub(r"<[^>]+>", "", definition)

    def replace_template(match: re.Match[str]) -> str:
        parts = [part.strip() for part in match.group(1).split("|")]
        if not parts:
            return ""
        name = parts[0].casefold()
        if name in {"lb", "label", "qualifier", "q", "glossary", "attention"}:
            return ""
        if name == "place":
            gloss_parts = [part for part in parts[2:] if "=" not in part and not part.startswith("continent/")]
            translations = [part.split("=", 1)[1] for part in parts[2:] if part.startswith("t")]
            return "; ".join([*gloss_parts, *translations])
        if name in {"l", "m", "link", "term"} and len(parts) >= 3:
            return parts[2]
        if name == "gloss" and len(parts) >= 2:
            return parts[-1]
        if " of" in name and len(parts) >= 2:
            return f"{name} {parts[-1]}"
        return ""

    previous = None
    while previous != definition:
        previous = definition
        definition = re.sub(r"\{\{([^{}]+)\}\}", replace_template, definition)

    definition = re.sub(r"\[\[([^|\]]+)\|([^|\]]+)\]\]", r"\2", definition)
    definition = re.sub(r"\[\[([^|\]]+)\]\]", r"\1", definition)
    definition = definition.replace("'''", "").replace("''", "")
    definition = re.sub(r"\s+", " ", definition)
    definition = re.sub(r"\s+([,.;:])", r"\1", definition)
    return definition.strip()


def lookup_wiktionary_gloss(word: str, language: str, cache: dict[str, str]) -> str:
    language_name = LANGUAGE_NAMES.get(language.casefold())
    if not language_name:
        raise ValueError(f"Unsupported Wiktionary language code: {language}")

    cache_key = f"{language.casefold()}:{word}"
    if cache.get(cache_key):
        return cache[cache_key]

    title_candidates = [word]
    titlecase_word = word[:1].upper() + word[1:]
    if titlecase_word != word:
        title_candidates.append(titlecase_word)

    wikitext = None
    for title in title_candidates:
        wikitext = fetch_wiktionary_wikitext(title)
        if wikitext and extract_language_section(wikitext, language_name):
            break

    if not wikitext:
        cache[cache_key] = ""
        return ""

    section = extract_language_section(wikitext, language_name)
    if not section:
        cache[cache_key] = ""
        return ""

    gloss = ""
    for line in section.splitlines():
        if line.startswith("#") and not line.startswith(("##", "#*", "#:")):
            gloss = clean_wiktionary_definition(line)
            if gloss:
                break

    cache[cache_key] = gloss
    return gloss


def create_rows(
    input_path: Path,
    metadata: str,
    language: str,
    gloss_file: Path | None,
    gloss_source: str,
    wiktionary_cache_path: Path,
    lowercase: bool,
    include_count: bool,
    include_language: bool,
    min_count: int,
) -> tuple[list[dict[str, str | int]], int]:
    text = input_path.read_text(encoding="utf-8-sig")
    word_counts = Counter(extract_words(text, lowercase=lowercase))
    glosses = load_glosses(gloss_file, lowercase=lowercase)
    wiktionary_cache = load_cache(wiktionary_cache_path) if gloss_source == "wiktionary" else {}

    rows: list[dict[str, str | int]] = []
    missing_gloss_count = 0
    for word in sorted(word_counts):
        count = word_counts[word]
        if count < min_count:
            continue

        gloss = glosses.get(word, "")
        if not gloss and gloss_source == "wiktionary":
            gloss = lookup_wiktionary_gloss(word, language, wiktionary_cache)
        if not gloss:
            missing_gloss_count += 1

        row: dict[str, str | int] = {
            "word": word,
            "gloss": gloss,
            "metadata": metadata,
        }
        if include_count:
            row["count"] = count
        if include_language:
            row["language"] = language
        rows.append(row)

    if gloss_source == "wiktionary":
        save_cache(wiktionary_cache_path, wiktionary_cache)

    return rows, missing_gloss_count


def write_csv(
    rows: list[dict[str, str | int]],
    output_path: Path,
    include_count: bool,
    include_language: bool,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["word", "gloss", "metadata"]
    if include_count:
        fieldnames.append("count")
    if include_language:
        fieldnames.append("language")

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract unique vocabulary from a plain text file and write word/gloss/metadata CSV."
    )
    parser.add_argument("--input", type=Path, required=True, help="Plain text input file.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--metadata",
        required=True,
        help="Source description to repeat in the metadata column.",
    )
    parser.add_argument(
        "--language",
        default="",
        help="Optional language code, such as es, fr, de, la, or grc.",
    )
    parser.add_argument(
        "--gloss-file",
        type=Path,
        help="Optional CSV/TSV with word and gloss columns. Used as gloss overrides.",
    )
    parser.add_argument(
        "--gloss-source",
        choices=["none", "gloss-file", "wiktionary"],
        help=(
            "Gloss lookup source. Defaults to gloss-file when --gloss-file is supplied, "
            "otherwise none."
        ),
    )
    parser.add_argument(
        "--wiktionary-cache",
        type=Path,
        default=DEFAULT_WIKTIONARY_CACHE,
        help=f"Wiktionary lookup cache path. Default: {DEFAULT_WIKTIONARY_CACHE}",
    )
    parser.add_argument(
        "--preserve-case",
        action="store_true",
        help="Keep original word casing instead of casefolding words.",
    )
    parser.add_argument(
        "--include-count",
        action="store_true",
        help="Add a count column with the number of occurrences in the input file.",
    )
    parser.add_argument(
        "--include-language",
        action="store_true",
        help="Add a language column with the value passed to --language.",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="Only include words with at least this many occurrences. Default: 1.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.min_count < 1:
        raise ValueError("--min-count must be at least 1")
    gloss_source = args.gloss_source or ("gloss-file" if args.gloss_file else "none")
    if gloss_source == "wiktionary" and not args.language:
        raise ValueError("--language is required when --gloss-source wiktionary is used")

    rows, missing_gloss_count = create_rows(
        input_path=args.input,
        metadata=args.metadata,
        language=args.language,
        gloss_file=args.gloss_file,
        gloss_source=gloss_source,
        wiktionary_cache_path=args.wiktionary_cache,
        lowercase=not args.preserve_case,
        include_count=args.include_count,
        include_language=args.include_language,
        min_count=args.min_count,
    )
    write_csv(
        rows,
        args.output,
        include_count=args.include_count,
        include_language=args.include_language,
    )

    print(f"Wrote {len(rows)} rows to {args.output}")
    if gloss_source != "none":
        print(f"Rows without glosses: {missing_gloss_count}")
    else:
        print("No gloss file provided; gloss column is blank.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
