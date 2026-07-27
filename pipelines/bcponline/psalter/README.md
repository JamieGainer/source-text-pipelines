# BCP Online Psalter

Download the Psalter from BCP Online and create a CSV with one row per half-verse.

```sh
python3 pipelines/bcponline/psalter/download_bcp_psalter_and_create_csv.py
```

Default output:

```text
outputs/bcp_psalter.csv
```

CSV columns:

- `Psalm`
- `Verse Number`
- `Verse Text`

Verse numbers use `a` for text before the asterisk and `b` for text after it, such as `3a` and `3b`.

Create per-psalm stats from the generated CSV:

```sh
python3 pipelines/bcponline/psalter/create_bcp_psalm_stats_csv.py
```

Default output:

```text
outputs/bcp_psalm_stats.csv
```

Stats columns:

- `Psalm`
- `Verse Count`
- `Word Count`
