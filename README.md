# Source Text Pipelines

A collection of independent scripts for reading, cleaning, formatting, and transforming source texts from websites and public text collections.

Planned source families include:

- Book of Common Prayer resources
- BibleGateway passages
- Project Gutenberg texts
- Wikipedia articles
- Other public-domain or study-oriented web texts

The goal is to turn useful source text into structured data for language-learning tools, memorization workflows, and Anki decks.

## Repository Shape

This repo is intended to hold separate pipelines rather than one monolithic scraper. Each source can define its own fetch, parse, normalize, and export steps.

Suggested layout:

```text
pipelines/
  biblegateway/
  bcp/
  gutenberg/
  wikipedia/
outputs/
tests/
```

## Status

Initial repo scaffold.

## General Vocabulary Glosses

Create a vocabulary CSV from any plain text file:

```sh
python3 scripts/create_vocab_gloss_csv.py \
  --input path/to/text.txt \
  --output outputs/vocab_glosses.csv \
  --language es \
  --metadata "Short source description" \
  --gloss-source wiktionary
```

The default output columns are `word`, `gloss`, and `metadata`. Optional flags can add `count` and `language`.

Glosses can come from English Wiktionary with `--gloss-source wiktionary`, or from a local CSV/TSV with `--gloss-file path/to/glossary.tsv`. A glossary file should have `word` and `gloss` columns and is used as an override layer when supplied.
