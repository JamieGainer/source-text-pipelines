#!/usr/bin/env python3
"""Create deterministic memorization chunks from plain text."""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OUTPUT = Path("outputs/memorization_chunks.tsv")
DEFAULT_MAXIMUM_WORDS_PER_ITEM = 15
SENTENCE_END_PATTERN = re.compile(r"(?<=[.!?])\s+")
SOFT_BREAK_PATTERN = re.compile(r"([,;:]|[—–]|\s+-\s+)")
WORD_PATTERN = re.compile(r"[^\W\d_]+(?:['’.-][^\W\d_]+)*", flags=re.UNICODE)


@dataclass
class MemorizationItem:
    item_number: str
    text: str


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return text.strip()


def count_words(text: str) -> int:
    return len(WORD_PATTERN.findall(text))


def split_on_sentences(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    pieces = SENTENCE_END_PATTERN.split(normalized)
    return [piece.strip() for piece in pieces if piece.strip()]


def split_on_lines(text: str) -> list[str]:
    return [normalize_text(line) for line in text.splitlines() if normalize_text(line)]


def choose_base_units(text: str, base_unit: str) -> list[str]:
    if base_unit == "line":
        return split_on_lines(text)

    sentence_units = split_on_sentences(text)
    has_sentence_punctuation = bool(re.search(r"[.!?]", text))
    if not has_sentence_punctuation or len(sentence_units) <= 1:
        line_units = split_on_lines(text)
        if len(line_units) > 1:
            return line_units
    return sentence_units


def split_with_delimiters(text: str) -> list[str]:
    parts = SOFT_BREAK_PATTERN.split(text)
    segments: list[str] = []
    current = ""

    for part in parts:
        if not part:
            continue
        if SOFT_BREAK_PATTERN.fullmatch(part):
            current += part
            segments.append(normalize_text(current))
            current = ""
        else:
            current += part

    if normalize_text(current):
        segments.append(normalize_text(current))

    return [segment for segment in segments if segment]


def hard_split(text: str, max_words: int) -> list[str]:
    tokens = re.findall(r"\S+", text)
    chunks: list[str] = []
    current_tokens: list[str] = []
    current_word_count = 0

    for token in tokens:
        token_word_count = count_words(token)
        if current_tokens and current_word_count + token_word_count > max_words:
            chunks.append(normalize_text(" ".join(current_tokens)))
            current_tokens = []
            current_word_count = 0

        current_tokens.append(token)
        current_word_count += token_word_count

    if current_tokens:
        chunks.append(normalize_text(" ".join(current_tokens)))

    return chunks


def split_long_unit(unit: str, max_words: int) -> list[str]:
    if count_words(unit) <= max_words:
        return [unit]

    soft_segments = split_with_delimiters(unit)
    if len(soft_segments) <= 1:
        return hard_split(unit, max_words)

    chunks: list[str] = []
    current = ""

    for segment in soft_segments:
        segment_chunks = hard_split(segment, max_words) if count_words(segment) > max_words else [segment]
        for segment_chunk in segment_chunks:
            candidate = normalize_text(f"{current} {segment_chunk}" if current else segment_chunk)
            if current and count_words(candidate) > max_words:
                chunks.append(current)
                current = segment_chunk
            else:
                current = candidate

    if current:
        chunks.append(current)

    merged_chunks = merge_tiny_chunks(chunks, max_words)

    final_chunks: list[str] = []
    for chunk in merged_chunks:
        if count_words(chunk) > max_words:
            final_chunks.extend(hard_split(chunk, max_words))
        else:
            final_chunks.append(chunk)
    return merge_tiny_chunks(final_chunks, max_words)


def merge_tiny_chunks(chunks: list[str], max_words: int) -> list[str]:
    merged: list[str] = []
    index = 0
    while index < len(chunks):
        chunk = chunks[index]
        if 0 < count_words(chunk) <= 2 and index + 1 < len(chunks):
            candidate = normalize_text(f"{chunk} {chunks[index + 1]}")
            if count_words(candidate) <= max_words:
                merged.append(candidate)
                index += 2
                continue
        merged.append(chunk)
        index += 1
    return merged


def letter_suffix(index: int) -> str:
    letters = ""
    while index >= 0:
        index, remainder = divmod(index, 26)
        letters = chr(ord("a") + remainder) + letters
        index -= 1
    return letters


def create_items(text: str, max_words: int, base_unit: str) -> list[MemorizationItem]:
    items: list[MemorizationItem] = []
    base_units = choose_base_units(text, base_unit)

    for base_index, base_unit in enumerate(base_units, start=1):
        chunks = split_long_unit(base_unit, max_words)
        if len(chunks) == 1:
            items.append(MemorizationItem(str(base_index), chunks[0]))
        else:
            for chunk_index, chunk in enumerate(chunks):
                items.append(
                    MemorizationItem(
                        f"{base_index}{letter_suffix(chunk_index)}",
                        chunk,
                    )
                )

    return items


def write_tsv(items: list[MemorizationItem], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file, delimiter="\t")
        writer.writerow(["Item Number", "Text"])
        for item in items:
            writer.writerow([item.item_number, item.text])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create deterministic memorization chunks from a plain text file."
    )
    parser.add_argument("--input", type=Path, required=True, help="Plain text input file.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"TSV output path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--max-words-per-item",
        type=int,
        default=DEFAULT_MAXIMUM_WORDS_PER_ITEM,
        help=f"Maximum words per memorization item. Default: {DEFAULT_MAXIMUM_WORDS_PER_ITEM}.",
    )
    parser.add_argument(
        "--base-unit",
        choices=["sentence", "line"],
        default="sentence",
        help="Initial split unit before length-based splitting. Default: sentence.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_words_per_item < 1:
        raise ValueError("--max-words-per-item must be at least 1")

    text = args.input.read_text(encoding="utf-8-sig")
    items = create_items(text, args.max_words_per_item, args.base_unit)
    write_tsv(items, args.output)
    print(f"Wrote {len(items)} memorization items to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
