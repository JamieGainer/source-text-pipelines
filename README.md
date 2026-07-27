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
