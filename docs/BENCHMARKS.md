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
| `empty` | 40,023 | 978 | — |
| `repeat` | 40,529 | 978 | +1.3% |
| `fill_dito` | 40,638 | 984 | **+1.5%** |
| JSON (`to_json`) | 71,322 | 1,108 | +78.2% |

**The overhead is much smaller than it looks, because span continuations are
rare.** Across the corpus only **3.0% of grid cells** (53 of 1,744) are span
continuations — and that fraction is the only thing any fill strategy can
affect. The other 97% of the table is identical no matter what you pick.

Per-table, though, the spread is wide:

| Variant | Median overhead | Max overhead |
|---|---|---|
| `repeat` | 0.0% | 54.4% |
| `fill_dito` | 0.0% | 55.7% |

So: for a typical table the choice is free, and for a span-heavy one it is
expensive. If you are chunking a few thousand tables, measure your own corpus
rather than trusting the median.

**`fill_dito` is free at the median** and costs 0.2 percentage points more than
`repeat` overall. What you get for it is a marker: the model can tell "this value
continues from above" apart from "this value was independently repeated". If that
distinction does not matter to your prompt, `repeat` is marginally cheaper — and
if you do not need the context at all, `empty` is cheapest.

**Markdown beats JSON by a wide margin.** Dumping the same tables as JSON costs
**78% more tokens**, because every row repeats every key. That gap dwarfs the
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
| `pandas.read_html` | 43 ms | 1.4 ms |
| `html-table-rescuer` | 126 ms | 4.2 ms |

**pandas is ~2.9x faster.** If you are parsing at volume and your HTML is clean,
that matters. Our parser does more per cell (recursive inline-formatting,
Markdown escaping, link preservation) and does not have pandas' C-backed
fast path.

### Span resolution — agreement on 27 of 30

| Result | Count |
|---|---|
| Identical grid shape | 27/30 |
| Different grid shape | 3/30 |
| — of which: multi-row headers | 0 |
| Either tool failed | 0/30 |

pandas resolves `rowspan`/`colspan` correctly. On well-formed tables the two
tools agree, and the three remaining differences are not about spans:

- **2 tables: Wikipedia navboxes.** Not data tables at all; both tools produce
  something meaningless, just with different row counts.
- **1 table: the periodic table.** pandas failed to detect a header at all
  (columns came out as `0, 1, 2…`); we detected it correctly.

> Earlier versions scored 24/30 here. Three of the six differences were
> multi-row headers, where pandas was more correct — that gap was closed in
> 0.4.0 by merging stacked headers, which is what moved the number to 27/30.

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

- **Nested tables are flattened** into the containing cell's text. Only
  top-level tables are emitted, so the inner table's content appears once — as
  text inside the cell that contains it — rather than as a table of its own.
- **Speed**: see above. No fast path; the parser is optimised for correctness on
  messy input, not throughput on clean input.
- **Single-row headers with `colspan` leave continuation cells empty.** A lone
  `<th colspan="2">Department</th>` renders as `| Department |  |`. Merging only
  kicks in for genuinely stacked headers, to keep existing output stable.

### Fixed since the first run of these benchmarks

- **Multi-row headers** were not merged; a stacked header put its second row into
  the body. Fixed in 0.4.0 — 3 of 30 corpus tables were affected, and grid
  agreement with pandas rose from 24/30 to 27/30.
- **Nested tables were emitted twice**, once flattened into the containing cell
  and once as a separate table, duplicating content in any downstream index.
  Fixed in 0.4.0. (An earlier revision of this document claimed the inner table
  was already suppressed — that was wrong.)
- **`<style>`/`<script>` content leaked into cells.** Fixed in 0.4.0.

## What is deliberately *not* in scope

Data-quality checks — null-density thresholds, type consistency, column
validation — belong in the pipeline that consumes the tables, not in the parser.
A parser's job is to report faithfully what the markup says, including that a
column is 90% empty. Deciding whether that is acceptable is an application
policy, and baking it in here would mean every consumer inherits someone else's
thresholds. `ParsedTable` gives you `headers` and `rows` as plain Python data;
validate downstream where you have the context to decide.
