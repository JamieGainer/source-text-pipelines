#!/usr/bin/env python3
"""Create Hebrew Bible vocabulary TSVs from MACULA Hebrew word-level data."""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from urllib.request import Request, urlopen


DEFAULT_INPUT = Path("data/macula-hebrew/WLC/tsv/macula-hebrew.tsv")
DEFAULT_OUTPUT = Path("outputs/genesis_5_vocab.tsv")
DEFAULT_DOWNLOAD_URL = (
    "https://media.githubusercontent.com/media/"
    "Clear-Bible/macula-hebrew/main/WLC/tsv/macula-hebrew.tsv"
)
REQUIRED_COLUMNS = {"ref", "text", "gloss", "lemma", "pos", "morph"}


@dataclass
class VocabEntry:
    lemma: str
    hebrew_forms: list[str] = field(default_factory=list)
    glosses: list[str] = field(default_factory=list)
    parts_of_speech: list[str] = field(default_factory=list)
    morphologies: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    occurrences: int = 0


def strip_cantillation(text: str) -> str:
    """Remove Hebrew cantillation marks while retaining vowel points."""
    if not text:
        return ""

    stripped = "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if not 0x0591 <= ord(char) <= 0x05AF
    )
    return unicodedata.normalize("NFC", stripped)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def append_unique(values: list[str], value: str) -> None:
    value = normalize_space(value)
    if value and value not in values:
        values.append(value)


def reference_from_macula_ref(
    ref: str,
    book_code: str,
    chapter: int,
    book_label: str,
) -> str | None:
    """Extract a verse reference from common MACULA reference formats."""
    if not ref:
        return None

    escaped_book_code = re.escape(book_code)
    escaped_book_label = re.escape(book_label)
    patterns = [
        rf"^{escaped_book_code}\s+{chapter}:(\d+)",
        rf"^{escaped_book_code}[.\s]+{chapter}[.:](\d+)",
        rf"^{escaped_book_label}[.\s]+{chapter}[.:](\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, ref, flags=re.IGNORECASE)
        if match:
            return f"{book_label} {chapter}:{int(match.group(1))}"

    return None


def download_file(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; source-text-pipelines/0.1; "
                "+https://github.com/JamieGainer/source-text-pipelines)"
            )
        },
    )
    with urlopen(request, timeout=120) as response, output_path.open("wb") as output_file:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output_file.write(chunk)


def validate_columns(fieldnames: list[str] | None) -> None:
    if fieldnames is None:
        raise ValueError("Input TSV has no header row.")

    missing = REQUIRED_COLUMNS - set(fieldnames)
    if missing:
        raise ValueError(
            f"Missing expected MACULA columns: {sorted(missing)}\n"
            f"Available columns: {fieldnames}"
        )


def create_vocab(
    input_path: Path,
    book_code: str,
    chapter: int,
    book_label: str,
) -> OrderedDict[str, VocabEntry]:
    vocab: OrderedDict[str, VocabEntry] = OrderedDict()
    sample_refs: list[str] = []
    matched_rows = 0

    with input_path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file, delimiter="\t")
        validate_columns(reader.fieldnames)
        has_stronglemma = "stronglemma" in (reader.fieldnames or [])

        for row in reader:
            ref = row.get("ref", "")
            if len(sample_refs) < 30 and ref and ref not in sample_refs:
                sample_refs.append(ref)

            reference = reference_from_macula_ref(ref, book_code, chapter, book_label)
            if reference is None:
                continue

            matched_rows += 1
            pointed_form = normalize_space(strip_cantillation(row.get("text", "")))
            gloss = normalize_space(row.get("gloss", ""))
            if not pointed_form or not gloss:
                continue

            lemma = normalize_space(row.get("lemma", ""))
            if not lemma and has_stronglemma:
                lemma = normalize_space(row.get("stronglemma", ""))
            if not lemma:
                lemma = pointed_form

            if lemma not in vocab:
                vocab[lemma] = VocabEntry(lemma=lemma)

            entry = vocab[lemma]
            append_unique(entry.hebrew_forms, pointed_form)
            append_unique(entry.glosses, gloss)
            append_unique(entry.parts_of_speech, row.get("pos", ""))
            append_unique(entry.morphologies, row.get("morph", ""))
            append_unique(entry.references, reference)
            entry.occurrences += 1

    if matched_rows == 0:
        raise ValueError(
            f"No {book_label} {chapter} rows matched. Sample reference values:\n"
            + "\n".join(sample_refs)
        )

    return vocab


def sorted_entries(vocab: OrderedDict[str, VocabEntry]) -> list[VocabEntry]:
    return sorted(vocab.values(), key=lambda entry: (-entry.occurrences, entry.lemma))


def write_vocab_tsv(entries: list[VocabEntry], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file, delimiter="\t")
        writer.writerow(
            [
                "Hebrew",
                "Gloss",
                "Lemma",
                "Part_of_speech",
                "Reference",
                "Occurrences",
                "Morphology",
            ]
        )
        for entry in entries:
            writer.writerow(
                [
                    "; ".join(entry.hebrew_forms),
                    "; ".join(entry.glosses),
                    entry.lemma,
                    "; ".join(entry.parts_of_speech),
                    "; ".join(entry.references),
                    entry.occurrences,
                    "; ".join(entry.morphologies),
                ]
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Hebrew Bible vocabulary TSVs from MACULA Hebrew word-level data."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"MACULA Hebrew TSV path. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Vocabulary TSV output path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--book",
        default="GEN",
        help="MACULA book code to extract. Default: GEN.",
    )
    parser.add_argument(
        "--book-label",
        default="Genesis",
        help="Readable book name for output references. Default: Genesis.",
    )
    parser.add_argument(
        "--chapter",
        type=int,
        default=5,
        help="Chapter number to extract. Default: 5.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the MACULA Hebrew TSV to --input if it does not already exist.",
    )
    parser.add_argument(
        "--download-url",
        default=DEFAULT_DOWNLOAD_URL,
        help=f"MACULA Hebrew TSV download URL. Default: {DEFAULT_DOWNLOAD_URL}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.download and not args.input.exists():
        print(f"Downloading {args.download_url} to {args.input}")
        download_file(args.download_url, args.input)

    if not args.input.exists():
        raise FileNotFoundError(
            f"Input file not found: {args.input}\n"
            "Pass --download to fetch the MACULA Hebrew TSV, or provide --input."
        )

    vocab = create_vocab(
        input_path=args.input,
        book_code=args.book,
        chapter=args.chapter,
        book_label=args.book_label,
    )
    entries = sorted_entries(vocab)
    write_vocab_tsv(entries, args.output)
    print(f"Wrote {len(entries)} vocabulary entries to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
