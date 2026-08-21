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
