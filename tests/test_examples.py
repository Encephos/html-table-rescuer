"""Die 13 Beispiel-Fälle aus examples/simple_usage.py als Regressionstests."""
import importlib.util
from pathlib import Path

import pytest

from html_table_rescuer import TableParser

_EXAMPLES = Path(__file__).parent.parent / "examples" / "simple_usage.py"
_spec = importlib.util.spec_from_file_location("simple_usage", _EXAMPLES)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

TEST_TABLES = _module.test_tables


@pytest.mark.parametrize("name", list(TEST_TABLES))
def test_example_parses_to_valid_markdown(name):
    """Jeder Beispiel-Fall muss ohne Crash zu strukturell validem Markdown parsen."""
    tables = TableParser(TEST_TABLES[name]).parse()
    assert tables, f"'{name}' lieferte keine Tabelle"

    for t in tables:
        # Ohne Caption, damit hier wirklich nur das Tabellen-Grid geprüft wird
        md = t.to_markdown(include_caption=False)
        lines = md.strip().split("\n")
        assert len(lines) >= 2, f"'{name}': zu wenige Zeilen"
        assert set(lines[1].replace("|", "").split()) == {"---"}, f"'{name}': Trennzeile fehlt"
        # Alle Zeilen müssen gleich viele Spalten haben
        pipe_counts = {line.count("|") for line in lines}
        assert len(pipe_counts) == 1, f"'{name}': ungleiche Spaltenzahl: {md}"


def test_example_rowspan_colspan_grid():
    """Der gestapelte Header wird zusammengeführt, nicht als Datenzeile ausgegeben."""
    table = TableParser(TEST_TABLES["Mit rowspan/colspan"]).parse()[0]
    assert table.headers == [
        "Kategorie",
        "Details - Unterpunkt A",
        "Details - Unterpunkt B",
    ]
    assert table.rows == [["Test", "Alpha", "Beta"]]


def test_example_nested_tables_emitted_once():
    """Die innere Tabelle steckt bereits im Text der äußeren Zelle."""
    tables = TableParser(TEST_TABLES["Verschachtelte Tabellen"]).parse()
    assert len(tables) == 1


def test_example_caption_is_extracted():
    table = TableParser(TEST_TABLES["Mit caption"]).parse()[0]
    assert table.caption == "Verkaufsübersicht"
    assert table.to_markdown().startswith("**Verkaufsübersicht**")
    assert "Verkaufsübersicht" not in table.to_markdown(include_caption=False)


def test_example_confluence_no_fake_headers():
    """Confluence-Tabellen ohne <th> dürfen keine Datenzeile als Header missbrauchen."""
    tables = TableParser(TEST_TABLES["Confluence Beispiel"]).parse()
    assert len(tables) == 1
    t = tables[0]
    assert t.headers == ["Column 1", "Column 2"]
    assert t.rows[0][0] == "**Allgemein**"
    assert len(t.rows) == 18
