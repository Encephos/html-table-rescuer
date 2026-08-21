from typing import List, Optional

from bs4 import BeautifulSoup, Tag

from .cleaner import clean_cell_content
from .models import ParseConfig, ParsedTable, RowspanStrategy

# HTML-Spec erlaubt maximal colspan="1000"
MAX_COLSPAN = 1000

def _parse_span(cell: Tag, attr: str) -> int:
    """Liest colspan/rowspan robust: ungültige Werte ("", "abc", "0", negativ) zählen als 1."""
    try:
        value = int(str(cell.get(attr, 1)).strip())
    except (ValueError, TypeError):
        return 1
    return max(value, 1)

class TableParser:
    def __init__(self, html_content: str, config: Optional[ParseConfig] = None):
        if config is None:
            self.config = ParseConfig()
        else:
            self.config = config
            
        self.soup = BeautifulSoup(html_content, self.config.parser_library)

    def parse(self) -> List[ParsedTable]:
        """Gibt eine Liste von ParsedTable Objekten zurück."""
        # Nur Top-Level-Tabellen: verschachtelte Tabellen erscheinen bereits als
        # Text in der Zelle, die sie enthält. Ohne diesen Filter landet ihr
        # Inhalt doppelt in der Ausgabe (und damit doppelt im RAG-Index).
        tables = [
            t for t in self.soup.find_all('table')
            if t.find_parent('table') is None
        ]
        results = []
        for table in tables:
            parsed_table = self._process_single_table(table)
            if parsed_table:
                results.append(parsed_table)
        return results

    def parse_to_markdown(self) -> List[str]:
        """Convenience: Gibt direkt Markdown-Strings zurück."""
        return [t.to_markdown() for t in self.parse()]

    def _process_single_table(self, table: Tag) -> ParsedTable:
        # FIX 1: Nur Zeilen (<tr>) nehmen, die direkt zu DIESER Tabelle gehören.
        all_trs = table.find_all('tr')
        rows = [tr for tr in all_trs if tr.find_parent('table') is table]
        
        if not rows:
            return None

        grid = {} # (row, col) -> content
        occupied_cells = set() # (row, col)
        # (row, col) -> Position der Zelle, aus der dieses Feld stammt. Damit lässt
        # sich später unterscheiden, ob ein Feld eine echte Zelle ist oder nur die
        # Fortsetzung eines Spans — nötig für mehrzeilige Header.
        cell_origin = {}
        origin_content = {} # Ursprungsposition -> ungefilterter Zellinhalt

        # Pre-Scan um Grid aufzubauen
        for r_idx, row in enumerate(rows):
            # FIX 2: Nur Zellen (td/th) nehmen, die direkt zu DIESER Zeile gehören.
            all_cells = row.find_all(['td', 'th'])
            cells = [cell for cell in all_cells if cell.find_parent('tr') is row]
            
            c_idx = 0 

            for cell in cells:
                # Überspringe belegte Zellen
                while (r_idx, c_idx) in occupied_cells:
                    c_idx += 1

                colspan = min(_parse_span(cell, 'colspan'), MAX_COLSPAN)
                # Rowspan endet wie im Browser an der letzten Zeile der Tabelle
                rowspan = min(_parse_span(cell, 'rowspan'), len(rows) - r_idx)
                
                # Inhalt säubern
                content = clean_cell_content(cell, self.config)
                origin = (r_idx, c_idx)
                origin_content[origin] = content

                # Strategie anwenden
                for r_offset in range(rowspan):
                    for c_offset in range(colspan):
                        target_r = r_idx + r_offset
                        target_c = c_idx + c_offset
                        occupied_cells.add((target_r, target_c))
                        cell_origin[(target_r, target_c)] = origin

                        # Logik für Zell-Inhalt
                        if r_offset == 0 and c_offset == 0:
                            # Das ist die Original-Zelle (oben links)
                            grid[(target_r, target_c)] = content
                        
                        elif r_offset > 0:
                            # Das ist eine vertikale Erweiterung (rowspan)
                            if self.config.rowspan_strategy == RowspanStrategy.FILL_WITH_DITO:
                                grid[(target_r, target_c)] = f"{self.config.dito_prefix} ({content})"
                            elif self.config.rowspan_strategy == RowspanStrategy.REPEAT_VALUE:
                                grid[(target_r, target_c)] = content
                            else:
                                grid[(target_r, target_c)] = "" # Empty
                        
                        else:
                            # Das ist eine horizontale Erweiterung (colspan)
                            # Markdown mag hier leere Zellen
                            grid[(target_r, target_c)] = ""

                c_idx += colspan

        if not occupied_cells:
            return None

        # Spaltenzahl aus dem tatsächlich belegten Grid ableiten
        max_col = max(c for _, c in occupied_cells) + 1

        # --- Intelligente Header-Erkennung ---
        header_count = self._count_header_rows(rows)

        if header_count == 1:
            # Einzelne Headerzeile: unverändertes Verhalten
            headers = [grid.get((0, c), "") for c in range(max_col)]
            start_row = 1
        elif header_count > 1:
            # Gestapelter Header (z.B. <th rowspan="2"> neben <th colspan="3">):
            # pro Spalte die Werte der Headerzeilen zusammenführen
            headers = [
                self._merge_header_column(c, header_count, cell_origin, origin_content)
                for c in range(max_col)
            ]
            start_row = header_count
        else:
            # Kein Header gefunden -> Dummy-Header generieren, Zeile 0 als Daten behandeln
            headers = [f"Column {c+1}" for c in range(max_col)]
            start_row = 0
            
        body_rows = []
        for r in range(start_row, len(rows)):
            row_data = [grid.get((r, c), "") for c in range(max_col)]
            body_rows.append(row_data)

        return ParsedTable(
            headers=headers, rows=body_rows, caption=self._extract_caption(table)
        )

    def _row_cells(self, row: Tag) -> List[Tag]:
        """Zellen, die direkt zu dieser Zeile gehören (nicht zu verschachtelten Tabellen)."""
        return [
            cell for cell in row.find_all(['td', 'th'])
            if cell.find_parent('tr') is row
        ]

    def _count_header_rows(self, rows: List[Tag]) -> int:
        """
        Zählt die führenden Zeilen, die zum Header gehören.

        Ein <thead> ist die verlässlichste Angabe. Sonst gelten führende Zeilen,
        die ausschließlich aus <th> bestehen, als Header — eine Zeile mit
        gemischten Zellen beendet den Header.
        """
        if not rows:
            return 0

        thead_rows = [r for r in rows if r.find_parent('thead') is not None]
        if thead_rows and rows[:len(thead_rows)] == thead_rows:
            header_count = len(thead_rows)
        else:
            header_count = 0
            for row in rows:
                cells = self._row_cells(row)
                if cells and all(cell.name == 'th' for cell in cells):
                    header_count += 1
                else:
                    break

            # Rückwärtskompatibel: eine erste Zeile mit *einzelnen* <th> zählt
            # weiterhin als Header, auch wenn sie daneben <td> enthält.
            if header_count == 0 and any(
                cell.name == 'th' for cell in self._row_cells(rows[0])
            ):
                header_count = 1

        # Niemals die ganze Tabelle als Header aufbrauchen
        if header_count > 1:
            header_count = min(header_count, len(rows) - 1)
        return header_count

    def _merge_header_column(
        self, col: int, header_count: int, cell_origin: dict, origin_content: dict
    ) -> str:
        """Führt die Headerzeilen einer Spalte zu einem Titel zusammen."""
        parts = []
        for r in range(header_count):
            origin = cell_origin.get((r, col))
            if origin is None:
                continue
            # Rowspan-Fortsetzung: der Wert wurde in einer höheren Zeile schon
            # aufgenommen. Colspan-Fortsetzung (origin[0] == r) dagegen liefert
            # die Gruppenüberschrift, die für diese Spalte weiterhin gilt.
            if origin[0] < r:
                continue
            value = origin_content.get(origin, "")
            if value and (not parts or parts[-1] != value):
                parts.append(value)
        return self.config.header_separator.join(parts)

    def _extract_caption(self, table: Tag) -> Optional[str]:
        """Liest die <caption> dieser Tabelle (nicht die einer verschachtelten)."""
        caption = next(
            (
                c for c in table.find_all('caption')
                if c.find_parent('table') is table
            ),
            None,
        )
        if caption is None:
            return None
        return clean_cell_content(caption, self.config) or None
