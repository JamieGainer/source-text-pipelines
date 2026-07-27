#!/usr/bin/env python3
"""Download the BCP Online Psalter and split verses into a/b CSV rows."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen


DEFAULT_URL = "https://www.bcponline.org/Psalter/the_psalter.html"
DEFAULT_OUTPUT = Path("outputs/bcp_psalter.csv")


@dataclass
class Cell:
    attrs: dict[str, str]
    text: str


@dataclass
class VersePart:
    psalm: str
    verse_number: str
    verse_text: str


class PsalterTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[Cell]] = []
        self._current_row: list[Cell] | None = None
        self._current_cell_attrs: dict[str, str] | None = None
        self._current_cell_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._current_row = []
        elif tag == "td" and self._current_row is not None:
            self._current_cell_attrs = {key: value or "" for key, value in attrs}
            self._current_cell_text = []
        elif tag == "br" and self._current_cell_text is not None:
            self._current_cell_text.append("\n")

    def handle_data(self, data: str) -> None:
        if self._current_cell_text is not None:
            self._current_cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._current_row is not None and self._current_cell_text is not None:
            self._current_row.append(
                Cell(
                    attrs=self._current_cell_attrs or {},
                    text="".join(self._current_cell_text),
                )
            )
            self._current_cell_attrs = None
            self._current_cell_text = None
        elif tag == "tr" and self._current_row is not None:
            self.rows.append(self._current_row)
            self._current_row = None


def download_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; source-text-pipelines/0.1; "
                "+https://github.com/JamieGainer/source-text-pipelines)"
            )
        },
    )
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_verse_parts(html: str) -> list[VersePart]:
    parser = PsalterTableParser()
    parser.feed(html)

    current_psalm: str | None = None
    verse_parts: list[VersePart] = []
    missing_asterisk: list[str] = []

    for row in parser.rows:
        if len(row) < 2:
            continue

        verse_number = normalize_text(row[0].text)
        verse_text = normalize_text(row[1].text)
        content_id = row[1].attrs.get("id", "")

        heading_match = re.match(r"^(\d{1,3})\b", verse_text)
        heading_psalm = heading_match.group(1) if heading_match else None

        if verse_number == "" and heading_psalm and 1 <= int(heading_psalm) <= 150:
            current_psalm = heading_psalm
            continue

        if verse_number == "" and content_id.isdigit():
            current_psalm = content_id
            continue

        if not current_psalm or not verse_number.isdigit() or not verse_text:
            continue

        if "*" not in verse_text:
            missing_asterisk.append(f"Psalm {current_psalm}:{verse_number}")
            verse_parts.append(VersePart(current_psalm, verse_number, verse_text))
            continue

        before_asterisk, after_asterisk = verse_text.split("*", 1)
        verse_parts.append(
            VersePart(
                psalm=current_psalm,
                verse_number=f"{verse_number}a",
                verse_text=normalize_text(before_asterisk),
            )
        )
        verse_parts.append(
            VersePart(
                psalm=current_psalm,
                verse_number=f"{verse_number}b",
                verse_text=normalize_text(after_asterisk),
            )
        )

    if missing_asterisk:
        refs = ", ".join(missing_asterisk[:10])
        extra = "" if len(missing_asterisk) <= 10 else f", and {len(missing_asterisk) - 10} more"
        print(f"Warning: verses without an asterisk: {refs}{extra}", file=sys.stderr)

    return verse_parts


def write_csv(rows: Iterable[VersePart], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Psalm", "Verse Number", "Verse Text"])
        for row in rows:
            writer.writerow([row.psalm, row.verse_number, row.verse_text])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the BCP Online Psalter and create a Psalm/verse-part CSV."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Source URL. Default: {DEFAULT_URL}")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path. Default: {DEFAULT_OUTPUT}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    html = download_html(args.url)
    verse_parts = parse_verse_parts(html)
    write_csv(verse_parts, args.output)
    print(f"Wrote {len(verse_parts)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
