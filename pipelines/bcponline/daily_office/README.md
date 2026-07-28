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

## Morning Prayer Canticles

Download the Rite II Morning Prayer canticles and split asterisked verses into half-verse rows.

```sh
python3 pipelines/bcponline/daily_office/download_morning_canticles.py
```

Default outputs:

```text
outputs/bcp_rite_ii_morning_prayer_canticles.tsv
outputs/bcp_rite_ii_morning_prayer_canticle_verses.tsv
```

Canticle metadata columns:

- `Canticle Number`
- `Name`
- `Latin Name`
- `Citation`

Canticle verse columns:

- `Canticle Number`
- `Verse Number`
- `Verse Text`

Verse numbers restart within each canticle. Asterisked verses use `a` for text before the asterisk and `b` for text after it, such as `1a` and `1b`.
