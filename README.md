# html-table-rescuer

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Encephos/html-table-rescuer/blob/main/examples/demo.ipynb)

A robust Python tool to extract complex HTML tables and convert them into clean Markdown, JSON, or CSV formats.

**[Try it in your browser](https://colab.research.google.com/github/Encephos/html-table-rescuer/blob/main/examples/demo.ipynb)** — an interactive Colab notebook, nothing to install.

Unlike simple formatters, this library features a **Grid Logic Solver** that correctly interprets `rowspan` and `colspan` attributes, normalizing complex HTML grids into perfectly aligned data structures.

## How is this different from other `table2md` packages?

There is an existing package called `table2md` on PyPI.

* The **existing package** is a *formatter*. You feed it Python lists/dicts, and it draws a Markdown table.

* **This package** is an *extractor and parser*. It takes raw HTML source code, uses `BeautifulSoup` to parse the tags, mathematically resolves complex cell spans (rowspans/colspans), and builds an internal representation before exporting to Markdown.

### The Problem:
Most parsers turn this `<td rowspan="2">` into a misaligned mess:
```bash
| Header | Value |
|---|---|
| Spanned | Row 1 |
| Row 2 | |   <-- Everything shifts!
```

### The Solution:
`html-table-rescuer` uses a grid solver to correctly normalize the matrix:
```bash
| Header | Value |
|---|---|
| Spanned | Row 1 |
| dito (Spanned) | Row 2 |
```
## Architecture

Our pipeline ensures that complex HTML structures are safely converted without data loss or misalignment:

```mermaid
graph TD
    n1["HTML Input"] --> n2["BeautifulSoup Parser"]
    n2 --> n3["Grid Logic<br>(Rowspan/Colspan Solver)"]
    n3 --> n4["ParsedTable Data Object"]
    n4 --> n5["Markdown Export"]
    n4 --> n6["JSON/CSV Export"]
    n4 --> n7["LangChain/LlamaIndex/Haystack Wrappers"]
```

## Installation

```bash
pip install html-table-rescuer

# With framework integrations
pip install "html-table-rescuer[langchain]"
pip install "html-table-rescuer[llamaindex]"
pip install "html-table-rescuer[haystack]"
```

## Quick Start

```python
from html_table_rescuer import TableParser

html_content = """
<table border="1">
  <tr>
    <th colspan="2">Header</th>
  </tr>
  <tr>
    <td>Data 1</td>
    <td>Data 2</td>
  </tr>
</table>
"""

# Initialize parser with your HTML
parser = TableParser(html_content)

# Parse all tables in the HTML
tables = parser.parse()

if tables:
    table = tables[0]
    
    # Export to Markdown (perfect for LLM context windows)
    print(table.to_markdown())
    
    # Export to JSON
    # print(table.to_json())
    
    # Export to CSV
    # print(table.to_csv())
```

## Command Line

The package installs an `html-table-rescuer` command that reads from a file, a URL, or stdin:

```bash
# From a file
html-table-rescuer page.html

# From a URL
html-table-rescuer https://example.com/page.html

# From stdin (pipe or '-')
curl -s https://example.com/page.html | html-table-rescuer
cat page.html | html-table-rescuer - --format json
```

Options:

| Option | Description |
|---|---|
| `--format`, `-f` | Output format: `markdown` (default), `json`, `csv` |
| `--strategy`, `-s` | Rowspan fill strategy: `fill_dito` (default), `repeat`, `empty` |
| `--dito-prefix` | Prefix used by the `fill_dito` strategy |
| `--table`, `-t` | Extract only the table with this index (0-based) |
| `--output`, `-o` | Write to a file instead of stdout; with CSV and multiple tables, writes `name_1.csv`, `name_2.csv`, … |
| `--no-links` / `--no-bold` / `--no-italic` | Strip the respective inline formatting |
| `--parser` | BeautifulSoup backend (`lxml` default, or `html.parser`) |

## AI Framework Integrations

Every table becomes its own document, so retrieval never splits a table in half.

### LangChain

```python
from html_table_rescuer.integrations.langchain import HTMLTableRescuerLoader

docs = HTMLTableRescuerLoader("page.html").load()
print(docs[0].page_content)   # Markdown table
print(docs[0].metadata)       # {'source': 'page.html', 'table_index': 0, 'parser': 'html_table_rescuer'}
```

### LlamaIndex

```python
from html_table_rescuer.integrations.llamaindex import HTMLTableRescuerReader

docs = HTMLTableRescuerReader().load_data("page.html")
```

Works as a `file_extractor` in `SimpleDirectoryReader`, so entire folders are handled for you:

```python
from llama_index.core import SimpleDirectoryReader

reader = SimpleDirectoryReader(
    "./docs",
    file_extractor={".html": HTMLTableRescuerReader()},
)
docs = reader.load_data()
```

### Haystack

```python
from html_table_rescuer.integrations.haystack import HTMLTableRescuerConverter

converter = HTMLTableRescuerConverter()
docs = converter.run(sources=["page.html"])["documents"]
```

Drops straight into a pipeline — unreadable sources are skipped with a warning
rather than failing the run, and `ParseConfig` survives pipeline serialization:

```python
from haystack import Pipeline

pipe = Pipeline()
pipe.add_component("converter", HTMLTableRescuerConverter())
result = pipe.run({"converter": {"sources": ["page.html"]}})
```

All three accept a `ParseConfig` to control rowspan handling and inline formatting:

```python
from html_table_rescuer import ParseConfig, RowspanStrategy

config = ParseConfig(rowspan_strategy=RowspanStrategy.REPEAT_VALUE)
docs = HTMLTableRescuerReader(config=config).load_data("page.html")
```

## Features

* [x] HTML parsing via `BeautifulSoup`
* [x] Recursive inline-tag formatting (keeps links, bold, and italic tags alive even if nested in divs)
* [x] Complex `rowspan` and `colspan` grid resolution (using flexible strategies like filling cells with "dito" to preserve context for LLMs)
* [x] Clean Markdown export
* [x] **Data Exports:** JSON and CSV serialization from the `ParsedTable` object
* [x] **CLI:** `html-table-rescuer` command with file/URL/stdin input and Markdown/JSON/CSV output
* [x] **AI Integrations:** Ready-to-use `LangChain` Document Loader, `LlamaIndex` Reader (works with `SimpleDirectoryReader`), and `Haystack` Converter
* [x] Robust against broken real-world HTML: invalid `colspan`/`rowspan` values, HTML comments, and oversized spans are handled gracefully

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

### Blog-Posts:
> ** Read the 1. blog:** [How to Stop LLMs from Hallucinating on Complex HTML Tables](https://html-table-rescuer.hashnode.dev/how-to-stop-llms-from-hallucinating-on-complex-html-tables-python)
> ** Read the 2. blog:** [How to Stop LLMs from Hallucinating on Complex HTML Tables](https://dev.to/encephos/how-to-stop-llms-from-hallucinating-on-complex-html-tables-python-2e0k)
