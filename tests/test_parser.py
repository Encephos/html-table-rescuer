import pytest

from html_table_rescuer.core import TableParser
from html_table_rescuer.models import ParseConfig, RowspanStrategy


# --- Fixtures (Optionale Vorbereitung) ---
@pytest.fixture
def simple_html():
    return """
    <table>
        <tr><th>Name</th><th>Alter</th></tr>
        <tr><td>Max</td><td>25</td></tr>
    </table>
    """

# --- Tests ---

def test_simple_table(simple_html):
    """Testet eine einfache 2x2 Tabelle."""
    parser = TableParser(simple_html)
    tables = parser.parse_to_markdown()
    
    assert len(tables) == 1
    output = tables[0]
    
    # Prüfen auf Markdown-Syntax
    assert "| Name | Alter |" in output
    assert "| --- | --- |" in output
    assert "| Max | 25 |" in output

def test_colspan_handling():
    """Testet, ob horizontale Verbindungen (colspan) korrekt aufgefüllt werden."""
    html = """
    <table>
        <tr>
            <td colspan="2">Breit</td>
            <td>Normal</td>
        </tr>
    </table>
    """
    parser = TableParser(html)
    result = parser.parse_to_markdown()[0]
    
    # Erwartung: "Breit" in Spalte 1, Spalte 2 leer, "Normal" in Spalte 3
    # Hinweis: Markdown Tabellen benötigen Pipes, leere Zellen sind oft "| |"
    assert "| Breit |  | Normal |" in result or "| Breit || Normal |" in result.replace(" ", "")

def test_rowspan_default_behavior():
    """Testet den Standard: Rowspans sollen mit 'dito' aufgefüllt werden."""
    html = """
    <table>
        <tr>
            <td rowspan="2">Oben</td>
            <td>Rechts 1</td>
        </tr>
        <tr>
            <td>Rechts 2</td>
        </tr>
    </table>
    """
    # Standard Config nutzen (sollte FILL_WITH_DITO sein)
    parser = TableParser(html)
    result = parser.parse_to_markdown()[0]
    
    assert "| Oben | Rechts 1 |" in result
    # Prüfen ob der Dito-Prefix standardmäßig da ist
    assert "dito (Oben)" in result
    assert "| Rechts 2 |" in result

@pytest.mark.parametrize("strategy, expected_snippet", [
    (RowspanStrategy.FILL_WITH_DITO, "dito (Test)"),
    (RowspanStrategy.REPEAT_VALUE, "| Test |"),
    (RowspanStrategy.EMPTY, "|  |"), # Oder leerer String zwischen Pipes
])
def test_rowspan_strategies(strategy, expected_snippet):
    """
    Testet alle 3 Strategien mit demselben HTML durch Parametrisierung.
    Das spart viel Code-Duplizierung.
    """
    html = """
    <table>
        <tr><td rowspan="2">Test</td><td>A</td></tr>
        <tr><td>B</td></tr>
    </table>
    """
    config = ParseConfig(rowspan_strategy=strategy)
    parser = TableParser(html, config)
    result = parser.parse_to_markdown()[0]
    
    # Wir splitten das Ergebnis in Zeilen, um die zweite Zeile zu prüfen
    lines = result.strip().split('\n')
    second_content_row = lines[-1] # Die letzte Zeile (wo der Rowspan wirkt)
    
    if strategy == RowspanStrategy.EMPTY:
        # Bei Empty muss die erste Zelle leer sein: "| | B |"
        assert result.count("Test") == 1 # Darf nur 1x oben vorkommen
    else:
        assert expected_snippet in second_content_row

def test_nested_tags_cleanup():
    """Testet, ob HTML Tags innerhalb von Zellen sauber konvertiert werden."""
    html = """
    <table>
        <tr>
            <td><b>Fett</b></td>
            <td><a href="http://test.de">Link</a></td>
            <td>Zeile1<br>Zeile2</td>
        </tr>
    </table>
    """
    parser = TableParser(html)
    result = parser.parse_to_markdown()[0]
    
    assert "**Fett**" in result
    assert "[Link](http://test.de)" in result
    assert "<br>" in result

def test_broken_html():
    """Testet Verhalten bei ungültigem Input."""
    html = "<html><body>Keine Tabelle hier</body></html>"
    parser = TableParser(html)
    tables = parser.parse_to_markdown()
    assert tables == []

def test_ragged_rows():
    """Testet Tabellen mit unterschiedlicher Zellenanzahl (Padding)."""
    html = """
    <table>
        <tr><td>A</td><td>B</td><td>C</td></tr>
        <tr><td>D</td></tr> 
    </table>
    """
    parser = TableParser(html)
    result = parser.parse_to_markdown()[0]
    
    # Zeile 2 muss aufgefüllt werden, damit Markdown valide ist
    # Wir erwarten 3 Spalten -> 2 Pipes am Ende für leere Zellen
    last_line = result.strip().split('\n')[-1]
    
    # Zählen der Pipes ist ein guter Weg, um die Struktur zu prüfen
    assert last_line.count("|") == 4 # Anfang + 3 Zellen + Ende = 4 Pipes
    assert "D" in last_line


def test_repr_markdown_for_notebooks():
    """Jupyter/Colab rendern Objekte mit _repr_markdown_ automatisch als Tabelle."""
    html = "<table><tr><th>A</th></tr><tr><td>1</td></tr></table>"
    table = TableParser(html).parse()[0]
    assert table._repr_markdown_() == table.to_markdown()


def test_style_and_script_content_is_not_cell_text():
    """CMS exports inline <style> blocks in tables; CSS must not leak into cells."""
    html = """
    <table>
        <tr><th><style>.foo{color:red}</style>Header</th></tr>
        <tr><td><script>alert(1)</script>Value</td></tr>
    </table>
    """
    table = TableParser(html).parse()[0]
    assert table.headers == ["Header"]
    assert table.rows[0] == ["Value"]


# --- Verschachtelte Tabellen --------------------------------------------------

def test_nested_table_is_emitted_once():
    """Die innere Tabelle steckt im Text der äußeren Zelle und darf nicht doppelt raus."""
    html = """
    <table>
        <tr><th>Outer</th></tr>
        <tr><td><table><tr><th>Inner</th></tr><tr><td>x</td></tr></table></td></tr>
    </table>
    """
    tables = TableParser(html).parse()
    assert len(tables) == 1
    assert tables[0].headers == ["Outer"]


def test_sibling_tables_are_both_emitted():
    """Nebeneinanderliegende Tabellen sind beide Top-Level und bleiben erhalten."""
    html = (
        "<table><tr><th>A</th></tr><tr><td>1</td></tr></table>"
        "<table><tr><th>B</th></tr><tr><td>2</td></tr></table>"
    )
    assert len(TableParser(html).parse()) == 2


# --- Mehrzeilige Header -------------------------------------------------------

STACKED_HEADER = """
<table>
    <tr><th rowspan="2">Title</th><th colspan="3">Peak positions</th></tr>
    <tr><th>US</th><th>AUS</th><th>CAN</th></tr>
    <tr><td>Thriller</td><td>1</td><td>2</td><td>3</td></tr>
</table>
"""


def test_stacked_header_is_merged():
    table = TableParser(STACKED_HEADER).parse()[0]
    assert table.headers == [
        "Title",
        "Peak positions - US",
        "Peak positions - AUS",
        "Peak positions - CAN",
    ]
    # Die zweite Headerzeile darf nicht als Datenzeile auftauchen
    assert table.rows == [["Thriller", "1", "2", "3"]]


def test_header_separator_is_configurable():
    config = ParseConfig(header_separator=" / ")
    table = TableParser(STACKED_HEADER, config).parse()[0]
    assert table.headers[1] == "Peak positions / US"


def test_thead_with_multiple_rows():
    html = """
    <table>
        <thead>
            <tr><th rowspan="2">Region</th><th colspan="2">2024</th></tr>
            <tr><th>Q1</th><th>Q2</th></tr>
        </thead>
        <tbody><tr><td>EU</td><td>10</td><td>20</td></tr></tbody>
    </table>
    """
    table = TableParser(html).parse()[0]
    assert table.headers == ["Region", "2024 - Q1", "2024 - Q2"]
    assert table.rows == [["EU", "10", "20"]]


def test_single_header_row_behaviour_unchanged():
    """Einzeiliger Header mit colspan bleibt wie bisher (leere Fortsetzungszelle)."""
    html = (
        '<table><tr><th colspan="2">Department</th><th>Employee</th></tr>'
        "<tr><td>Eng</td><td>Backend</td><td>Ada</td></tr></table>"
    )
    table = TableParser(html).parse()[0]
    assert table.headers == ["Department", "", "Employee"]


def test_mixed_row_ends_the_header():
    """Eine Zeile mit td beendet den Header, auch wenn sie ein th enthält."""
    html = """
    <table>
        <tr><th>A</th><th>B</th></tr>
        <tr><th>Row label</th><td>1</td></tr>
    </table>
    """
    table = TableParser(html).parse()[0]
    assert table.headers == ["A", "B"]
    assert table.rows == [["Row label", "1"]]


def test_all_th_table_keeps_a_data_row():
    """Eine Tabelle aus lauter th darf nicht komplett im Header verschwinden."""
    html = (
        "<table><tr><th>A</th></tr><tr><th>B</th></tr><tr><th>C</th></tr></table>"
    )
    table = TableParser(html).parse()[0]
    assert table.rows, "Es muss mindestens eine Datenzeile übrig bleiben"


# --- Caption ------------------------------------------------------------------

def test_caption_is_extracted_and_rendered():
    html = (
        "<table><caption>Quarterly results</caption>"
        "<tr><th>Q</th></tr><tr><td>1</td></tr></table>"
    )
    table = TableParser(html).parse()[0]
    assert table.caption == "Quarterly results"
    assert table.to_markdown().startswith("**Quarterly results**\n\n|")
    assert table.to_markdown(include_caption=False).startswith("| Q |")


def test_caption_absent_is_none():
    table = TableParser("<table><tr><th>A</th></tr><tr><td>1</td></tr></table>").parse()[0]
    assert table.caption is None


def test_caption_keeps_inline_formatting():
    html = (
        "<table><caption>Sales <b>2024</b></caption>"
        "<tr><th>A</th></tr><tr><td>1</td></tr></table>"
    )
    assert TableParser(html).parse()[0].caption == "Sales **2024**"


def test_nested_table_caption_does_not_leak():
    """Die Caption einer verschachtelten Tabelle darf nicht der äußeren zugeschlagen werden."""
    html = """
    <table>
        <tr><th>Outer</th></tr>
        <tr><td><table><caption>Inner caption</caption><tr><td>x</td></tr></table></td></tr>
    </table>
    """
    assert TableParser(html).parse()[0].caption is None
