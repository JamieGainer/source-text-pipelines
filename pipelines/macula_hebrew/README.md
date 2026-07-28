# MACULA Hebrew Vocabulary

Create Hebrew Bible vocabulary TSVs from the MACULA Hebrew word-level TSV.

Download the MACULA TSV if it is not already present, then create a Genesis 5 vocabulary file:

```sh
python3 pipelines/macula_hebrew/create_hebrew_bible_vocab_tsv.py --download
```

Default input:

```text
data/macula-hebrew/WLC/tsv/macula-hebrew.tsv
```

Default output:

```text
outputs/genesis_5_vocab.tsv
```

The script can target another chapter:

```sh
python3 pipelines/macula_hebrew/create_hebrew_bible_vocab_tsv.py \
  --book EXO \
  --book-label Exodus \
  --chapter 3 \
  --output outputs/exodus_3_vocab.tsv
```

Output columns:

- `Hebrew`
- `Gloss`
- `Lemma`
- `Part_of_speech`
- `Reference`
- `Occurrences`
- `Morphology`

Hebrew cantillation marks are stripped from surface forms while vowel points and dagesh are retained.
