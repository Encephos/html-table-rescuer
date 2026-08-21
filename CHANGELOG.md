# Changelog

## 0.4.0 (2026-08-21)

### Added
- **Multi-row headers are merged.** A stacked header — a `<th rowspan="2">` next
  to a grouped `<th colspan="3">`, as used in discographies, sports results and
  financial reports — now produces one header per column
  (`Peak positions - US`) instead of pushing the second header row into the
  data. Configurable via `ParseConfig(header_separator=...)`. This closes the
  only gap where `pandas.read_html` was measurably more correct; grid agreement
  with pandas rose from 24/30 to 27/30 on the benchmark corpus.
- **`<caption>` support.** The table title is extracted into
  `ParsedTable.caption`, prepended to the Markdown as a bold line (turn off with
  `to_markdown(include_caption=False)`), and exposed in the metadata of the
  LangChain, LlamaIndex and Haystack integrations — where it is one of the most
  valuable fields a retrieved chunk can carry.
- Benchmarks (`benchmarks/`, results in `docs/BENCHMARKS.md`) measuring the token
  cost of each rowspan strategy and comparing against `pandas.read_html` on 30
  real-world Wikipedia tables — including where pandas wins (it is ~2.9x faster).

### Fixed
- **Nested tables were emitted twice** — once flattened into the containing
  cell's text and once as a table of their own — which duplicated content in any
  downstream index. Only top-level tables are emitted now.
- `<style>` and `<script>` content no longer leaks into cell text. Wikipedia and
  many CMS exports inline CSS inside tables, which previously ended up as cell
  content. Found by the new benchmarks.

### Changed
- Tables with a `<caption>` now render with a bold title line above the table by
  default. Pass `to_markdown(include_caption=False)` for the previous output.

## 0.3.1 (2026-07-30)

### Added
- `ParsedTable` now renders as a real table in Jupyter/Colab via
  `_repr_markdown_`.
- Interactive demo notebook (`examples/demo.ipynb`) with an "Open in Colab"
  badge in the README, so the tool can be tried in the browser without
  installing anything.

## 0.3.0 (2026-07-30)

### Added
- LlamaIndex integration: `HTMLTableRescuerReader` (extra: `llamaindex`). Each
  table becomes its own `Document`. Works as a `file_extractor` in
  `SimpleDirectoryReader`; `extra_info` passed by the framework takes precedence
  over the reader's own metadata.
- Haystack integration: `HTMLTableRescuerConverter` (extra: `haystack`). Unlike
  Haystack's own `HTMLToDocument`, one source yields one `Document` per table.
  Accepts file paths and `ByteStream`s, follows the Haystack convention of
  skipping unreadable sources with a warning instead of failing the pipeline,
  and supports `to_dict`/`from_dict` so a `ParseConfig` survives pipeline
  serialization. Compatible with both haystack-ai 2.x and 3.x.
- Test coverage for all framework integrations (26 tests); the LangChain loader
  was previously untested. CI now installs the integration extras so these run.

## 0.2.1 (2026-07-30)

### Changed
- **Breaking:** the import package was renamed from `table2md` to
  `html_table_rescuer`, matching the distribution name and the renamed GitHub
  repository (`Encephos/html-table-rescuer`). Update imports accordingly:
  `from html_table_rescuer import TableParser`.
- The installed CLI command is now `html-table-rescuer` (was `table2md`).
- The LangChain loader class was renamed from `Table2MDLoader` to
  `HTMLTableRescuerLoader`.

## 0.2.0 (2026-07-30)

### Added
- `table2md` CLI (Typer): file/URL/stdin input, `--format markdown|json|csv`,
  `--strategy`, `--dito-prefix`, `--table`, `--output`, `--no-links`,
  `--no-bold`, `--no-italic`, `--parser`. Piped input works without an
  argument (`curl … | table2md`).
- Public API exports from the package root: `from table2md import TableParser`.
- `py.typed` marker (PEP 561).
- CI workflow (ruff + pytest on Python 3.9 and 3.12).
- Test suite grown from 9 to 50 tests, including the 13 example cases as
  regression tests.

### Fixed
- Invalid `colspan`/`rowspan` values (`""`, `"abc"`, `"0"`, negative) no longer
  crash the parser or silently drop cell content.
- `rowspan` is capped at the last table row (browser behavior); huge values
  like `rowspan="10000"` no longer allocate unbounded grids.
- HTML comments no longer leak into cell output.
- README installation instructions now name the actual PyPI package
  (`html-table-rescuer`).

## 0.1.0 (2025-12-10)

- Initial release: HTML table extraction with rowspan/colspan grid solving,
  Markdown/JSON/CSV export, LangChain document loader.
