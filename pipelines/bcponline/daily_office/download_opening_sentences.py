#!/usr/bin/env python3
"""Download Rite II Daily Office opening and closing sentences from BCP Online."""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen


MORNING_URL = "https://www.bcponline.org/DailyOffice/mp2.html"
EVENING_URL = "https://www.bcponline.org/DailyOffice/ep2.html"
DEFAULT_MORNING_OUTPUT = Path("outputs/bcp_rite_ii_morning_prayer_opening_sentences.tsv")
DEFAULT_EVENING_OUTPUT = Path("outputs/bcp_rite_ii_evening_prayer_opening_sentences.tsv")
DEFAULT_MORNING_CLOSING_OUTPUT = Path("outputs/bcp_rite_ii_morning_prayer_closing_sentences.tsv")
DEFAULT_EVENING_CLOSING_OUTPUT = Path("outputs/bcp_rite_ii_evening_prayer_closing_sentences.tsv")
CITE_START = "\u0000CITE_START\u0000"
CITE_END = "\u0000CITE_END\u0000"
EM_START = "\u0000EM_START\u0000"
EM_END = "\u0000EM_END\u0000"
CLOSING_SENTENCES_RUBRIC = "The Officiant may then conclude with one of the following"

MORNING_SEASONS = {
    "Advent",
    "Christmas",
    "Epiphany",
    "Lent",
    "Holy Week",
    "Easter Season, including Ascension Day and the Day of Pentecost",
    "Trinity Sunday",
    "All Saints and other Major Saints' Days",
    "Occasions of Thanksgiving",
    "At any Time",
}


@dataclass
class MorningSentence:
    season: str
    verse_from_season_number: int
    verse: str
    citation: str


@dataclass
class NumberedSentence:
    verse_number: int
    verse: str
    citation: str


class OpeningSentencesParser(HTMLParser):
    """Extract text between the Opening Sentences and Confession sections."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self._in_sentences_rubric = False
        self._capturing = False
        self._stopped = False
        self._em_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}

        if attr_map.get("id") == "confession":
            self._capturing = False
            self._stopped = True
            return

        if self._stopped:
            return

        if attr_map.get("id") == "sentences":
            self._in_sentences_rubric = True
            return

        if not self._capturing:
            return

        if tag == "br":
            self.text_parts.append("\n")
        elif tag == "hr":
            self.text_parts.append("\n\n")
        elif tag == "p":
            self.text_parts.append("\n\n")
        elif tag == "em":
            marker = "citation" if "small" in attr_map.get("class", "").split() else "em"
            self._em_stack.append(marker)
            self.text_parts.append(CITE_START if marker == "citation" else EM_START)

    def handle_data(self, data: str) -> None:
        if self._capturing and not self._stopped:
            data = data.replace("\r", "").strip("\n")
            if not data.replace("\xa0", " ").strip():
                return
            self.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._stopped:
            return

        if self._in_sentences_rubric and tag == "p":
            self._in_sentences_rubric = False
            self._capturing = True
            return

        if not self._capturing:
            return

        if tag == "p":
            self.text_parts.append("\n\n")
        elif tag == "em" and self._em_stack:
            marker = self._em_stack.pop()
            self.text_parts.append(CITE_END if marker == "citation" else EM_END)

    @property
    def text(self) -> str:
        return "".join(self.text_parts)


class ClosingSentencesParser(HTMLParser):
    """Extract text after the concluding-sentences rubric."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self._capturing = False
        self._em_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self._capturing:
            return

        attr_map = {key: value or "" for key, value in attrs}
        if tag == "br":
            self.text_parts.append("\n")
        elif tag == "hr":
            self.text_parts.append("\n\n")
        elif tag == "p":
            self.text_parts.append("\n\n")
        elif tag == "em":
            marker = "citation" if "small" in attr_map.get("class", "").split() else "em"
            self._em_stack.append(marker)
            self.text_parts.append(CITE_START if marker == "citation" else EM_START)

    def handle_data(self, data: str) -> None:
        data = data.replace("\r", "").strip("\n")
        if not data.replace("\xa0", " ").strip():
            return

        if not self._capturing and CLOSING_SENTENCES_RUBRIC in normalize_text(data):
            self._capturing = True
            return

        if self._capturing:
            self.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._capturing:
            return

        if tag == "p":
            self.text_parts.append("\n\n")
        elif tag == "em" and self._em_stack:
            marker = self._em_stack.pop()
            self.text_parts.append(CITE_END if marker == "citation" else EM_END)

    @property
    def text(self) -> str:
        return "".join(self.text_parts)


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


def extract_opening_sentence_text(html: str) -> str:
    parser = OpeningSentencesParser()
    parser.feed(html)
    return parser.text


def extract_closing_sentence_text(html: str) -> str:
    parser = ClosingSentencesParser()
    parser.feed(html)
    return parser.text


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return text.strip()


def without_page_artifacts(text: str) -> str:
    clean_lines = []
    for line in text.splitlines():
        line = normalize_text(line)
        line = line.replace(EM_START, "").replace(EM_END, "")
        if not line:
            clean_lines.append("")
            continue
        if re.fullmatch(r"(Morning|Evening) Prayer II\s+\d+", line):
            continue
        if re.fullmatch(r"\d+\s+(Morning|Evening) Prayer II", line):
            continue
        if re.fullmatch(r"\d+", line):
            continue
        clean_lines.append(line)
    return "\n".join(clean_lines)


def remove_morning_season_headers(text: str) -> tuple[str | None, str]:
    season: str | None = None

    def replace_header(match: re.Match[str]) -> str:
        nonlocal season
        candidate = normalize_text(match.group(1))
        if candidate in MORNING_SEASONS:
            season = candidate
            return "\n\n"
        return match.group(0).replace(EM_START, "").replace(EM_END, "")

    text_without_headers = re.sub(f"{EM_START}(.*?){EM_END}", replace_header, text, flags=re.DOTALL)
    return season, text_without_headers


def sentence_text_before_citation(text: str) -> str:
    text = without_page_artifacts(text)
    paragraphs = [normalize_text(paragraph) for paragraph in re.split(r"\n[ \t\r\f\v]*\n", text)]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]

    # The Easter opening acclamation is not a Scripture sentence and has no citation.
    if len(paragraphs) > 1 and paragraphs[-1][:1].isupper():
        paragraphs = paragraphs[-1:]

    return normalize_text(" ".join(paragraphs))


def parse_morning_sentences(html: str) -> list[MorningSentence]:
    text = extract_opening_sentence_text(html)
    rows: list[MorningSentence] = []
    current_season: str | None = None
    verse_numbers_by_season: dict[str, int] = {}
    cursor = 0

    for match in re.finditer(f"{CITE_START}(.*?){CITE_END}", text, flags=re.DOTALL):
        raw_before_citation = text[cursor : match.start()]
        new_season, raw_verse = remove_morning_season_headers(raw_before_citation)
        if new_season:
            current_season = new_season

        citation = normalize_text(match.group(1))
        verse = sentence_text_before_citation(raw_verse)
        cursor = match.end()

        if not current_season or not verse or not citation:
            continue

        verse_numbers_by_season[current_season] = verse_numbers_by_season.get(current_season, 0) + 1
        rows.append(
            MorningSentence(
                season=current_season,
                verse_from_season_number=verse_numbers_by_season[current_season],
                verse=verse,
                citation=citation,
            )
        )

    return rows


def parse_numbered_sentences(text: str) -> list[NumberedSentence]:
    rows: list[NumberedSentence] = []
    cursor = 0

    for match in re.finditer(f"{CITE_START}(.*?){CITE_END}", text, flags=re.DOTALL):
        raw_verse = text[cursor : match.start()]
        citation = normalize_text(match.group(1))
        verse = sentence_text_before_citation(raw_verse)
        cursor = match.end()

        if verse and citation:
            rows.append(NumberedSentence(verse_number=len(rows) + 1, verse=verse, citation=citation))

    return rows


def parse_evening_sentences(html: str) -> list[NumberedSentence]:
    return parse_numbered_sentences(extract_opening_sentence_text(html))


def parse_closing_sentences(html: str) -> list[NumberedSentence]:
    return parse_numbered_sentences(extract_closing_sentence_text(html))


def write_tsv(rows: Iterable[object], output_path: Path, fieldnames: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as tsv_file:
        writer = csv.DictWriter(tsv_file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field.lower().replace(" ", "_")) for field in fieldnames})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Rite II Morning and Evening Prayer opening and closing sentences as TSV."
    )
    parser.add_argument("--morning-url", default=MORNING_URL, help=f"Default: {MORNING_URL}")
    parser.add_argument("--evening-url", default=EVENING_URL, help=f"Default: {EVENING_URL}")
    parser.add_argument(
        "--morning-output",
        type=Path,
        default=DEFAULT_MORNING_OUTPUT,
        help=f"Default: {DEFAULT_MORNING_OUTPUT}",
    )
    parser.add_argument(
        "--evening-output",
        type=Path,
        default=DEFAULT_EVENING_OUTPUT,
        help=f"Default: {DEFAULT_EVENING_OUTPUT}",
    )
    parser.add_argument(
        "--morning-closing-output",
        type=Path,
        default=DEFAULT_MORNING_CLOSING_OUTPUT,
        help=f"Default: {DEFAULT_MORNING_CLOSING_OUTPUT}",
    )
    parser.add_argument(
        "--evening-closing-output",
        type=Path,
        default=DEFAULT_EVENING_CLOSING_OUTPUT,
        help=f"Default: {DEFAULT_EVENING_CLOSING_OUTPUT}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    morning_html = download_html(args.morning_url)
    evening_html = download_html(args.evening_url)
    morning_rows = parse_morning_sentences(morning_html)
    evening_rows = parse_evening_sentences(evening_html)
    morning_closing_rows = parse_closing_sentences(morning_html)
    evening_closing_rows = parse_closing_sentences(evening_html)

    write_tsv(
        morning_rows,
        args.morning_output,
        ["Season", "Verse from Season Number", "Verse", "Citation"],
    )
    write_tsv(evening_rows, args.evening_output, ["Verse Number", "Verse", "Citation"])
    write_tsv(morning_closing_rows, args.morning_closing_output, ["Verse Number", "Verse", "Citation"])
    write_tsv(evening_closing_rows, args.evening_closing_output, ["Verse Number", "Verse", "Citation"])

    print(f"Wrote {len(morning_rows)} rows to {args.morning_output}")
    print(f"Wrote {len(evening_rows)} rows to {args.evening_output}")
    print(f"Wrote {len(morning_closing_rows)} rows to {args.morning_closing_output}")
    print(f"Wrote {len(evening_closing_rows)} rows to {args.evening_closing_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
