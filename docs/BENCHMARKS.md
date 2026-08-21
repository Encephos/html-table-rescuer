# Benchmarks

Two questions come up often enough to answer them with numbers instead of
opinions:

1. What does the `dito` fill strategy actually cost in tokens?
2. When should you use this instead of `pandas.read_html`?

Everything below is reproducible:

```bash
pip install "html-table-rescuer[benchmark]"
python benchmarks/token_overhead.py
python benchmarks/vs_pandas.py
```

The corpus is 30 real Wikipedia tables that use `rowspan`/`colspan` — discographies,
sports results, election tables, the periodic table. It is cached in
`benchmarks/data/corpus.json` so runs are reproducible offline; rebuild it with
`python benchmarks/corpus.py`.

Numbers below: Python 3.12, pandas 3.0.5, tokenizer `o200k_base` (GPT-4o family).

---

## 1. Token overhead of the rowspan strategies

When a cell spans rows, the continuation cells have to contain *something*.
`fill_dito` writes `dito (Engineering)`, `repeat` writes `Engineering`, `empty`
writes nothing. The concern is that duplicating content burns context window.

| Variant | Total tokens | Median/table | vs `empty` |
|---|---|---|---|
| `empty` | 41,685 | 1,142 | — |
| `repeat` | 42,317 | 1,148 | +1.5% |
| `fill_dito` | 42,450 | 1,150 | **+1.8%** |
| JSON (`to_json`) | 64,788 | 1,169 | +55.4% |

**The overhead is much smaller than it looks, because span continuations are
rare.** Across the corpus only **3.5% of grid cells** (63 of 1,789) are span
continuations — and that fraction is the only thing any fill strategy can
affect. The other 96.5% of the table is identical no matter what you pick.

Per-table, though, the spread is wide:

| Variant | Median overhead | Max overhead |
|---|---|---|
| `repeat` | 0.0% | 55.7% |
| `fill_dito` | 0.3% | 57.0% |

So: for a typical table the choice is free, and for a span-heavy one it is
expensive. If you are chunking a few thousand tables, measure your own corpus
rather than trusting the median.

**`fill_dito` costs 0.3 percentage points more than `repeat`** at the median.
What you get for it is a marker: the model can tell "this value continues from
above" apart from "this value was independently repeated". If that distinction
does not matter to your prompt, `repeat` is strictly cheaper — and if you do not
need the context at all, `empty` is cheapest.

**Markdown beats JSON by a wide margin.** Dumping the same tables as JSON costs
**55% more tokens**, because every row repeats every key. That gap dwarfs the
entire strategy question — the fill strategy is a rounding error next to the
choice of output format.

### Picking a strategy

| Use | Strategy |
|---|---|
| RAG chunks where a row must stand alone | `fill_dito` (default) |
| Feeding a model that will aggregate/count rows | `repeat` — no marker noise |
| Reproducing the visual table, span cells are noise | `empty` |
| Structured consumption by code, not a model | `to_json()` — tokens don't matter |

---

## 2. Against `pandas.read_html`

pandas is the real alternative, so here is the honest comparison — including
where it wins.

### Speed — pandas wins

| | Total (30 tables) | Per table |
|---|---|---|
| `pandas.read_html` | 48 ms | 1.6 ms |
| `html-table-rescuer` | 124 ms | 4.1 ms |

**pandas is ~2.6x faster.** If you are parsing at volume and your HTML is clean,
that matters. Our parser does more per cell (recursive inline-formatting,
Markdown escaping, link preservation) and does not have pandas' C-backed
fast path.

### Span resolution — agreement on 24 of 30

| Result | Count |
|---|---|
| Identical grid shape | 24/30 |
| Different grid shape | 6/30 |
| — of which: multi-row headers | 3 |
| Either tool failed | 0/30 |

pandas resolves `rowspan`/`colspan` correctly. On well-formed tables the two
tools agree, and where they differ it is usually not about spans:

- **3 tables: multi-row headers.** pandas promotes a stacked header into a
  `MultiIndex`; we keep only the first row as the header, so the second header
  row shows up as a data row. **pandas is more correct here** — this is a known
  limitation, see below.
- **2 tables: Wikipedia navboxes.** Not data tables at all; both tools produce
  something meaningless, just with different row counts.
- **1 table: the periodic table.** pandas failed to detect a header at all
  (columns came out as `0, 1, 2…`); we detected it correctly.

### Malformed markup — we win

Every case below renders fine in a browser, which is exactly why scrapers hit them.

| Case | html-table-rescuer | pandas |
|---|---|---|
| `colspan="abc"` | ok | **ValueError** |
| `colspan="2.5"` | ok | **ValueError** |
| `colspan=""` | ok | ok |
| `colspan="0"` | ok | ok |
| `rowspan="-2"` | ok | ok |
| `rowspan="100000"` | ok | ok |
| Unclosed tags | ok | ok |
| HTML comment in cell | ok | ok |
| **Survived** | **8/8** | **6/8** |

pandas raises `ValueError: invalid literal for int() with base 10: 'abc'` on
non-numeric span values. One such cell aborts the whole call, so a single
malformed table in a scraping batch takes down the batch.

### So which should you use?

**Use `pandas.read_html` when** your HTML is clean and machine-generated, you
want DataFrames, you are parsing at volume, or you already depend on pandas.

**Use `html-table-rescuer` when** you are feeding tables to an LLM (Markdown out,
with span context preserved), your HTML comes from the wild and may be
malformed, you want the RAG integrations (one document per table), or you want
to avoid a pandas dependency — the base install is ~5 MB against pandas' ~70 MB.

---

## Known limitations

Found by these benchmarks, listed here rather than hidden:

- **Multi-row headers are not merged.** A table with a stacked header
  (`<th rowspan="2">` next to grouped `<th colspan="3">`) keeps only the first
  row as the header; the second lands in the body. pandas handles this with a
  `MultiIndex`. Affected 3 of 30 corpus tables.
- **Nested tables are flattened** into the containing cell's text (the inner
  table is not emitted separately — that part is deliberate, to avoid duplicate
  output).
- **Speed**: see above. No fast path; the parser is optimised for correctness on
  messy input, not throughput on clean input.

## What is deliberately *not* in scope

Data-quality checks — null-density thresholds, type consistency, column
validation — belong in the pipeline that consumes the tables, not in the parser.
A parser's job is to report faithfully what the markup says, including that a
column is 90% empty. Deciding whether that is acceptable is an application
policy, and baking it in here would mean every consumer inherits someone else's
thresholds. `ParsedTable` gives you `headers` and `rows` as plain Python data;
validate downstream where you have the context to decide.
