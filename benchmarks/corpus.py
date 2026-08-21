"""Builds a cached corpus of real-world HTML tables for the benchmarks.

Wikipedia is used as the source because its tables are genuinely messy: nested
markup, footnote superscripts, and — most importantly for us — heavy use of
rowspan/colspan in discographies, sports results and election tables.

Run `python benchmarks/corpus.py` to refresh `benchmarks/data/corpus.json`.
The cached file is committed so the benchmarks are reproducible offline.
"""
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_FILE = Path(__file__).parent / "data" / "corpus.json"

# Pages picked for span-heavy tables, not for pretty ones.
PAGES = [
    "Help:Table",
    "List_of_countries_by_GDP_(nominal)",
    "Michael_Jackson_discography",
    "2024_Summer_Olympics_medal_table",
    "List_of_Formula_One_World_Drivers'_Champions",
    "Comparison_of_programming_languages",
    "List_of_countries_by_population_(United_Nations)",
    "UEFA_Euro_2024",
    "List_of_highest-grossing_films",
    "Periodic_table",
]

MAX_TABLES = 30
# Keep the cached corpus small enough to live in git.
MAX_TABLE_BYTES = 60_000


def has_spans(table) -> bool:
    for cell in table.find_all(["td", "th"]):
        if cell.get("rowspan") or cell.get("colspan"):
            return True
    return False


def fetch_page(title: str) -> str:
    url = f"https://en.wikipedia.org/wiki/{title}"
    response = requests.get(
        url, headers={"User-Agent": "html-table-rescuer-benchmark"}, timeout=30
    )
    response.raise_for_status()
    return response.text


def build() -> list:
    corpus = []
    for title in PAGES:
        try:
            html = fetch_page(title)
        except Exception as e:  # noqa: BLE001 - a flaky page must not kill the run
            print(f"  ! {title}: {e}", file=sys.stderr)
            continue

        soup = BeautifulSoup(html, "lxml")
        # Only top-level tables, mirroring what the parser itself considers.
        tables = [t for t in soup.find_all("table") if t.find_parent("table") is None]
        picked = 0
        for table in tables:
            if not has_spans(table):
                continue
            markup = str(table)
            if len(markup) > MAX_TABLE_BYTES:
                continue
            # Collapse whitespace runs; keeps the cache small without changing structure.
            markup = re.sub(r"\n\s*", " ", markup)
            corpus.append({"source": title, "html": markup})
            picked += 1
            if picked >= 4:  # spread the corpus across pages
                break
        print(f"  {title}: {picked} tables with spans")

        if len(corpus) >= MAX_TABLES:
            break

    return corpus[:MAX_TABLES]


if __name__ == "__main__":
    print("Fetching Wikipedia pages...")
    corpus = build()
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Compact: the file is data, and a re-run should not produce a huge diff.
    DATA_FILE.write_text(
        json.dumps(corpus, separators=(",", ":")), encoding="utf-8"
    )
    size_kb = DATA_FILE.stat().st_size / 1024
    print(f"\nWrote {len(corpus)} tables to {DATA_FILE} ({size_kb:.0f} KB)")
