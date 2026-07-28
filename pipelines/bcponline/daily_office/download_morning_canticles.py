#!/usr/bin/env python3
"""Download Rite II Morning Prayer canticles from BCP Online as TSV files."""

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


DEFAULT_URL = "https://www.bcponline.org/DailyOffice/mp2.html"
DEFAULT_VERSES_OUTPUT = Path("outputs/bcp_rite_ii_morning_prayer_canticle_verses.tsv")
DEFAULT_METADATA_OUTPUT = Path("outputs/bcp_rite_ii_morning_prayer_canticles.tsv")
NUM_START = "\u0000NUM_START\u0000"
NUM_END = "\u0000NUM_END\u0000"
STRONG_START = "\u0000STRONG_START\u0000"
STRONG_END = "\u0000STRONG_END\u0000"
EM_START = "\u0000EM_START\u0000"
EM_END = "\u0000EM_END\u0000"
CITE_START = "\u0000CITE_START\u0000"
CITE_END = "\u0000CITE_END\u0000"


@dataclass
class Paragraph:
    attrs: dict[str, str]
    text: str


@dataclass
class CanticleMetadata:
    canticle_number: str
    name: str
    latin_name: str
    citation: str


@dataclass
class CanticleVersePart:
    canticle_number: str
    verse_number: str
    verse_text: str


class MorningCanticlesParser(HTMLParser):
    """Extract paragraphs between Canticle 8 and the Apostles' Creed."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[Paragraph] = []
        self._capturing = False
        self._stopped = False
        self._current_attrs: dict[str, str] | None = None
        self._current_text: list[str] | None = None
        self._strong_stack: list[str] = []
        self._em_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}

        if attr_map.get("id") == "acreed":
            self._stopped = True
            self._capturing = False
            return

        if self._stopped:
            return

        if attr_map.get("id") == "canticles":
            self._capturing = True
            if self._current_text is None:
                self._current_attrs = {}
                self._current_text = []

        if not self._capturing:
            return

        if tag == "p" and self._current_text is None:
            self._current_attrs = attr_map
            self._current_text = []
        elif tag == "br" and self._current_text is not None:
            self._current_text.append("\n")
        elif tag == "strong" and self._current_text is not None:
            marker = "number" if "x-large" in attr_map.get("class", "").split() else "strong"
            self._strong_stack.append(marker)
            self._current_text.append(NUM_START if marker == "number" else STRONG_START)
        elif tag == "em" and self._current_text is not None:
            marker = "citation" if "small" in attr_map.get("class", "").split() else "em"
            self._em_stack.append(marker)
            self._current_text.append(CITE_START if marker == "citation" else EM_START)

    def handle_data(self, data: str) -> None:
        if not self._capturing or self._stopped or self._current_text is None:
            return

        data = data.replace("\r", "").strip("\n")
        if not data.replace("\xa0", " ").strip():
            return
        self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._capturing or self._stopped:
            return

        if tag == "p" and self._current_text is not None:
            self.paragraphs.append(
                Paragraph(
                    attrs=self._current_attrs or {},
                    text="".join(self._current_text),
                )
            )
            self._current_attrs = None
            self._current_text = None
        elif tag == "strong" and self._current_text is not None and self._strong_stack:
            marker = self._strong_stack.pop()
            self._current_text.append(NUM_END if marker == "number" else STRONG_END)
        elif tag == "em" and self._current_text is not None and self._em_stack:
            marker = self._em_stack.pop()
            self._current_text.append(CITE_END if marker == "citation" else EM_END)


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
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return text.strip()


def visible_text(text: str) -> str:
    for marker in [
        NUM_START,
        NUM_END,
        STRONG_START,
        STRONG_END,
        EM_START,
        EM_END,
        CITE_START,
        CITE_END,
    ]:
        text = text.replace(marker, "")
    return normalize_text(text)


def raw_visible_text(text: str) -> str:
    for marker in [
        NUM_START,
        NUM_END,
        STRONG_START,
        STRONG_END,
        EM_START,
        EM_END,
        CITE_START,
        CITE_END,
    ]:
        text = text.replace(marker, "")
    return text.replace("\xa0", " ")


def is_page_artifact(paragraph: Paragraph) -> bool:
    text = visible_text(paragraph.text)
    if not text:
        return True
    if paragraph.attrs.get("class") in {"leftfoot", "rightfoot"}:
        return True
    return bool(re.fullmatch(r"(Morning Prayer II\s+\d+|\d+\s+Morning Prayer II|\d+)", text))


def parse_heading(text: str) -> CanticleMetadata | None:
    number_match = re.search(f"{NUM_START}(.*?){NUM_END}", text, flags=re.DOTALL)
    name_match = re.search(f"{STRONG_START}(.*?){STRONG_END}", text, flags=re.DOTALL)
    latin_match = re.search(f"{EM_START}(.*?){EM_END}", text, flags=re.DOTALL)
    citation_match = re.search(f"{CITE_START}(.*?){CITE_END}", text, flags=re.DOTALL)

    if not number_match or not name_match:
        return None

    return CanticleMetadata(
        canticle_number=normalize_text(number_match.group(1)),
        name=normalize_text(name_match.group(1)),
        latin_name=normalize_text(latin_match.group(1)) if latin_match else "",
        citation=normalize_text(citation_match.group(1)) if citation_match else "",
    )


def is_non_verse_paragraph(paragraph: Paragraph) -> bool:
    if paragraph.attrs.get("class") == "rubric":
        return True
    text = paragraph.text
    visible = visible_text(text)
    if not visible:
        return True
    if EM_START in text and "*" not in visible:
        return True
    if CITE_START in text and NUM_START not in text:
        return True
    return False


def append_verse_parts(
    paragraph_text: str,
    metadata: CanticleMetadata,
    verse_parts: list[CanticleVersePart],
    next_verse_number: int,
) -> int:
    raw_text = raw_visible_text(paragraph_text)
    raw_lines = [line for line in raw_text.splitlines() if normalize_text(line)]
    lines = [
        {
            "text": normalize_text(line),
            "indented": line.startswith((" ", "\t", "\xa0")),
        }
        for line in raw_lines
    ]

    if not lines:
        return next_verse_number

    if not any("*" in line["text"] for line in lines):
        verse_parts.append(
            CanticleVersePart(
                canticle_number=metadata.canticle_number,
                verse_number=str(next_verse_number),
                verse_text=normalize_text(" ".join(line["text"] for line in lines)),
            )
        )
        return next_verse_number + 1

    current_before: str | None = None
    current_after_lines: list[str] = []
    current_verse_number = next_verse_number
    pending_before_lines: list[str] = []

    def flush_current_verse() -> None:
        if current_before is None:
            return
        after_asterisk = normalize_text(" ".join(current_after_lines))

        if current_before:
            verse_parts.append(
                CanticleVersePart(
                    canticle_number=metadata.canticle_number,
                    verse_number=f"{current_verse_number}a",
                    verse_text=current_before,
                )
            )
        if after_asterisk:
            verse_parts.append(
                CanticleVersePart(
                    canticle_number=metadata.canticle_number,
                    verse_number=f"{current_verse_number}b",
                    verse_text=after_asterisk,
                )
            )

    for line in lines:
        text = line["text"]
        if "*" in text:
            if current_before is not None:
                flush_current_verse()
                current_verse_number += 1
            before_asterisk, after_asterisk = text.split("*", 1)
            current_before = normalize_text(" ".join([*pending_before_lines, before_asterisk]))
            current_after_lines = [normalize_text(after_asterisk)] if after_asterisk.strip() else []
            pending_before_lines = []
        elif current_before is not None and (line["indented"] or not current_after_lines):
            current_after_lines.append(text)
        elif current_before is not None:
            flush_current_verse()
            current_verse_number += 1
            current_before = None
            current_after_lines = []
            pending_before_lines = [text]
        else:
            pending_before_lines.append(text)

    if pending_before_lines:
        print(
            f"Warning: unpaired text in Canticle {metadata.canticle_number}: "
            f"{normalize_text(' '.join(pending_before_lines))}",
            file=sys.stderr,
        )

    if current_before is not None:
        flush_current_verse()
        current_verse_number += 1

    return current_verse_number


def parse_canticles(html: str) -> tuple[list[CanticleMetadata], list[CanticleVersePart]]:
    parser = MorningCanticlesParser()
    parser.feed(html)

    metadata_rows: list[CanticleMetadata] = []
    verse_parts: list[CanticleVersePart] = []
    current_metadata: CanticleMetadata | None = None
    next_verse_number = 1

    for paragraph in parser.paragraphs:
        if is_page_artifact(paragraph):
            continue

        heading = parse_heading(paragraph.text)
        if heading is not None:
            current_metadata = heading
            metadata_rows.append(heading)
            next_verse_number = 1

            text_after_citation = re.split(f"{CITE_END}", paragraph.text, maxsplit=1)
            if len(text_after_citation) == 2:
                next_verse_number = append_verse_parts(
                    text_after_citation[1],
                    current_metadata,
                    verse_parts,
                    next_verse_number,
                )
            continue

        if current_metadata is None or is_non_verse_paragraph(paragraph):
            continue

        next_verse_number = append_verse_parts(
            paragraph.text,
            current_metadata,
            verse_parts,
            next_verse_number,
        )

    return metadata_rows, verse_parts


def write_metadata_tsv(rows: Iterable[CanticleMetadata], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as tsv_file:
        writer = csv.writer(tsv_file, delimiter="\t")
        writer.writerow(["Canticle Number", "Name", "Latin Name", "Citation"])
        for row in rows:
            writer.writerow([row.canticle_number, row.name, row.latin_name, row.citation])


def write_verse_parts_tsv(rows: Iterable[CanticleVersePart], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as tsv_file:
        writer = csv.writer(tsv_file, delimiter="\t")
        writer.writerow(["Canticle Number", "Verse Number", "Verse Text"])
        for row in rows:
            writer.writerow([row.canticle_number, row.verse_number, row.verse_text])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Rite II Morning Prayer canticles and split asterisked verses."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Source URL. Default: {DEFAULT_URL}")
    parser.add_argument(
        "--verses-output",
        type=Path,
        default=DEFAULT_VERSES_OUTPUT,
        help=f"Default: {DEFAULT_VERSES_OUTPUT}",
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=DEFAULT_METADATA_OUTPUT,
        help=f"Default: {DEFAULT_METADATA_OUTPUT}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metadata_rows, verse_parts = parse_canticles(download_html(args.url))
    write_metadata_tsv(metadata_rows, args.metadata_output)
    write_verse_parts_tsv(verse_parts, args.verses_output)
    print(f"Wrote {len(metadata_rows)} rows to {args.metadata_output}")
    print(f"Wrote {len(verse_parts)} rows to {args.verses_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
