"""Measures what each rowspan strategy costs in LLM tokens.

The `fill_dito` default duplicates content into spanned cells, which preserves
context for a model reading a single row — but it is not free. This quantifies
the trade-off against `repeat`, `empty`, and against dumping the table as JSON.

Run: python benchmarks/token_overhead.py
Needs: pip install "html-table-rescuer[benchmark]"
"""
import json
import statistics
from pathlib import Path

import tiktoken

from html_table_rescuer import ParseConfig, RowspanStrategy, TableParser

CORPUS_FILE = Path(__file__).parent / "data" / "corpus.json"
ENCODING = "o200k_base"  # GPT-4o / GPT-4.1 family


def count_tokens(text: str, encoder) -> int:
    return len(encoder.encode(text))


def main() -> None:
    corpus = json.loads(CORPUS_FILE.read_text(encoding="utf-8"))
    encoder = tiktoken.get_encoding(ENCODING)

    variants = {
        "empty": lambda t: t.to_markdown(),
        "repeat": lambda t: t.to_markdown(),
        "fill_dito": lambda t: t.to_markdown(),
        "json": lambda t: t.to_json(indent=None),
    }
    strategies = {
        "empty": RowspanStrategy.EMPTY,
        "repeat": RowspanStrategy.REPEAT_VALUE,
        "fill_dito": RowspanStrategy.FILL_WITH_DITO,
        "json": RowspanStrategy.FILL_WITH_DITO,
    }

    totals = {name: 0 for name in variants}
    per_table = {name: [] for name in variants}
    tables_measured = 0
    span_cells = 0
    total_cells = 0

    for entry in corpus:
        parsed = {}
        for name, strategy in strategies.items():
            config = ParseConfig(rowspan_strategy=strategy)
            tables = TableParser(entry["html"], config).parse()
            if not tables:
                break
            parsed[name] = variants[name](tables[0])
        if len(parsed) != len(variants):
            continue

        tables_measured += 1
        for name, text in parsed.items():
            tokens = count_tokens(text, encoder)
            totals[name] += tokens
            per_table[name].append(tokens)

        # How much of the grid is actually span continuation? This is what
        # decides whether the strategy choice matters at all for a given table.
        empty_t = TableParser(
            entry["html"], ParseConfig(rowspan_strategy=RowspanStrategy.EMPTY)
        ).parse()[0]
        repeat_t = TableParser(
            entry["html"], ParseConfig(rowspan_strategy=RowspanStrategy.REPEAT_VALUE)
        ).parse()[0]
        for e_row, r_row in zip(empty_t.rows, repeat_t.rows):
            for e_cell, r_cell in zip(e_row, r_row):
                total_cells += 1
                if e_cell != r_cell:
                    span_cells += 1

    baseline = totals["empty"]
    print(f"Corpus: {tables_measured} real-world tables with spans")
    print(f"Tokenizer: {ENCODING}\n")

    header = f"{'variant':<12} {'total':>9} {'median':>8} {'vs empty':>10}"
    print(header)
    print("-" * len(header))
    for name in variants:
        overhead = (totals[name] / baseline - 1) * 100 if baseline else 0
        median = statistics.median(per_table[name])
        print(
            f"{name:<12} {totals[name]:>9,} {median:>8,.0f} {overhead:>9.1f}%"
        )

    density = span_cells / total_cells * 100 if total_cells else 0
    print(
        f"\nSpan density: {span_cells:,} of {total_cells:,} cells "
        f"({density:.1f}%) are span continuations."
    )
    print("That fraction is what any fill strategy can possibly affect.")

    # Per-table spread matters more than the total: a few huge tables can hide
    # what a span-heavy one costs.
    print("\nPer-table overhead vs empty:")
    for name in ("repeat", "fill_dito"):
        deltas = [
            (v / e - 1) * 100
            for v, e in zip(per_table[name], per_table["empty"])
            if e
        ]
        print(
            f"  {name:<10} median {statistics.median(deltas):>5.1f}%   "
            f"max {max(deltas):>5.1f}%"
        )


if __name__ == "__main__":
    main()
