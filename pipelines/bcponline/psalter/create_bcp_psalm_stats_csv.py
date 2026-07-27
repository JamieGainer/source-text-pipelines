#!/usr/bin/env python3
"""Create per-psalm verse and word counts from the BCP Psalter CSV."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path


DEFAULT_INPUT = Path("outputs/bcp_psalter.csv")
DEFAULT_OUTPUT = Path("outputs/bcp_psalm_stats.csv")
WORD_PATTERN = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)?")


def verse_root(verse_number: str) -> str:
    return re.sub(r"[A-Za-z]+$", "", verse_number)


def word_count(text: str) -> int:
    return len(WORD_PATTERN.findall(text))


def create_stats(input_path: Path) -> list[dict[str, int]]:
    verses_by_psalm: dict[str, set[str]] = defaultdict(set)
    words_by_psalm: dict[str, int] = defaultdict(int)

    with input_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            psalm = row["Psalm"]
            verses_by_psalm[psalm].add(verse_root(row["Verse Number"]))
            words_by_psalm[psalm] += word_count(row["Verse Text"])

    return [
        {
            "Psalm": int(psalm),
            "Verse Count": len(verses_by_psalm[psalm]),
            "Word Count": words_by_psalm[psalm],
        }
        for psalm in sorted(verses_by_psalm, key=int)
    ]


def write_csv(rows: list[dict[str, int]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["Psalm", "Verse Count", "Word Count"])
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create per-psalm verse and word counts from bcp_psalter.csv."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input half-verse CSV. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Stats CSV output path. Default: {DEFAULT_OUTPUT}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = create_stats(args.input)
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
