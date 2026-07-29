# Memorization Chunk TSV

Create deterministic memorization chunks from a plain text file.

```sh
python3 pipelines/memorization/create_memorization_chunks_tsv.py \
  --input path/to/text.txt \
  --output outputs/memorization_chunks.tsv \
  --base-unit sentence
```

Default output:

```text
outputs/memorization_chunks.tsv
```

Output columns:

- `Item Number`
- `Text`

By default, the script first splits on sentence-ending punctuation. If the text has no sentence-ending punctuation, or if everything is one sentence, it uses non-empty input lines as the base units instead.

For poetry or intentionally lineated text, use line mode:

```sh
python3 pipelines/memorization/create_memorization_chunks_tsv.py \
  --input path/to/poem.txt \
  --output outputs/poem_memorization_chunks.tsv \
  --base-unit line
```

If a base unit is longer than `--max-words-per-item`, the script splits further at commas, semicolons, colons, em dashes, en dashes, and spaced hyphens. It accumulates those punctuation-separated pieces into the fewest chunks it can while staying under the word limit. Any piece still over the limit is hard-split by word count.

Default maximum:

```text
15 words
```
