# BCP Online Daily Office Sentences

Download the Rite II Morning and Evening Prayer opening and closing sentences from BCP Online and write TSV files.

```sh
python3 pipelines/bcponline/daily_office/download_opening_sentences.py
```

Default outputs:

```text
outputs/bcp_rite_ii_morning_prayer_opening_sentences.tsv
outputs/bcp_rite_ii_evening_prayer_opening_sentences.tsv
outputs/bcp_rite_ii_morning_prayer_closing_sentences.tsv
outputs/bcp_rite_ii_evening_prayer_closing_sentences.tsv
```

Morning Prayer columns:

- `Season`
- `Verse from Season Number`
- `Verse`
- `Citation`

Evening Prayer opening columns:

- `Verse Number`
- `Verse`
- `Citation`

Morning and Evening Prayer closing columns:

- `Verse Number`
- `Verse`
- `Citation`

The files are tab-delimited because the verse text and citations contain commas.
