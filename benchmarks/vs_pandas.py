"""Benchmarks html-table-rescuer against pandas.read_html.

pandas is the serious alternative for HTML table extraction, so the honest
question is not "are we better" but "when should you pick which". This measures
three things on the same inputs: speed, agreement on span resolution, and
survival on malformed markup.

Run: python benchmarks/vs_pandas.py
Needs: pip install "html-table-rescuer[benchmark]"
"""
import json
import time
from io import StringIO
from pathlib import Path

import pandas as pd

from html_table_rescuer import TableParser

CORPUS_FILE = Path(__file__).parent / "data" / "corpus.json"
REPEATS = 3

# Malformed markup of the kind that shows up in exported wikis, CMS output and
# scraped pages. Each one is valid input in the sense that a browser renders it.
MALFORMED = {
    "non-numeric colspan": '<table><tr><th>A</th><th>B</th></tr>'
    '<tr><td colspan="abc">x</td><td>1</td></tr></table>',
    "empty colspan": '<table><tr><th>A</th></tr><tr><td colspan="">x</td></tr></table>',
    "colspan=0": '<table><tr><th>A</th><th>B</th></tr>'
    '<tr><td colspan="0">x</td><td>1</td></tr></table>',
    "negative rowspan": '<table><tr><th>A</th></tr>'
    '<tr><td rowspan="-2">x</td></tr></table>',
    "huge rowspan": '<table><tr><th>A</th></tr>'
    '<tr><td rowspan="100000">x</td></tr></table>',
    "unclosed tags": "<table><tr><th>A</th><th>B</th><tr><td>x</td><td>1</table>",
    "html comment in cell": "<table><tr><th>A</th></tr>"
    "<tr><td>x<!-- internal note --></td></tr></table>",
    "float colspan": '<table><tr><th>A</th><th>B</th></tr>'
    '<tr><td colspan="2.5">x</td></tr></table>',
}


def time_it(fn, payloads) -> float:
    best = float("inf")
    for _ in range(REPEATS):
        start = time.perf_counter()
        for payload in payloads:
            try:
                fn(payload)
            except Exception:  # noqa: BLE001 - failures are counted separately
                pass
        best = min(best, time.perf_counter() - start)
    return best


def rescuer_parse(html):
    return TableParser(html).parse()


def pandas_parse(html):
    return pd.read_html(StringIO(html))


def main() -> None:
    corpus = json.loads(CORPUS_FILE.read_text(encoding="utf-8"))
    htmls = [entry["html"] for entry in corpus]

    print(f"Corpus: {len(htmls)} real-world tables with spans")
    print(f"pandas {pd.__version__}\n")

    # --- Speed -------------------------------------------------------------
    print("Speed (best of %d runs over the whole corpus)" % REPEATS)
    t_rescuer = time_it(rescuer_parse, htmls)
    t_pandas = time_it(pandas_parse, htmls)
    print(f"  html-table-rescuer  {t_rescuer * 1000:7.1f} ms  "
          f"({t_rescuer / len(htmls) * 1000:.1f} ms/table)")
    print(f"  pandas.read_html    {t_pandas * 1000:7.1f} ms  "
          f"({t_pandas / len(htmls) * 1000:.1f} ms/table)")
    faster, factor = (
        ("pandas", t_rescuer / t_pandas)
        if t_pandas < t_rescuer
        else ("html-table-rescuer", t_pandas / t_rescuer)
    )
    print(f"  -> {faster} is {factor:.1f}x faster\n")

    # --- Agreement on span resolution --------------------------------------
    print("Grid agreement on the same tables")
    same_shape = diff_shape = rescuer_only = pandas_only = both_failed = 0
    multirow_header = 0
    for html in htmls:
        try:
            ours = rescuer_parse(html)
            our_shape = (
                (len(ours[0].rows), len(ours[0].headers)) if ours else None
            )
        except Exception:  # noqa: BLE001
            our_shape = None
        try:
            theirs = pandas_parse(html)
            their_shape = theirs[0].shape if theirs else None
        except Exception:  # noqa: BLE001
            their_shape = None

        if our_shape and their_shape:
            if our_shape == their_shape:
                same_shape += 1
            else:
                diff_shape += 1
                # pandas promotes a stacked header into a MultiIndex; we keep
                # only the first row as the header. Worth separating out,
                # because it is a known limitation rather than a span bug.
                if isinstance(theirs[0].columns, pd.MultiIndex):
                    multirow_header += 1
        elif our_shape:
            rescuer_only += 1
        elif their_shape:
            pandas_only += 1
        else:
            both_failed += 1

    print(f"  identical grid shape       {same_shape:>3}/{len(htmls)}")
    print(f"  different grid shape       {diff_shape:>3}/{len(htmls)}")
    print(f"    of which multi-row header{multirow_header:>3}   "
          f"(pandas builds a MultiIndex, we keep row 0 only)")
    print(f"  only html-table-rescuer    {rescuer_only:>3}/{len(htmls)}")
    print(f"  only pandas                {pandas_only:>3}/{len(htmls)}")
    print(f"  both failed                {both_failed:>3}/{len(htmls)}\n")

    # --- Robustness --------------------------------------------------------
    print("Malformed markup (browsers render all of these)")
    print(f"  {'case':<24} {'rescuer':<10} {'pandas':<10}")
    print(f"  {'-' * 24} {'-' * 10} {'-' * 10}")
    ours_ok = theirs_ok = 0
    for name, html in MALFORMED.items():
        try:
            result = rescuer_parse(html)
            our_status = "ok" if result else "no table"
            ours_ok += bool(result)
        except Exception as e:  # noqa: BLE001
            our_status = type(e).__name__
        try:
            result = pandas_parse(html)
            their_status = "ok" if len(result) else "no table"
            theirs_ok += bool(len(result))
        except Exception as e:  # noqa: BLE001
            their_status = type(e).__name__
        print(f"  {name:<24} {our_status:<10} {their_status:<10}")

    total = len(MALFORMED)
    print(f"\n  survived: html-table-rescuer {ours_ok}/{total}, "
          f"pandas {theirs_ok}/{total}")


if __name__ == "__main__":
    main()
